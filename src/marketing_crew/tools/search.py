import requests
import json
import os
from typing import Union, List

from crewai_tools import BrightDataSearchTool,ScrapeWebsiteTool
from crewai.tools import tool
    
@tool("search internet")
def search_internet(query: str):
    """
    Performs a Google search to find relevant web results for the given query.

    The AI Agent can use this tool to gather up-to-date information from the web.
    It returns summarized search results (titles, snippets, and URLs) from Google
    based on the query provided.
    """
    tool = BrightDataSearchTool(
        query=query,
        country="SG",
    )
    return tool.run()

@tool("search instagram")
def search_instagram(query: str):
    """
    Performs a Google search limited to Instagram post results.

    The AI Agent can use this tool to find public Instagram profiles or posts 
    related to the query by searching `site:instagram.com` through Google.
    It returns summarized results with page titles, snippets, and URLs.
    """
    tool = BrightDataSearchTool(
        query=f"site:instagram.com/p/ {query}",
        country="SG",
    )
    return tool.run()

@tool("open pages")
def open_pages(website_urls: list[str]):
    """
    Opens and extracts the readable text content from one or more webpages.

    The AI Agent can use this tool to access one or more webpages and retrieve their main text 
    (such as article content, descriptions, or captions). This helps the Agent 
    understand what the pages are about for deeper context or summarization.
    """
    results = []
    for website_url in website_urls:
        scrape_tool = ScrapeWebsiteTool(
            website_url=website_url,
        )
        results.append(scrape_tool.run())
    
    return results