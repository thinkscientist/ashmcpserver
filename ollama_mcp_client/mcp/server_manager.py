"""MCP server lifecycle and management."""

import subprocess
import sys
import importlib.util
from typing import Dict, Any
from .config import ConfigManager


class ServerManager:
    """Handles MCP server lifecycle and management."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.servers = {}
    
    async def initialize_servers(self):
        """Initialize all configured servers."""
        servers_config = self.config_manager.get_servers_config()
        
        for server_name, server_config in servers_config.items():
            await self._initialize_server(server_name, server_config)
    
    async def _initialize_server(self, server_name: str, server_config: Dict[str, Any]):
        """Initialize a single server based on its type."""
        # Skip disabled servers
        if not server_config.get("enabled", True):
            print(f"⏭️ Skipping disabled server: {server_name}")
            return
            
        server_type = server_config.get("type")
        
        if server_type == "subprocess":
            try:
                # Build subprocess command
                command = server_config.get("command", "")
                args = server_config.get("args", [])
                
                if isinstance(command, str):
                    full_command = [command] + args
                else:
                    full_command = command
                
                # Get additional options
                cwd = server_config.get("cwd", None)
                env = server_config.get("env", None)
                
                process = subprocess.Popen(
                    full_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=0,
                    cwd=cwd,
                    env=env
                )
                
                self.servers[server_name] = {
                    "type": "subprocess",
                    "process": process,
                    "config": server_config
                }
                print(f"✅ Initialized subprocess server: {server_name}")
                
            except Exception as e:
                print(f"❌ Failed to initialize subprocess server '{server_name}': {e}")
                
        elif server_type == "local":
            try:
                # Import local module
                module_path = server_config.get("module_path")
                if module_path and importlib.util.find_spec(module_path):
                    module = importlib.import_module(module_path)
                    self.servers[server_name] = {
                        "type": "local", 
                        "module": module,
                        "config": server_config
                    }
                    print(f"✅ Initialized local server: {server_name}")
                else:
                    print(f"❌ Local module '{module_path}' not found for server '{server_name}'")
                    
            except Exception as e:
                print(f"❌ Failed to initialize local server '{server_name}': {e}")
                
        elif server_type == "remote":
            # Remote servers are initialized on-demand
            self.servers[server_name] = {
                "type": "remote",
                "config": server_config
            }
            print(f"✅ Configured remote server: {server_name}")
        else:
            print(f"⚠️ Unknown server type '{server_type}' for server '{server_name}'")
    
    def get_servers(self) -> Dict[str, Any]:
        """Get all initialized servers."""
        return self.servers
    
    def get_server(self, server_name: str) -> Dict[str, Any]:
        """Get a specific server by name."""
        return self.servers.get(server_name, {})
    
    def list_servers(self) -> Dict[str, Any]:
        """Get summary information about all servers."""
        result = {}
        for server_name, server_info in self.servers.items():
            result[server_name] = {
                "type": server_info.get("type", "unknown"),
                "description": server_info.get("config", {}).get("description", "No description"),
                "tools_count": 0  # This will be updated by ToolDiscovery
            }
        return result