"""OllamaClient facade for backwards compatibility."""

from typing import Optional
from .llm_client import OllamaHTTPClient, ToolIntegratedLLMClient


class OllamaClient:
    """Facade for Ollama HTTP client with tool integration - backwards compatible interface."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.http_client = OllamaHTTPClient(base_url)
        self.tool_client = ToolIntegratedLLMClient(self.http_client)
        
        # Backwards compatibility attributes
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.mcp_tools = None
    
    async def __aenter__(self):
        await self.http_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def list_models(self) -> list:
        """List all available models."""
        return await self.http_client.list_models()
    
    def set_mcp_tools(self, mcp_tools):
        """Set MCP tools for tool integration."""
        self.mcp_tools = mcp_tools
        self.tool_client.set_mcp_tools(mcp_tools)
    
    async def chat(self, model: str, message: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Send a chat message with tool integration."""
        return await self.tool_client.chat(model, message, system_prompt)
    
    async def chat_stream(self, model: str, message: str, system_prompt: Optional[str] = None):
        """Send a chat message with tool integration and streaming."""
        async for chunk in self.tool_client.chat_stream(model, message, system_prompt):
            yield chunk