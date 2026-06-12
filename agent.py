"""
RAG Agent — Retrieval-Augmented Generation agent backed by local services.

Composes the EmbeddingsClient, ChromaService, and LlamafileClient into a
single reusable agent that answers questions grounded in ingested documents.

Usage:
    from agent import RAGAgent

    agent = RAGAgent()
    answer = agent.ask("What is MCP?")
    print(answer.content)
"""

import sys
from typing import List, Optional
from pydantic import BaseModel, Field

from clients import EmbeddingsClient, ChromaService, LlamafileClient
from models import SearchResult, DocumentChunk


# ---------------------------------------------------------------------------
# Response Model
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Structured response from the RAG agent."""
    query: str = Field(..., description="The original user query")
    content: str = Field(..., description="The generated answer text")
    sources: List[SearchResult] = Field(
        default_factory=list,
        description="The retrieved document chunks used as context",
    )
    model: str = Field(default="", description="Model that generated the answer")
    total_tokens: int = Field(default=0, description="Total tokens used for generation")


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions using the provided context.

Rules:
- Provide a detailed and comprehensive explanation based on the available facts in the context.
- If the context does not directly answer the question but contains related or relevant information, synthesize and explain these findings in detail.
- Cite the source (filename or URL) when referencing specific information.
- Only make statements that are supported by the provided context. Do not make up facts.\
"""


def _run_mcp_search(query: str) -> dict:
    """Run MCP search tool directly by starting the FastMCP server via stdio transport."""
    import asyncio
    import json
    import os
    from dotenv import load_dotenv
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def _search():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        search_tool_path = os.path.join(base_dir, "search_tool.py")

        env = os.environ.copy()
        if "TAVILY_API_KEY" not in env:
            load_dotenv(os.path.join(base_dir, ".env"))
            env = os.environ.copy()

        server_params = StdioServerParameters(
            command="uv",
            args=["run", search_tool_path],
            env=env
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.call_tool("web_search", {"query": query})
                
                tavily_data = {}
                for item in response.content:
                    if hasattr(item, "text") and item.text:
                        try:
                            tavily_data = json.loads(item.text)
                            break
                        except Exception:
                            pass
                return tavily_data

    return asyncio.run(_search())


# ---------------------------------------------------------------------------
# RAG Agent
# ---------------------------------------------------------------------------

class RAGAgent:
    """
    A Retrieval-Augmented Generation agent that answers questions using
    ingested documents stored in ChromaDB and a local LLM.

    This agent is designed to be initialised once and reused throughout
    the project for any document-grounded Q&A.
    """

    def __init__(
        self,
        llm_base_url: str = "http://127.0.0.1:8086",
        embeddings_base_url: str = "http://127.0.0.1:8085",
        chroma_persist_dir: str = "./chroma_db",
        collection_name: str = "documents",
        n_results: int = 3,
        temperature: float = 0.3,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        """
        Initialise the RAG agent with all required service clients.

        Args:
            llm_base_url: Base URL of the llamafile/OpenAI-compatible LLM server.
            embeddings_base_url: Base URL of the encoderfile embeddings server.
            chroma_persist_dir: Directory for ChromaDB on-disk persistence.
            collection_name: Name of the ChromaDB collection to query.
            n_results: Number of context chunks to retrieve per query.
            temperature: LLM sampling temperature (lower = more deterministic).
            system_prompt: System instructions for the LLM.
        """
        self.llm = LlamafileClient(base_url=llm_base_url)
        self.embeddings = EmbeddingsClient(base_url=embeddings_base_url)
        self.chroma = ChromaService(
            persist_dir=chroma_persist_dir,
            collection_name=collection_name,
        )
        self.n_results = n_results
        self.temperature = temperature
        self.system_prompt = system_prompt

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def ask(self, question: str) -> AgentResponse:
        """
        Answer a question using RAG: retrieve relevant context, then generate.

        Args:
            question: The user's natural-language question.

        Returns:
            AgentResponse with the answer, sources, and metadata.
        """
        # 1. Embed the question
        query_embedding = self.embeddings.get_embeddings(
            inputs=[question]
        ).first_embedding

        # 2. Retrieve relevant chunks
        results = self.chroma.query(
            query_embedding=query_embedding,
            n_results=self.n_results,
        )

        # Check retrieval confidence: if no results or max score is below threshold
        confidence_threshold = 0.35
        is_low_confidence = not results or max(r.score for r in results) < confidence_threshold

        if is_low_confidence:
            print(f"Retrieval confidence is low or empty (max score: {max(r.score for r in results) if results else 0.0:.3f}). Querying web search via MCP...")
            try:
                tavily_data = _run_mcp_search(question)
                web_results = []
                for idx, res in enumerate(tavily_data.get("results", [])):
                    chunk = DocumentChunk(
                        id=f"web_search_{idx}",
                        text=res.get("content", ""),
                        embedding=[],
                        source=res.get("url", "")
                    )
                    score = res.get("score", 1.0)
                    web_results.append(SearchResult(chunk=chunk, score=score))
                if web_results:
                    results = web_results
            except Exception as e:
                print(f"Failed to query MCP web search: {e}", file=sys.stderr)

        # 3. Build context block from retrieved chunks
        context = self._build_context(results)

        # 4. Construct messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {question}"
                ),
            },
        ]

        # 5. Generate answer via LLM
        completion = self.llm.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
        )

        return AgentResponse(
            query=question,
            content=completion.assistant_content or "",
            sources=results,
            model=completion.model,
            total_tokens=completion.usage.total_tokens,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(results: List[SearchResult]) -> str:
        """Format retrieved chunks into a numbered context string."""
        if not results:
            return "(No relevant documents found.)"

        blocks = []
        for i, r in enumerate(results, start=1):
            blocks.append(
                f"[{i}] Source: {r.chunk.source} "
                f"(relevance: {r.score * 100:.0f}%)\n"
                f"{r.chunk.text}"
            )
        return "\n\n".join(blocks)
