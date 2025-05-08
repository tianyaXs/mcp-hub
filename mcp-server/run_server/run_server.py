import sys
import os
import argparse
import asyncio
import sys
import os
import logging
import uvicorn
import time
from fastapi.responses import JSONResponse
from mcp.server import FastMCP, Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount

mcp = FastMCP("run_server.py")

logger = logging.getLogger(__name__)

# 确保 mcp 工具装饰器能正确处理异步函数
@mcp.tool()
async def start_service(path: str):
    """
    通过执行指定路径的 Python 文件在后台启动服务。
    子进程的日志将输出到运行此工具的主服务器的标准输出/错误流中。
    此函数在成功启动子进程后立即返回。
    :param path: 要执行的 Python 文件的绝对路径。
    :return: 指示启动成功（含PID）或失败的消息字符串。
    """
    # 验证路径是否存在
    if not os.path.isfile(path):
        error_msg = f"Error: Script not found at {path}"
        logger.error(error_msg)
        return error_msg
        
    command = [sys.executable, path] # 构建命令
    script_directory = os.path.dirname(path) or '.' 
    
    process = None
    try:
        logger.info(f"Attempting to start service in background: {' '.join(command)} in directory '{script_directory}'")
        
        # 异步创建子进程
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=None,
            stderr=None,
            cwd=script_directory,
            # start_new_session=True 
        )
        
        pid = process.pid
        logger.info(f"Service process launched successfully with PID: {pid}")

        return f"Service launched successfully with PID: {pid}. Check server's console output for logs."

    # FileNotFoundError 应该在 isfile 检查时被捕获，但保留以防万一
    except FileNotFoundError: 
        error_msg = f"Error: Script not found at {path}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        # 捕获启动过程中的其他异常
        error_msg = f"An error occurred trying to start the process for '{path}': {e}"
        logger.error(error_msg, exc_info=True)
        return f"Failed to launch service. Error: {e}"
async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "timestamp": int(time.time())}) 
def create_starlette_app(mcp_server: Server, *, debug: bool = False):
    """Create Starlette application that provides MCP service through SSE"""
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
            Route("/sse/health", endpoint=health_check, methods=["GET"])
        ],
    )    

if __name__ == "__main__":
    mcp_server = mcp._mcp_server
 
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument("--host", default="0.0.0.0", help="MCP server host")
    parser.add_argument("--port", default=18183, type=int, help="MCP server port")
    args = parser.parse_args()
 
    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)

