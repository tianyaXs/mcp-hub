import asyncio
import json
import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from zhipuai import ZhipuAI
import toml
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self,pyproject_file=None):
        """初始化MCP客户端"""
        self.exit_stack = AsyncExitStack()
        self.sessions = {}  # 存储所有连接的 session，键为服务 URL
        self.service_health = {}
        self.HEARTBEAT_INTERVAL = timedelta(minutes=1)
        self.HEARTBEAT_TIMEOUT = timedelta(minutes=3)
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
        logger.info(f"Connecting to {server_url}")
        stream_context = await self.exit_stack.enter_async_context(sse_client(url=server_url))
        read_stream, write_stream = stream_context
        session = await ClientSession(read_stream, write_stream).__aenter__()
        await session.initialize()
        self.sessions[server_url] = session
        self.service_health[server_url] = datetime.now()
        tools_response = await session.list_tools()
        logger.info(f"Connected to {server_url}, available tools: {[tool.name for tool in tools_response.tools]}")

    async def start_heartbeat_monitor(self):
        """启动心跳检测任务"""
        while True:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL.total_seconds())
            await self.check_services()

    async def check_services(self):
        """检查所有服务的健康状态"""
        current_time = datetime.now()
        for url in list(self.sessions.keys()):
            last_heartbeat = self.service_health.get(url, datetime.min)
            if current_time - last_heartbeat > self.HEARTBEAT_TIMEOUT:
                await self.disconnect_service(url)
            else:
                await self.send_heartbeat(url)
    async def send_heartbeat(self, url):
        """发送心跳探测，通过调用服务的 /health 接口"""
        try:
            # 构造健康检查的完整URL
            health_url = f"{url}/health"
            
            # 使用异步HTTP客户端发送GET请求
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=5)  # 设置超时时间
                
                if response.status_code == 200:
                    # 更新健康状态时间戳
                    self.service_health[url] = datetime.now()
                    logger.debug(f"健康检查成功: {url}")
                else:
                    logger.warning(f"健康检查失败: {url} 返回状态码 {response.status_code}")
            
        except Exception as e:
            logger.warning(f"心跳检测失败: {url} - {str(e)}")

    async def disconnect_service(self, url):
        if url in self.sessions:
            session = self.sessions.pop(url)
            try:
                await self.exit_stack.aclose_resource(session)
            except Exception as e:
                logger.error(f"Failed to close session {url}: {str(e)}")
            del self.service_health[url]
            logger.info(f"服务 {url} 已断开，移除服务能力")
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
        self.service_health.clear()
    def is_service_healthy(self, url):
        last_heartbeat = self.service_health.get(url, datetime.min)
        return datetime.now() - last_heartbeat <= self.HEARTBEAT_TIMEOUT    

# 使用 lifespan 管理生命周期
async def lifespan(app: FastAPI):
    client = MCPClient()
    app.state.client = client
    # 启动心跳检测任务
    app.state.heartbeat_task = asyncio.create_task(client.start_heartbeat_monitor())
    yield
    # 关闭时清理资源
    app.state.heartbeat_task.cancel()
    await client.cleanup()

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
@app.post("/register")
async def register_service(request: Request):
    try:
        data = await request.json()
        server_url = data.get('url')
        if not server_url:
            raise HTTPException(status_code=400, detail="Missing 'url' parameter")

        # 如果已存在会话，先断开
        if server_url in app.state.client.sessions:
            await app.state.client.disconnect_from_server(server_url)

        # 重新连接
        await app.state.client.connect_to_server(server_url)
        return JSONResponse(
            content={
                "status": "success", 
                "message": f"Service {server_url} re-registered"
            }
        )
    except Exception as e:
        logger.error(f"Failed to register service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
@app.get("/health")
async def get_health_status():
    client = app.state.client
    return {
        "services": [
            {
                "url": url,
                "last_connected": str(client.service_health[url])
            } 
            for url in client.service_health
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)