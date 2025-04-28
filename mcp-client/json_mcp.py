import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MCPConfig:
    """Handle loading, parsing and saving of mcp.json file, compatible with Cursor official format"""
    
    def __init__(self, json_path: str = None):
        """Initialize MCP configuration handler
        
        Args:
            json_path: Path to mcp.json file, if None, default path will be used
        """
        self.json_path = json_path or os.path.join(os.path.dirname(__file__), "mcp.json")
        logger.info(f"MCP configuration initialized, using file path: {self.json_path}")
    
    def load_config(self) -> Dict[str, Any]:
        """Load complete configuration from mcp.json file
        
        Returns:
            MCP configuration dictionary
        """
        if not os.path.exists(self.json_path):
            logger.warning(f"mcp.json file does not exist: {self.json_path}, will create empty file")
            self.save_config({"mcpServers": {}})
            return {"mcpServers": {}}
        
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Configuration loaded from mcp.json")
                return data
        except json.JSONDecodeError:
            logger.error(f"Failed to parse mcp.json file: {self.json_path}")
            return {"mcpServers": {}}
        except Exception as e:
            logger.error(f"Error reading mcp.json file: {e}")
            return {"mcpServers": {}}
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to mcp.json file
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Whether the save was successful
        """
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"Configuration saved to {self.json_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving to mcp.json file: {e}")
            return False
    
    def load_services(self) -> List[Dict[str, Any]]:
        """Load service list (compatibility mode)
        
        Returns:
            Service configuration list [{"name": "service name", "url": "service URL", "env": {...}}]
        """
        config = self.load_config()
        servers = config.get("mcpServers", {})
        services = []
        
        # Convert mcpServers format to service list format
        for name, server_config in servers.items():
            service = {
                "name": name,
                "url": server_config.get("url", ""),
                "type": "sse"  # Default to SSE type
            }
            
            # Add environment variables
            if "env" in server_config:
                service["env"] = server_config["env"]
                
            # Verify service has URL
            if service["url"]:
                services.append(service)
        
        return services
    
    def add_service(self, service: Dict[str, Any]) -> bool:
        """Add a service to mcp.json file
        
        Args:
            service: Service configuration {"name": "service name", "url": "service URL", ...}
            
        Returns:
            Whether addition was successful
        """
        config = self.load_config()
        servers = config.get("mcpServers", {})
        
        service_name = service.get("name", "")
        service_url = service.get("url", "")
        
        if not service_name or not service_url:
            logger.error("Service missing name or URL")
            return False
            
        # Build service configuration
        server_config = {
            "url": service_url
        }
        
        # Add environment variables
        if "env" in service:
            server_config["env"] = service["env"]
            
        # Add to configuration
        servers[service_name] = server_config
        config["mcpServers"] = servers
        
        logger.info(f"Service added/updated: {service_name}")
        return self.save_config(config)
    
    def remove_service(self, name: str) -> bool:
        """Remove a service from mcp.json file
        
        Args:
            name: Service name
            
        Returns:
            Whether removal was successful
        """
        config = self.load_config()
        servers = config.get("mcpServers", {})
        
        if name in servers:
            del servers[name]
            config["mcpServers"] = servers
            logger.info(f"Service removed from mcp.json: {name}")
            return self.save_config(config)
        else:
            logger.warning(f"Service to remove not found: {name}")
            return False 
