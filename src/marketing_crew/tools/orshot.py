import os
import requests
from typing import Type, Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# This schema defines a single edit operation
class OrshotEdit(BaseModel):
    element_id: str = Field(..., description="The ID of the template element to edit.")
    value: str = Field(..., description="The new value (e.g., text string or public image URL).")

# This is the input for the tool
class CreateOrshotDesignInput(BaseModel):
    """Input schema for the CreateOrshotDesignTool."""
    template_id: Union[str, int] = Field(..., description="The ID of the Orshot template to use (e.g., 1201).")
    modifications: Dict[str, Any] = Field(..., 
        description="A JSON object (dictionary) where keys are the element IDs (e.g., 'title', 'image') "
                    "and values are the new content (e.g., 'New Title', 'http://...')."
    )

# --- The Tool Itself ---
class CreateOrshotDesignTool(BaseTool):
    name: str = "Create Orshot Design"
    description: str = (
        "Creates a new design from an Orshot template by applying a list of edits. "
        "Each edit specifies an 'element_id' and its new 'value' (text or image URL)."
    )
    args_schema: Type[BaseModel] = CreateOrshotDesignInput

    def _run(self, template_id: str, modifications: Dict[str, Any]) -> str:
        api_key = os.environ.get("ORSHOT_API_KEY")
        if not api_key:
            return "Error: ORSHOT_API_KEY is not set in the environment."
            
        # !!! YOU MUST REPLACE THIS with the real Orshot API endpoint
        api_endpoint = "https://api.orshot.com/v1/studio/render"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # This payload now perfectly matches your flexible design
        payload = {
            "templateId": template_id,
            "modifications": modifications,
            "response": {
                "type": "url",
                "format": "webp",
                "scale": 1
            }
        }

        try:
            response = requests.post(api_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # !!! YOU MUST REPLACE THIS with the correct key for the final URL
            design_url = data.get("data", {}).get("content")
            
            if design_url:
                return f"Successfully created Orshot design: {design_url}"
            else:
                return f"Error: API call successful, but no URL was returned. Response: {data}"
        except Exception as e:
            return f"Error creating Orshot design: {e}"