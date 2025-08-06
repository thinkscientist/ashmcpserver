"""Interactive chat interface for the Ollama MCP client."""

from .loading import LoadingIndicator


class ChatInterface:
    """Handles the interactive chat interface and commands."""
    
    def __init__(self, client, mcp_tools=None):
        self.client = client
        self.mcp_tools = mcp_tools
        self.streaming = True
        
    async def start_chat(self, model_name: str):
        """Start the interactive chat session."""
        print(f"\n🎯 Using model: {model_name}")
        print("\n💬 Chat started! Your model has access to MCP tools.")
        print("   Type 'quit', 'exit', or press Ctrl+C to exit.")
        print("   Type 'stream' to toggle streaming mode.")
        print("   Type 'tools' to see available tools.")
        print("   Type 'servers' to see configured servers.")
        print("   📝 Note: MCP tools work seamlessly in both streaming and non-streaming modes.")
        print("-" * 60)
        
        try:
            while True:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                # Handle quit/exit commands
                if user_input.lower() in ['quit', 'exit']:
                    break
                
                # Handle other commands
                if await self._handle_command(user_input):
                    continue
                
                if not user_input:
                    continue
                
                await self._handle_chat_message(model_name, user_input)
                        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
    
    async def _handle_command(self, user_input: str) -> bool:
        """Handle special commands. Returns True if command was handled."""
        command = user_input.lower()
        
        if command == 'stream':
            self.streaming = not self.streaming
            print(f"🔄 Streaming mode: {'ON' if self.streaming else 'OFF'}")
            return True
        
        if command == 'tools':
            self._show_tools()
            return True
        
        if command == 'servers':
            self._show_servers()
            return True
        
        return False
    
    def _show_tools(self):
        """Display available MCP tools."""
        if self.mcp_tools and self.mcp_tools.available_tools:
            print("\n🔧 Available MCP Tools:")
            print(self.mcp_tools.get_tools_description())
        else:
            print("\n❌ No MCP tools available.")
    
    def _show_servers(self):
        """Display configured MCP servers."""
        if self.mcp_tools and self.mcp_tools.servers:
            print("\n📡 Configured MCP Servers:")
            servers_info = self.mcp_tools.list_servers()
            for server_name, info in servers_info.items():
                status = "✅ Active" if info['tools_count'] > 0 else "⚠️ No tools"
                print(f"   • {server_name} ({info['type']}) - {status}")
                print(f"     {info['description']}")
                print(f"     Tools: {info['tools_count']}")
        else:
            print("\n❌ No MCP servers configured.")
    
    async def _handle_chat_message(self, model_name: str, user_input: str):
        """Handle a chat message from the user."""
        if self.streaming:
            await self._handle_streaming_response(model_name, user_input)
        else:
            await self._handle_non_streaming_response(model_name, user_input)
    
    async def _handle_streaming_response(self, model_name: str, user_input: str):
        """Handle streaming response from the LLM."""
        loading = LoadingIndicator("🤖 Assistant: ")
        loading.start()
        
        try:
            response_parts = []
            first_content = True
            
            async for chunk in self.client.chat_stream(model_name, user_input):
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
    
    async def _handle_non_streaming_response(self, model_name: str, user_input: str):
        """Handle non-streaming response from the LLM."""
        loading = LoadingIndicator("🤖 Assistant: ")
        loading.start()
        
        try:
            response = await self.client.chat(model_name, user_input)
            loading.stop()
            
            if response:
                print(response)
            else:
                print("❌ No response received.")
        except Exception as e:
            loading.stop()
            print(f"❌ Error getting response: {e}")


async def setup_mcp_tools():
    """Setup and initialize MCP tools."""
    from ..mcp import MCPTools
    
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
            
            return mcp_tools
        else:
            print("⚠️  No MCP tools available. Continuing without tools.")
            return None
    else:
        print("🚫 MCP tools disabled for testing.")
        return None


async def select_model(client):
    """Allow user to select a model."""
    print("\n📋 Available models:")
    models = await client.list_models()
    if models:
        for i, model in enumerate(models[:5], 1):  # Show first 5 models
            print(f"   {i}. {model}")
        if len(models) > 5:
            print(f"   ... and {len(models) - 5} more")
    else:
        print("   ❌ No models found. Make sure Ollama is running.")
        return None
    
    # Get model choice
    model_name = input(f"\n🤖 Choose model (default: {models[0] if models else 'llama2'}): ").strip()
    if not model_name:
        model_name = models[0] if models else 'llama2'
    
    return model_name