import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from typing import Dict, Any, Optional, List, Literal
from config import load_app_config
from registry import ServiceRegistry
from client import MCPOrchestrator
from json_mcp import MCPConfigAPI  # Modified import to use MCPConfigAPI
import asyncio
import sys
from datetime import datetime
from fastapi import BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sse_starlette.sse import EventSourceResponse
import uvicorn
from pydantic import BaseModel, Field
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("mcp_service.log")])
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
          raise HTTPException(status_code=503, detail="Service not ready (Orchestrator not initialized)")
     return orchestrator

def get_registry() -> ServiceRegistry:
     registry = app_state.get("registry")
     if registry is None:
           raise HTTPException(status_code=503, detail="Service not ready (Registry not initialized)")
     return registry

# --- Request Models (Pydantic) ---
from pydantic import BaseModel, HttpUrl

class QueryRequest(BaseModel):
    query: str
    mode: Optional[Literal["standard", "react"]] = "react"  # Default to using ReAct mode
    include_trace: Optional[bool] = False  # Whether to include execution trace in response
    stream: Optional[bool] = False  # Whether to use streaming response

class RegisterRequest(BaseModel):
     # Add URL validation using HttpUrl
     url: HttpUrl # Ensures URL is well-formed
     name: str = "" # Service name, defaults to empty string
     
class ServiceInfoRequest(BaseModel):
     url: str

# New Pydantic models for handling MCP configuration
class MCPConfigResponse(BaseModel):
    mcpServers: Dict[str, Dict[str, Any]]

class MCPConfigUpdateRequest(BaseModel):
    mcpServers: Dict[str, Dict[str, Any]]

