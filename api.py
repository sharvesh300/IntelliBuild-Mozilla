import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

# Ensure imports from current directory work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clients import EmbeddingsClient, ChromaService
from agent import RAGAgent
from scripts.ingest import chunk_text, embed_chunks

# ---------------------------------------------------------------------------
# Setup FastAPI and CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="IntelliBuild RAG API", description="Backend API for Local Document Q&A RAG")

# Enable Cross-Origin Resource Sharing (CORS) for local frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production if needed, allow all for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared State & Services Setup
# ---------------------------------------------------------------------------

EMBEDDINGS_URL = "http://127.0.0.1:8085"
LLM_URL = "http://127.0.0.1:8086"
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "documents"

# Initialize Agent & Services
agent = RAGAgent(
    llm_base_url=LLM_URL,
    embeddings_base_url=EMBEDDINGS_URL,
    chroma_persist_dir=CHROMA_PERSIST_DIR,
    collection_name=COLLECTION_NAME,
)

chroma = agent.chroma
embeds = agent.embeddings

# ---------------------------------------------------------------------------
# Pydantic Request/Response Schema
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., description="The question/query to ask the RAG agent")

class SourceResponse(BaseModel):
    source: str
    text: str
    score: float

class ChatResponse(BaseModel):
    answer: str
    tokens: int
    model: str
    sources: List[SourceResponse]

class StatsResponse(BaseModel):
    chunk_count: int

class UploadResponse(BaseModel):
    success: bool
    message: str
    files_processed: int
    chunks_created: int

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text pages from PDF bytes."""
    import io
    pdf_file = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_file)
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts)

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Check connectivity to embedding and llamafile servers."""
    import requests
    embeddings_ok = False
    llm_ok = False
    
    # Check embedding server
    try:
        res = requests.get(EMBEDDINGS_URL, timeout=1.0)
        embeddings_ok = True
    except Exception:
        try:
            requests.post(f"{EMBEDDINGS_URL}/predict", json={"inputs": ["test"]}, timeout=1.0)
            embeddings_ok = True
        except Exception:
            pass
            
    # Check LLM server
    try:
        requests.get(f"{LLM_URL}/v1/models", timeout=1.0)
        llm_ok = True
    except Exception:
        pass
        
    return {
        "status": "healthy" if (embeddings_ok and llm_ok) else "degraded",
        "services": {
            "embeddings_server": "connected" if embeddings_ok else "disconnected",
            "llm_server": "connected" if llm_ok else "disconnected"
        }
    }

@app.get("/api/stats", response_model=StatsResponse)
def get_database_stats() -> StatsResponse:
    """Get the number of chunks currently stored in ChromaDB."""
    try:
        count = chroma.count()
        return StatsResponse(chunk_count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch database stats: {e}")

@app.post("/api/upload", response_model=UploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)) -> UploadResponse:
    """Accepts multiple documents, extracts text, chunks, embeds, and stores them."""
    raw_chunks = []
    files_processed = 0

    for file in files:
        filename = file.filename
        if not filename:
            continue
            
        try:
            file_bytes = await file.read()
            
            # Determine how to parse the file
            if filename.lower().endswith(".pdf"):
                content = extract_text_from_pdf(file_bytes)
            else:
                # Text/Markdown files
                content = file_bytes.decode("utf-8", errors="ignore")
                
            if not content.strip():
                continue
                
            # Perform text chunking
            doc_chunks = chunk_text(content)
            for i, chunk_text_content in enumerate(doc_chunks):
                raw_chunks.append({
                    "id": f"{filename}:chunk_{i}",
                    "source": filename,
                    "text": chunk_text_content,
                })
            files_processed += 1
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process file {filename}: {e}")

    if not raw_chunks:
        return UploadResponse(
            success=False,
            message="No text chunks were generated from the uploaded files.",
            files_processed=0,
            chunks_created=0
        )

    try:
        # Generate embeddings and add to vector store
        document_chunks = embed_chunks(raw_chunks, embeds)
        chroma.add_chunks(document_chunks)
        
        return UploadResponse(
            success=True,
            message=f"Indexed {files_processed} files successfully.",
            files_processed=files_processed,
            chunks_created=len(document_chunks)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed and index documents: {e}")

@app.post("/api/chat", response_model=ChatResponse)
def ask_rag_agent(request: ChatRequest) -> ChatResponse:
    """Query the local RAG agent and return answers and grounded citations."""
    try:
        # Check if we have chunks indexed first
        if chroma.count() == 0:
            return ChatResponse(
                answer="No documents are currently indexed. Please upload and index documents before asking questions.",
                tokens=0,
                model="N/A",
                sources=[]
            )
            
        agent_res = agent.ask(request.message)
        
        # Structure source outputs
        sources_list = [
            SourceResponse(
                source=src.chunk.source,
                text=src.chunk.text,
                score=src.score
            ) for src in agent_res.sources
        ]
        
        return ChatResponse(
            answer=agent_res.content,
            tokens=agent_res.total_tokens,
            model=agent_res.model,
            sources=sources_list
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent failed to process query: {e}")

@app.post("/api/reset")
def reset_database() -> Dict[str, Any]:
    """Wipe the ChromaDB collection to start clean."""
    global chroma, agent
    try:
        chroma.delete_collection()
        # Recreate collection to keep service active
        chroma = ChromaService(persist_dir=CHROMA_PERSIST_DIR, collection_name=COLLECTION_NAME)
        # Reset Chroma reference in agent
        agent.chroma = chroma
        
        return {"success": True, "message": "Vector store wiped and reset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {e}")

# ---------------------------------------------------------------------------
# Bare Execution entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
