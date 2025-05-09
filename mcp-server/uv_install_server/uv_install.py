import argparse
import logging
import os
import subprocess
import asyncio
import uvicorn
import time
from fastapi.responses import JSONResponse
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server import FastMCP, Server
from mcp.server.sse import SseServerTransport

mcp = FastMCP("mcp_install_tool")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def check_uv_installed():
    try:
        subprocess.run(["uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ uv 未安装，请先安装 uv：")
        logger.error("   pip install uv")
        return False
async def install_package(package_name: str):
    if not check_uv_installed():
        raise Exception("❌ uv 未安装，请先安装 uv。")

    logger.info(f"📦 正在安装包: {package_name}")
    process = await asyncio.create_subprocess_exec(
        "uv", "pip", "install", package_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        logger.error(f"❌ 安装 {package_name} 失败: {error_msg}")
        raise Exception(f"安装 {package_name} 失败: {error_msg}")

    logger.info(f"✅ {package_name} 安装成功")
    return f"{package_name} 安装成功"
async def install_from_requirements(requirements_file: str):
    if not os.path.exists(requirements_file):
        logger.error(f"❌ 文件 {requirements_file} 不存在")
        raise Exception(f"文件 {requirements_file} 不存在")

    if not check_uv_installed():
        raise Exception("❌ uv 未安装，请先安装 uv。")

    logger.info(f"📦 正在从 {requirements_file} 安装依赖")
    process = await asyncio.create_subprocess_exec(
        "uv", "pip", "install", "-r", requirements_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        logger.error(f"❌ 依赖安装失败: {error_msg}")
        raise Exception(f"依赖安装失败: {error_msg}")

    logger.info("✅ 依赖安装成功")
    return "依赖安装成功"
@mcp.tool()
async def install_tool(package: str = None, requirements: str = None):
    """
    通过 uv 安装 Python 依赖包或从 requirements.txt 安装依赖

    :param package: 要安装的包名（例如 requests）
    :param requirements: requirements.txt 文件路径
    :return: 安装结果
    """
    if requirements:
        return await install_from_requirements(requirements)
    elif package:
        return await install_package(package)
    else:
        raise Exception("❌ 请提供包名或指定 requirements 文件")
async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "timestamp": int(time.time())
    })
def create_starlette_app(mcp_server: Server, debug: bool = False):
    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse_transport.connect_sse(
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
            Mount("/messages/", app=sse_transport.handle_post_message),
            Route("/sse/health", endpoint=health_check, methods=["GET"]),
        ],
    )

if __name__ == "__main__":
    mcp_server = mcp._mcp_server

    parser = argparse.ArgumentParser(description="运行 MCP 安装工具服务")
    parser.add_argument("--host", default="0.0.0.0", help="绑定主机地址")
    parser.add_argument("--port", default=18860, type=int, help="绑定端口号")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    args = parser.parse_args()

    starlette_app = create_starlette_app(mcp_server, debug=args.debug)
    logger.info(f"🚀 正在启动 MCP 安装工具服务: http://{args.host}:{args.port}/sse")
    uvicorn.run(starlette_app, host=args.host, port=args.port)