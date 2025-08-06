#!/usr/bin/env python3
"""
LLM client for chatting with Ollama models with MCP server integration.
"""

import aiohttp
import asyncio
import json
import sys
import subprocess
import os
import threading
import time
from typing import Optional, Dict, Any, List

# ==================== UTILITIES ====================

class LoadingIndicator:
    """Shows a loading animation while waiting for responses."""
    
    def __init__(self, message="🤖 Assistant: "):
        self.message = message
        self.chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the loading animation."""
        if self.running:
            return
        self.running = True
        print(self.message, end="", flush=True)
        self.thread = threading.Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop the loading animation and clear the line."""
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.1)
        # Clear the loading indicator
        print("\r" + " " * (len(self.message) + 2) + "\r", end="", flush=True)
        print(self.message, end="", flush=True)
    
    def _animate(self):
        """Run the loading animation."""
        i = 0
        while self.running:
            print(f"\r{self.message}{self.chars[i % len(self.chars)]}", end="", flush=True)
            time.sleep(0.1)
            i += 1

# ==================== PHASE 2: REFACTORED COMPONENTS ====================

class ConfigManager:
    """Handles configuration loading and validation."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file {self.config_path} not found. Using default config.")
            return {
                "mcp_servers": {
                    "local_server": {
                        "type": "local",
                        "script_path": "server.py",
                        "description": "Default local MCP server"
                    }
                },
                "settings": {
                    "auto_discover_tools": True,
                    "tool_timeout": 30
                }
            }
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing config file: {e}")
            return {}
    
    def get_servers_config(self) -> dict:
        """Get server configurations."""
        return self.config.get("mcp_servers", {})
    
    def get_settings(self) -> dict:
        """Get general settings."""
        return self.config.get("settings", {})
    
    def get_server_config(self, server_name: str) -> Optional[dict]:
        """Get configuration for a specific server."""
        return self.get_servers_config().get(server_name)

class ServerManager:
    """Handles MCP server lifecycle and management."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.servers = {}
    
    async def initialize_servers(self):
        """Initialize all configured MCP servers."""
        servers_config = self.config_manager.get_servers_config()
        
        if not servers_config:
            print("⚠️  No MCP servers configured.")
            return
        
        for server_name, server_config in servers_config.items():
            if server_config.get("enabled", True):  # Default to enabled
                try:
                    await self._initialize_server(server_name, server_config)
                except Exception as e:
                    print(f"⚠️  Failed to initialize server '{server_name}': {e}")
    
    async def _initialize_server(self, name: str, config: dict):
        """Initialize a single MCP server."""
        server_type = config.get("type", "local")
        
        if server_type == "local":
            script_path = config.get("script_path", "server.py")
            self.servers[name] = {
                "type": "local",
                "config": config,
                "script_path": script_path
            }
            print(f"✅ Initialized local server: {name}")
            
        elif server_type == "remote":
            url = config.get("url")
            if url:
                self.servers[name] = {
                    "type": "remote", 
                    "config": config,
                    "url": url
                }
                print(f"✅ Initialized remote server: {name}")
            else:
                print(f"⚠️  Remote server '{name}' missing URL")
                
        elif server_type == "subprocess":
            command = config.get("command")
            args = config.get("args", [])
            if command:
                self.servers[name] = {
                    "type": "subprocess",
                    "config": config,
                    "command": command,
                    "args": args
                }
                print(f"✅ Initialized subprocess server: {name}")
            else:
                print(f"⚠️  Subprocess server '{name}' missing command")
    
    def get_servers(self) -> dict:
        """Get all initialized servers."""
        return self.servers
    
    def get_server(self, server_name: str) -> Optional[dict]:
        """Get a specific server."""
        return self.servers.get(server_name)
    
    def list_servers(self, tools_count_map: dict = None) -> dict:
        """Get information about configured servers."""
        tools_count_map = tools_count_map or {}
        return {
            name: {
                "type": info["type"],
                "description": info.get("config", {}).get("description", ""),
                "tools_count": tools_count_map.get(name, 0)
            }
            for name, info in self.servers.items()
        }

