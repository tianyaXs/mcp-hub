import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from typing import Dict, Any, Optional
from config import load_app_config
from registry import ServiceRegistry
from client import MCPOrchestrator
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app_state: Dict[str, Any] = {}

# --- Lifespan Management ---
async def lifespan(app: FastAPI):
    """Initializes and cleans up application resources."""
    logger.info("Application startup: Initializing components...")
    # Pass the directory of main.py to help locate config relative to it
    config_dir = os.path.dirname(__file__)
    config = load_app_config(os.path.join(config_dir, "..", "pyproject.toml"))

    registry = ServiceRegistry()
    orchestrator = MCPOrchestrator(config=config, registry=registry)

    await orchestrator.setup() # Init http client etc.
    await orchestrator.start_monitoring() # Start background tasks

    # Store instances in app state for dependency injection access
    app_state["orchestrator"] = orchestrator
    app_state["registry"] = registry
    logger.info("Components initialized and background tasks started.")

    yield

    # --- Shutdown sequence ---
    logger.info("Application shutdown: Cleaning up resources...")
    orch: Optional[MCPOrchestrator] = app_state.get("orchestrator")
    if orch:
        await orch.cleanup()
    app_state.clear() # Clear state
    logger.info("Application shutdown complete.")

app = FastAPI(lifespan=lifespan)

# --- Dependency Injection Functions ---
def get_orchestrator() -> MCPOrchestrator:
     orchestrator = app_state.get("orchestrator")
     if orchestrator is None:
          raise HTTPException(status_code=503, detail="服务暂未就绪 (Orchestrator not initialized)")
     return orchestrator

def get_registry() -> ServiceRegistry:
     registry = app_state.get("registry")
     if registry is None:
           raise HTTPException(status_code=503, detail="服务暂未就绪 (Registry not initialized)")
     return registry

# --- Request Models (Pydantic) ---
from pydantic import BaseModel, HttpUrl

class QueryRequest(BaseModel):
    query: str

class RegisterRequest(BaseModel):
     # Add URL validation using HttpUrl
     url: HttpUrl # Ensures URL is well-formed
     name: str = "" # 服务名称，默认为空字符串
     
class ServiceInfoRequest(BaseModel):
     url: str

# --- API Endpoints ---
@app.post("/query", response_model=Dict[str, Any]) # Added response model hint
async def query_endpoint(
    payload: QueryRequest,
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Handles user queries via the orchestrator."""
    logger.info(f"Received query request: '{payload.query[:100]}...'")
    try:
        result = await orchestrator.process_query(payload.query)
        # Check if result indicates an internal error from orchestrator
        if isinstance(result, str) and result.startswith("错误："):
             # Log the internal error detail, return a generic message to client
             logger.error(f"Orchestrator processing error for query '{payload.query[:50]}...': {result}")
             raise HTTPException(status_code=500, detail="处理查询时发生内部错误。")

        logger.info("Query processed successfully.")
        return {"result": result} # FastAPI automatically uses JSONResponse here

    except HTTPException as http_exc:
        raise http_exc # Let FastAPI handle deliberate HTTP exceptions
    except Exception as e: # Catch unexpected errors in the endpoint itself
        logger.error(f"Unhandled error in /query endpoint for query '{payload.query[:50]}...': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="处理查询请求时发生意外的服务器错误。")


@app.post("/register", response_model=Dict[str, str])
async def register_service_endpoint(
    payload: RegisterRequest,
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Registers or re-registers an MCP tool server. Adds to retry on failure."""
    server_url_str = str(payload.url) # Convert HttpUrl back to string if needed by orchestrator
    service_name = payload.name or server_url_str.split('/')[-2] # 如果没有提供名称，使用URL的一部分作为默认名称
    
    logger.info(f"收到注册请求，目标URL: {server_url_str}，服务名称: {service_name}")
    try:
        # Pass string URL to orchestrator
        success, message = await orchestrator.connect_service(server_url_str, service_name)
        if success:
            logger.info(f"服务 {service_name} ({server_url_str}) 注册成功: {message}")
            return {"status": "success", "message": message} # FastAPI automatically uses JSONResponse
        else:
            logger.error(f"服务 {service_name} ({server_url_str}) 注册失败: {message}")
            status_code = 500 # Default
            is_connection_issue = False
            if "502 Bad Gateway" in message: status_code = 502; is_connection_issue = True
            elif "连接失败" in message or "网络连接错误" in message: status_code = 502; is_connection_issue = True

            if is_connection_issue:
                 logger.info(f"将服务 {service_name} ({server_url_str}) 添加到自动重连列表。")
                 orchestrator.pending_reconnection.add(server_url_str)

            raise HTTPException(status_code=status_code, detail=message)
    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        logger.error(f"处理注册请求时发生未知错误 (URL: {server_url_str}): {e}", exc_info=True)
        # Optionally add to retry list even on unexpected errors
        # orchestrator.pending_reconnection.add(server_url_str)
        raise HTTPException(status_code=500, detail=f"处理注册请求时发生意外的内部服务器错误。")


@app.get("/health", response_model=Dict[str, Any])
async def get_health_status(
    registry: ServiceRegistry = Depends(get_registry),
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Returns the health status of the orchestrator and connected services."""
    service_statuses = registry.get_registered_services_details()
    # Add current health status based on timeout logic
    for status in service_statuses:
         is_healthy = orchestrator.is_service_healthy(status["url"])
         status["status"] = "healthy" if is_healthy else "unhealthy"

    return {
        "orchestrator_status": "running",
        "active_services": registry.get_session_count(),
        "total_tools": registry.get_tool_count(),
        "pending_reconnection_count": len(orchestrator.pending_reconnection),
        "connected_services_details": service_statuses
    }

@app.get("/service_info", response_model=Dict[str, Any])
async def get_service_info(
    url: str,
    registry: ServiceRegistry = Depends(get_registry),
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """返回指定服务的详细信息，包括工具列表"""
    logger.info(f"收到服务信息查询请求，目标URL: {url}")
    
    # 获取服务详情
    service_details = registry.get_service_details(url)
    
    if not service_details:
        raise HTTPException(status_code=404, detail=f"服务未找到: {url}")
    
    # 添加健康状态
    is_healthy = orchestrator.is_service_healthy(url)
    service_details["status"] = "healthy" if is_healthy else "unhealthy"
    
    return {
        "service": service_details
    }

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Setup Uvicorn logging (same as before)
    log_config = uvicorn.config.LOGGING_CONFIG
    # (log config settings...)
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(client_addr)s - '%(request_line)s' %(status_code)s"
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    log_config["loggers"]["uvicorn.error"]["level"] = "INFO"
    log_config["loggers"]["uvicorn.access"]["level"] = "INFO"
    # Example: Reduce httpx noise if desired
    # logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting Uvicorn server...")
    # Run the FastAPI app instance directly
    uvicorn.run(app, host="0.0.0.0", port=18200, log_config=log_config)
