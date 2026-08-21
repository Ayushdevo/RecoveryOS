import os
import json
import google.generativeai as genai
from pydantic import BaseModel
from apps.backend.config import settings

# Configure Gemini
api_key = settings.GEMINI_API_KEY
if api_key:
    genai.configure(api_key=api_key)

def get_gemini_model(model_name: str = "gemini-1.5-flash"):
    """
    Initialize and return the Gemini model.
    """
    return genai.GenerativeModel(model_name)

def generate_structured_output(prompt: str, response_schema: type[BaseModel], model_name: str = "gemini-1.5-flash") -> BaseModel:
    """
    Call Gemini to generate output conforming to the Pydantic schema.
    Includes fallback heuristics in case of API failure.
    """
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        raise ValueError("GEMINI_API_KEY is not configured in the environment.")
        
    try:
        model = get_gemini_model(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.1
            ),
            timeout=10.0
        )
        
        # Parse output
        content = response.text.strip()
        parsed_json = json.loads(content)
        return response_schema(**parsed_json)
        
    except Exception as e:
        print(f"Gemini API execution failed: {e}. Raising exception for upper layer escalation.")
        raise RuntimeError(f"Agent LLM Call Failed: {str(e)}") from e
