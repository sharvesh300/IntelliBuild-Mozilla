import sys
from clients import LlamafileClient, EmbeddingsClient

def test_live_chat_completion():
    print("=== 1. Requesting Live Chat Completion ===")
    
    # Initialize the client pointing to localhost:8086
    client = LlamafileClient(base_url="http://127.0.0.1:8086")
    
    messages = [
        {
            "role": "user",
            "content": "Explain MCP in simple terms."
        }
    ]
    
    print("Sending request to http://127.0.0.1:8086/v1/chat/completions...")
    try:
        response = client.create_chat_completion(
            messages=messages,
            temperature=0.7
        )
        print("\nRequest Successful!")
        print(f"Response ID: {response.id}")
        print(f"Model Used: {response.model}")
        print(f"Total Tokens: {response.usage.total_tokens}")
        if response.timings:
            print(f"Generation Speed: {response.timings.predicted_per_second:.2f} tokens/sec")
            
        print("\n--- Assistant's Response ---")
        print(response.assistant_content)
        
    except Exception as e:
        print(f"Error communicating with the llamafile server: {e}", file=sys.stderr)
        print("Please ensure the llamafile server is running on port 8086.", file=sys.stderr)

def test_live_embeddings():
    print("\n=== 2. Requesting Live Embeddings ===")
    
    # Initialize the embeddings client pointing to localhost:8085
    client = EmbeddingsClient(base_url="http://127.0.0.1:8085")
    
    inputs = ["Hello world", "Model Context Protocol"]
    
    print(f"Sending request to http://127.0.0.1:8085/predict for inputs: {inputs}...")
    try:
        response = client.get_embeddings(inputs=inputs)
        print("\nEmbeddings Request Successful!")
        print(f"Model ID: {response.model_id}")
        print(f"Number of vectors returned: {len(response.results)}")
        
        for idx, res in enumerate(response.results):
            vector = res.embedding
            print(f"  Input {idx} ('{inputs[idx]}') embedding dimensions: {len(vector)}")
            print(f"  First 4 values: {vector[:4]}")
            
    except Exception as e:
        print(f"Error communicating with the embeddings server: {e}", file=sys.stderr)
        print("Please ensure the embeddings server is running on port 8085.", file=sys.stderr)

def main():
    test_live_chat_completion()
    test_live_embeddings()

if __name__ == "__main__":
    main()