class ToolDiscovery:
    """Handles tool discovery from different server types."""
    
    def __init__(self, server_manager: ServerManager):
        self.server_manager = server_manager
    
    async def discover_all_tools(self) -> List[dict]:
        """Discover tools from all initialized servers."""
        all_tools = []
        
        for server_name, server_info in self.server_manager.get_servers().items():
            try:
                tools = await self._discover_server_tools(server_name, server_info)
                for tool in tools:
                    # Prefix tool names with server name to avoid conflicts
                    tool["server"] = server_name
                    tool["name"] = f"{server_name}_{tool['name']}"
                    all_tools.append(tool)
                    
                print(f"📋 Discovered {len(tools)} tools from server '{server_name}'")
                
            except Exception as e:
                print(f"⚠️  Error discovering tools from server '{server_name}': {e}")
        
        return all_tools
    
    async def _discover_server_tools(self, server_name: str, server_info: dict) -> list:
        """Discover tools from a specific server."""
        server_type = server_info["type"]
        
        if server_type == "local":
            return await self._discover_local_tools(server_info)
        elif server_type == "remote":
            return await self._discover_remote_tools(server_info)
        elif server_type == "subprocess":
            return await self._discover_subprocess_tools(server_info)
        else:
            return []
    
    async def _discover_local_tools(self, server_info: dict) -> list:
        """Discover tools from a local MCP server."""
        print(f"⚠️  Local tool discovery not yet implemented in new structure")
        return []
    
    async def _discover_remote_tools(self, server_info: dict) -> list:
        """Discover tools from a remote MCP server."""
        print(f"⚠️  Remote tool discovery not yet implemented")
        return []
    
    async def _discover_subprocess_tools(self, server_info: dict) -> list:
        """Discover tools from a subprocess MCP server."""
        try:
            command = server_info.get("command")
            args = server_info.get("args", [])
            cwd = server_info.get("cwd", ".")
            env = server_info.get("env", {})
            
            if not command:
                print(f"⚠️  No command specified for subprocess server")
                return []
            
            # Start the MCP server process
            full_env = dict(os.environ)
            full_env.update(env)
            
            # Create the subprocess
            process = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env
            )
            
            # Send initialize request to get tools
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
            
            request_json = json.dumps(initialize_request) + "\n"
            process.stdin.write(request_json.encode())
            await process.stdin.drain()
            
            # Read the response
            response_line = await process.stdout.readline()
            if response_line:
                try:
                    response = json.loads(response_line.decode().strip())
                    if "result" in response:
                        # Send initialized notification
                        initialized_notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {}
                        }
                        
                        notification_json = json.dumps(initialized_notification) + "\n"
                        process.stdin.write(notification_json.encode())
                        await process.stdin.drain()
                        
                        # Small delay to let server process notification
                        await asyncio.sleep(0.1)
                        
                        # Server initialized, now get tools
                        tools_request = {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/list",
                            "params": {}
                        }
                        
                        request_json = json.dumps(tools_request) + "\n"
                        process.stdin.write(request_json.encode())
                        await process.stdin.drain()
                        
                        # Read tools response
                        tools_response_line = await process.stdout.readline()
                        if tools_response_line:
                            tools_response = json.loads(tools_response_line.decode().strip())
                            if "result" in tools_response and "tools" in tools_response["result"]:
                                tools = []
                                for tool_data in tools_response["result"]["tools"]:
                                    tool_info = {
                                        "name": tool_data.get("name", ""),
                                        "description": tool_data.get("description", ""),
                                        "parameters": tool_data.get("inputSchema", {}).get("properties", {}),
                                        "subprocess_info": server_info,  # Store for later calling
                                        "tool_schema": tool_data  # Store original schema
                                    }
                                    tools.append(tool_info)
                                
                                # Terminate the process
                                process.stdin.close()
                                await process.wait()
                                
                                return tools
                except json.JSONDecodeError as e:
                    print(f"⚠️  Error parsing MCP server response: {e}")
            
            # Clean up process
            process.stdin.close()
            await process.wait()
            return []
            
        except Exception as e:
            print(f"⚠️  Error discovering subprocess tools: {e}")
            return []

# ==================== PHASE 3: LLM CLIENT ARCHITECTURE ====================

from abc import ABC, abstractmethod

class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    async def list_models(self) -> list:
        """List available models."""
        pass
    
    @abstractmethod 
    async def chat(self, model: str, message: str, system_prompt: Optional[str] = None, tools: Optional[list] = None) -> Optional[dict]:
        """Send a chat message and get response."""
        pass
    
    @abstractmethod
    async def chat_stream(self, model: str, message: str, system_prompt: Optional[str] = None, tools: Optional[list] = None):
        """Send a chat message and get streaming response."""
        pass

