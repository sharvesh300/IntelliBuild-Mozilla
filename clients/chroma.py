import chromadb
from typing import List, Optional

from models import DocumentChunk, SearchResult


class ChromaService:
    """Service wrapper for ChromaDB vector store operations."""

    def __init__(
        self,
        persist_dir: str = "./chroma_db",
        collection_name: str = "documents",
    ):
        """
        Initialise the ChromaDB persistent client and collection.

        Args:
            persist_dir: Directory for on-disk persistence.
            collection_name: Name of the collection to create or retrieve.
        """
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Add a list of DocumentChunk objects to the collection.

        Args:
            chunks: Pre-embedded DocumentChunk models produced by the ingest pipeline.
        """
        if not chunks:
            return

        self.collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=[c.embedding for c in chunks],
            metadatas=[{"source": c.source} for c in chunks],
        )
        print(f"Added {len(chunks)} chunks to collection '{self.collection.name}'")

    def add_chunk(self, chunk: DocumentChunk) -> None:
        """Add a single DocumentChunk to the collection."""
        self.add_chunks([chunk])

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
    ) -> List[SearchResult]:
        """
        Query the collection with a pre-computed embedding vector.

        Args:
            query_embedding: The embedding vector to search with.
            n_results: Number of results to return.

        Returns:
            A list of SearchResult models ordered by relevance.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "embeddings", "distances"],
        )

        search_results: List[SearchResult] = []

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        embeddings = results["embeddings"][0]
        distances = results["distances"][0]

        for doc_id, text, meta, emb, distance in zip(
            ids, documents, metadatas, embeddings, distances
        ):
            chunk = DocumentChunk(
                id=doc_id,
                text=text,
                embedding=emb,
                source=meta.get("source", ""),
            )
            # Chroma cosine distance is in [0, 2]; convert to a similarity score in [0, 1]
            score = 1.0 - (distance / 2.0)
            search_results.append(SearchResult(chunk=chunk, score=score))

        return search_results

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of items in the collection."""
        return self.collection.count()

    def delete_collection(self) -> None:
        """Delete the current collection."""
        self.client.delete_collection(name=self.collection.name)
        print(f"Deleted collection '{self.collection.name}'")
