import sys
import os
import argparse
import asyncio
import logging # sys and os were imported twice, removed duplicates
import uvicorn
import time
from fastapi.responses import JSONResponse
from mcp.server import FastMCP, Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount

mcp = FastMCP("run_server.py")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# 确保 mcp 工具装饰器能正确处理异步函数
@mcp.tool()
async def start_service(path: str):
    """
    通过执行指定路径的 Python 文件在后台启动服务，并将其输出记录到日志文件。
    使用 'uv python <path>' 命令执行。
    子进程的日志将输出到 'service_logs/<script_name>.log' 文件中。
    此函数在成功启动子进程后立即返回。
    :param path: 要执行的 Python 文件的绝对路径。
    :return: 指示启动成功（含PID和日志路径）或失败的消息字符串。
    """
    # 验证路径是否存在
    if not os.path.isfile(path):
        error_msg = f"错误: 脚本未在 {path} 找到"
        logger.error(error_msg)
        return error_msg

    # 定义日志目录和日志文件路径
    log_dir = os.path.join(os.getcwd(), "service_logs")
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            logger.info(f"日志目录已创建: {log_dir}")
    except OSError as e:
        error_msg = f"错误: 无法创建日志目录 {log_dir}: {e}"
        logger.error(error_msg)
        return error_msg

    script_filename = os.path.basename(path)
    log_file_path = os.path.join(log_dir, f"{script_filename}.log")

    # 构建命令以使用 uv 启动脚本
    # 我们假设 'uv python script.py' 是期望的执行方式，类似于 'python script.py'
    command = ["uv", "run", path]
    script_directory = os.path.dirname(path) or '.'

    process = None
    try:
        logger.info(f"尝试在后台启动服务: {' '.join(command)} 在目录 '{script_directory}'")
        logger.info(f"服务日志将输出到: {log_file_path}")

        # 以追加模式打开日志文件，以便多次运行不会覆盖之前的日志
        # 文件句柄将传递给子进程，父进程可以在创建子进程后关闭它。
        with open(log_file_path, 'ab') as log_file: # 使用二进制追加模式 'ab'
            # 异步创建子进程
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=log_file,          # 重定向子进程的标准输出到日志文件
                stderr=log_file,          # 重定向子进程的标准错误到日志文件
                cwd=script_directory,
                # start_new_session=True # 如果需要完全分离的进程会话，可以取消注释
                                        # 但这可能使父进程更难管理子进程的生命周期（如果需要的话）
            )

        pid = process.pid
        success_msg = f"服务成功启动，PID: {pid}。日志记录在: {log_file_path}"
        logger.info(success_msg)
        return success_msg

    except FileNotFoundError:
        # 这个错误通常意味着 'uv' 命令没有找到，或者脚本路径在执行瞬间失效
        error_msg = f"错误: 'uv' 命令未找到或脚本 '{path}' 未找到。请确保 'uv' 已安装并在 PATH 中。"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        # 捕获启动过程中的其他异常
        error_msg = f"尝试为 '{path}' 启动进程时发生错误: {e}"
        logger.error(error_msg, exc_info=True)
        return f"服务启动失败。错误: {e}"

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
            request._send, # type: ignore
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
            Mount("/messages/", app=sse.handle_post_message), # type: ignore
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
    logger.info(f"Starting MCP Server on http://{args.host}:{args.port}")
    uvicorn.run(starlette_app, host=args.host, port=args.port)