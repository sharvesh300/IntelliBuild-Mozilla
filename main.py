import sys
from scripts.ingest import ingest
from clients import EmbeddingsClient, ChromaService


def main():
    # 1. Ingest corpus and embed chunks
    print("=== 1. Ingesting Corpus ===")
    chunks = ingest("corpus/sample", "http://localhost:8085")
    if not chunks:
        print("No chunks produced. Exiting.", file=sys.stderr)
        return

    # 2. Store in ChromaDB
    print("\n=== 2. Storing in ChromaDB ===")
    chroma = ChromaService(persist_dir="./chroma_db", collection_name="documents")
    chroma.add_chunks(chunks)
    print(f"Collection size: {chroma.count()} chunks")

    # 3. Query with semantic search
    print("\n=== 3. Semantic Search ===")
    embed_client = EmbeddingsClient(base_url="http://localhost:8085")

    query = "What is MCP and how does it work?"
    print(f"Query: \"{query}\"")

    query_embedding = embed_client.get_embeddings(inputs=[query]).first_embedding
    results = chroma.query(query_embedding=query_embedding, n_results=3)

    print(f"\nTop {len(results)} results:\n")
    for i, result in enumerate(results, start=1):
        confidence = result.score * 100
        print(f"  [{i}] Confidence: {confidence:.1f}%  |  ID: {result.chunk.id}")
        print(f"      Source: {result.chunk.source}")
        print(f"      Text:   {result.chunk.text[:120]}...")
        print()


if __name__ == "__main__":
    main()
