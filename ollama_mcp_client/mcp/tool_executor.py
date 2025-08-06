"""Tool execution for different MCP server types."""

import json
import aiohttp
from typing import Dict, Any
from .server_manager import ServerManager


class ToolExecutor:
    """Handles tool execution and calling."""
    
    def __init__(self, server_manager: ServerManager):
        self.server_manager = server_manager
    
    async def call_tool(self, tool_info: dict, arguments: dict) -> str:
        """Execute a tool with the given arguments."""
        server_name = tool_info.get("server_name", "")
        server_info = self.server_manager.get_server(server_name)
        
        if not server_info:
            return f"❌ Server '{server_name}' not found"
        
        server_type = server_info.get("type")
        
        try:
            if server_type == "local":
                return await self._call_local_tool(tool_info, arguments)
            elif server_type == "remote":
                return await self._call_remote_tool(tool_info, arguments, server_info)
            elif server_type == "subprocess":
                return await self._call_subprocess_tool(tool_info, arguments, server_info)
            else:
                return f"❌ Unknown server type: {server_type}"
        except Exception as e:
            return f"❌ Error calling tool '{tool_info.get('name', 'unknown')}': {e}"
    
    async def _call_local_tool(self, tool_info: dict, arguments: dict) -> str:
        """Call a tool from a local Python module."""
        function = tool_info.get("function")
        if not function:
            return "❌ No function found for local tool"
        
        try:
            result = function(**arguments)
            return str(result)
        except Exception as e:
            return f"❌ Error executing local tool: {e}"
    
    async def _call_remote_tool(self, tool_info: dict, arguments: dict, server_info: dict) -> str:
        """Call a tool from a remote MCP server."""
        config = server_info.get("config", {})
        base_url = config.get("url", "")
        tool_name = tool_info.get("name", "").replace("remote_server_", "")
        
        if not base_url:
            return "❌ No URL configured for remote server"
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "tool": tool_name,
                    "arguments": arguments
                }
                async with session.post(f"{base_url}/execute", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", "No result")
                    else:
                        return f"❌ Remote tool call failed with status {response.status}"
        except Exception as e:
            return f"❌ Error calling remote tool: {e}"
    
    async def _call_subprocess_tool(self, tool_info: dict, arguments: dict, server_info: dict) -> str:
        """Call a tool from a subprocess MCP server."""
        process = server_info.get("process")
        if not process:
            return "❌ No process found for subprocess server"
        
        # Extract actual tool name (remove server prefix)
        tool_name = tool_info.get("name", "").replace("local_server_", "")
        
        try:
            # Send tool call request via JSON-RPC
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                
                if "result" in response:
                    content = response["result"].get("content", [])
                    if content and len(content) > 0:
                        return content[0].get("text", "No result")
                    else:
                        return "No content in result"
                elif "error" in response:
                    return f"❌ Tool error: {response['error'].get('message', 'Unknown error')}"
                else:
                    return "❌ Invalid response format"
            else:
                return "❌ No response from subprocess"
        except Exception as e:
            return f"❌ Error calling subprocess tool: {e}"