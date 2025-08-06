"""Ollama MCP Client - A modular client for chatting with Ollama models with MCP server integration."""

# Core exports
from .core import OllamaClient, LLMClient, OllamaHTTPClient, ToolIntegratedLLMClient

# MCP exports  
from .mcp import MCPTools, ConfigManager, ServerManager, ToolDiscovery, ToolExecutor

# UI exports
from .ui import ChatInterface, LoadingIndicator

__version__ = "1.0.0"
__author__ = "Assistant"
__description__ = "Modular Ollama client with MCP server integration"

__all__ = [
    # Core
    'OllamaClient',
    'LLMClient', 
    'OllamaHTTPClient',
    'ToolIntegratedLLMClient',
    
    # MCP
    'MCPTools',
    'ConfigManager',
    'ServerManager', 
    'ToolDiscovery',
    'ToolExecutor',
    
    # UI
    'ChatInterface',
    'LoadingIndicator'
]