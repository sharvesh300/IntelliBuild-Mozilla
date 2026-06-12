import requests
from typing import List, Dict, Any, Optional
from models import ChatCompletionResponse

class LlamafileClient:
    """Client wrapper for llamafile / OpenAI-compatible chat API servers."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8086"):
        self.base_url = base_url.rstrip("/")

    def create_chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Sends a chat completion request to the llamafile server and parses the response.
        
        Args:
            messages: A list of message dictionaries, e.g., [{"role": "user", "content": "hello"}]
            temperature: Sampling temperature to use.
            max_tokens: Maximum number of tokens to generate.
            **kwargs: Extra parameters passed to the request payload.
            
        Returns:
            ChatCompletionResponse: The validated Pydantic model representation of the response.
        """
        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
            
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Parse and return validated Pydantic model
        return ChatCompletionResponse.model_validate(response.json())
