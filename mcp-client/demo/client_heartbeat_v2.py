import asyncio
import json
import os
import httpx
import toml
import logging
from datetime import datetime, timedelta
from contextlib import AsyncExitStack
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any, Tuple

# MCP and ZhipuAI specific imports (ensure these libraries are installed)
# Assuming 'mcp' provides ClientSession, sse_client and structure for tool responses
# Assuming 'zhipuai' provides ZhipuAI client
from mcp import ClientSession  # type: ignore # Placeholder if library is not strictly typed
from mcp.client.sse import sse_client # type: ignore # Placeholder
from zhipuai import ZhipuAI # type: ignore # Placeholder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration Constants ---
# Consider moving these to a dedicated config file or Pydantic settings
HEARTBEAT_INTERVAL_SECONDS = 3 # Check every 60 seconds
HEARTBEAT_TIMEOUT_SECONDS = 180 # Disconnect after 180 seconds of no response
HTTP_TIMEOUT_SECONDS = 10 # Timeout for HTTP health checks

class MCPClient:
    """
    Manages connections to MCP tool servers, interacts with ZhipuAI LLM,
    and orchestrates tool calls.
    """
    def __init__(self, pyproject_file: Optional[str] = None):
        """Initializes the MCP client, loading configuration and setting up resources."""
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}  # server_url -> session
        self.service_health: Dict[str, datetime] = {} # server_url -> last_heartbeat_time
        # tool_name -> { "type": "function", "function": {...} }
        self.tool_cache: Dict[str, Dict[str, Any]] = {}
        # tool_name -> ClientSession
        self.tool_to_session_map: Dict[str, ClientSession] = {}
        self.http_client: Optional[httpx.AsyncClient] = None # Initialized in setup

        # --- Configuration Loading ---
        if pyproject_file is None:
            # Default path relative to this file's location
            current_dir = os.path.dirname(__file__)
            pyproject_file = os.path.join(current_dir, "..", "pyproject.toml")
            # Adjust the relative path if your structure differs (e.g., if this file is in project root)
            # pyproject_file = os.path.join(current_dir, "pyproject.toml") # Example if in root

        try:
            logger.info(f"Loading configuration from: {pyproject_file}")
            with open(pyproject_file, "r", encoding="utf-8") as f:
                config = toml.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {pyproject_file} not found!")
            raise RuntimeError(f"配置文件 {pyproject_file} 未找到！")
        except Exception as e:
            logger.error(f"Error parsing configuration file: {e}", exc_info=True)
            raise RuntimeError(f"解析配置文件时出错: {e}")

        zhipu_config = config.get("tool", {}).get("zhipu", {})
        self.openai_api_key: Optional[str] = zhipu_config.get("openai_api_key")
        self.model: Optional[str] = zhipu_config.get("model")

        if not self.openai_api_key:
            logger.warning("ZhipuAI API key not found in configuration.")
            # Decide if this is a fatal error or if it can run without LLM
            # raise ValueError("Missing ZhipuAI API Key in configuration")
        if not self.model:
            logger.warning("ZhipuAI model name not found in configuration.")
            # raise ValueError("Missing ZhipuAI model name in configuration")

        # Initialize ZhipuAI client only if key is present
        self.client = ZhipuAI(api_key=self.openai_api_key) if self.openai_api_key else None

        # Configuration for timing
        self.heartbeat_interval = timedelta(seconds=HEARTBEAT_INTERVAL_SECONDS)
        self.heartbeat_timeout = timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)

    async def setup(self):
        """Asynchronous setup for resources like the HTTP client."""
        self.http_client = await self.exit_stack.enter_async_context(httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS))
        logger.info("MCPClient setup complete. HTTP client initialized.")

    async def connect_to_server(self, server_url: str) -> Tuple[bool, str]:
        """
        Connects to an MCP tool server, initializes the session, and registers its tools.

        Returns:
            Tuple[bool, str]: (success_status, message)
        """
        if not self.http_client:
             logger.error("HTTP Client not initialized. Call setup() first.")
             return False, "Internal client error: HTTP Client not ready"

        if server_url in self.sessions:
            logger.warning(f"Already connected to {server_url}. Disconnecting first.")
            await self.disconnect_service(server_url)

        logger.info(f"Attempting to connect to MCP server: {server_url}")
        try:
            # Enter SSE client context
            stream_context = await self.exit_stack.enter_async_context(sse_client(url=server_url))
            read_stream, write_stream = stream_context

            # Enter ClientSession context
            session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))

            await session.initialize()
            self.sessions[server_url] = session
            self.service_health[server_url] = datetime.now() # Mark as healthy upon connection

            # List tools and update caches
            tools_response = await session.list_tools()
            added_tools = []
            for tool in tools_response.tools:
                # --- Process tool schema ---
                parameters = tool.inputSchema or {}
                # Ensure parameters follow OpenAI structure (object type with properties)
                if not isinstance(parameters, dict) or parameters.get("type") != "object":
                     parameters = {
                         "type": "object",
                         "properties": parameters,
                         # Attempt to infer required fields if not specified, otherwise list all
                         "required": list(parameters.keys()) # Simple default, might need refinement
                     }

                tool_definition = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": parameters
                    }
                }

                # Check for conflicts before adding
                if tool.name in self.tool_cache:
                     logger.warning(f"Tool name conflict: '{tool.name}' from {server_url} conflicts with existing tool. Skipping.")
                     # Optionally, allow overwriting or add suffix, but skipping is safer
                     continue

                self.tool_cache[tool.name] = tool_definition
                self.tool_to_session_map[tool.name] = session
                added_tools.append(tool.name)

            logger.info(f"Successfully connected to {server_url}. Added tools: {added_tools}")
            return True, f"Connected. Tools added: {', '.join(added_tools) if added_tools else 'None'}"

        except httpx.RequestError as e:
            logger.error(f"Connection error for {server_url}: {e}", exc_info=True)
            # Ensure partial resources are potentially cleaned by exit_stack, but log failure
            # await self.exit_stack.aclose() # Attempt cleanup if connection failed mid-setup
            return False, f"Connection error: {e}"
        except Exception as e:
            logger.error(f"Failed to connect or initialize session for {server_url}: {e}", exc_info=True)
            # Ensure partial resources are potentially cleaned by exit_stack
            # await self.exit_stack.aclose() # Attempt cleanup if connection failed mid-setup
            return False, f"Failed to initialize: {e}"

    async def disconnect_service(self, server_url: str):
        """Disconnects from a service, closes the session, and removes its tools."""
        if server_url not in self.sessions:
            logger.warning(f"Attempted to disconnect non-existent session: {server_url}")
            return

        session = self.sessions.pop(server_url)
        logger.info(f"Disconnecting from service: {server_url}")

        # Remove tools associated with this session
        tools_to_remove = [name for name, owner_session in self.tool_to_session_map.items() if owner_session == session]
        if tools_to_remove:
            logger.info(f"Removing tools from {server_url}: {tools_to_remove}")
            for tool_name in tools_to_remove:
                if tool_name in self.tool_cache:
                    del self.tool_cache[tool_name]
                if tool_name in self.tool_to_session_map:
                    del self.tool_to_session_map[tool_name]

        # Close the MCP session resources using the exit stack
        try:
            # Note: Aclosing the *session* specifically might be tricky if managed by stack
            # Often, aclose() on the stack handles all entered contexts.
            # If ClientSession needs explicit close separate from SSE stream:
            # await session.close() # If session has an explicit close method
            # Let exit_stack handle the SSE stream closure implicitly if possible.
            # Direct aclose_resource might be needed if stack management is complex.
            # For simplicity, assume stack's aclose handles session if entered via stack.
             logger.debug(f"MCP Session for {server_url} should be closed by AsyncExitStack.")
             # If explicit closing needed: await self.exit_stack.aclose_resource(session)
        except Exception as e:
            logger.error(f"Error closing session resources for {server_url}: {e}", exc_info=True)

        # Remove health record
        if server_url in self.service_health:
            del self.service_health[server_url]

        logger.info(f"Service {server_url} disconnected and resources cleaned up.")


    async def start_heartbeat_monitor(self):
        """Starts the background task to periodically check service health."""
        logger.info(f"Starting heartbeat monitor. Interval: {self.heartbeat_interval.total_seconds()}s, Timeout: {self.heartbeat_timeout.total_seconds()}s")
        while True:
            await asyncio.sleep(self.heartbeat_interval.total_seconds())
            logger.debug("Running periodic health checks...")
            await self.check_services()

    async def check_services(self):
        """Checks health of all connected services concurrently and handles timeouts."""
        current_time = datetime.now()
        urls_to_check = list(self.sessions.keys()) # Copy keys to avoid modification issues
        tasks = []
        disconnected_due_to_timeout = []

        for url in urls_to_check:
            last_heartbeat = self.service_health.get(url) # Should always exist if session exists
            if last_heartbeat is None:
                 logger.warning(f"Missing heartbeat record for active session {url}, disconnecting.")
                 disconnected_due_to_timeout.append(url)
                 continue

            if current_time - last_heartbeat > self.heartbeat_timeout:
                logger.warning(f"Service {url} timed out (last heartbeat: {last_heartbeat}). Disconnecting.")
                disconnected_due_to_timeout.append(url)
            else:
                # Schedule heartbeat task
                tasks.append(self.send_heartbeat(url))

        # Disconnect timed out services first
        for url in disconnected_due_to_timeout:
             # Use create_task to avoid blocking checks while disconnecting
             asyncio.create_task(self.disconnect_service(url))

        # Run remaining health checks concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # The error is already logged within send_heartbeat
                    logger.error(f"Exception during concurrent heartbeat check for task {i}: {result}")
                    # Consider if repeated failures warrant disconnection

        logger.debug(f"Health check cycle complete. Active sessions: {len(self.sessions)}")


    async def send_heartbeat(self, server_url: str):
        """Sends a health check GET request to the service's /health endpoint."""
        if not self.http_client:
            logger.error(f"Cannot send heartbeat to {server_url}: HTTP client not available.")
            return # Or raise an exception

        health_url = ""
        try:
            # Construct health check URL robustly
            base_url = server_url # Assuming server_url is the base like "http://localhost:8001"
            health_path = "/health"
            health_url = urljoin(base_url + ("/" if not base_url.endswith("/") else ""), health_path.lstrip("/"))

            logger.debug(f"Sending heartbeat to: {health_url}")
            response = await self.http_client.get(health_url) # Timeout managed by client instance

            response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses

            # If successful (2xx status code)
            self.service_health[server_url] = datetime.now()
            logger.debug(f"Health check SUCCESS for: {server_url}")

        except httpx.TimeoutException:
             logger.warning(f"Health check TIMEOUT for: {health_url}")
             # Consider marking as unhealthy or incrementing failure count
        except httpx.RequestError as e:
            logger.warning(f"Health check NETWORK ERROR for {health_url}: {e}")
            # Consider marking as unhealthy
        except httpx.HTTPStatusError as e:
            logger.warning(f"Health check FAILED for {health_url}: Status {e.response.status_code}")
            # Consider marking as unhealthy
        except Exception as e:
            logger.error(f"Unexpected error during heartbeat for {health_url}: {e}", exc_info=True)
            # Consider marking as unhealthy


    async def process_query(self, query: str) -> Any:
        """
        Processes a user query: sends to LLM with available tools, handles tool calls.

        Returns:
            The final result, either text from LLM or result from a tool call.
            Can be a string, dict, list, etc., depending on tool output.
        """
        if not self.client:
            logger.error("ZhipuAI client is not initialized. Cannot process query.")
            return "错误：语言模型客户端未初始化。" # Error message in Chinese

        messages = [
            {"role": "system", "content": "你是一个智能助手，能够利用可用工具来回答问题。"},
            {"role": "user", "content": query}
        ]

        # Use cached tools
        available_tools = list(self.tool_cache.values())
        logger.debug(f"Sending query to LLM. Query: '{query}'. Available tools: {list(self.tool_cache.keys())}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=available_tools if available_tools else None # Pass None if no tools
            )

            # Assuming ZhipuAI's response structure is similar to OpenAI's
            choice = response.choices[0]
            message = choice.message

            # Check if LLM decided to call a tool
            if choice.finish_reason == "tool_calls" and message.tool_calls:
                tool_call = message.tool_calls[0] # Handle one tool call for simplicity
                function_name = tool_call.function.name
                logger.info(f"LLM requested to call tool: '{function_name}'")

                try:
                    function_args = json.loads(tool_call.function.arguments)
                    logger.debug(f"Tool arguments: {function_args}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tool arguments for {function_name}: {e}", exc_info=True)
                    return f"错误：无法解析工具 '{function_name}' 的参数。"

                # Find the session using the optimized map
                target_session = self.tool_to_session_map.get(function_name)

                if target_session:
                    # Check if the session is still considered healthy
                    if not self.is_service_healthy(target_session.url): # Assuming session has url attribute or lookup needed
                         logger.warning(f"Target service for tool '{function_name}' ({target_session.url}) is unhealthy. Aborting call.")
                         return f"错误：执行工具 '{function_name}' 所需的服务当前不可用。"

                    logger.info(f"Executing tool '{function_name}' via session {target_session.url}")
                    try:
                        # Make the tool call via MCP session
                        result = await target_session.call_tool(function_name, function_args)
                        # Process result - assuming simple text for now, adapt if needed
                        # Check if result.content exists and is not empty
                        if result.content and isinstance(result.content, list) and hasattr(result.content[0], 'text'):
                            tool_output = result.content[0].text
                            logger.info(f"Tool '{function_name}' executed successfully. Result received.")
                            logger.debug(f"Tool Raw Output: {tool_output}")
                            # The output might be JSON string, plain text, etc.
                            # Return it directly. The endpoint will handle JSON response creation.
                            return tool_output
                        else:
                             logger.warning(f"Tool '{function_name}' returned unexpected content structure: {result.content}")
                             return f"信息：工具 '{function_name}' 执行完毕，但返回了非预期的结果格式。"

                    except Exception as e:
                        logger.error(f"Error calling tool '{function_name}' on {target_session.url}: {e}", exc_info=True)
                        return f"错误：调用工具 '{function_name}' 时发生内部错误。"
                else:
                    logger.error(f"Tool '{function_name}' requested by LLM, but no corresponding service session found.")
                    # This might happen if the service disconnected after the LLM call started
                    return f"错误：找不到可用服务来执行工具 '{function_name}'。"

            else:
                # No tool call, return LLM's direct response content
                logger.info("LLM provided direct response without tool call.")
                return message.content.strip() if message.content else ""

        except Exception as e:
            logger.error(f"Error during LLM interaction or tool processing: {e}", exc_info=True)
            return "错误：处理您的请求时发生意外错误。"


    async def cleanup(self):
        """Cleans up all resources managed by the AsyncExitStack."""
        logger.info("Cleaning up MCPClient resources...")
        try:
            await self.exit_stack.aclose()
            logger.info("AsyncExitStack closed successfully.")
        except Exception as e:
            logger.error(f"Error during AsyncExitStack cleanup: {e}", exc_info=True)
        self.sessions.clear()
        self.service_health.clear()
        self.tool_cache.clear()
        self.tool_to_session_map.clear()
        self.http_client = None # Mark as closed
        logger.info("MCPClient cleanup finished.")

    def is_service_healthy(self, server_url: str) -> bool:
        """Checks if a service is currently considered healthy based on last heartbeat."""
        last_heartbeat = self.service_health.get(server_url)
        if not last_heartbeat:
            return False # Not connected or no heartbeat recorded yet
        return (datetime.now() - last_heartbeat) <= self.heartbeat_timeout

