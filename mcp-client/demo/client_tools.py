import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Optional
 
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from zhipuai import ZhipuAI


load_dotenv()
 
class MCPClient:
    def __init__(self):
        """初始化MCP客户端"""
        self.exit_stack = AsyncExitStack()
        self.sessions = {}  # 存储所有连接的 session，键为服务 URL
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('BASE_URL')
        self.model = os.getenv('MODEL')
        if not self.openai_api_key:
            raise ValueError("❌未找到OpenAI API Key，请在.env文件中设置OPENAI_API_KEY")
 
        self.client = ZhipuAI(api_key=self.openai_api_key)
        self.session: Optional[ClientSession] = None
 
 
    async def connect_to_server(self, server_url):
        print(f"Connecting to {server_url}")
        # 创建新的流上下文
        stream_context = await self.exit_stack.enter_async_context(sse_client(url=server_url))
        read_stream, write_stream = stream_context
        
        # 创建新的 ClientSession 并加入 sessions
        session = await ClientSession(read_stream, write_stream).__aenter__()
        await session.initialize()
        self.sessions[server_url] = session  # 存储 session
        
        # 获取工具列表并合并到全局可用工具中
        tools_response = await session.list_tools()
        print(f"Connected to {server_url}, available tools: {[tool.name for tool in tools_response.tools]}")
 
 
    async def process_query(self, query):
        messages = [
            {"role": "system", "content": "你是一个智能助手，帮助用户回答问题。"},
            {"role": "user", "content": query}
        ]
        
        # 收集所有服务的工具
        all_tools = []
        for server_url, session in self.sessions.items():
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                parameters = tool.inputSchema or {}
                if not parameters.get("type"):
                    parameters = {
                        "type": "object",
                        "properties": parameters,
                        "required": list(parameters.keys())
                    }
                all_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": parameters
                    }
                })
        
        # 调用模型并处理工具调用
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=all_tools
        )
        
        # 处理工具调用结果（选择正确的服务执行）
        content = response.choices[0]
        if content.finish_reason == "tool_calls":
            tool_call = content.message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # 查找哪个服务有该工具
            target_session = None
            for session in self.sessions.values():
                tools = await session.list_tools()
                for tool in tools.tools:
                    if tool.name == function_name:
                        target_session = session
                        break
                if target_session:
                    break
            
            if target_session:
                result = await target_session.call_tool(function_name, function_args)
                result_content = result.content[0].text
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": result_content,
                })
                return result_content
            else:
                return f"工具 {function_name} 未找到"
        
        return content.message.content.strip()
 
 
    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("✅MCP 客户端已启动！输入 'quit' 退出")
 
        while True:
            try:
                query = input("输入你的问题：").strip()
                if query.lower() == 'quit':
                    break
 
                response = await self.process_query(query)
 
                print(f"openai：{response}")
            except Exception as e:
                print(f"发生错误：{e}")
 
    # async def cleanup(self):
    #     """清理资源"""
    #     await self.exit_stack.aclose()
    async def cleanup(self):
        await self.exit_stack.aclose()  # 自动关闭所有上下文
        self.sessions.clear()  # 清空 session 引用    
 
 
async def main():
    # if len(sys.argv) < 2:
    #     print("请提供 MCP 服务器脚本路径作为参数")
    #     sys.exit(1)
    client = MCPClient()
    try:
        await client.connect_to_server("http://localhost:18150/sse")
        await client.connect_to_server("http://localhost:18100/sse")
        await client.chat_loop()
    finally:
        await client.cleanup()
 
 
if __name__ == "__main__":
    asyncio.run(main())
