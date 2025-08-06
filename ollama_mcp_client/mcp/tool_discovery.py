"""Tool discovery from different MCP server types."""

import json
import aiohttp
import inspect
from typing import List, Dict, Any
from .server_manager import ServerManager


class ToolDiscovery:
    """Handles tool discovery from different server types."""
    
    def __init__(self, server_manager: ServerManager):
        self.server_manager = server_manager
    
    async def discover_all_tools(self) -> List[dict]:
        """Discover tools from all configured servers."""
        all_tools = []
        servers = self.server_manager.get_servers()
        
        for server_name, server_info in servers.items():
            try:
                tools = await self._discover_server_tools(server_name, server_info)
                all_tools.extend(tools)
                print(f"📋 Discovered {len(tools)} tools from server '{server_name}'")
            except Exception as e:
                print(f"❌ Error discovering tools from server '{server_name}': {e}")
        
        return all_tools
    
    async def _discover_server_tools(self, server_name: str, server_info: dict) -> list:
        """Discover tools from a specific server."""
        server_type = server_info.get("type")
        
        if server_type == "local":
            return await self._discover_local_tools(server_info)
        elif server_type == "remote":
            return await self._discover_remote_tools(server_info)
        elif server_type == "subprocess":
            return await self._discover_subprocess_tools(server_info)
        else:
            print(f"⚠️ Unknown server type: {server_type}")
            return []
    
    async def _discover_local_tools(self, server_info: dict) -> list:
        """Discover tools from a local Python module."""
        tools = []
        module = server_info.get("module")
        if not module:
            return tools
        
        # Look for functions decorated with @tool or similar
        for name in dir(module):
            obj = getattr(module, name)
            if callable(obj) and not name.startswith('_'):
                # Extract tool information
                tool_info = {
                    "name": f"local_server_{name}",
                    "server_name": "local_server", 
                    "function": obj,
                    "description": getattr(obj, '__doc__', f"Execute {name}"),
                    "parameters": self._extract_tool_parameters(obj)
                }
                tools.append(tool_info)
        
        return tools
    
    async def _discover_remote_tools(self, server_info: dict) -> list:
        """Discover tools from a remote MCP server."""
        tools = []
        config = server_info.get("config", {})
        base_url = config.get("url", "")
        
        if not base_url:
            return tools
        
        try:
            async with aiohttp.ClientSession() as session:
                # Assuming the remote server has a /tools endpoint
                async with session.get(f"{base_url}/tools") as response:
                    if response.status == 200:
                        tools_data = await response.json()
                        for tool_data in tools_data.get("tools", []):
                            tool_info = {
                                "name": f"remote_server_{tool_data.get('name', 'unknown')}",
                                "server_name": "remote_server",
                                "description": tool_data.get("description", "Remote tool"),
                                "parameters": tool_data.get("parameters", {}),
                                "url": base_url
                            }
                            tools.append(tool_info)
        except Exception as e:
            print(f"❌ Error discovering remote tools: {e}")
        
        return tools
    
    async def _discover_subprocess_tools(self, server_info: dict) -> list:
        """Discover tools from a subprocess MCP server."""
        tools = []
        process = server_info.get("process")
        if not process:
            return tools
        
        try:
            # Step 1: Send initialize request
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ollama-mcp-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            process.stdin.write(json.dumps(initialize_request) + "\n")
            process.stdin.flush()
            
            # Read initialize response
            response_line = process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                if "result" in response:
                    # Step 2: Send initialized notification
                    initialized_notification = {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {}
                    }
                    
                    process.stdin.write(json.dumps(initialized_notification) + "\n")
                    process.stdin.flush()
                    
                    # Small delay for server to process
                    import asyncio
                    await asyncio.sleep(0.1)
                    
                    # Step 3: Send tools/list request
                    tools_request = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {}
                    }
                    
                    process.stdin.write(json.dumps(tools_request) + "\n")
                    process.stdin.flush()
                    
                    # Read tools response
                    tools_response_line = process.stdout.readline()
                    if tools_response_line:
                        tools_response = json.loads(tools_response_line.strip())
                        
                        if "result" in tools_response and "tools" in tools_response["result"]:
                            for tool_data in tools_response["result"]["tools"]:
                                tool_info = {
                                    "name": f"local_server_{tool_data.get('name', 'unknown')}",
                                    "server_name": "local_server",
                                    "description": tool_data.get("description", "Tool description"),
                                    "parameters": tool_data.get("inputSchema", {}).get("properties", {}),
                                    "process": process
                                }
                                tools.append(tool_info)
        except Exception as e:
            print(f"❌ Error discovering subprocess tools: {e}")
        
        return tools
    
    def _extract_tool_parameters(self, tool_obj) -> dict:
        """Extract parameter information from a function."""
        try:
            sig = inspect.signature(tool_obj)
            parameters = {}
            
            for param_name, param in sig.parameters.items():
                param_info = {
                    "type": "string",  # Default type
                    "required": param.default == inspect.Parameter.empty
                }
                
                # Try to infer type from annotation
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_info["type"] = "integer"
                    elif param.annotation == float:
                        param_info["type"] = "number" 
                    elif param.annotation == bool:
                        param_info["type"] = "boolean"
                    # Add more type mappings as needed
                
                parameters[param_name] = param_info
            
            return parameters
        except Exception:
            return {}