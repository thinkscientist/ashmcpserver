# Ollama MCP Client Setup Guide

## 🚀 Quick Start

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd ashmcpserver
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the client:**
   ```bash
   python main.py
   ```

## 🔧 Configuration

The `config.json` file uses environment variables for portability:

- `${PROJECT_ROOT}` - Automatically detected project root directory
- You can override by setting: `export PROJECT_ROOT=/your/custom/path`

### Custom Configuration

If you need to customize server paths, you can either:

1. **Set environment variables:**
   ```bash
   export PROJECT_ROOT=/path/to/your/project
   python main.py
   ```

2. **Edit config.json** with your specific paths (not recommended for sharing)

## 📁 Project Structure

```
ashmcpserver/
├── main.py                 # Entry point  
├── server.py              # MCP server
├── config.json            # Configuration (portable)
├── requirements.txt       # Dependencies
└── ollama_mcp_client/     # Modular client package
    ├── core/              # LLM client logic
    ├── mcp/               # MCP integration  
    ├── ui/                # User interface
    └── utils/             # Utilities
```

## 🔧 Requirements

- Python 3.8+
- Ollama server running locally
- FastMCP package for the server