# --- API Endpoints ---
@app.post("/query", response_model=Dict[str, Any]) # Added response model hint
async def query_endpoint(
    payload: QueryRequest,
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Process user queries, supporting both standard and ReAct modes"""
    logger.info(f"Received query request: '{payload.query[:100]}...', mode: {payload.mode}")
    try:
        # If streaming response is specified, redirect to streaming endpoint
        if payload.stream:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "For streaming responses, please use the /query_stream endpoint"
                }
            )
            
        # Choose processing method based on request mode
        if payload.mode == "react":
            # If execution trace is requested
            if payload.include_trace:
                result, trace = await orchestrator.process_query_with_trace(payload.query)
                # Build response with trace
                response = {"result": result}
                if trace:
                    # Convert trace to frontend-friendly format
                    formatted_trace = []
                    for step in trace:
                        if step["role"] == "assistant":
                            formatted_trace.append({"type": "thinking", "content": step["content"]})
                        elif step["role"] == "tool":
                            formatted_trace.append({
                                "type": "tool_call", 
                                "tool": step["name"],
                                "result": step["result"]
                            })
                    response["execution_trace"] = formatted_trace
                return response
            else:
                # ReAct processing without trace
                result = await orchestrator.process_query_with_react(payload.query)
        else:
            # Standard mode processing
            result = await orchestrator.process_query(payload.query)

        # Check if result contains error message
        if isinstance(result, str) and result.startswith("Error:"):
             logger.error(f"Error processing query: {result}")
             raise HTTPException(status_code=500, detail=result)

        logger.info("Query processed successfully")
        return {"result": result}

    except HTTPException as http_exc:
        raise http_exc # Let FastAPI handle deliberate HTTP exceptions
    except Exception as e: # Catch unexpected errors in the endpoint itself
        logger.error(f"Unhandled error while processing query request: '{payload.query[:50]}...': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred while processing the query request.")

@app.post("/query_stream")
async def query_stream(request: QueryRequest):
    """Process streaming query request, return SSE streaming response"""
    async def event_generator():
        try:
            logger.info(f"Received streaming query: {request.query}")
            
            # Use stream_process_query method for streaming processing
            orchestrator = get_orchestrator()
            async for response in orchestrator.stream_process_query(request.query):
                # Serialize response data to JSON string, so SSE library can pass it through data field
                # Instead of trying to pass the entire object as keyword arguments to ServerSentEvent constructor
                yield {
                    "data": json.dumps(response)
                }
                
            logger.info(f"Streaming query processing complete")
        except Exception as e:
            logger.error(f"Error processing streaming query: {e}", exc_info=True)
            # Send error response
            yield {
                "data": json.dumps({
                    "thinking_step": None,
                    "is_final": True,
                    "result": f"Error processing streaming query: {str(e)}"
                })
            }
    
    return EventSourceResponse(event_generator())

@app.get("/query_stream")
async def query_stream_get(request: Request, query: Optional[str] = None):
    """GET method for processing streaming query requests, retrieves user query from URL query parameter
    
    In some cases, particularly during tool calls, GET requests without a query parameter may be received.
    These requests are typically initiated by internal tool calling mechanisms and should not cause
    the entire process to abort. We handle this by making the query parameter optional and returning
    an early error response when it's missing.
    """
    # Log request headers and all query parameters for debugging
    headers = dict(request.headers)
    query_params = str(request.query_params)
    logger.debug(f"GET /query_stream received request | Query params: {query_params} | Source: {headers.get('referer', 'unknown')}")
    
    async def event_generator():
        try:
            # Check if query parameter exists
            if not query:
                logger.warning(f"Received GET streaming query request, but missing query parameter")
                # If it's a request during a tool call, return empty response to avoid blocking
                yield {
                    "data": json.dumps({
                        "thinking_step": None,
                        "is_final": True,
                        "result": "Error: Missing required query parameter"
                    })
                }
                return
                
            logger.info(f"Received GET streaming query: {query}")
            
            # Use stream_process_query method for streaming processing
            orchestrator = get_orchestrator()
            async for response in orchestrator.stream_process_query(query):
                # Serialize response data to JSON string
                yield {
                    "data": json.dumps(response)
                }
                
            logger.info(f"GET streaming query processing complete")
        except Exception as e:
            logger.error(f"Error processing GET streaming query: {e}", exc_info=True)
            # Send error response
            yield {
                "data": json.dumps({
                    "thinking_step": None,
                    "is_final": True,
                    "result": f"Error processing streaming query: {str(e)}"
                })
            }
    
    return EventSourceResponse(event_generator())

@app.post("/register", response_model=Dict[str, str])
async def register_service_endpoint(
    payload: RegisterRequest,
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Registers or re-registers an MCP tool server. Adds to retry on failure."""
    server_url_str = str(payload.url) # Convert HttpUrl back to string if needed by orchestrator
    service_name = payload.name or server_url_str.split('/')[-2] # If no name provided, use part of URL as default name
    
    logger.info(f"Received registration request, target URL: {server_url_str}, service name: {service_name}")
    try:
        # Pass string URL to orchestrator
        success, message = await orchestrator.connect_service(server_url_str, service_name)
        if success:
            logger.info(f"Service {service_name} ({server_url_str}) registered successfully: {message}")
            return {"status": "success", "message": message} # FastAPI automatically uses JSONResponse
        else:
            logger.error(f"Service {service_name} ({server_url_str}) registration failed: {message}")
            status_code = 500 # Default
            is_connection_issue = False
            if "502 Bad Gateway" in message: status_code = 502; is_connection_issue = True
            elif "Connection failed" in message or "Network connection error" in message: status_code = 502; is_connection_issue = True

            if is_connection_issue:
                 logger.info(f"Adding service {service_name} ({server_url_str}) to auto-reconnect list.")
                 orchestrator.pending_reconnection.add(server_url_str)

            raise HTTPException(status_code=status_code, detail=message)
    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        logger.error(f"Unknown error processing registration request (URL: {server_url_str}): {e}", exc_info=True)
        # Optionally add to retry list even on unexpected errors
        # orchestrator.pending_reconnection.add(server_url_str)
        raise HTTPException(status_code=500, detail=f"An unexpected internal server error occurred while processing the registration request.")


@app.get("/health", response_model=Dict[str, Any])
async def get_health_status(
    registry: ServiceRegistry = Depends(get_registry),
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Returns the health status of the orchestrator and connected services."""
    service_statuses = registry.get_registered_services_details()
    # Add current health status based on timeout logic
    for status in service_statuses:
         is_healthy = await orchestrator.is_service_healthy(status["url"])
         status["status"] = "healthy" if is_healthy else "unhealthy"

    return {
        "orchestrator_status": "running",
        "active_services": registry.get_session_count(),
        "total_tools": registry.get_tool_count(),
        "pending_reconnection_count": len(orchestrator.pending_reconnection),
        "react_enabled": orchestrator.react_agent is not None,
        "connected_services_details": service_statuses
    }

@app.get("/service_info", response_model=Dict[str, Any])
async def get_service_info(
    url: str,
    registry: ServiceRegistry = Depends(get_registry),
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Returns detailed information about the specified service, including tool list"""
    logger.info(f"Received service info request, target URL: {url}")
    
    # Get service details
    service_details = registry.get_service_details(url)
    
    if not service_details:
        raise HTTPException(status_code=404, detail=f"Service not found: {url}")
    
    # Add health status
    is_healthy = await orchestrator.is_service_healthy(url)
    service_details["status"] = "healthy" if is_healthy else "unhealthy"
    
    return {
        "service": service_details
    }

# --- New API Endpoints ---
@app.get("/mcp_config", response_model=MCPConfigResponse)
async def get_mcp_config():
    """Get mcp.json configuration"""
    try:
        config_api = MCPConfigAPI()
        return config_api.get_config()
    except Exception as e:
        logger.error(f"Error getting mcp.json configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get mcp.json configuration: {str(e)}")

@app.post("/update_mcp_config", response_model=Dict[str, Any])
async def update_mcp_config(
    config: MCPConfigUpdateRequest,
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Update mcp.json configuration and synchronize services"""
    try:
        config_api = MCPConfigAPI()
        # Pass orchestrator parameter to achieve service synchronization
        result = await config_api.update_config(config, orchestrator)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating mcp.json configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update mcp.json configuration: {str(e)}")

@app.post("/register_mcp_services", response_model=Dict[str, Any])
async def register_mcp_services(
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Register all services from mcp.json"""
    try:
        config_api = MCPConfigAPI()
        result = await config_api.register_services(orchestrator)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error registering mcp.json services: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register mcp.json services: {str(e)}")

@app.post("/remove_service", response_model=Dict[str, Any])
async def remove_service_endpoint(
    url: str,
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Remove service from registry and disconnect"""
    try:
        logger.info(f"Received remove service request, target URL: {url}")
        
        # Check if service exists
        registry = orchestrator.registry
        service_details = registry.get_service_details(url)
        
        if not service_details:
            raise HTTPException(status_code=404, detail=f"Service not found: {url}")
        
        # Get service name for return message
        service_name = registry.get_service_name(url)
        
        # Disconnect service
        await orchestrator.disconnect_service(url)
        
        logger.info(f"Service {service_name} ({url}) successfully removed")
        return {
            "status": "success",
            "message": f"Service {service_name} successfully removed",
            "service": service_details
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error removing service: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove service: {str(e)}")

@app.post("/remove_service_from_config", response_model=Dict[str, Any])
async def remove_service_from_config(
    url: str,
    service_name: str = "",
    orchestrator: MCPOrchestrator = Depends(get_orchestrator)
):
    """Remove service from mcp.json configuration"""
    try:
        logger.info(f"Received request to remove service from config, target URL: {url}, service name: {service_name}")
        
        # Get config API
        config_api = MCPConfigAPI()
        
        # Load current configuration
        config = config_api.get_config()
        old_servers = config.get("mcpServers", {})
        
        # If service name not provided, find by URL
        if not service_name:
            for name, server in old_servers.items():
                if server.get("url") == url:
                    service_name = name
                    break
        
        if not service_name:
            raise HTTPException(status_code=404, detail=f"Cannot find service name by URL: {url}")
            
        # Check if service exists
        if service_name not in old_servers:
            raise HTTPException(status_code=404, detail=f"Service does not exist in configuration: {service_name}")
        
        # Remove service
        del old_servers[service_name]
        config["mcpServers"] = old_servers
        
        # Save configuration
        success = config_api.mcp_config.save_config(config)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to save configuration")
        
        logger.info(f"Service {service_name} removed from configuration")
        return {
            "status": "success",
            "message": f"Service {service_name} removed from configuration",
            "service_name": service_name
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error removing service from configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove service from configuration: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to MCP API"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": load_app_config(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")).get("version", "0.1.0")
    }
    
    # Check LLM service
    try:
        # Simple LLM connection check
        provider = load_app_config(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")).get("llm_config", {}).get("provider", "unknown")
        health_status["llm_service"] = {
            "status": "connected",
            "provider": provider
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["llm_service"] = {
            "status": "disconnected",
            "error": str(e)
        }
    
    # Check connected tool services
    connected_services = get_registry().get_connected_services()
    health_status["connected_services"] = connected_services
    health_status["service_count"] = len(connected_services)
    
    return health_status

@app.get("/tools")
async def list_tools():
    """List all available tools"""
    try:
        tools = get_registry().get_all_tool_info()
        return {"tools": tools, "count": len(tools)}
    except Exception as e:
        logger.error(f"Error getting tool list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting tool list: {str(e)}")

@app.get("/services")
async def list_services():
    """List all connected services"""
    try:
        services = get_registry().get_connected_services()
        return {"services": services, "count": len(services)}
    except Exception as e:
        logger.error(f"Error getting service list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting service list: {str(e)}")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.warning(f"Request validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body}
    )

# --- Main Execution ---
if __name__ == "__main__":
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
