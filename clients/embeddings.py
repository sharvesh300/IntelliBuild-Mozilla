import requests
from typing import List
from models import EmbeddingResponse

class EmbeddingsClient:
    """Client wrapper for the embedding/encoder service."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8085"):
        self.base_url = base_url.rstrip("/")

    def get_embeddings(self, inputs: List[str]) -> EmbeddingResponse:
        """
        Sends a request to retrieve embeddings for the given list of text inputs.
        
        Args:
            inputs: A list of text strings to embed.
            
        Returns:
            EmbeddingResponse: The validated Pydantic model representation of the response.
        """
        url = f"{self.base_url}/predict"
        headers = {"Content-Type": "application/json"}
        payload = {
            "inputs": inputs
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return EmbeddingResponse.model_validate(response.json())