# --- FastAPI Application ---

# Use lifespan for setup and cleanup
async def lifespan(app: FastAPI):
    """Manages the MCPClient lifecycle within the FastAPI application."""
    logger.info("Application startup: Initializing MCPClient...")
    client = MCPClient() # Add path to pyproject.toml if not default
    await client.setup() # Perform async setup
    app.state.client = client
    logger.info("MCPClient initialized and stored in app state.")

    # Start background tasks
    app.state.heartbeat_task = asyncio.create_task(client.start_heartbeat_monitor())
    logger.info("Heartbeat monitor task started.")

    yield # Application runs here

    # --- Shutdown sequence ---
    logger.info("Application shutdown: Cleaning up resources...")
    if hasattr(app.state, 'heartbeat_task') and app.state.heartbeat_task:
        app.state.heartbeat_task.cancel()
        try:
            await app.state.heartbeat_task
        except asyncio.CancelledError:
            logger.info("Heartbeat monitor task cancelled.")
        except Exception as e:
            logger.error(f"Error during heartbeat task cancellation: {e}", exc_info=True)

    if hasattr(app.state, 'client') and app.state.client:
        await app.state.client.cleanup()
    logger.info("Application shutdown complete.")


app = FastAPI(lifespan=lifespan)

@app.post("/query")
async def query_endpoint(request: Request):
    """Handles user queries, routes them through MCPClient."""
    client: MCPClient = request.app.state.client
    if not client:
        raise HTTPException(status_code=503, detail="Service Unavailable: Client not initialized")

    try:
        data = await request.json()
        query = data.get('query')
        if not query or not isinstance(query, str):
            raise HTTPException(status_code=400, detail="Missing or invalid 'query' parameter (must be a string)")

        logger.info(f"Received query request: '{query[:100]}...'") # Log truncated query
        result = await client.process_query(query)

        # Result can be string, dict, list, etc. JSONResponse handles serialization.
        logger.info("Query processed successfully.")
        logger.debug(f"Returning result: {result}")
        return JSONResponse(content={"result": result})

    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON request body.")
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON format in request body."},
        )
    except HTTPException as http_exc:
         # Re-raise HTTPExceptions to let FastAPI handle them
         raise http_exc
    except Exception as e:
        logger.error(f"Unhandled error processing query: {e}", exc_info=True)
        # Return a generic 500 error for unexpected issues
        return JSONResponse(
            status_code=500,
            content={"error": "An internal server error occurred."},
            # Avoid leaking internal error details like str(e) to the client
            # headers={"X-Error": "True"} # Optional: custom header for monitoring
        )

