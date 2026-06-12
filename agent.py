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
    conflict: Optional[str] = Field(default=None, description="Factual conflict summary between internal documents and web search")


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

        # 2. Retrieve local chunks from ChromaDB
        local_results = []
        if self.chroma.count() > 0:
            local_results = self.chroma.query(
                query_embedding=query_embedding,
                n_results=self.n_results,
            )

        # 3. Retrieve web results from MCP Web Search
        web_results = []
        try:
            tavily_data = _run_mcp_search(question)
            for idx, res in enumerate(tavily_data.get("results", [])):
                chunk = DocumentChunk(
                    id=f"web_search_{idx}",
                    text=res.get("content", ""),
                    embedding=[],
                    source=res.get("url", "")
                )
                score = res.get("score", 1.0)
                web_results.append(SearchResult(chunk=chunk, score=score))
        except Exception as e:
            print(f"Failed to query MCP web search: {e}", file=sys.stderr)

        # Determine if we have high-confidence local results
        confidence_threshold = 0.35
        has_local = len(local_results) > 0 and max(r.score for r in local_results) >= confidence_threshold

        conflict_result = None
        if len(local_results) > 0 and len(web_results) > 0:
            # Invoke conflict detection using any-agent
            try:
                from any_agent import AnyAgent, AgentConfig
                conflict_config = AgentConfig(
                    model_id="openai:qwen",
                    api_base="http://127.0.0.1:8086/v1",
                    api_key="none",
                    instructions=(
                        "You are a factual conflict detector. You are given a user query, "
                        "retrieved internal documents, and retrieved recent web search results. "
                        "Your job is to compare the internal documents and web search results to see "
                        "if there is any contradiction, mismatch, or conflict (e.g., conflicting numbers, "
                        "revenues, dates, status, or features).\n\n"
                        "If a conflict is detected, you MUST start your response with '⚠️ Conflict detected.' "
                        "and summarize what the internal documents say versus what the web sources say. "
                        "Keep it concise and clear.\n"
                        "If NO conflict is detected, reply with exactly: 'No conflict'"
                    ),
                    tools=[],
                    callbacks=[]
                )
                conflict_agent = AnyAgent.create("tinyagent", conflict_config)
                
                conflict_prompt = (
                    f"User Query: {question}\n\n"
                    f"Internal Documents Context:\n{self._build_context(local_results)}\n\n"
                    f"Web Search Context:\n{self._build_context(web_results)}"
                )
                
                agent_run = conflict_agent.run(conflict_prompt)
                run_output = agent_run.final_output.strip()
                if "Conflict detected" in run_output or "⚠️" in run_output:
                    conflict_result = run_output
            except Exception as e:
                print(f"Failed to run conflict agent: {e}", file=sys.stderr)

        # Decide on sources and context to pass to the final LLM generator
        if conflict_result:
            results = local_results + web_results
        elif has_local:
            results = local_results
        else:
            results = web_results

        # 4. Build context block from selected chunks
        context = self._build_context(results)

        # 5. Construct messages
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

        # 6. Generate answer via LLM
        completion = self.llm.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
        )

        final_content = completion.assistant_content or ""
        if conflict_result:
            final_content = f"{conflict_result}\n\n{final_content}"

        return AgentResponse(
            query=question,
            content=final_content,
            sources=results,
            model=completion.model,
            total_tokens=completion.usage.total_tokens,
            conflict=conflict_result,
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
