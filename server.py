from fastmcp import FastMCP
import wikipedia
import requests
import json

mcp = FastMCP("Ash")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool
def search_wikipedia(query: str, sentences: int = 2) -> str:
    """
    Search Wikipedia for a query and return a summary.
    
    Args:
        query: The search term to look up on Wikipedia
        sentences: Number of sentences to return in the summary (default: 2)
    
    Returns:
        A summary of the Wikipedia article
    """
    try:
        # Get the summary of the article
        summary = wikipedia.summary(query, sentences=sentences)
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        # If there are multiple options, return the first few
        options = e.options[:5]  # Get first 5 options
        return f"Multiple articles found for '{query}'. Did you mean one of these?\n" + "\n".join(f"- {option}" for option in options)
    except wikipedia.exceptions.PageError:
        # If no page found, try searching for similar terms
        try:
            search_results = wikipedia.search(query, results=5)
            if search_results:
                return f"No exact match found for '{query}'. Similar articles:\n" + "\n".join(f"- {result}" for result in search_results)
            else:
                return f"No Wikipedia articles found for '{query}'"
        except:
            return f"Unable to search Wikipedia for '{query}'"
    except Exception as e:
        return f"Error searching Wikipedia: {str(e)}"
    
@mcp.tool
def search_ibmtutorials(query: str) -> str:
    """
    Search for tutorials on GitHub by downloading a JSON file from a GitHub repo and searching the payload for any relevant results and the respective details
    
    Args:
        query: The search term to look for in tutorial titles and URLs
    
    Returns:
        A formatted list of relevant tutorial results
    """
    try:
        # Download the JSON file from the GitHub repo
        url = "https://raw.githubusercontent.com/IBM/ibmdotcom-tutorials/refs/heads/main/docs_index.json"
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse the JSON data
        tutorials = response.json()
        
        # Search for relevant tutorials (case-insensitive)
        query_lower = query.lower()
        relevant_tutorials = []
        
        for tutorial in tutorials:
            # Search in title and URL
            title = tutorial.get('title', '').lower()
            url_path = tutorial.get('url', '').lower()
            
            if query_lower in title or query_lower in url_path:
                relevant_tutorials.append(tutorial)
        
        # Format and return results
        if not relevant_tutorials:
            return f"No IBM tutorials found matching '{query}'"
        
        # Format the results
        result_lines = [f"Found {len(relevant_tutorials)} tutorial(s) matching '{query}':\n"]
        
        for i, tutorial in enumerate(relevant_tutorials, 1):
            title = tutorial.get('title', 'No title')
            url = tutorial.get('url', 'No URL')
            date = tutorial.get('date', 'No date')
            author = tutorial.get('author', '')
            
            result_lines.append(f"{i}. **{title}**")
            result_lines.append(f"   URL: {url}")
            result_lines.append(f"   Date: {date}")
            if author:
                result_lines.append(f"   Author: {author}")
            result_lines.append("")  # Empty line for spacing
        
        return "\n".join(result_lines)
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching tutorials from GitHub: {str(e)}"
    except json.JSONDecodeError as e:
        return f"Error parsing JSON data: {str(e)}"
    except Exception as e:
        return f"Error searching IBM tutorials: {str(e)}"

if __name__ == "__main__":
    mcp.run()