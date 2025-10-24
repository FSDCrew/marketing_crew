import os
import requests
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# --- Input Schema ---
# This defines the arguments your agent MUST provide when using the tool.
# The descriptions are critical as they tell the LLM *what* to put in each field.

class CanvaToolInput(BaseModel):
    """Input schema for the Canva Designer Tool."""
    template_id: str = Field(..., description="The ID of the Canva template to use (e.g., 'brand_instagram_post_template').")
    headline_text: str = Field(..., description="The main headline text to place onto the design.")
    body_text: Optional[str] = Field(default=None, description="Optional: The secondary body text to place on the design.")
    image_url: Optional[str] = Field(default=None, description="Optional: A URL for the image to place on the design. The layer in Canva must be named 'main_image'.")

# --- Tool Class ---

class CanvaTool(BaseTool):
    name: str = "Canva Designer"
    description: str = (
        "A tool to create a new Canva design by populating a specific template "
        "with headline and body text. It returns a URL to the newly created design."
    )
    args_schema: Type[BaseModel] = CanvaToolInput

    def _run(self, template_id: str, headline_text: str, body_text: Optional[str] = None, image_url: Optional[str] = None) -> str:
        """
        The main execution method for the tool.
        This is where it connects to the external Canva API.
        """
        
        # 1. Get API Key from environment variables
        api_key = os.environ.get("CANVA_API_KEY")
        if not api_key:
            return "Error: CANVA_API_KEY is not set in the environment. The agent cannot use this tool."

        # 2. Define Canva API endpoint and headers
        api_endpoint = "https://api.canva.com/v1/designs/create"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 3. Dynamically build the data payload
        # IMPORTANT: This assumes your Canva template has editable layers
        # named "headline" and "body". You must name them this
        # in the Canva editor (check the "Layers" panel).
        
        data_fields = {}
        if headline_text:
            data_fields["headline"] = {"type": "TEXT", "value": headline_text}
        if body_text:
            data_fields["body"] = {"type": "TEXT", "value": body_text}
        
        if image_url:
            # This assumes your Canva template has an image layer named 'main_image'
            data_fields["main_image"] = {"type": "IMAGE", "value": image_url}

        if not data_fields:
            return "Error: No text was provided for either headline or body."

        payload = {
            "type": "Design",
            "template": {"id": template_id},
            "data": data_fields,
            # You can also add "export" options here if needed
        }

        # 4. Make the API call with robust error handling
        try:
            response = requests.post(api_endpoint, headers=headers, json=payload)
            
            # Raise an error for bad status codes (4xx or 5xx)
            response.raise_for_status()
            
            # 5. Parse the successful response
            data = response.json()
            design_url = data.get("design", {}).get("url")
            
            if design_url:
                return f"Successfully created design. View it here: {design_url}"
            else:
                return f"Error: API call successful, but no design URL was returned. Response: {data}"
                
        except requests.exceptions.HTTPError as http_err:
            return f"Error calling Canva API (HTTPError): {http_err}. Response: {response.text}"
        except requests.exceptions.RequestException as req_err:
            return f"Error calling Canva API (RequestException): {req_err}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"
