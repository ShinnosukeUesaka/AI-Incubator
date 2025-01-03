import json
import os
from datetime import datetime

from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.document_loaders import WebBaseLoader
from langchain.tools import Tool
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_openai import ChatOpenAI


def web_page_reader(url: str) -> str:
    loader = WebBaseLoader(url)
    content = loader.load()[0].page_content
    return content



def search_for_websites(query: str, result_limit: int = 3) -> list[dict]:
    """
    Search for websites based on a query and return citation information and content summary.
    
    Args:
        query: Detailed search query based on paper content
        result_limit: Maximum number of results to return
        
    Returns:
        List of dictionaries containing citation info and content summary
    """
    # Update instructions for website citation task
    citation_instructions = (
        "You are a research assistant helping to find and cite web content. "
        "For each website:\n"
        "1. Extract key information for citation (title, author if available, website name, URL, access date)\n"
        "2. Analyze the content and provide a brief summary relevant to the search query\n"
        "3. Format the information in a structured way for citation purposes\n\n"
        "Focus on finding high-quality, relevant sources that support the paper's arguments."
    )
    
    # Update agent prompt
    base_prompt = hub.pull("langchain-ai/react-agent-template")
    prompt = base_prompt.partial(instructions=citation_instructions)
    llm = ChatOpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"], 
        base_url="https://api.deepseek.com/v1",
        model_name="deepseek-chat",
    )
    
    # Create agent with updated wrapper for result limit
    wrapper = DuckDuckGoSearchAPIWrapper(max_results=result_limit)
    search = DuckDuckGoSearchResults(api_wrapper=wrapper, output_format="list")
    web_page_loader = Tool(
        name = "WebBaseLoader",
        func=web_page_reader,
        description="This tool is used to get the content of a web page. The argument is a URL string. Use this tool for websites, since snippet is not the whole content of the web page."
     )

    tools = [web_page_loader, search]
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    # ----------------------------------------------------------------------
    # *** UPDATED INPUT PROMPT ***
    # ----------------------------------------------------------------------
    # We request the final answer as a JSON array of objects.
    # We also provide an example to guide the LLM’s formatting.
    json_prompt = f"""Find and analyze websites for the following research topic: {query}

At the end please return JSON (no extra text, headings, ```json etc.) after Final Answer:Use the following structure, as an array of objects:

Thought: Do I need to use a tool? No
Final Answer:
[
  {{
    "title": "...",
    "author": "...", 
    "website": "...",
    "url": "...",
    "access_date": "...",
    "summary": "...",
    "key_quotes": ["...", "..."]
  }},
  ...
]

Where:
- title = Title of the page
- author = Author or 'N/A' if not available  
- website = Website name or publisher
- url = The page's URL
- access_date = Current date in YYYY-MM-DD format
- summary = A brief summary of relevant content answering the query.
- key_quotes = List of quotes/findings that support the research"""
    # ----------------------------------------------------------------------
    
    # Execute search and process results
    response = agent_executor.invoke({"input": json_prompt})
    

    try:
        results_data = json.loads(response["output"].strip("```json").strip("```"))
        for item in results_data:
            assert set(item.keys()) == set(["title", "author", "website", "url", "access_date", "summary", "key_quotes"]), "The structure of the JSON is not correct"
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from agent's response: {e}")
        return []
    
    # Convert to final structured format
    results = []
    for item in results_data:
        results.append({
            "title": item["title"],
            "authors": item["author"],
            "venue": item["website"],
            "url": item["url"],
            "year": item["access_date"],
            "summary": item["summary"],
            "key_quotes": item["key_quotes"],
            "citationStyles": {
                "bibtex": generate_website_bibtex(item)
            }
        })
    
    return results

def generate_website_bibtex(item: dict) -> str:
    """Generate BibTeX citation for a website."""
    # Create a unique citation key by lowercasing and replacing spaces
    cite_key = f"web_{item['title'].lower().replace(' ', '_')[:30]}"
    today_str = item["access_date"]
    
    return f"""@misc{{{cite_key},
    title = {{{item['title']}}},
    author = {{{item['author']}}},
    howpublished = {{\\url{{{item['url']}}}}},
    year = {today_str[:4]},
    note = {{Accessed: {today_str}}}
}}
"""

# Example usage
if __name__ == "__main__":
    query = "Explain the impact of AI on software development productivity with focus on pair programming"
    results = search_for_websites(query)
    for result in results:
        print(f"Title: {result['title']}")
        print(f"URL: {result['url']}")
        print(f"Summary: {result['summary']}")
        print(f"Key Quotes: {result['key_quotes']}")
        print(f"BibTeX: {result['citationStyles']['bibtex']}")
        print("---")