@app.post("/register")
async def register_service(request: Request):
    """Registers or re-registers an MCP tool server."""
    client: MCPClient = request.app.state.client
    if not client:
        raise HTTPException(status_code=503, detail="Service Unavailable: Client not initialized")

    try:
        data = await request.json()
        server_url = data.get('url')
        if not server_url or not isinstance(server_url, str):
            # Basic validation - consider adding more robust URL validation
            raise HTTPException(status_code=400, detail="Missing or invalid 'url' parameter (must be a string)")

        logger.info(f"Received registration request for URL: {server_url}")

        # connect_to_server now handles potential existing connections internally
        success, message = await client.connect_to_server(server_url)

        if success:
            logger.info(f"Service {server_url} registration successful: {message}")
            return JSONResponse(
                content={"status": "success", "message": message}
            )
        else:
             logger.error(f"Failed to register service {server_url}: {message}")
             # Return a more specific error code if possible (e.g., 502 if connection failed)
             raise HTTPException(status_code=500, detail=f"Failed to connect to service: {message}")

    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON request body for registration.")
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON format in request body."},
        )
    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        logger.error(f"Unhandled error during service registration for {data.get('url', 'N/A')}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error during registration: {str(e)}")


@app.get("/health")
async def get_health_status(request: Request):
    """Returns the health status of the orchestrator and connected services."""
    client: MCPClient = request.app.state.client
    if not client:
        return JSONResponse(status_code=503, content={"status": "initializing"})

    service_statuses = []
    for url, session in client.sessions.items():
        last_heartbeat = client.service_health.get(url)
        is_healthy = client.is_service_healthy(url)
        status = {
            "url": url,
            "status": "healthy" if is_healthy else "unhealthy",
            "last_heartbeat": str(last_heartbeat) if last_heartbeat else "N/A"
        }
        # Optionally add list of tools provided by this service
        # tools = [name for name, owner_session in client.tool_to_session_map.items() if owner_session == session]
        # status["tools"] = tools
        service_statuses.append(status)

    return {
        "orchestrator_status": "running",
        "connected_services": service_statuses
    }

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Recommended: Configure Uvicorn logging to be compatible with standard logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(client_addr)s - '%(request_line)s' %(status_code)s"
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    log_config["loggers"]["uvicorn.error"]["level"] = "INFO"
    log_config["loggers"]["uvicorn.access"]["level"] = "INFO"

    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=log_config)