#!/usr/bin/env python3
"""
Main entry point for the Ollama MCP Client.
Uses the new modular package structure.
"""

import asyncio
import sys
from ollama_mcp_client import OllamaClient
from ollama_mcp_client.ui.interface import ChatInterface, setup_mcp_tools, select_model


async def main():
    """Main function to run the interactive chat client."""
    try:
        print("🦙 Ollama Chat Client with MCP Tools")
        print("=" * 60)
        
        async with OllamaClient() as client:
            # Setup MCP tools
            print("🔧 Setting up MCP tools...")
            mcp_tools = await setup_mcp_tools()
            if mcp_tools:
                client.set_mcp_tools(mcp_tools)
            
            # Select model
            print("📋 Selecting model...")
            model_name = await select_model(client)
            if not model_name:
                print("❌ No model selected. Exiting.")
                return
            
            # Start chat interface
            print("💬 Starting chat interface...")
            chat_interface = ChatInterface(client, mcp_tools)
            await chat_interface.start_chat(model_name)
            
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())