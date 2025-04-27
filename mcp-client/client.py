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
        """使用超时和日志连接服务。"""
        display_name = service_name or server_url
        
        if not self.http_client:
             logger.error(f"无法连接服务 {display_name}：HTTP 客户端未就绪。")
             return False, "内部客户端错误：HTTP 客户端未就绪"

        if self.registry.get_session(server_url):
            logger.warning(f"服务 {display_name} ({server_url}) 已注册。将重新连接。")
            await self.disconnect_service(server_url) # 先断开

        logger.info(f"[{display_name}] 尝试连接 MCP 服务器 {server_url}...")
        session: Optional[ClientSession] = None
        try:
            # 添加连接重试逻辑
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    logger.debug(f"[{display_name}] 进入 SSE 客户端上下文... (尝试 {retry_count + 1}/{max_retries})")
                    stream_context = await self.exit_stack.enter_async_context(sse_client(url=server_url, timeout=30.0))
                    read_stream, write_stream = stream_context
                    logger.debug(f"[{display_name}] SSE 流已获取。")
                    
                    # 连接成功，跳出重试循环
                    session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                    last_error = e
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"[{display_name}] 连接失败 (尝试 {retry_count}/{max_retries}): {e}. 重试中...")
                        await asyncio.sleep(1)  # 短暂等待后重试
                    else:
                        logger.error(f"[{display_name}] 连接失败，已达到最大重试次数: {e}")
                        raise  # 重新抛出最后一个异常
            
            if not session:
                # 如果所有重试都失败但没有触发异常，这是一个兜底检查
                error_msg = f"无法建立连接，所有重试均失败" if last_error else "无法建立连接，未知原因"
                raise ConnectionError(error_msg)
                
            logger.info(f"[{display_name}] 尝试初始化 MCP 会话 (超时={30}s)...")
            try:
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=30
                )
                logger.info(f"[{display_name}] MCP 会话初始化成功。")
            except asyncio.TimeoutError:
                logger.error(f"[{display_name}] 在 session.initialize() 期间发生超时。")
                raise 
            except Exception as init_err:
                logger.error(f"[{display_name}] 在 session.initialize() 期间发生错误: {init_err}", exc_info=True)
                raise 

            logger.info(f"[{display_name}] 尝试列出工具 (超时={30}s)...")
            try:
                tools_response = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=30
                )
                logger.info(f"[{display_name}] 工具列出成功。")
            except asyncio.TimeoutError:
                logger.error(f"[{display_name}] 在 session.list_tools() 期间发生超时。")
                raise
            except Exception as list_err:
                logger.error(f"[{display_name}] 在 session.list_tools() 期间发生错误: {list_err}", exc_info=True)
                raise

            processed_tools = []
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
                setattr(session, 'url', server_url) # 尝试设置 URL 属性
                setattr(session, 'name', display_name) # 尝试设置名称属性
            except Exception: 
                logger.warning(f"无法在会话对象上设置属性 {display_name} ({server_url})")

            # 从待重连列表中移除
            self.pending_reconnection.discard(server_url)
            logger.info(f"服务 {display_name} ({server_url}) 成功连接/重连，已从待重连列表移除。")

            final_message = f"连接成功。添加的工具: {', '.join(added_tool_names) if added_tool_names else '无'}"
            logger.info(f"[{display_name}] {final_message}")
            return True, final_message

        # --- 统一处理异常 ---
        except asyncio.TimeoutError:
            logger.error(f"[{display_name}] 连接过程在 MCP 协议操作 (initialize/list_tools) 期间超时。")
            return False, f"连接超时：与服务 {display_name} ({server_url}) 的协议交互超时 ({30}秒)。请检查目标服务器响应性。"

        except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
            logger.error(f"[{display_name}] 无法连接到服务: {e}", exc_info=True)
            return False, f"无法连接到服务 {display_name} ({server_url}): {e}。请检查服务是否运行及网络连接。"

        except httpx.RequestError as e:
            logger.error(f"[{display_name}] 初始 SSE 连接时网络错误: {e}", exc_info=True)
            return False, f"网络连接错误: {e}"

        except Exception as e:
            logger.error(f"[{display_name}] 连接或设置失败: {e}", exc_info=True)
            # (检查 502 等 HTTP 错误 - 逻辑同前)
            is_502_error = False; status_code = None; actual_error = e
            if hasattr(e, 'exceptions'):
                 for sub_exc in getattr(e, 'exceptions', []):
                      if isinstance(sub_exc, httpx.HTTPStatusError): actual_error = sub_exc; break
            if isinstance(actual_error, httpx.HTTPStatusError):
                 status_code = actual_error.response.status_code
                 if status_code == 502: is_502_error = True

            if is_502_error: return False, f"连接失败：目标服务返回 502 Bad Gateway。请检查目标服务 ('{display_name}') 是否健康。"
            elif status_code: return False, f"连接失败：目标服务返回 HTTP {status_code} 错误。"
            else: return False, f"服务初始化或设置失败 (类型: {type(e).__name__}): {e}"

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
    def is_service_healthy(self, server_url: str) -> bool:
         """Checks health based on registry data and timeout."""
         last_heartbeat = self.registry.get_last_heartbeat(server_url)
         if not last_heartbeat: return False
         # Use configured timeout
         return (datetime.now() - last_heartbeat) <= self.heartbeat_timeout

    async def process_query(self, query: str) -> Any:
        """Processes a user query using LLM and registered tools."""
        if not self.llm_client: return "错误：语言模型客户端未配置。"

        messages = [
            {"role": "system", "content": "你是一个智能助手，能够利用可用工具来回答问题。"},
            {"role": "user", "content": query}
        ]
        
        # Get configured model name
        llm_config = self.config.get("llm_config")
        if not llm_config or not llm_config.model:
            return "错误：语言模型名称未配置。"
            
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
                except json.JSONDecodeError as e: logger.error(...); return f"错误：无法解析工具 '{function_name}' 的参数。"
                target_session = self.registry.get_session_for_tool(function_name)
                if not target_session: logger.error(...); return f"错误：找不到执行工具 '{function_name}' 的服务。"
                session_url = getattr(target_session, 'url', 'unknown_url')
                if not self.is_service_healthy(session_url): logger.warning(...); return f"错误：执行工具 '{function_name}' 所需的服务当前不可用。"
                logger.info(f"Executing tool '{function_name}' via session {session_url}")
                try:
                    result = await target_session.call_tool(function_name, function_args)
                    # (Process result...)
                    if result.content and isinstance(result.content, list) and hasattr(result.content[0], 'text'): return result.content[0].text
                    else: logger.warning(...); return f"信息：工具 '{function_name}' 执行完毕，但结果格式非预期。"
                except Exception as e: logger.error(...); return f"错误：调用工具 '{function_name}' 时发生内部错误。"
            # (Handle direct response - code omitted for brevity)
            else: logger.info(...); return message.content.strip() if message.content else ""

        except TypeError as e:
             # Catch the specific TypeError seen before
             logger.error(f"TypeError during LLM call: {e}. Check SDK arguments for model '{model_name}'.", exc_info=True)
             return f"错误：调用语言模型时发生类型错误，请检查 SDK 参数。({e})"
        except Exception as e:
            logger.error(f"Error during LLM interaction or tool processing: {e}", exc_info=True)
            return f"错误：处理您的请求时发生意外错误。({type(e).__name__}: {e})"


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
