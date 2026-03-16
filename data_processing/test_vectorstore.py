"""
test_vectorstore.py

Tests retrieval quality from the PCAOB Chroma vector store.

Usage:
    python test_vectorstore.py
    python test_vectorstore.py --query "indemnification clauses"
    python test_vectorstore.py --filter spotlight
"""

import os
import argparse
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

MODEL = "text-embedding-3-small"
COLLECTION_NAME = "pcaob_standards"
CHROMA_PATH = "../data/chroma_db"
ENV_LOC = "../.env"

# Queries that a drafter or reviewer agent would likely make
TEST_QUERIES = [
    "audit committee pre-approval requirements",
    "prohibited non-audit services",
    "indemnification clauses independence",
    "contingent fees",
    "unpaid fees mutual interest",
    "partner rotation requirements",
    "financial relationships independence",
    "tax services financial reporting oversight role",
    "business and employment relationships audit client",
    "auditor independence quality control policies",
]


def get_collection():
    """Connect to the Chroma collection."""
    embedding_function = OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=MODEL
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )
    return collection


def run_query(collection, query: str, n_results: int = 3, where: dict = None):
    """Run a query and print results."""
    kwargs = {
        "query_texts": [query],
        "n_results": n_results,
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    print(f"\n{'='*70}")
    print(f"Query: \"{query}\"")
    if where:
        print(f"Filter: {where}")
    print(f"{'='*70}")

    for i in range(len(results["ids"][0])):
        doc_id = results["ids"][0][i]
        distance = results["distances"][0][i]
        metadata = results["metadatas"][0][i]
        text = results["documents"][0][i]

        heading = metadata.get("heading_chain", "")
        doc_type = metadata.get("document_type", "")
        chunk_type = metadata.get("chunk_type", "")

        print(f"\n  [{i+1}] {doc_id} (distance: {distance:.4f})")
        print(f"      Type: {doc_type} / {chunk_type}")
        print(f"      Heading: {heading}")
        preview = text[:200].replace('\n', ' ')
        print(f"      Preview: {preview}...")


def run_all_tests(collection, n_results: int = 3):
    """Run all test queries."""
    print(f"\nCollection has {collection.count()} documents")

    for query in TEST_QUERIES:
        run_query(collection, query, n_results=n_results)

    # Test metadata filtering
    print(f"\n\n{'#'*70}")
    print("METADATA FILTER TESTS")
    print(f"{'#'*70}")

    run_query(
        collection,
        "independence requirements",
        n_results=3,
        where={"document_type": "spotlight"}
    )

    run_query(
        collection,
        "independence requirements",
        n_results=3,
        where={"document_type": "standard"}
    )


if __name__ == "__main__":
    load_dotenv(ENV_LOC)

    parser = argparse.ArgumentParser(description="Test PCAOB vector store retrieval.")
    parser.add_argument("--query", "-q", help="Run a single query instead of all tests")
    parser.add_argument("--n", type=int, default=3, help="Number of results per query (default: 3)")
    parser.add_argument("--filter", "-f", choices=["standard", "rule", "bulletin", "spotlight"],
                        help="Filter results by document type")
    args = parser.parse_args()

    try:
        collection = get_collection()
        print(f"Connected to collection '{COLLECTION_NAME}' ({collection.count()} documents)")

        if args.query:
            where = {"document_type": args.filter} if args.filter else None
            run_query(collection, args.query, n_results=args.n, where=where)
        else:
            run_all_tests(collection, n_results=args.n)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)
