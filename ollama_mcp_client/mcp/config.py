"""Configuration management for MCP servers."""

import json
import os
import re
from typing import Dict, Any


class ConfigManager:
    """Handles configuration loading and validation."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not os.path.exists(self.config_path):
            print(f"⚠️ Configuration file '{self.config_path}' not found. Using defaults.")
            return {
                "mcp_servers": {},
                "settings": {
                    "default_model": "llama2",
                    "streaming": True
                }
            }
        
        try:
            with open(self.config_path, 'r') as f:
                config_text = f.read()
                # Replace environment variables
                config_text = self._expand_environment_variables(config_text)
                return json.loads(config_text)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing config file: {e}")
            return {"mcp_servers": {}, "settings": {}}
        except Exception as e:
            print(f"❌ Error loading config file: {e}")
            return {"mcp_servers": {}, "settings": {}}
    
    def _expand_environment_variables(self, text: str) -> str:
        """Expand environment variables in config text."""
        # Replace ${VAR} with environment variable values
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(3) if match.group(3) else ""
            
            # Special handling for PROJECT_ROOT
            if var_name == "PROJECT_ROOT":
                return os.environ.get(var_name, self._get_project_root())
            
            return os.environ.get(var_name, default_value)
        
        # Pattern: ${VAR} or ${VAR:default}
        pattern = r'\$\{([^}:]+)(:([^}]*))?\}'
        return re.sub(pattern, replace_var, text)
    
    def _get_project_root(self) -> str:
        """Auto-detect project root directory."""
        # Start from config file location and work upward
        current_dir = os.path.dirname(os.path.abspath(self.config_path))
        
        # Look for common project indicators
        project_indicators = [
            'requirements.txt', 
            'pyproject.toml', 
            '.git',
            'main.py',
            'server.py'
        ]
        
        while current_dir != os.path.dirname(current_dir):  # Not at filesystem root
            for indicator in project_indicators:
                if os.path.exists(os.path.join(current_dir, indicator)):
                    return current_dir
            current_dir = os.path.dirname(current_dir)
        
        # Fallback to current directory
        return os.getcwd()
    
    def get_servers_config(self) -> Dict[str, Any]:
        """Get the servers configuration."""
        return self.config.get("mcp_servers", {})
    
    def get_settings(self) -> Dict[str, Any]:
        """Get general settings."""
        return self.config.get("settings", {})
    
    def get_server_config(self, server_name: str) -> Dict[str, Any]:
        """Get configuration for a specific server."""
        servers = self.get_servers_config()
        return servers.get(server_name, {})