"""
create_vectorstore.py

Ingests chunked PCAOB content into a Chroma vector store.

Usage:
    python create_vectorstore.py
    python create_vectorstore.py --input ../data/pcaob_chunks.json
    python create_vectorstore.py --reset  # Delete and recreate the collection
"""

import os
import json
import argparse
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

MODEL = "text-embedding-3-small"
COLLECTION_NAME = "pcaob_standards"
CHUNKS_PATH = "../data/pcaob_chunks.json"
CHROMA_PATH = "../data/chroma_db"
ENV_LOC = "../.env"


def prepare_metadata(metadata: dict) -> dict:
    """Prepare metadata for Chroma storage.
    
    Chroma metadata values must be strings, ints, floats, or bools.
    Convert any None values and lists to strings.
    """
    cleaned = {}
    for key, value in metadata.items():
        if value is None:
            continue
        elif isinstance(value, list):
            cleaned[key] = ", ".join(str(v) for v in value)
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


def ingest_chunks(chunks_path: str, reset: bool = False):
    """Load chunks from JSON and ingest into Chroma."""

    # Load chunks
    with open(chunks_path, "r") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks from {chunks_path}")

    # Set up embedding function
    embedding_function = OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=MODEL
    )

    # Create persistent Chroma client
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Reset collection if requested
    if reset:
        try:
            client.delete_collection(name=COLLECTION_NAME)
            print(f"Deleted existing collection: {COLLECTION_NAME}")
        except ValueError:
            pass

    # Create or get collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )

    # Prepare data for Chroma
    ids = [f"chunk_{i:04d}" for i in range(len(chunks))]
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [prepare_metadata(chunk["metadata"]) for chunk in chunks]

    # Ingest in batches (Chroma recommends batches of ~5000)
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        batch_end = min(i + batch_size, len(documents))
        collection.add(
            ids=ids[i:batch_end],
            documents=documents[i:batch_end],
            metadatas=metadatas[i:batch_end]
        )
        print(f"  Ingested chunks {i} - {batch_end - 1}")

    print(f"\nDone. {len(documents)} chunks ingested into collection '{COLLECTION_NAME}'")
    print(f"Chroma DB path: {CHROMA_PATH}")


if __name__ == "__main__":
    load_dotenv(ENV_LOC)

    parser = argparse.ArgumentParser(description="Ingest PCAOB chunks into Chroma.")
    parser.add_argument("--input", "-i", default=CHUNKS_PATH,
                        help=f"Path to chunks JSON (default: {CHUNKS_PATH})")
    parser.add_argument("--reset", action="store_true",
                        help="Delete and recreate the collection before ingesting")
    args = parser.parse_args()

    try:
        ingest_chunks(args.input, reset=args.reset)
    except Exception as e:
        print(f"\n❌ Failed to ingest: {e}")
        exit(1)