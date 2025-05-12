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

class MCPConfigAPI:
    """API helper for MCPConfig, providing methods for API endpoints"""
    
    def __init__(self, config_path=None):
        """Initialize API helper with MCPConfig instance
        
        Args:
            config_path: Optional path to mcp.json file
        """
        self.mcp_config = MCPConfig(config_path)
    
    def get_config(self) -> Dict[str, Any]:
        """Get complete configuration for API response
        
        Returns:
            MCP configuration dictionary
        """
        return self.mcp_config.load_config()
    
    async def update_config(self, config_data: Dict[str, Any], orchestrator=None) -> Dict[str, str]:
        """Update configuration from API request and optionally synchronize services
        
        Args:
            config_data: New configuration data
            orchestrator: Optional MCP orchestrator instance to synchronize services
                
        Returns:
            Response dictionary with status and message
        """
        try:
            # Since pydantic models have dict() method for conversion to dictionary, we also accept dictionary types here
            config_dict = config_data
            if hasattr(config_data, 'dict') and callable(getattr(config_data, 'dict')):
                config_dict = config_data.dict()
            
            # Get old configuration for comparison before saving
            old_config = self.mcp_config.load_config()
            old_servers = old_config.get("mcpServers", {})
            
            # Save new configuration
            success = self.mcp_config.save_config(config_dict)
            if not success:
                return {"status": "error", "message": "Configuration update failed"}
            
            # If no orchestrator provided, just update the config file
            if orchestrator is None:
                return {"status": "success", "message": "Configuration updated successfully"}
            
            # If orchestrator provided, synchronize services
            new_servers = config_dict.get("mcpServers", {})
            
            # Build service sets for comparison
            old_services = {url: name for name, config in old_servers.items() 
                          for url in [config.get("url")] if url}
            new_services = {url: name for name, config in new_servers.items() 
                          for url in [config.get("url")] if url}
            
            # Find services to add
            services_to_add = set(new_services.keys()) - set(old_services.keys())
            # Find services to remove
            services_to_remove = set(old_services.keys()) - set(new_services.keys())
            
            # Build synchronization results
            sync_results = []
            
            # Register newly added services
            for service_url in services_to_add:
                service_name = new_services[service_url]
                success, message = await orchestrator.connect_service(service_url, service_name)
                sync_results.append({
                    "action": "add",
                    "name": service_name,
                    "url": service_url,
                    "success": success,
                    "message": message
                })
                
                # If connection fails, add to auto-reconnect list
                if not success:
                    logger.info(f"Adding service {service_name} ({service_url}) to auto-reconnect list.")
                    orchestrator.pending_reconnection.add(service_url)
            
            # Remove deleted services
            for service_url in services_to_remove:
                service_name = old_services[service_url]
                try:
                    # Disconnect service by calling disconnect_service method
                    await orchestrator.disconnect_service(service_url)
                    sync_results.append({
                        "action": "remove",
                        "name": service_name,
                        "url": service_url,
                        "success": True,
                        "message": "Service disconnected"
                    })
                except Exception as e:
                    logger.error(f"Failed to disconnect service {service_name} ({service_url}): {e}")
                    sync_results.append({
                        "action": "remove",
                        "name": service_name,
                        "url": service_url,
                        "success": False,
                        "message": f"Failed to disconnect service: {str(e)}"
                    })
            
            # Build final result
            added_count = len([r for r in sync_results if r["action"] == "add" and r["success"]])
            removed_count = len([r for r in sync_results if r["action"] == "remove" and r["success"]])
            
            return {
                "status": "success",
                "message": f"Configuration updated successfully, services synchronized: {added_count} added, {removed_count} removed",
                "sync_results": sync_results
            }
        except Exception as e:
            logger.error(f"Error updating mcp.json configuration: {e}")
            return {"status": "error", "message": f"Failed to update mcp.json configuration: {str(e)}"}
    
    async def register_services(self, orchestrator) -> Dict[str, Any]:
        """Register all services from mcp.json with orchestrator
        
        Args:
            orchestrator: MCP orchestrator instance
            
        Returns:
            Response dictionary with status, message and results
        """
        try:
            services = self.mcp_config.load_services()
            
            results = []
            for service in services:
                service_name = service.get("name", "")
                service_url = service.get("url", "")
                
                if service_url:
                    success, message = await orchestrator.connect_service(service_url, service_name)
                    results.append({
                        "name": service_name or service_url,
                        "url": service_url,
                        "success": success,
                        "message": message
                    })
                    
                    # If connection fails, add to auto-reconnect list
                    if not success:
                        logger.info(f"Adding service {service_name} ({service_url}) to auto-reconnect list.")
                        orchestrator.pending_reconnection.add(service_url)
            
            return {
                "status": "success",
                "message": f"Processed {len(services)} services",
                "results": results
            }
        except Exception as e:
            logger.error(f"Error registering mcp.json services: {e}")
            return {"status": "error", "message": f"Failed to register mcp.json services: {str(e)}"} 
