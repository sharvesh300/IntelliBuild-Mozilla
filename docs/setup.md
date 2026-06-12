# Local AI Services Setup Guide

This guide describes how to run and initialize the local Large Language Model (LLM) and Embedding models required by the project.

---

## Prerequisites

Ensure you have downloaded the binary executables in the root of the project directory:
*   `Qwen3.5-0.8B-Q8_0.llamafile` (LLM Server)
*   `minillm.encoderfile` (Embeddings Server)

Make sure both files have execution permissions. If not, run:
```bash
chmod +x Qwen3.5-0.8B-Q8_0.llamafile minillm.encoderfile
```

---

## 1. LLM Chat Completions Server

The chat completions service is powered by **Llamafile** executing a quantized `Qwen 3.5` model.

### Command to Initialize
To start the LLM server on port `8086`, run the following command in your terminal:

```bash
./Qwen3.5-0.8B-Q8_0.llamafile --server --port 8086
```

> [!NOTE]
> Once started, the OpenAI-compatible API endpoint will be available at `http://127.0.0.1:8086/v1/chat/completions`.
> You can access its interactive web UI by visiting `http://127.0.0.1:8086` in your browser.

---

## 2. Text Embeddings Server

The text embeddings service is powered by the `minillm` encoder module, serving the `sentence-transformers/all-MiniLM-L6-v2` representation model.

### Command to Initialize
To start the embeddings service on port `8085`, run:

```bash
./minillm.encoderfile serve --http-port 8085
```

> [!NOTE]
> Once running, the service accepts POST requests at `http://127.0.0.1:8085/predict` with input strings to generate vectors.

---

## Project Clients Integration

You can easily interact with these services using our pre-configured Pydantic clients located in the `clients` directory:

```python
from clients import LlamafileClient, EmbeddingsClient

# Initialize Chat Client
chat_client = LlamafileClient(base_url="http://127.0.0.1:8086")
completion = chat_client.create_chat_completion(
    messages=[{"role": "user", "content": "Explain MCP in simple terms."}]
)
print(completion.assistant_content)

# Initialize Embeddings Client
embeddings_client = EmbeddingsClient(base_url="http://127.0.0.1:8085")
response = embeddings_client.get_embeddings(inputs=["Hello world"])
print(response.first_embedding)
```