class OllamaHTTPClient(LLMClient):
    """Pure HTTP client for Ollama API without tool integration."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def list_models(self) -> list:
        """List all available models."""
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                response.raise_for_status()
                data = await response.json()
                return [model['name'] for model in data.get('models', [])]
        except aiohttp.ClientError as e:
            print(f"Error connecting to Ollama server: {e}")
            return []
        except json.JSONDecodeError:
            print("Error parsing response from Ollama server")
            return []
    
    async def chat(self, model: str, message: str, system_prompt: Optional[str] = None, tools: Optional[list] = None) -> Optional[dict]:
        """Send a chat message and get response."""
        try:
            payload = {
                "model": model,
                "messages": [],
                "stream": False
            }
            
            if system_prompt:
                payload["messages"].append({"role": "system", "content": system_prompt})
            
            payload["messages"].append({"role": "user", "content": message})
            
            if tools:
                payload["tools"] = tools
            
            async with self.session.post(f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientError as e:
            print(f"Error communicating with Ollama: {e}")
            return None
        except json.JSONDecodeError:
            print("Error parsing response from Ollama")
            return None
    
    async def chat_stream(self, model: str, message: str, system_prompt: Optional[str] = None, tools: Optional[list] = None):
        """Send a chat message and get streaming response."""
        try:
            payload = {
                "model": model, 
                "messages": [],
                "stream": True
            }
            
            if system_prompt:
                payload["messages"].append({"role": "system", "content": system_prompt})
            
            payload["messages"].append({"role": "user", "content": message})
            
            if tools:
                payload["tools"] = tools
            
            async with self.session.post(f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line.decode().strip())
                            yield chunk
                        except json.JSONDecodeError:
                            continue
                            
        except aiohttp.ClientError as e:
            print(f"Error communicating with Ollama: {e}")
            return
        except Exception as e:
            print(f"Unexpected error during streaming: {e}")
            return

class ToolIntegratedLLMClient:
    """Handles tool integration with any LLM client."""
    
    def __init__(self, llm_client: LLMClient, mcp_tools: "MCPTools" = None):
        self.llm_client = llm_client
        self.mcp_tools = mcp_tools
    
    def set_mcp_tools(self, mcp_tools: "MCPTools"):
        """Set the MCP tools client."""
        self.mcp_tools = mcp_tools
    
    async def chat(self, model: str, message: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Send a chat message with tool integration."""
        # Build system prompt with tools if available
        full_system_prompt = system_prompt or ""
        if self.mcp_tools:
            tools_desc = self.mcp_tools.get_tools_description()
            full_system_prompt = f"{full_system_prompt}\n\n{tools_desc}".strip()
        
        # Get response from LLM
        response = await self.llm_client.chat(model, message, full_system_prompt)
        if not response:
            return None
        
        # Process tool calls if present
        return await self._process_response_with_tools(response)
    
    async def chat_stream(self, model: str, message: str, system_prompt: Optional[str] = None):
        """Send a chat message with tool integration and streaming."""
        # For streaming mode, use a hybrid approach due to model compatibility issues
        if self.mcp_tools:
            # Try streaming first, but if it fails fall back to non-streaming
            full_system_prompt = system_prompt or ""
            tools_desc = self.mcp_tools.get_tools_description()
            full_system_prompt = f"{full_system_prompt}\n\n{tools_desc}".strip()
            
            # Test if the model can handle tool descriptions in streaming mode
            accumulated_text = ""
            content_received = False
            
            try:
                async for chunk in self.llm_client.chat_stream(model, message, full_system_prompt):
                    if chunk.get("done", False):
                        # If we got no content, the model can't handle tools in streaming mode
                        if not content_received:
                            # Fall back to non-streaming mode with tools
                            response = await self.chat(model, message, system_prompt)
                            if response:
                                yield {"message": {"content": response}, "done": False}
                        yield chunk
                        return
                    
                    # Handle content streaming
                    message_data = chunk.get("message", {})
                    if "content" in message_data:
                        content = message_data["content"]
                        if content:
                            content_received = True
                            accumulated_text += content
                            yield chunk
                    else:
                        yield chunk
                        
            except Exception as e:
                # If streaming fails, fall back to non-streaming
                response = await self.chat(model, message, system_prompt)
                if response:
                    yield {"message": {"content": response}, "done": False}
                yield {"done": True}
        else:
            # No tools, just stream normally
            async for chunk in self.llm_client.chat_stream(model, message, system_prompt):
                yield chunk
    
    async def _process_response_with_tools(self, response: dict) -> Optional[str]:
        """Process LLM response and execute any tool calls."""
        message = response.get("message", {})
        content = message.get("content", "")
        
        # Handle Ollama native tool calls
        if "tool_calls" in message:
            tool_calls = message["tool_calls"]
            if tool_calls:
                tool_results = await self._execute_tool_calls(tool_calls)
                return self._format_tool_results(tool_results)
        
        # Handle custom tool call format [TOOL:name:args]
        processed_content = await self._process_tool_calls_async(content)
        return processed_content
    
    async def _execute_tool_calls(self, tool_calls: list, debug: bool = False) -> list:
        """Execute a list of tool calls."""
        if not self.mcp_tools:
            return [{"error": "No MCP tools available"}]
        
        results = []
        for tool_call in tool_calls:
            try:
                # Handle both Ollama native format and our custom format
                if isinstance(tool_call, dict):
                    if "function" in tool_call:
                        # Ollama native format
                        func_info = tool_call["function"]
                        tool_name = func_info.get("name", "").replace("tool.", "")
                        arguments = func_info.get("arguments", {})
                    else:
                        # Custom format
                        tool_name = tool_call.get("name", "")
                        arguments = tool_call.get("arguments", {})
                else:
                    # Fallback
                    continue
                
                if debug:
                    print(f"🔧 Executing tool: {tool_name} with args: {arguments}")
                
                result = await self.mcp_tools.call_tool(tool_name, arguments)
                results.append({"tool": tool_name, "result": result})
                
            except Exception as e:
                error_msg = f"Error executing tool {tool_call}: {e}"
                if debug:
                    print(f"❌ {error_msg}")
                results.append({"tool": str(tool_call), "error": error_msg})
        
        return results
    
    def _format_tool_results(self, results: list, for_streaming: bool = False) -> str:
        """Format tool execution results for display."""
        if not results:
            return ""
        
        formatted_results = []
        for result in results:
            if "error" in result:
                formatted_results.append(f"❌ Error: {result['error']}")
            else:
                tool_name = result.get("tool", "unknown")
                tool_result = result.get("result", "")
                formatted_results.append(f"🔧 {tool_name}: {tool_result}")
        
        result_text = "\n".join(formatted_results)
        
        if for_streaming:
            return f"\n\n{result_text}"
        else:
            return result_text
    
    async def _process_tool_calls_async(self, text: str) -> str:
        """Process custom tool call format [TOOL:name:args] in text with proper async execution."""
        import re
        
        # Pattern to match [TOOL:name:args]
        pattern = r'\[TOOL:([^:]+):([^\]]*)\]'
        matches = re.findall(pattern, text)
        
        if not matches:
            return text
        
        # Process each tool call found
        result_text = text
        for tool_name, args_str in matches:
            try:
                arguments = json.loads(args_str) if args_str.strip() else {}
                if self.mcp_tools:
                    tool_result = await self.mcp_tools.call_tool(tool_name, arguments)
                    replacement = f"🔧 {tool_name}: {tool_result}"
                else:
                    replacement = f"❌ No MCP tools available for {tool_name}"
                    
                # Replace the tool call with the result
                tool_call_pattern = f"\\[TOOL:{re.escape(tool_name)}:{re.escape(args_str)}\\]"
                result_text = re.sub(tool_call_pattern, replacement, result_text)
                
            except Exception as e:
                replacement = f"❌ Error calling {tool_name}: {e}"
                tool_call_pattern = f"\\[TOOL:{re.escape(tool_name)}:{re.escape(args_str)}\\]"
                result_text = re.sub(tool_call_pattern, replacement, result_text)
        
        return result_text
    
    def _process_tool_calls(self, text: str) -> str:
        """Sync version for streaming - just returns text as-is."""
        return text

