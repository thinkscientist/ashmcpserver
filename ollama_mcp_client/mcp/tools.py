"""MCP Tools facade - orchestrates all MCP components."""

from typing import Dict, List
from .config import ConfigManager
from .server_manager import ServerManager
from .tool_discovery import ToolDiscovery
from .tool_executor import ToolExecutor


class MCPTools:
    """Facade for MCP server communication - orchestrates all components."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_manager = ConfigManager(config_path)
        self.server_manager = ServerManager(self.config_manager)
        self.tool_discovery = ToolDiscovery(self.server_manager)
        self.tool_executor = ToolExecutor(self.server_manager)
        self.available_tools = []
    
    async def initialize_servers(self):
        """Initialize all servers and discover tools."""
        await self.server_manager.initialize_servers()
        self.available_tools = await self.tool_discovery.discover_all_tools()
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> str:
        """Call a tool by name with the given arguments."""
        # Find the tool by name
        tool_info = None
        for tool in self.available_tools:
            if tool.get("name") == tool_name:
                tool_info = tool
                break
        
        if not tool_info:
            return f"❌ Tool '{tool_name}' not found"
        
        return await self.tool_executor.call_tool(tool_info, arguments)
    
    def get_tools_description(self) -> str:
        """Get a formatted description of all available tools."""
        if not self.available_tools:
            return "No MCP tools available."
        
        # Group tools by server
        servers_tools = {}
        for tool in self.available_tools:
            server_name = tool.get("server_name", "unknown")
            if server_name not in servers_tools:
                servers_tools[server_name] = []
            servers_tools[server_name].append(tool)
        
        tools_desc = "You have access to these MCP tools:\n\n"
        
        for server_name, tools in servers_tools.items():
            server_info = self.server_manager.get_server(server_name)
            server_config = server_info.get("config", {})
            server_desc = server_config.get("description", f"{server_name} server")
            
            tools_desc += f"📡 {server_desc}:\n"
            
            for tool in tools:
                tool_name = tool.get("name", "unknown")
                tool_desc = tool.get("description", "No description")
                tools_desc += f"  - {tool_name}: {tool_desc}\n"
                
                # Add parameter information
                params = []
                parameters = tool.get("parameters", {})
                for param_name, param_info in parameters.items():
                    param_type = param_info.get("type", "string") 
                    required = " (required)" if param_info.get('required', False) else ""
                    params.append(f"{param_name} ({param_type}){required}")
                if params:
                    tools_desc += f"    Parameters: {', '.join(params)}\n"
        
        tools_desc += "\n\nTo use a tool, include: [TOOL:tool_name:{\"param\":\"value\"}]"
        return tools_desc
    
    def list_servers(self) -> dict:
        """Get information about configured servers."""
        servers_info = self.server_manager.list_servers()
        
        # Add tool counts
        for server_name in servers_info:
            tool_count = len([t for t in self.available_tools if t.get("server_name") == server_name])
            servers_info[server_name]["tools_count"] = tool_count
        
        return servers_info
    
    @property
    def servers(self) -> Dict:
        """Get all initialized servers (for backward compatibility)."""
        return self.server_manager.get_servers()