import sys
from scripts.ingest import ingest
from clients import ChromaService
from agent import RAGAgent


def main():
    # 1. Ingest corpus and store in ChromaDB
    print("=== 1. Ingesting Corpus ===")
    chunks = ingest("corpus/sample", "http://localhost:8085")
    if not chunks:
        print("No chunks produced. Exiting.", file=sys.stderr)
        return

    chroma = ChromaService(persist_dir="./chroma_db", collection_name="documents")
    chroma.add_chunks(chunks)
    print(f"Collection size: {chroma.count()} chunks\n")

    # 2. Initialise the RAG Agent
    print("=== 2. RAG Agent Ready ===")
    agent = RAGAgent()

    # 3. Ask questions
    questions = [
        "What is MCP and how does it work?",
        "What are the key features of MCP servers?",
    ]

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"{'='*60}")

        response = agent.ask(question)

        print(f"\nA: {response.content}")
        print(f"\n--- Metadata ---")
        print(f"Model: {response.model}")
        print(f"Tokens: {response.total_tokens}")
        print(f"Sources used:")
        for i, src in enumerate(response.sources, start=1):
            print(f"  [{i}] {src.chunk.source} (confidence: {src.score * 100:.1f}%)")


if __name__ == "__main__":
    main()