# ==================== ORIGINAL IMPLEMENTATION (TO BE REPLACED) ====================

class MCPTools:
    """Facade for MCP server communication - orchestrates all components."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize MCP tools with all components."""
        # New refactored components
        self.config_manager = ConfigManager(config_path)
        self.server_manager = ServerManager(self.config_manager)
        self.tool_discovery = ToolDiscovery(self.server_manager)
        
        # Keep original interface
        self.available_tools = []
        self.config_path = config_path
        self.config = self.config_manager.config
        self.servers = {}
        
    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file {self.config_path} not found. Using default config.")
            return {
                "mcp_servers": {
                    "local_server": {
                        "type": "local",
                        "script_path": "server.py",
                        "description": "Default local MCP server"
                    }
                },
                "settings": {
                    "auto_discover_tools": True,
                    "tool_timeout": 30
                }
            }
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing config file: {e}")
            return {}
    
    # ==================== SERVER MANAGEMENT ====================
    
    async def initialize_servers(self):
        """Initialize all configured MCP servers."""
        # Use new components
        await self.server_manager.initialize_servers()
        self.available_tools = await self.tool_discovery.discover_all_tools()
        
        # Maintain backwards compatibility
        self.servers = self.server_manager.get_servers()
    
    async def _initialize_server(self, name: str, config: dict):
        """Initialize a single MCP server."""
        server_type = config.get("type", "local")
        
        if server_type == "local":
            # Local server - import the module
            script_path = config.get("script_path", "server.py")
            self.servers[name] = {
                "type": "local",
                "config": config,
                "script_path": script_path
            }
            print(f"✅ Initialized local server: {name}")
            
        elif server_type == "remote":
            # Remote server - HTTP connection
            url = config.get("url")
            if url:
                self.servers[name] = {
                    "type": "remote", 
                    "config": config,
                    "url": url
                }
                print(f"✅ Initialized remote server: {name}")
            else:
                print(f"⚠️  Remote server '{name}' missing URL")
                
        elif server_type == "subprocess":
            # Subprocess server - spawn process
            command = config.get("command")
            args = config.get("args", [])
            if command:
                self.servers[name] = {
                    "type": "subprocess",
                    "config": config,
                    "command": command,
                    "args": args
                }
                print(f"✅ Initialized subprocess server: {name}")
            else:
                print(f"⚠️  Subprocess server '{name}' missing command")
    
    # ==================== TOOL DISCOVERY ====================
    
    async def _discover_all_tools(self):
        """Discover tools from all initialized servers."""
        self.available_tools = []
        
        for server_name, server_info in self.servers.items():
            try:
                tools = await self._discover_server_tools(server_name, server_info)
                for tool in tools:
                    # Prefix tool names with server name to avoid conflicts
                    tool["server"] = server_name
                    tool["name"] = f"{server_name}_{tool['name']}"
                    self.available_tools.append(tool)
                    
                print(f"📋 Discovered {len(tools)} tools from server '{server_name}'")
                
            except Exception as e:
                print(f"⚠️  Error discovering tools from server '{server_name}': {e}")
    
    async def _discover_server_tools(self, server_name: str, server_info: dict) -> list:
        """Discover tools from a specific server."""
        server_type = server_info["type"]
        
        if server_type == "local":
            return await self._discover_local_tools(server_info)
        elif server_type == "remote":
            return await self._discover_remote_tools(server_info)
        elif server_type == "subprocess":
            return await self._discover_subprocess_tools(server_info)
        else:
            return []
    
    async def _discover_local_tools(self, server_info: dict) -> list:
        """Discover tools from a local MCP server."""
        try:
            script_path = server_info["script_path"]
            
            # Import the server module
            import sys
            import os
            import importlib.util
            
            # Add current directory to path if not already there
            current_dir = os.getcwd()
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            # Import the module
            module_name = script_path.replace('.py', '').replace('/', '.')
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the FastMCP instance
            if hasattr(module, 'mcp'):
                mcp_instance = module.mcp
                tools_dict = await mcp_instance.get_tools()
                
                tools = []
                for tool_name, tool_obj in tools_dict.items():
                    # Extract tool schema
                    tool_info = {
                        "name": tool_name,
                        "description": getattr(tool_obj, 'description', tool_name),
                        "parameters": self._extract_tool_parameters(tool_obj),
                        "tool_obj": tool_obj  # Store reference for calling
                    }
                    tools.append(tool_info)
                
                return tools
            else:
                print(f"⚠️  No 'mcp' instance found in {script_path}")
                return []
                
        except Exception as e:
            print(f"⚠️  Error discovering local tools: {e}")
            return []
    
    async def _discover_remote_tools(self, server_info: dict) -> list:
        """Discover tools from a remote MCP server."""
        # TODO: Implement remote tool discovery via HTTP
        print(f"⚠️  Remote tool discovery not yet implemented")
        return []
    
    async def _discover_subprocess_tools(self, server_info: dict) -> list:
        """Discover tools from a subprocess MCP server."""
        try:
            command = server_info.get("command")
            args = server_info.get("args", [])
            cwd = server_info.get("cwd", ".")
            env = server_info.get("env", {})
            
            if not command:
                print(f"⚠️  No command specified for subprocess server")
                return []
            
            # Start the MCP server process
            full_env = dict(os.environ)
            full_env.update(env)
            
            # Create the subprocess
            process = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env
            )
            
            # Send initialize request to get tools
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
            
            request_json = json.dumps(initialize_request) + "\n"
            process.stdin.write(request_json.encode())
            await process.stdin.drain()
            
            # Read the response
            response_line = await process.stdout.readline()
            if response_line:
                try:
                    response = json.loads(response_line.decode().strip())
                    if "result" in response:
                        # Send initialized notification
                        initialized_notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {}
                        }
                        
                        notification_json = json.dumps(initialized_notification) + "\n"
                        process.stdin.write(notification_json.encode())
                        await process.stdin.drain()
                        
                        # Small delay to let server process notification
                        await asyncio.sleep(0.1)
                        
                        # Server initialized, now get tools
                        tools_request = {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/list",
                            "params": {}
                        }
                        
                        request_json = json.dumps(tools_request) + "\n"
                        process.stdin.write(request_json.encode())
                        await process.stdin.drain()
                        
                        # Read tools response
                        tools_response_line = await process.stdout.readline()
                        if tools_response_line:
                            tools_response = json.loads(tools_response_line.decode().strip())
                            if "result" in tools_response and "tools" in tools_response["result"]:
                                tools = []
                                for tool_data in tools_response["result"]["tools"]:
                                    tool_info = {
                                        "name": tool_data.get("name", ""),
                                        "description": tool_data.get("description", ""),
                                        "parameters": tool_data.get("inputSchema", {}).get("properties", {}),
                                        "subprocess_info": server_info,  # Store for later calling
                                        "tool_schema": tool_data  # Store original schema
                                    }
                                    tools.append(tool_info)
                                
                                # Terminate the process
                                process.stdin.close()
                                await process.wait()
                                
                                return tools
                except json.JSONDecodeError as e:
                    print(f"⚠️  Error parsing MCP server response: {e}")
            
            # Clean up process
            process.stdin.close()
            await process.wait()
            return []
            
        except Exception as e:
            print(f"⚠️  Error discovering subprocess tools: {e}")
            return []
    
    def _extract_tool_parameters(self, tool_obj) -> dict:
        """Extract parameter schema from a tool object."""
        try:
            # Try to get schema from the tool object
            if hasattr(tool_obj, 'input_schema'):
                schema = tool_obj.input_schema
                if hasattr(schema, 'properties'):
                    return schema.properties
                elif isinstance(schema, dict):
                    return schema.get('properties', {})
            
            # Fallback to function inspection
            import inspect
            if hasattr(tool_obj, 'fn'):
                sig = inspect.signature(tool_obj.fn)
                params = {}
                for param_name, param in sig.parameters.items():
                    param_type = "string"
                    if param.annotation != inspect.Parameter.empty:
                        if param.annotation == int:
                            param_type = "integer"
                        elif param.annotation == float:
                            param_type = "number"
                        elif param.annotation == bool:
                            param_type = "boolean"
                    
                    params[param_name] = {
                        "type": param_type,
                        "description": f"{param_name} parameter",
                        "required": param.default == inspect.Parameter.empty
                    }
                return params
            
            return {}
            
        except Exception as e:
            print(f"⚠️  Error extracting tool parameters: {e}")
            return {}
    
    # ==================== TOOL EXECUTION ====================
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> str:
        """Call an MCP tool from any configured server."""
        try:
            # Find the tool in our available tools
            tool_info = None
            for tool in self.available_tools:
                if tool["name"] == tool_name:
                    tool_info = tool
                    break
            
            if not tool_info:
                return f"Tool '{tool_name}' not found in any configured server"
            
            server_name = tool_info["server"]
            server_info = self.servers.get(server_name)
            
            if not server_info:
                return f"Server '{server_name}' not found"
            
            # Call the tool based on server type
            if server_info["type"] == "local":
                return await self._call_local_tool(tool_info, arguments)
            elif server_info["type"] == "remote":
                return await self._call_remote_tool(tool_info, arguments, server_info)
            elif server_info["type"] == "subprocess":
                return await self._call_subprocess_tool(tool_info, arguments, server_info)
            else:
                return f"Unknown server type: {server_info['type']}"
                
        except Exception as e:
            return f"Error executing tool {tool_name}: {e}"
    
    async def _call_local_tool(self, tool_info: dict, arguments: dict) -> str:
        """Call a tool from a local MCP server."""
        try:
            tool_obj = tool_info.get("tool_obj")
            if not tool_obj:
                return f"Tool object not found for {tool_info['name']}"
            
            # Call the tool's function
            if hasattr(tool_obj, 'fn'):
                if asyncio.iscoroutinefunction(tool_obj.fn):
                    result = await tool_obj.fn(**arguments)
                else:
                    result = tool_obj.fn(**arguments)
                return str(result)
            else:
                return f"Tool function not found for {tool_info['name']}"
                
        except Exception as e:
            return f"Error calling local tool: {e}"
    
    async def _call_remote_tool(self, tool_info: dict, arguments: dict, server_info: dict) -> str:
        """Call a tool from a remote MCP server."""
        # TODO: Implement remote tool calling
        return f"Remote tool calling not yet implemented"
    
    async def _call_subprocess_tool(self, tool_info: dict, arguments: dict, server_info: dict) -> str:
        """Call a tool from a subprocess MCP server."""
        try:
            command = server_info.get("command")
            args = server_info.get("args", [])
            cwd = server_info.get("cwd", ".")
            env = server_info.get("env", {})
            
            if not command:
                return f"No command specified for subprocess server"
            
            # Get the original tool name (without server prefix)
            # The tool name format is: server_name_tool_name, so we need to remove server_name_
            server_name = tool_info.get("server", "local_server")
            tool_name_with_prefix = tool_info["name"]
            
            if tool_name_with_prefix.startswith(f"{server_name}_"):
                original_tool_name = tool_name_with_prefix[len(f"{server_name}_"):]
            else:
                # Fallback: split by first underscore and take the rest
                parts = tool_name_with_prefix.split("_", 1)
                original_tool_name = parts[1] if len(parts) > 1 else parts[0]
            
            # Start the MCP server process
            full_env = dict(os.environ)
            full_env.update(env)
            
            process = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env
            )
            
            try:
                # Initialize the server
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
                
                request_json = json.dumps(initialize_request) + "\n"
                process.stdin.write(request_json.encode())
                await process.stdin.drain()
                
                # Read initialize response
                response_line = await process.stdout.readline()
                if not response_line:
                    return "Failed to initialize MCP server"
                
                init_response = json.loads(response_line.decode().strip())
                if "error" in init_response:
                    return f"MCP server initialization error: {init_response['error']}"
                
                # Send initialized notification
                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                
                notification_json = json.dumps(initialized_notification) + "\n"
                process.stdin.write(notification_json.encode())
                await process.stdin.drain()
                
                # Small delay to let server process notification
                await asyncio.sleep(0.1)
                
                # Call the tool
                tool_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": original_tool_name,
                        "arguments": arguments
                    }
                }
                
                request_json = json.dumps(tool_request) + "\n"
                process.stdin.write(request_json.encode())
                await process.stdin.drain()
                
                # Read tool response
                tool_response_line = await process.stdout.readline()
                if tool_response_line:
                    tool_response = json.loads(tool_response_line.decode().strip())
                    
                    if "error" in tool_response:
                        return f"Tool execution error: {tool_response['error']}"
                    
                    if "result" in tool_response:
                        result = tool_response["result"]
                        
                        # Handle different result formats
                        if isinstance(result, dict):
                            if "content" in result:
                                # MCP standard format
                                content = result["content"]
                                if isinstance(content, list) and len(content) > 0:
                                    return content[0].get("text", str(result))
                                else:
                                    return str(content)
                            else:
                                # Direct result
                                return str(result)
                        else:
                            return str(result)
                    
                    return "No result returned from tool"
                else:
                    return "No response from MCP server"
                    
            finally:
                # Clean up process
                if process.stdin and not process.stdin.is_closing():
                    process.stdin.close()
                await process.wait()
                
        except json.JSONDecodeError as e:
            return f"Error parsing MCP response: {e}"
        except Exception as e:
            return f"Error calling subprocess tool: {e}"
    
    # ==================== UTILITY METHODS ====================
    
    def get_tools_description(self) -> str:
        """Get a formatted description of available tools for the LLM."""
        if not self.available_tools:
            return "No MCP tools available."
        
        # Group tools by server for better organization
        servers = {}
        for tool in self.available_tools:
            server_name = tool.get("server", "unknown")
            if server_name not in servers:
                servers[server_name] = []
            servers[server_name].append(tool)
        
        tools_desc = "You have access to these MCP tools:\n"
        
        for server_name, tools in servers.items():
            server_config = self.servers.get(server_name, {}).get("config", {})
            server_desc = server_config.get("description", f"Server: {server_name}")
            tools_desc += f"\n📡 {server_desc}:\n"
            
            for tool in tools:
                original_name = tool["name"].replace(f"{server_name}_", "")
                tools_desc += f"  - {tool['name']}: {tool['description']}\n"
                
                if tool['parameters']:
                    params = []
                    for param_name, param_info in tool['parameters'].items():
                        param_type = param_info.get('type', 'string')
                        required = " (required)" if param_info.get('required', False) else ""
                        params.append(f"{param_name} ({param_type}){required}")
                    if params:
                        tools_desc += f"    Parameters: {', '.join(params)}\n"
        
        tools_desc += "\n\nTo use a tool, include: [TOOL:tool_name:{\"param\":\"value\"}]"
        return tools_desc
    
    def list_servers(self) -> dict:
        """Get information about configured servers."""
        return {
            name: {
                "type": info["type"],
                "description": info.get("config", {}).get("description", ""),
                "tools_count": len([t for t in self.available_tools if t.get("server") == name])
            }
            for name, info in self.servers.items()
        }


