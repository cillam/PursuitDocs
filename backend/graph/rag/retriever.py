"""
retriever.py

Shared retrieval interface for the PCAOB Chroma vector store.

Provides functions for connecting to the vector store and querying
for relevant PCAOB standards, rules, and guidance.

Usage (run from backend/):
    python -m graph.rag.retriever --query "auditor objectivity"
    python -m graph.rag.retriever --query "contingent fees" --filter rule --n 5
"""

import argparse
import json
import os

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

ENV_LOC = '../../secrets/pursuitdocs/backend/.env'
CHROMA_PATH = "../data/chroma_db" if os.getenv("ENVIRONMENT", "local") == "local" else "/tmp/chroma_db"
COLLECTION_NAME = "pcaob_standards"
EMBEDDING_MODEL = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_collection = None


def get_collection():
    """Connect to the PCAOB Chroma collection.

    Caches the connection so repeated calls don't re-initialize.
    """
    global _collection
    if _collection is not None:
        return _collection

    embedding_function = OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=EMBEDDING_MODEL,
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    _collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
    )
    return _collection


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    n_results: int = 3,
    document_type: str = None,
    collection=None,
) -> list[dict]:
    """Query the vector store and return matching chunks with metadata.

    Args:
        query: The search query (a concept, not exact text)
        n_results: Number of results to return
        document_type: Optional filter — "standard", "rule", "bulletin", or "spotlight"
        collection: Optional pre-connected collection (uses cached default if None)

    Returns:
        List of dicts, each with:
            - text: The chunk content
            - heading_chain: Full heading hierarchy
            - document_type: standard, rule, bulletin, or spotlight
            - source_title: Title of the source document
            - standard_number: Standard or rule number (e.g., "Rule 3520")
            - distance: Similarity distance (lower = more similar)
    """
    if collection is None:
        collection = get_collection()

    kwargs = {
        "query_texts": [query],
        "n_results": n_results,
    }
    if document_type:
        kwargs["where"] = {"document_type": document_type}

    results = collection.query(**kwargs)

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "heading_chain": results["metadatas"][0][i].get("heading_chain", ""),
            "document_type": results["metadatas"][0][i].get("document_type", ""),
            "source_title": results["metadatas"][0][i].get("source_title", ""),
            "standard_number": results["metadatas"][0][i].get("standard_number", ""),
            "distance": results["distances"][0][i],
        })
    return chunks


def retrieve_multi(
    queries: list[str],
    n_results: int = 3,
    document_type: str = None,
    deduplicate: bool = True,
) -> list[dict]:
    """Run multiple queries and return combined results.

    Useful when the reviewer has multiple findings and needs standards
    for each one. Optionally deduplicates by chunk text.

    Args:
        queries: List of search queries
        n_results: Number of results per query
        document_type: Optional filter by document type
        deduplicate: If True, remove duplicate chunks across queries

    Returns:
        Combined list of chunk dicts
    """
    all_chunks = []
    seen_texts = set()

    for query in queries:
        chunks = retrieve(query, n_results=n_results, document_type=document_type)
        for chunk in chunks:
            if deduplicate:
                if chunk["text"] in seen_texts:
                    continue
                seen_texts.add(chunk["text"])
            all_chunks.append(chunk)

    return all_chunks


def format_chunks_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks into a string suitable for an LLM prompt.

    Args:
        chunks: List of chunk dicts from retrieve()

    Returns:
        Formatted string with source info and content for each chunk
    """
    sections = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["source_title"]
        standard = chunk["standard_number"]
        heading = chunk["heading_chain"]
        text = chunk["text"]

        sections.append(
            f"[{i}] {source} {standard}\n"
            f"    Section: {heading}\n"
            f"    Content: {text}"
        )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Query the PCAOB vector store."
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Search query",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=3,
        help="Number of results (default: 3)",
    )
    parser.add_argument(
        "--filter", "-f",
        choices=["standard", "rule", "bulletin", "spotlight"],
        help="Filter by document type",
    )

    args = parser.parse_args()

    load_dotenv(ENV_LOC)

    chunks = retrieve(args.query, n_results=args.n, document_type=args.filter)

    print(f"\nQuery: \"{args.query}\"")
    if args.filter:
        print(f"Filter: {args.filter}")
    print(f"Results: {len(chunks)}")

    for i, chunk in enumerate(chunks, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] {chunk['source_title']} {chunk['standard_number']}")
        print(f"    Section: {chunk['heading_chain']}")
        print(f"    Distance: {chunk['distance']:.4f}")
        print(f"    Type: {chunk['document_type']}")
        preview = chunk["text"][:300].replace("\n", " ")
        print(f"    Preview: {preview}...")


if __name__ == "__main__":
    main()
