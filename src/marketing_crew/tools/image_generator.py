import os
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import boto3
import uuid

class ImageGeneratorToolInput(BaseModel):
    """Input schema for the ImageGeneratorTool."""
    prompt: str = Field(..., description="The detailed text description to generate an image from.")

class ImageGeneratorTool(BaseTool):
    name: str = "Gemini Image Generator"
    description: str = (
        "Generates an image from a text prompt using Gemini API, " 
        "uploads it to a S3 bucket"
        "and returns the image URL."
    )
    args_schema: Type[BaseModel] = ImageGeneratorToolInput

    # def __init__(self, model="gemini-2.5-flash-image", output_path="generated_image.png"):
    #     super().__init__()
    #     self.model = model
    #     self.output_path = output_path
    #     self.client = genai.Client()

    def _run(self, prompt: str) -> str:
        """
        The main execution method for the tool.
        This connects to the OpenAI API to generate an image.
        """
        
        # 1. Get API Key
        bucket_name = os.environ.get("S3_BUCKET_NAME")
        region = os.environ.get("S3_REGION")

        if not bucket_name or not region:
            return "Error: S3_BUCKET_NAME or S3_REGION is not set in the environment."

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return "Error: GEMINI_API_KEY is not set. The agent cannot use this tool."

        try:
            client = genai.Client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",  # Using the model you specified
                contents=[prompt],
            )
            
            image_data = None
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    break
            
            if not image_data:
                return "Error: The model did not return any image data."

            # --- 3. Upload Data to S3 (Boto3) ---
            # Boto3 will automatically find AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
            s3_client = boto3.client('s3', region_name=region)
            
            # Create a unique file name
            file_name = f"marketing-images/{uuid.uuid4()}.png"
            
            # Upload the image bytes
            s3_client.upload_fileobj(
                BytesIO(image_data),
                bucket_name,
                file_name,
                ExtraArgs={'ContentType': 'image/png'} # Set content type
            )
            
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': file_name},
                ExpiresIn=3600
            )
            
            # --- 4. Return the Public URL ---
            # Construct the standard public S3 URL
            public_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{file_name}"
            
            return f"Successfully generated and uploaded image: {presigned_url}"

        except Exception as e:
            return f"An unexpected error occurred: {e}"