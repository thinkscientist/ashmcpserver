# Ash MCP Server

A Model Context Protocol (MCP) server that provides useful tools for information retrieval and basic calculations. Built with FastMCP and Python.

## Features

This MCP server provides three main tools:

### 🧮 **Add Calculator**
- Simple addition calculator for two numbers
- Useful for basic mathematical operations

### 📚 **Wikipedia Search**
- Search Wikipedia articles and get concise summaries
- Configurable summary length (number of sentences)
- Intelligent error handling for disambiguation and missing pages
- Fallback search suggestions when exact matches aren't found

### 🔍 **IBM Tutorials Search**
- Search IBM's tutorial database from their GitHub repository
- Finds relevant tutorials by title and URL matching
- Returns formatted results with titles, URLs, dates, and authors
- Searches through IBM's comprehensive tutorial collection

## Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/thinkscientist/ashmcpserver.git
   cd ashmcpserver
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   python server.py
   ```

## Requirements

- Python 3.7+
- fastmcp
- wikipedia
- requests (for IBM tutorials search)

## Tools Documentation

### `add(a: int, b: int) -> int`
**Description:** Add two numbers together.

**Parameters:**
- `a` (int): First number
- `b` (int): Second number

**Returns:** The sum of the two numbers

**Example:**
```python
add(5, 3)  # Returns: 8
```

### `search_wikipedia(query: str, sentences: int = 2) -> str`
**Description:** Search Wikipedia for a query and return a summary.

**Parameters:**
- `query` (str): The search term to look up on Wikipedia
- `sentences` (int, optional): Number of sentences to return in the summary (default: 2)

**Returns:** A summary of the Wikipedia article or suggestions if no exact match is found

**Example:**
```python
search_wikipedia("Python programming", 3)
# Returns: A 3-sentence summary about Python programming
```

**Error Handling:**
- **Disambiguation:** If multiple articles match, returns a list of options
- **Page Not Found:** Provides similar article suggestions
- **Network Errors:** Graceful error messages

### `search_ibmtutorials(query: str) -> str`
**Description:** Search IBM's tutorial database for relevant tutorials.

**Parameters:**
- `query` (str): The search term to look for in tutorial titles and URLs

**Returns:** A formatted list of relevant tutorials with details

**Example:**
```python
search_ibmtutorials("machine learning")
# Returns: List of IBM tutorials related to machine learning
```

**Tutorial Information Included:**
- Title
- Full URL
- Publication date
- Author (when available)

## Data Sources

- **Wikipedia:** Uses the official Wikipedia API through the `wikipedia` Python package
- **IBM Tutorials:** Fetches data from IBM's tutorial index at `https://raw.githubusercontent.com/IBM/ibmdotcom-tutorials/refs/heads/main/docs_index.json`

## Usage in MCP Clients

This server can be used with any MCP-compatible client. The server exposes three tools that can be called programmatically:

1. `add` - for mathematical calculations
2. `search_wikipedia` - for Wikipedia information retrieval
3. `search_ibmtutorials` - for IBM tutorial discovery

## Project Structure

```
ashmcpserver/
├── server.py          # Main MCP server implementation
├── requirements.txt   # Python dependencies
├── .gitignore        # Git ignore rules
├── LICENSE           # MIT License
└── README.md         # This file
```

## Development

### Adding New Tools

To add a new tool to the server:

1. Define your function with proper type hints
2. Add the `@mcp.tool` decorator
3. Include a descriptive docstring
4. Handle errors gracefully

Example:
```python
@mcp.tool
def your_new_tool(param: str) -> str:
    """
    Description of what your tool does.
    
    Args:
        param: Description of the parameter
    
    Returns:
        Description of what is returned
    """
    try:
        # Your implementation here
        return result
    except Exception as e:
        return f"Error: {str(e)}"
```

### Error Handling

All tools implement comprehensive error handling to ensure graceful failures and helpful error messages for users.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The MIT License is a permissive license that allows for commercial use, modification, distribution, and private use with minimal restrictions.

## Author

**Ash** - MCP Server Developer

---

*Built with [FastMCP](https://github.com/jlowin/fastmcp) - A modern, fast MCP server framework for Python.*
