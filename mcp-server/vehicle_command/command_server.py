import argparse
import json
 
import httpx
import uvicorn
from mcp.server import FastMCP, Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
import random
import time
import requests
from fastapi.responses import JSONResponse
 

mcp = FastMCP("vehicle_command_server")

def get_current_timestamp():
    return int(time.time())
@mcp.tool()
async def get_vehicle_agent(query: str):
    """
    获取车控指令
    :param query: 指令内容
    :return: 协议信息
    """
    url = "http://192.168.2.18:8605/api/v1/chat/command_agent"
    headers = {
        "Authorization": "Bearer dataset-NqyKToNvDuPSfcslnoGsrWWL",
        "Content-Type": "application/json"
    }
    session_id = str(random.randint(10000, 99999))
    msg_id = str(random.randint(10000, 99999))
    timestamp = get_current_timestamp()

    payload = {
        "session_id": session_id,
        "msg_id": msg_id,
        "type": "text",
        "content": query,
        "timestamp": timestamp,
        "history": [],  # 假设没有历史记录
        "car_info": {
            "foreground_app": ""
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        # print(f"响应状态码: {response.status_code}")

        # 尝试通过正确的编码解码内容
        response.encoding = 'utf-8'
        raw_text = response.text

        if "data:" in raw_text:
            raw_lines = raw_text.split("\n")
            for line in raw_lines:
                if line.startswith("data:"):
                    raw_data = line[5:].strip()
                    return {"parsed_data": json.loads(raw_data), "status_code": response.status_code}

        parsed_data = json.loads(raw_text)
        if isinstance(parsed_data.get("data"), str):
            parsed_data["data"] = json.loads(parsed_data["data"])

        return {"parsed_data": parsed_data, "status_code": response.status_code}

    except requests.exceptions.RequestException as e:

        return {"error": str(e)}
 
async def health_check(request):
    """健康检查接口"""
    return JSONResponse({"status": "healthy", "timestamp": int(time.time())}) 
def create_starlette_app(mcp_server: Server, *, debug: bool = False):
    """创建 Starlette 应用能通过sse提供mcp服务"""
    sse = SseServerTransport("/messages/")
    
    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
    
    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
            Route("/sse/health", endpoint=health_check, methods=["GET"])  # 新增健康检查路由
        ],
    )
 
 
 
if __name__ == "__main__":
    mcp_server = mcp._mcp_server
 
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument("--host", default="0.0.0.0", help="MCP server host")
    parser.add_argument("--port", default=18080, type=int, help="MCP server port")
    args = parser.parse_args()
 
    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)