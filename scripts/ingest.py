"""
Ingest documents into a local vector store using encoderfile for embeddings.

Usage:
    uv run python scripts/ingest.py --corpus-dir corpus/sample
    uv run python scripts/ingest.py --corpus-dir corpus/sample --encoderfile-url http://localhost:8085

This script:
1. Reads all .md and .txt files from the corpus directory
2. Chunks them into overlapping segments
3. Embeds each chunk via the EmbeddingsClient (encoderfile REST API)
4. Returns a list of DocumentChunk objects ready for vector store insertion
"""

import argparse
import sys
from pathlib import Path
from typing import List

# Allow imports from project root when running as `python scripts/ingest.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients import EmbeddingsClient
from models import DocumentChunk


# ---------------------------------------------------------------------------
# 1. Document Reading
# ---------------------------------------------------------------------------

def read_documents(corpus_dir: str) -> List[dict]:
    """Read all markdown and text files from a directory."""
    docs = []
    corpus_path = Path(corpus_dir)

    if not corpus_path.exists():
        print(f"Error: corpus directory '{corpus_dir}' does not exist.")
        return docs

    for ext in ("*.md", "*.txt"):
        for filepath in sorted(corpus_path.rglob(ext)):
            content = filepath.read_text(encoding="utf-8")
            docs.append(
                {
                    "path": str(filepath),
                    "filename": filepath.name,
                    "content": content,
                }
            )

    print(f"Read {len(docs)} documents from {corpus_dir}")
    return docs


# ---------------------------------------------------------------------------
# 2. Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[str]:
    """Split text into overlapping chunks by character count.

    Uses a simple character-based chunking strategy. For a hackathon
    this is fine — production systems would use sentence-aware splitting.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Don't create tiny trailing chunks
        if len(chunk.strip()) < 50 and chunks:
            # Append to previous chunk instead
            chunks[-1] += chunk
        else:
            chunks.append(chunk.strip())

        start += chunk_size - overlap

    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# 3. Embedding via EmbeddingsClient
# ---------------------------------------------------------------------------

def embed_chunks(
    chunks: List[dict],
    embeddings_client: EmbeddingsClient,
    batch_size: int = 32,
) -> List[DocumentChunk]:
    """Embed text chunks in batches and return a list of DocumentChunk models.

    Args:
        chunks: List of dicts with keys 'id', 'source', 'text'.
        embeddings_client: An initialised EmbeddingsClient instance.
        batch_size: Number of texts to embed per request.

    Returns:
        A list of fully-populated DocumentChunk Pydantic models.
    """
    document_chunks: List[DocumentChunk] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_texts = [c["text"] for c in batch]

        response = embeddings_client.get_embeddings(inputs=batch_texts)

        for chunk_meta, embedding_vector in zip(batch, response.embeddings):
            document_chunks.append(
                DocumentChunk(
                    id=chunk_meta["id"],
                    text=chunk_meta["text"],
                    embedding=embedding_vector,
                    source=chunk_meta["source"],
                )
            )

        print(f"  Embedded {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")

    return document_chunks


# ---------------------------------------------------------------------------
# 4. Pipeline
# ---------------------------------------------------------------------------

def ingest(corpus_dir: str, encoderfile_url: str) -> List[DocumentChunk]:
    """Main ingestion pipeline.

    Returns:
        A list of DocumentChunk objects with populated embeddings.
    """

    # 1. Read documents
    docs = read_documents(corpus_dir)
    if not docs:
        print(f"No .md or .txt files found in {corpus_dir}")
        return []

    # 2. Chunk documents
    raw_chunks = []
    for doc in docs:
        doc_chunks = chunk_text(doc["content"])
        for i, chunk_text_content in enumerate(doc_chunks):
            raw_chunks.append(
                {
                    "id": f"{doc['filename']}:chunk_{i}",
                    "source": doc["filename"],
                    "path": doc["path"],
                    "text": chunk_text_content,
                }
            )

    print(f"Created {len(raw_chunks)} chunks from {len(docs)} documents")

    # 3. Embed chunks using the existing EmbeddingsClient
    embeddings_client = EmbeddingsClient(base_url=encoderfile_url)
    print(f"Embedding chunks via {encoderfile_url}...")
    document_chunks = embed_chunks(raw_chunks, embeddings_client)

    print(f"\nIngestion complete:")
    print(f"  {len(docs)} documents")
    print(f"  {len(document_chunks)} chunks with embeddings")
    if document_chunks:
        print(f"  {len(document_chunks[0].embedding)}-dimensional embeddings")

    return document_chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into vector store")
    parser.add_argument(
        "--corpus-dir",
        default="corpus/sample",
        help="Directory containing .md/.txt files",
    )
    parser.add_argument(
        "--encoderfile-url",
        default="http://localhost:8085",
        help="URL of the running encoderfile server",
    )
    args = parser.parse_args()

    chunks = ingest(args.corpus_dir, args.encoderfile_url)

    # Quick preview of results
    if chunks:
        print(f"\n--- Preview of first chunk ---")
        first = chunks[0]
        print(f"ID:     {first.id}")
        print(f"Source: {first.source}")
        print(f"Text:   {first.text[:120]}...")
        print(f"Embed:  [{', '.join(f'{v:.6f}' for v in first.embedding[:4])}, ...]")
