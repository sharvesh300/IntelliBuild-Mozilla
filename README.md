# IntelliBuild - Local RAG Workspace with Direct FastMCP Fallback

IntelliBuild is a Retrieval-Augmented Generation (RAG) system built on local AI services. It lets users upload local documents (PDFs, Markdown, text files), indexes them into a local vector store (ChromaDB), and enables natural-language Q&A using a local LLM. 

When retrieval confidence from local documents is low, the backend automatically initiates a fallback web search using a subprocess-spawner connected to a FastMCP search server (`search_tool.py`), querying the Tavily Search API. Web references are displayed as clickable hyperlinks in the user interface.

---

## System Architecture

Below is the 3D isometric representation of the RAG system architecture:

![System Architecture](/Users/sharveshsivagnanam/.gemini/antigravity-ide/brain/c68e20fd-cd37-4c62-bd41-6d9e81383b5d/rag_architecture_diagram_1781251429714.png)

---

## Detailed Data Flow

The following Mermaid diagram outlines the step-by-step query processing flow:

```mermaid
flowchart TD
    subgraph Frontend [Mozilla Frontend - Next.js]
        UI["Chat Interface (page.tsx)"]
    end

    subgraph Backend [IntelliBuild Backend - FastAPI]
        API["FastAPI Server (api.py)"]
        Agent["RAG Agent (agent.py)"]
        Chroma["Chroma Service (chroma.py)"]
        Decision{"Is Max Similarity 35 percent or more?"}
        FormatContext["Use Local Document Chunks"]
        FormatWebContext["Use Web Search Results (URLs as sources)"]
        LLMCall["Compile Prompt and Context"]
        MCPCall["Spawn and Call MCP Server (web_search)"]
    end

    subgraph External_Services [Local and Remote Services]
        EmbedSrv["Embeddings Server minillm.encoderfile on Port 8085"]
        LLMSrv["Llamafile LLM Server Qwen3.5 on Port 8086"]
        VectorDB[("ChromaDB Vector Store (chroma_db)")]
        MCPSrv["FastMCP Search Server search_tool.py via stdio"]
        Tavily["Tavily Web Search API"]
    end

    %% Flow Steps
    UI --> API
    API --> Agent
    
    Agent --> EmbedSrv
    EmbedSrv --> Agent
    
    Agent --> Chroma
    Chroma --> VectorDB
    VectorDB --> Chroma
    Chroma --> Agent
    
    Agent --> Decision

    Decision -- "Yes" --> FormatContext
    Decision -- "No" --> MCPCall
    
    MCPCall --> MCPSrv
    MCPSrv --> Tavily
    Tavily --> MCPSrv
    MCPSrv --> Agent
    Agent --> FormatWebContext
    
    FormatContext --> LLMCall
    FormatWebContext --> LLMCall
    
    LLMCall --> LLMSrv
    LLMSrv --> Agent
    
    Agent --> API
    API --> UI
    
    %% Styling
    classDef frontend fill:#4c1d95,stroke:#8b5cf6,stroke-width:2px,color:#fff;
    classDef backend fill:#1e1b4b,stroke:#4f46e5,stroke-width:2px,color:#fff;
    classDef services fill:#064e3b,stroke:#059669,stroke-width:2px,color:#fff;
    classDef database fill:#78350f,stroke:#d97706,stroke-width:2px,color:#fff;
    
    class UI frontend;
    class API,Agent,Chroma,Decision,FormatContext,FormatWebContext,LLMCall,MCPCall backend;
    class EmbedSrv,LLMSrv,MCPSrv,Tavily services;
    class VectorDB database;
```

---

## Web Search Fallback Engine (Direct FastMCP)

Rather than running through `mcpd`, the RAG agent directly controls the lifecycle of the search tool subprocess:
1. When ChromaDB returns document chunks, their cosine distances are parsed into true cosine similarities in the range `[0, 1]`:
   $$\text{similarity} = 1.0 - \text{distance}$$
2. If the maximum similarity score falls below **`0.35`** (or if the database is empty), a low-confidence state triggers.
3. The agent spawns the `search_tool.py` subprocess via standard I/O (using python `mcp` SDK's `stdio_client` and `ClientSession`), executing the `web_search` tool.
4. The retrieved search content is injected directly as the grounded context for the local LLM.

---

## Local Setup and Running

### 1. Requirements
- Python `>= 3.14`
- `uv` package manager

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
TAVILY_API_KEY=your-api-key-here
```

### 3. Launch Embeddings Server
Start the local embeddings server on port `8085`:
```bash
./minillm.encoderfile serve --http-port 8085
```

### 4. Launch LLM Server
Start the llamafile server on port `8086`:
```bash
./Qwen3.5-0.8B-Q8_0.llamafile --server --port 8086
```

### 5. Start Backend Server
Run the FastAPI application:
```bash
uv run api.py
```

### 6. Start Frontend App
Navigate to the Next.js frontend directory and launch the server:
```bash
cd frontend/mozilla-frontend
npm run dev
# or
bun run dev
```
Access the application dashboard at `http://localhost:3000`.
