"""LLM client implementations."""

import json
import re
import aiohttp
from abc import ABC, abstractmethod
from typing import Optional, List


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
    
    def __init__(self, llm_client: LLMClient, mcp_tools=None):
        self.llm_client = llm_client
        self.mcp_tools = mcp_tools
    
    def set_mcp_tools(self, mcp_tools):
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