class OllamaClient:
    """Facade for Ollama HTTP client with tool integration - backwards compatible interface."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """Initialize the Ollama client using new architecture."""
        self.http_client = OllamaHTTPClient(base_url)
        self.tool_client = ToolIntegratedLLMClient(self.http_client)
        
        # Backwards compatibility
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.mcp_tools = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.http_client.__aenter__()
        # Update backwards compatibility
        self.session = self.http_client.session
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
        # Clean up backwards compatibility
        self.session = None
    
    async def list_models(self) -> list:
        """List all available models."""
        return await self.http_client.list_models()
    
    def set_mcp_tools(self, mcp_tools: "MCPTools"):
        """Set the MCP tools client."""
        self.mcp_tools = mcp_tools
        self.tool_client.set_mcp_tools(mcp_tools)
    
    async def chat(self, model: str, message: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Send a chat message with tool integration."""
        return await self.tool_client.chat(model, message, system_prompt)
    
    async def chat_stream(self, model: str, message: str, system_prompt: Optional[str] = None):
        """Send a chat message with tool integration and streaming."""
        async for chunk in self.tool_client.chat_stream(model, message, system_prompt):
            yield chunk

# ==================== MAIN FUNCTION ====================

async def main():
    """Main function to run the interactive chat client."""
    async with OllamaClient() as client:
        print("🦙 Ollama Chat Client with MCP Tools")
        print("=" * 60)
        
        # Initialize MCP tools from configuration
        print("🔧 Loading MCP tools from configuration...")
        use_tools = input("\n🤔 Enable MCP tools? (y/n, default: y): ").strip().lower()
        
        if use_tools in ['', 'y', 'yes']:
            mcp_tools = MCPTools()
            await mcp_tools.initialize_servers()
            
            if mcp_tools.available_tools:
                print(f"✅ Loaded MCP tools! Found {len(mcp_tools.available_tools)} tools from {len(mcp_tools.servers)} servers:")
                
                # Show server summary
                servers_info = mcp_tools.list_servers()
                for server_name, info in servers_info.items():
                    print(f"   📡 {server_name} ({info['type']}): {info['tools_count']} tools - {info['description']}")
                
                client.set_mcp_tools(mcp_tools)
            else:
                print("⚠️  No MCP tools available. Continuing without tools.")
                mcp_tools = None
        else:
            print("🚫 MCP tools disabled for testing.")
            mcp_tools = None
        
        # List available models
        print("\n📋 Available models:")
        models = await client.list_models()
        if models:
            for i, model in enumerate(models[:5], 1):  # Show first 5 models
                print(f"   {i}. {model}")
            if len(models) > 5:
                print(f"   ... and {len(models) - 5} more")
        else:
            print("   ❌ No models found. Make sure Ollama is running.")
            return
        
        # Get model choice
        model_name = input(f"\n🤖 Choose model (default: {models[0] if models else 'llama2'}): ").strip()
        if not model_name:
            model_name = models[0] if models else 'llama2'
        
        print(f"\n🎯 Using model: {model_name}")
        print("\n💬 Chat started! Your model has access to MCP tools.")
        print("   Type 'quit', 'exit', or press Ctrl+C to exit.")
        print("   Type 'stream' to toggle streaming mode.")
        print("   Type 'tools' to see available tools.")
        print("   Type 'servers' to see configured servers.")
        print("   📝 Note: MCP tools work seamlessly in both streaming and non-streaming modes.")
        print("-" * 60)
        
        streaming = True
        
        try:
            while True:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                
                if user_input.lower() == 'stream':
                    streaming = not streaming
                    print(f"🔄 Streaming mode: {'ON' if streaming else 'OFF'}")
                    continue
                
                if user_input.lower() == 'tools':
                    if mcp_tools and mcp_tools.available_tools:
                        print("\n🔧 Available MCP Tools:")
                        print(mcp_tools.get_tools_description())
                    else:
                        print("\n❌ No MCP tools available.")
                    continue
                
                if user_input.lower() == 'servers':
                    if mcp_tools and mcp_tools.servers:
                        print("\n📡 Configured MCP Servers:")
                        servers_info = mcp_tools.list_servers()
                        for server_name, info in servers_info.items():
                            status = "✅ Active" if info['tools_count'] > 0 else "⚠️ No tools"
                            print(f"   • {server_name} ({info['type']}) - {status}")
                            print(f"     {info['description']}")
                            print(f"     Tools: {info['tools_count']}")
                    else:
                        print("\n❌ No MCP servers configured.")
                    continue
                
                if not user_input:
                    continue
                
                if streaming:
                    # Stream the response with loading indicator
                    loading = LoadingIndicator("🤖 Assistant: ")
                    loading.start()
                    
                    try:
                        response_parts = []
                        first_content = True
                        
                        async for chunk in client.chat_stream(model_name, user_input):
                            if chunk.get("done", False):
                                break
                            
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                if first_content:
                                    loading.stop()
                                    first_content = False
                                print(content, end="", flush=True)
                                response_parts.append(content)
                        
                        if first_content:  # No content was streamed
                            loading.stop()
                        
                        print()  # New line after streaming
                    except Exception as e:
                        loading.stop()
                        print(f"❌ Error during streaming: {e}")
                else:
                    # Get non-streaming response with loading indicator
                    loading = LoadingIndicator("🤖 Assistant: ")
                    loading.start()
                    
                    try:
                        response = await client.chat(model_name, user_input)
                        loading.stop()
                        
                        if response:
                            print(response)
                        else:
                            print("❌ No response received.")
                    except Exception as e:
                        loading.stop()
                        print(f"❌ Error getting response: {e}")
                        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
