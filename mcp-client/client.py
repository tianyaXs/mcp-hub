import asyncio
import json
import httpx
import logging
from datetime import datetime, timedelta
from contextlib import AsyncExitStack
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any, Tuple, Set

from mcp import ClientSession
from mcp.client.sse import sse_client
from registry import ServiceRegistry
from llm_factory import create_llm_client
from react_agent import ReActAgent

logger = logging.getLogger(__name__)

class MCPOrchestrator:
    """Orchestrates MCP connections, LLM interactions, and health checks with auto-reconnect."""

    def __init__(self, config: Dict[str, Any], registry: ServiceRegistry):
        self.config = config
        self.registry = registry
        self.exit_stack = AsyncExitStack()
        self.http_client: Optional[httpx.AsyncClient] = None
        self.llm_client = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.pending_reconnection: Set[str] = set()
        self.reconnection_task: Optional[asyncio.Task] = None
        self.react_agent: Optional[ReActAgent] = None

        # Timing configuration from loaded config
        self.heartbeat_interval = timedelta(seconds=int(self.config.get("heartbeat_interval", 60)))
        self.heartbeat_timeout = timedelta(seconds=int(self.config.get("heartbeat_timeout", 180)))
        self.reconnection_interval = timedelta(seconds=int(self.config.get("reconnection_interval", 60)))
        self.http_timeout = int(self.config.get("http_timeout", 10))

        # Initialize LLM client
        llm_config = self.config.get("llm_config")
        if llm_config:
            self.llm_client = create_llm_client(llm_config)
            if self.llm_client:
                logger.info(f"{llm_config.provider.capitalize()} Client initialized.")
                # Initialize ReAct agent if LLM client is available
                self.react_agent = ReActAgent(self.llm_client, self.registry, self.config)
                self.react_agent.is_service_healthy = self.is_service_healthy
                logger.info("ReAct Agent initialized.")
            else:
                logger.warning("LLM Client initialization failed.")
        else:
            logger.warning("LLM client configuration not found.")

    async def setup(self):
        """Initializes shared resources like the HTTP client."""
        # Use configured HTTP timeout
        self.http_client = await self.exit_stack.enter_async_context(
            httpx.AsyncClient(timeout=self.http_timeout)
        )
        logger.info("MCPOrchestrator setup complete. HTTP client ready.")

    async def start_monitoring(self):
        """Starts the background health check and reconnection monitors."""
        # Start Heartbeat Monitor
        if self.heartbeat_task is None or self.heartbeat_task.done():
            logger.info(f"Starting heartbeat monitor. Interval: {self.heartbeat_interval.total_seconds()}s")
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        # Start Reconnection Monitor
        if self.reconnection_task is None or self.reconnection_task.done():
             logger.info(f"Starting reconnection monitor. Interval: {self.reconnection_interval.total_seconds()}s")
             self.reconnection_task = asyncio.create_task(self._reconnection_loop())

    async def stop_monitoring(self):
        """Stops the background health check and reconnection monitors."""
        tasks_to_stop = [self.heartbeat_task, self.reconnection_task]
        task_names = ["Heartbeat", "Reconnection"]
        for i, task in enumerate(tasks_to_stop):
            name = task_names[i]
            if task and not task.done():
                task.cancel()
                try: await task
                except asyncio.CancelledError: logger.info(f"{name} monitor task cancelled.")
                except Exception as e: logger.error(f"Error during {name} task cancellation: {e}", exc_info=True)
        self.heartbeat_task = None
        self.reconnection_task = None

    async def connect_service(self, server_url: str, service_name: str = "") -> Tuple[bool, str]:
        """Connect to service with timeout and logging."""
        display_name = service_name or server_url
        
        if not self.http_client:
             logger.error(f"Cannot connect to service {display_name}: HTTP client not ready.")
             return False, "Internal client error: HTTP client not ready"

        if self.registry.get_session(server_url):
            logger.warning(f"Service {display_name} ({server_url}) already registered. Will reconnect.")
            await self.disconnect_service(server_url) # Disconnect first

        logger.info(f"[{display_name}] Attempting to connect to MCP server {server_url}...")
        session: Optional[ClientSession] = None
        try:
            # Add connection retry logic
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    logger.debug(f"[{display_name}] Entering SSE client context... (attempt {retry_count + 1}/{max_retries})")
                    stream_context = await self.exit_stack.enter_async_context(sse_client(url=server_url, timeout=30.0))
                    read_stream, write_stream = stream_context
                    logger.debug(f"[{display_name}] SSE stream acquired.")
                    
                    # Connection successful, break the retry loop
                    session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                    last_error = e
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"[{display_name}] Connection failed (attempt {retry_count}/{max_retries}): {e}. Retrying...")
                        await asyncio.sleep(1)  # Brief wait before retry
                    else:
                        logger.error(f"[{display_name}] Connection failed, maximum retries reached: {e}")
                        raise  # Re-raise the last exception
            
            if not session:
                # If all retries failed but no exception triggered, this is a fallback check
                error_msg = f"Could not establish connection, all retries failed" if last_error else "Could not establish connection, unknown reason"
                raise ConnectionError(error_msg)
                
            logger.info(f"[{display_name}] Attempting to initialize MCP session (timeout={30}s)...")
            try:
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=30
                )
                logger.info(f"[{display_name}] MCP session initialized successfully.")
            except asyncio.TimeoutError:
                logger.error(f"[{display_name}] Timeout occurred during session.initialize().")
                raise 
            except Exception as init_err:
                logger.error(f"[{display_name}] Error during session.initialize(): {init_err}", exc_info=True)
                raise 

            logger.info(f"[{display_name}] Attempting to list tools (timeout={30}s)...")
            try:
                tools_response = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=30
                )
                logger.info(f"[{display_name}] Tools listed successfully.")
            except asyncio.TimeoutError:
                logger.error(f"[{display_name}] Timeout occurred during session.list_tools().")
                raise
            except Exception as list_err:
                logger.error(f"[{display_name}] Error during session.list_tools(): {list_err}", exc_info=True)
                raise

            # If ReAct agent is available, use it to process tool definitions to enhance descriptions
            processed_tools = []
            if self.react_agent:
                processed_tools = self.react_agent.process_tool_definitions(tools_response)
                logger.info(f"[{display_name}] Processed tool definitions using ReAct agent")
            else:
                # Use original processing logic
                for tool in tools_response.tools:
                    parameters = tool.inputSchema or {}
                    if not isinstance(parameters, dict) or parameters.get("type") != "object":
                         parameters = { "type": "object", "properties": parameters, "required": list(parameters.keys()) }
                    tool_definition = {
                        "type": "function", "function": {
                            "name": tool.name, "description": tool.description, "parameters": parameters
                        }
                    }
                    processed_tools.append((tool.name, tool_definition))

            added_tool_names = self.registry.add_service(server_url, session, processed_tools, service_name)
            try: 
                setattr(session, 'url', server_url) # Try to set URL attribute
                setattr(session, 'name', display_name) # Try to set name attribute
            except Exception: 
                logger.warning(f"Could not set attributes on session object {display_name} ({server_url})")

            # Remove from pending reconnection list
            self.pending_reconnection.discard(server_url)
            logger.info(f"Service {display_name} ({server_url}) successfully connected/reconnected, removed from pending reconnection list.")

            final_message = f"Connection successful. Added tools: {', '.join(added_tool_names) if added_tool_names else 'none'}"
            logger.info(f"[{display_name}] {final_message}")
            return True, final_message

        # --- Unified exception handling ---
        except asyncio.TimeoutError:
            logger.error(f"[{display_name}] Connection process timed out during MCP protocol operations (initialize/list_tools).")
            return False, f"Connection timeout: Protocol interaction with service {display_name} ({server_url}) timed out ({30} seconds). Please check target server responsiveness."

        except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
            logger.error(f"[{display_name}] Could not connect to service: {e}", exc_info=True)
            return False, f"Could not connect to service {display_name} ({server_url}): {e}. Please check if the service is running and network connectivity."

        except httpx.RequestError as e:
            logger.error(f"[{display_name}] Network error during initial SSE connection: {e}", exc_info=True)
            return False, f"Network connection error: {e}"

        except Exception as e:
            logger.error(f"[{display_name}] Connection or setup failed: {e}", exc_info=True)
            # (Check for 502 and other HTTP errors - logic same as before)
            is_502_error = False; status_code = None; actual_error = e
            if hasattr(e, 'exceptions'):
                 for sub_exc in getattr(e, 'exceptions', []):
                      if isinstance(sub_exc, httpx.HTTPStatusError): actual_error = sub_exc; break
            if isinstance(actual_error, httpx.HTTPStatusError):
                 status_code = actual_error.response.status_code
                 if status_code == 502: is_502_error = True

            if is_502_error: return False, f"Connection failed: Target service returned 502 Bad Gateway. Please check if target service ('{display_name}') is healthy."
            elif status_code: return False, f"Connection failed: Target service returned HTTP {status_code} error."
            else: return False, f"Service initialization or setup failed (type: {type(e).__name__}): {e}"

    async def disconnect_service(self, server_url: str):
        """Removes service from registry. Resource cleanup relies on exit_stack."""
        logger.info(f"Removing service from active registry: {server_url}")
        # Removing from registry stops heartbeats and tool usage
        session = self.registry.remove_service(server_url)
        if session:
             logger.debug(f"Session object for {server_url} removed from registry. Underlying resources managed by exit stack.")
        else:
             logger.warning(f"Attempted disconnect for {server_url} not found in active registry.")

    # --- Heartbeat Methods ---
    async def _heartbeat_loop(self):
        """Background loop for periodic health checks."""
        while True:
            await asyncio.sleep(self.heartbeat_interval.total_seconds())
            await self._check_all_services() # Error handling is inside this call

    async def _check_all_services(self):
        """Checks health of registered services."""
        logger.debug("Running periodic health checks...")
        current_time = datetime.now()
        urls_to_check = self.registry.get_all_service_urls() # Get currently active URLs
        tasks = {} # url -> task mapping for error correlation

        urls_timed_out = []
        for url in urls_to_check:
            last_heartbeat = self.registry.get_last_heartbeat(url)
            # Check for timeout
            if last_heartbeat and (current_time - last_heartbeat > self.heartbeat_timeout):
                logger.warning(f"Service {url} timed out (last: {last_heartbeat}). Adding to pending and disconnecting.")
                self.pending_reconnection.add(url) # Mark for reconnection
                urls_timed_out.append(url)
            elif last_heartbeat is None: # Should not happen if registry is consistent
                 logger.warning(f"Missing heartbeat record for active service {url}. Marking for reconnect/disconnect.")
                 self.pending_reconnection.add(url)
                 urls_timed_out.append(url)
            else:
                # If not timed out, schedule a heartbeat check
                tasks[url] = asyncio.create_task(self._send_one_heartbeat(url))

        # Disconnect services that timed out in this cycle
        if urls_timed_out:
            disconnect_tasks = [self.disconnect_service(url) for url in urls_timed_out]
            await asyncio.gather(*disconnect_tasks, return_exceptions=True) # Disconnect concurrently

        # Wait for heartbeat checks for non-timed-out services
        if tasks:
            await asyncio.gather(*tasks.values(), return_exceptions=True) # Exceptions logged in _send_one_heartbeat

        logger.debug(f"Health check cycle complete. Active: {self.registry.get_session_count()}, Pending Reconnect: {len(self.pending_reconnection)}")

    async def _send_one_heartbeat(self, server_url: str):
        """Sends a single health check request. Logs errors, raises on failure."""
        if not self.http_client or not hasattr(self.http_client, 'is_closed') or self.http_client.is_closed:
            # Added check for closed client
            logger.error(f"Cannot send heartbeat to {server_url}: HTTP client not available or closed.")
            raise RuntimeError(f"HTTP Client not available/closed for heartbeat to {server_url}")

        health_url = ""
        try:
            base_url = server_url
            health_path = "/health"
            health_url = urljoin(base_url + ("/" if not base_url.endswith("/") else ""), health_path.lstrip("/"))
            logger.debug(f"Sending heartbeat to: {health_url}")
            response = await self.http_client.get(health_url) # Use instance client
            response.raise_for_status() # Check 4xx/5xx

            # Success: Update health in the registry
            self.registry.update_service_health(server_url)
            logger.debug(f"Health check SUCCESS for: {server_url}")
        except Exception as e:
            # Log appropriate warning/error based on exception type
            if isinstance(e, httpx.TimeoutException): logger.warning(f"Health check TIMEOUT for: {health_url}")
            elif isinstance(e, httpx.RequestError): logger.warning(f"Health check NETWORK ERROR for {health_url}: {e}")
            elif isinstance(e, httpx.HTTPStatusError): logger.warning(f"Health check FAILED for {health_url}: Status {e.response.status_code}")
            elif isinstance(e, RuntimeError) and "closed" in str(e): pass # Already logged error, avoid flooding
            else: logger.error(f"Unexpected error during heartbeat for {health_url}: {e}", exc_info=True)
            # Re-raise the exception so asyncio.gather in _check_all_services knows it failed
            # This allows potential future logic based on repeated failures, but we currently ignore it there.
            raise e

    # --- Auto Reconnection Methods ---
    async def _reconnection_loop(self):
        """Periodically attempts to reconnect to services in the pending list."""
        while True:
            await asyncio.sleep(self.reconnection_interval.total_seconds())
            await self._attempt_reconnections()

    async def _attempt_reconnections(self):
        """Tries to reconnect once to all services pending reconnection."""
        if not self.pending_reconnection: return # Skip if nothing is pending

        # Create a copy to avoid issues if set is modified during iteration
        urls_to_retry = list(self.pending_reconnection)
        logger.info(f"Attempting to reconnect {len(urls_to_retry)} service(s): {urls_to_retry}")

        # Run connection attempts concurrently
        tasks = [self.connect_service(url) for url in urls_to_retry]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results (removal from pending happens in connect_service on success)
        for url, result in zip(urls_to_retry, results):
            if isinstance(result, tuple) and result[0] is True:
                 logger.info(f"Reconnection successful for: {url}")
            elif isinstance(result, Exception): # Unexpected error during connect_service
                 logger.error(f"Unexpected error during reconnection attempt for {url}: {result}", exc_info=isinstance(result, Exception))
            else: # connect_service returned (False, message)
                 logger.warning(f"Reconnection attempt failed for {url}: {result[1]}")
                 # Keep the URL in self.pending_reconnection for the next cycle

    # --- Other Methods ---
    async def is_service_healthy(self, server_url: str) -> bool:
         """Checks health based on registry data and timeout."""
         last_heartbeat = self.registry.get_last_heartbeat(server_url)
         if not last_heartbeat: return False
         # Use configured timeout
         return (datetime.now() - last_heartbeat) <= self.heartbeat_timeout

    async def process_query(self, query: str) -> Any:
        """Process user query using standard method"""
        if not self.llm_client: return "Error: Language model client not configured."

        messages = [
            {"role": "system", "content": "You are an intelligent assistant that can utilize available tools to answer questions."},
            {"role": "user", "content": query}
        ]
        
        # Get configured model name
        llm_config = self.config.get("llm_config")
        if not llm_config or not llm_config.model:
            return "Error: Language model name not configured."
            
        model_name = llm_config.model
        available_tools = self.registry.get_all_tools()
        provider = llm_config.provider
        logger.debug(f"Sending query to LLM ({provider}/{model_name}). Query: '{query[:50]}...'. Tools: {len(available_tools)}")

        try:
            # Ensure keyword arguments match the SDK's expectations
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=available_tools if available_tools else None
                # Verify other required parameters for your specific provider if needed
            )
            choice = response.choices[0]
            message = choice.message

            # (Handle tool calls - code omitted for brevity, same as before using registry)
            if choice.finish_reason == "tool_calls" and message.tool_calls:
                tool_call = message.tool_calls[0]; function_name = tool_call.function.name
                logger.info(f"LLM requested tool call: '{function_name}'")
                try: function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e: logger.error(f"Error parsing tool arguments: {e}"); return f"Error: Unable to parse parameters for tool '{function_name}'."
                target_session = self.registry.get_session_for_tool(function_name)
                if not target_session: logger.error(f"Tool service not found: {function_name}"); return f"Error: Could not find service to execute tool '{function_name}'."
                session_url = getattr(target_session, 'url', 'unknown_url')
                if not await self.is_service_healthy(session_url): logger.warning(f"Tool service unhealthy: {session_url}"); return f"Error: The service required to execute tool '{function_name}' is currently unavailable."
                logger.info(f"Executing tool '{function_name}' via session {session_url}")
                try:
                    result = await target_session.call_tool(function_name, function_args)
                    # (Process result...)
                    if result.content and isinstance(result.content, list) and hasattr(result.content[0], 'text'): return result.content[0].text
                    else: logger.warning(f"Unexpected tool result format: {result}"); return f"Info: Tool '{function_name}' executed, but result format was unexpected."
                except Exception as e: logger.error(f"Error calling tool: {e}", exc_info=True); return f"Error: An internal error occurred while calling tool '{function_name}'."
            # (Handle direct response - code omitted for brevity)
            else: logger.info("LLM provided direct response"); return message.content.strip() if message.content else ""

        except TypeError as e:
             # Catch the specific TypeError seen before
             logger.error(f"TypeError during LLM call: {e}. Check SDK arguments for model '{model_name}'.", exc_info=True)
             return f"Error: Type error during language model call, please check SDK parameters. ({e})"
        except Exception as e:
            logger.error(f"Error during LLM interaction or tool processing: {e}", exc_info=True)
            return f"Error: An unexpected error occurred while processing your request. ({type(e).__name__}: {e})"

    async def process_query_with_react(self, query: str) -> str:
        """Process user query using ReAct agent, supporting multi-round tool calls"""
        if not self.react_agent:
            logger.warning("ReAct Agent not initialized. Falling back to standard query processing.")
            return await self.process_query(query)
        
        logger.info(f"Processing query with ReAct agent: '{query[:50]}...'")
        result, trace = await self.react_agent.process_query(query)
        
        # Optionally process trace for debugging
        if trace and self.config.get("react_enable_trace", False):
            trace_str = self.react_agent._format_execution_trace(trace)
            logger.debug(f"ReAct execution trace:\n{trace_str}")
            
        return result

    async def process_query_with_trace(self, query: str) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """Process user query using ReAct agent and return execution trace"""
        if not self.react_agent:
            logger.warning("ReAct Agent not initialized. Falling back to standard query processing.")
            result = await self.process_query(query)
            return result, None
        
        logger.info(f"Processing query with ReAct agent (with trace): '{query[:50]}...'")
        # Temporarily enable trace recording
        original_trace_setting = self.react_agent.enable_trace
        self.react_agent.enable_trace = True
        
        # Process query
        result, trace = await self.react_agent.process_query(query)
        
        # Restore original setting
        self.react_agent.enable_trace = original_trace_setting
        
        return result, trace

    async def stream_process_query(self, query: str):
        """
        Process user query using ReAct agent's streaming capability
        
        Args:
            query: User query string
            
        Returns:
            Stream response generator, returning results immediately after each step completes
        """
        if not self.react_agent:
            logger.warning("ReAct Agent not initialized. Cannot execute streaming query.")
            yield {
                "thinking_step": None,
                "is_final": True,
                "result": "Error: ReAct Agent not initialized, cannot execute streaming thought process."
            }
            return
        
        logger.info(f"Starting streaming query processing with ReAct agent: '{query[:50]}...'")
        
        # Use streaming processing method
        async for response in self.react_agent.stream_process_query(query):
            yield response
        
        logger.info(f"Streaming query processing complete: '{query[:50]}...'")

    async def cleanup(self):
        """Stops monitoring and cleans up resources."""
        logger.info("Cleaning up MCPOrchestrator resources...")
        await self.stop_monitoring() # Stop background tasks first
        try:
            # Close the exit stack - this should close http_client and active SSE/MCP resources
            await self.exit_stack.aclose()
            logger.info("AsyncExitStack closed successfully.")
        except Exception as e:
            logger.error(f"Error during AsyncExitStack cleanup: {e}", exc_info=True)
        self.http_client = None
        logger.info("MCPOrchestrator cleanup finished.")
