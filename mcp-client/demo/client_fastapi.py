import json
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from zhipuai import ZhipuAI
import toml



class MCPClient:
    def __init__(self,pyproject_file=None):
        """初始化MCP客户端"""
        self.exit_stack = AsyncExitStack()
        self.sessions = {}  # 存储所有连接的 session，键为服务 URL
        # self.openai_api_key = os.getenv('OPENAI_API_KEY')
        # self.base_url = os.getenv('BASE_URL')
        # self.model = os.getenv('MODEL')
        # 如果未指定路径，默认假设 pyproject.toml 位于项目根目录
        if pyproject_file is None:
            pyproject_file = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
        
        # 读取 pyproject.toml 文件
        try:
            with open(pyproject_file, "r", encoding="utf-8") as f:
                config = toml.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"配置文件 {pyproject_file} 未找到！")
        except Exception as e:
            raise RuntimeError(f"解析配置文件时出错: {e}")
        
        zhipu_config = config.get("tool", {}).get("zhipu", {})
        self.openai_api_key = zhipu_config.get("openai_api_key")
        self.model = zhipu_config.get("model")
        self.client = ZhipuAI(api_key=self.openai_api_key)

    async def connect_to_server(self, server_url):
        print(f"Connecting to {server_url}")
        stream_context = await self.exit_stack.enter_async_context(sse_client(url=server_url))
        read_stream, write_stream = stream_context
        session = await ClientSession(read_stream, write_stream).__aenter__()
        await session.initialize()
        self.sessions[server_url] = session
        tools_response = await session.list_tools()
        print(f"Connected to {server_url}, available tools: {[tool.name for tool in tools_response.tools]}")

    async def process_query(self, query):
        messages = [
            {"role": "system", "content": "你是一个智能助手，帮助用户回答问题。"},
            {"role": "user", "content": query}
        ]
        
        all_tools = []
        for session in self.sessions.values():
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
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=all_tools
        )
        
        content = response.choices[0]
        if content.finish_reason == "tool_calls":
            tool_call = content.message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
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
                return result.content[0].text
            else:
                return f"工具 {function_name} 未找到"
        
        return content.message.content.strip()

    async def cleanup(self):
        await self.exit_stack.aclose()
        self.sessions.clear()

async def lifespan(app: FastAPI):
    # 启动时初始化客户端
    app.state.client = MCPClient()
    await app.state.client.connect_to_server("http://localhost:18150/sse")
    await app.state.client.connect_to_server("http://localhost:18100/sse")
    yield
    # 关闭时清理资源
    await app.state.client.cleanup()

app = FastAPI(lifespan=lifespan)    
@app.post("/query")
async def query_endpoint(request: Request):
    """处理HTTP请求的接口"""
    try:
        data = await request.json()
        query = data.get('query')
        if not query:
            raise HTTPException(status_code=400, detail="Missing 'query' parameter")
        
        result = await app.state.client.process_query(query)
        try:
            result = json.loads(result)
        except Exception as e:
            print(f"json is erros")
        return JSONResponse(content={"result": result})
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers={"X-Error": "True"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
