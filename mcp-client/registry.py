import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Set
from mcp import ClientSession

logger = logging.getLogger(__name__)

class ServiceRegistry:
    """Manages the state of connected services and their tools."""
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}  # server_url -> session
        self.service_health: Dict[str, datetime] = {} # server_url -> last_heartbeat_time
        self.tool_cache: Dict[str, Dict[str, Any]] = {} # tool_name -> tool_definition
        self.tool_to_session_map: Dict[str, ClientSession] = {} # tool_name -> session
        logger.info("ServiceRegistry initialized.")

    def add_service(self, url: str, session: ClientSession, tools: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
        """Adds a new service, its session, and tools to the registry. Returns added tool names."""
        if url in self.sessions:
            logger.warning(f"Attempting to add already registered service: {url}. Overwriting.")

        self.sessions[url] = session
        self.service_health[url] = datetime.now() # Mark healthy on add

        added_tool_names = []
        for tool_name, tool_definition in tools:
             if tool_name in self.tool_cache:
                 logger.warning(f"Tool name conflict: '{tool_name}' from {url} conflicts with existing tool. Skipping this tool.")
                 continue
             self.tool_cache[tool_name] = tool_definition
             self.tool_to_session_map[tool_name] = session
             added_tool_names.append(tool_name)
        logger.info(f"Service '{url}' added with tools: {added_tool_names}")
        return added_tool_names

    def remove_service(self, url: str) -> Optional[ClientSession]:
        """Removes a service and its associated tools from the registry."""
        session = self.sessions.pop(url, None) # Use pop with default None
        if not session:
            logger.warning(f"Attempted to remove non-existent service: {url}")
            return None

        # Remove health record
        if url in self.service_health:
            del self.service_health[url]

        # Remove associated tools efficiently
        tools_to_remove = [name for name, owner_session in self.tool_to_session_map.items() if owner_session == session]
        if tools_to_remove:
            logger.info(f"Removing tools from registry associated with {url}: {tools_to_remove}")
            for tool_name in tools_to_remove:
                # Check existence before deleting, although keys should be consistent
                if tool_name in self.tool_cache: del self.tool_cache[tool_name]
                if tool_name in self.tool_to_session_map: del self.tool_to_session_map[tool_name]

        logger.info(f"Service '{url}' removed from registry.")
        return session

    def get_session(self, url: str) -> Optional[ClientSession]:
        return self.sessions.get(url)

    def get_session_for_tool(self, tool_name: str) -> Optional[ClientSession]:
        return self.tool_to_session_map.get(tool_name)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return list(self.tool_cache.values())

    def get_all_service_urls(self) -> List[str]:
        # Get URLs only for currently active sessions
        return list(self.sessions.keys())

    def update_service_health(self, url: str):
        """Updates the last heartbeat time for a service."""
        if url in self.sessions: # Only update health for active sessions
            self.service_health[url] = datetime.now()
            logger.debug(f"Health updated for service: {url}")

    def get_last_heartbeat(self, url: str) -> Optional[datetime]:
        return self.service_health.get(url)

    def get_registered_services_details(self) -> List[Dict[str, Any]]:
         """Returns details for the /health endpoint."""
         details = []
         # Iterate through active sessions
         for url in self.get_all_service_urls():
             last_heartbeat = self.service_health.get(url)
             details.append({
                 "url": url,
                 "last_heartbeat": str(last_heartbeat) if last_heartbeat else "N/A",
             })
         return details

    def get_tool_count(self) -> int:
         return len(self.tool_cache)

    def get_session_count(self) -> int:
         return len(self.sessions)