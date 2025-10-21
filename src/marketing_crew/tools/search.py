import requests
import json
import os

from crewai_tools import BrightDataSearchTool,ScrapeWebsiteTool
from crewai.tools import tool
    
@tool("search internet")
def search_internet(query: str):
    """Tool to search the internet using BrightDataSearchTool."""
    tool = BrightDataSearchTool(
        query=query,
        country="SG",
    )
    return tool.run()

@tool("search instagram")
def search_instagram(query: str):
    """Tool to search Instagram using BrightDataSearchTool."""
    tool = BrightDataSearchTool(
        query=f"site:instagram.com {query}",
        country="SG",
    )
    return tool.run()

@tool("open page")
def open_page(website_url: str):
    """Tool to open a page using ScrapeWebsiteTool."""
    scrape_tool = ScrapeWebsiteTool(
        website_url=website_url,
    )
    return scrape_tool.run()
