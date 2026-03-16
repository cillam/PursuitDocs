"""
chunk_pcaob.py

Chunks PCAOB JSON content for embedding into a vector store.

Usage:
    python chunk_pcaob.py <path_to_json> [--threshold 512] [-o output_path]
    python chunk_pcaob.py ../data/pcaob_content/standards/as_1000.json
    python chunk_pcaob.py ../data/pcaob_content/ --all
    python chunk_pcaob.py ../data/pcaob_content/ --all -o ../data/pcaob_chunks.json

Output defaults to data/pcaob_chunks.json.

Chunking rules:
    - Each section under a heading is the base unit
    - Footnotes appended to the chunk via [fn_X] markers
    - Full parent heading chain in metadata
    - 512 token threshold (tiktoken, OpenAI cl100k_base)
    - Never split after :\n\n (colon + double newline = intro to list)

    Standards:  Split between numbered paragraphs (.01, .02, etc.)
    Rules:      Split at last paragraph boundary (\n\n)
    Bulletins:  Split at last paragraph boundary (\n\n)
    Spotlights: Split at table row or paragraph boundary
"""

import json
import re
import argparse
import tiktoken
from pathlib import Path


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

# cl100k_base is the tokenizer for text-embedding-3-small and text-embedding-3-large
enc = tiktoken.get_encoding("cl100k_base")
THRESHOLD = 512


def count_tokens(text: str) -> int:
    """Count tokens using OpenAI's cl100k_base tokenizer."""
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# Footnote helpers
# ---------------------------------------------------------------------------

def extract_footnote_refs(text: str) -> list[str]:
    """Find all [fn_X] markers in text and return the footnote numbers."""
    return re.findall(r'\[fn_(\d+)\]', text)


def build_footnote_text(text: str, footnotes: dict) -> str:
    """Build the footnote appendix for a chunk based on [fn_X] markers in the text."""
    refs = extract_footnote_refs(text)
    if not refs:
        return ""
    lines = []
    for ref in sorted(set(refs), key=int):
        if ref in footnotes:
            lines.append(f"[fn_{ref}]: {footnotes[ref]}")
    if lines:
        return "\n\n---\nFootnotes:\n" + "\n".join(lines)
    return ""


def attach_footnotes(text: str, footnotes: dict) -> str:
    """Return text with its referenced footnotes appended."""
    fn_text = build_footnote_text(text, footnotes)
    return text + fn_text


# ---------------------------------------------------------------------------
# Heading chain
# ---------------------------------------------------------------------------

def build_heading_chain(section: dict, all_sections: list) -> str:
    """Build the full parent heading chain for a section.
    
    E.g., "Appendix: PCAOB Inspection Categories > Global Network Firm (GNF)"
    """
    chain = [section["heading"]]
    parent = section.get("parent")
    
    # Walk up the parent chain
    while parent:
        chain.insert(0, parent)
        # Find the parent section to check if it also has a parent
        parent_section = next((s for s in all_sections if s["heading"] == parent), None)
        if parent_section:
            parent = parent_section.get("parent")
        else:
            parent = None
    
    return " > ".join(chain)


# ---------------------------------------------------------------------------
# Splitting logic
# ---------------------------------------------------------------------------

# Pattern for numbered paragraphs in standards: .01, .02, etc.
NUMBERED_PARA_RE = re.compile(r'(?=\.\d{2}\s)')

# Pattern for colon + double newline (intro to list — do NOT split here)
COLON_NEWLINE_RE = re.compile(r':\n\n')


def is_colon_split(text: str, split_pos: int) -> bool:
    """Check if a split position falls right after a colon + \\n\\n pattern.
    
    We look backward from split_pos to see if the preceding paragraph 
    ends with a colon.
    """
    # Find the \n\n that precedes this split position
    # The split_pos should be at the start of a new paragraph
    # Check if the text just before the \n\n ends with ':'
    before = text[:split_pos].rstrip('\n')
    return before.endswith(':')


def find_paragraph_boundaries(text: str) -> list[int]:
    """Find all positions where paragraphs start (after \\n\\n).
    
    Returns positions of the first character after each \\n\\n.
    """
    boundaries = []
    for match in re.finditer(r'\n\n', text):
        pos = match.end()
        if pos < len(text):
            boundaries.append(pos)
    return boundaries


def find_numbered_section_boundaries(text: str) -> list[int]:
    """Find boundaries between numbered sections (.01, .02, etc.) in standards.
    
    Returns positions where each numbered section starts.
    """
    boundaries = []
    for match in NUMBERED_PARA_RE.finditer(text):
        if match.start() > 0:  # Don't include position 0
            boundaries.append(match.start())
    return boundaries


def split_standards(text: str, footnotes: dict, threshold: int) -> list[str]:
    """Split standards content between numbered paragraph boundaries.
    
    Keep adding numbered paragraphs until the next would push over threshold.
    If no numbered paragraphs, fall back to paragraph boundary splitting.
    """
    boundaries = find_numbered_section_boundaries(text)
    
    if not boundaries:
        # No numbered sections — fall back to paragraph splitting
        return split_at_paragraphs(text, footnotes, threshold)
    
    # Add start and end positions
    boundaries = [0] + boundaries + [len(text)]
    
    chunks = []
    current_start = 0
    current_end = boundaries[1] if len(boundaries) > 1 else len(text)
    
    for i in range(2, len(boundaries)):
        next_end = boundaries[i]
        candidate = text[current_start:next_end]
        candidate_with_fn = attach_footnotes(candidate, footnotes)
        
        if count_tokens(candidate_with_fn) > threshold:
            # Adding the next numbered section would exceed threshold
            # Finalize current chunk
            chunk_text = text[current_start:current_end]
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
            current_start = current_end
            current_end = next_end
        else:
            current_end = next_end
    
    # Don't forget the last chunk
    remaining = text[current_start:].strip()
    if remaining:
        chunks.append(remaining)
    
    return chunks


def split_at_paragraphs(text: str, footnotes: dict, threshold: int) -> list[str]:
    """Split at paragraph boundaries (\\n\\n), respecting the colon rule.
    
    Used for rules, bulletins, and standards without numbered sections.
    """
    boundaries = find_paragraph_boundaries(text)
    
    if not boundaries:
        # No paragraph breaks — return as-is even if over threshold
        return [text.strip()]
    
    # Add start position
    boundaries = [0] + boundaries
    
    chunks = []
    current_start = 0
    current_end_idx = 1  # Index into boundaries
    
    for i in range(2, len(boundaries)):
        next_pos = boundaries[i]
        candidate = text[current_start:next_pos]
        candidate_with_fn = attach_footnotes(candidate, footnotes)
        
        if count_tokens(candidate_with_fn) > threshold:
            # Check colon rule: don't split if previous paragraph ends with ':'
            if is_colon_split(text, boundaries[current_end_idx]):
                # Can't split here — keep going
                current_end_idx = i
                continue
            
            # Finalize current chunk
            chunk_text = text[current_start:boundaries[current_end_idx]]
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
            current_start = boundaries[current_end_idx]
            current_end_idx = i
        else:
            current_end_idx = i
    
    # Last chunk
    remaining = text[current_start:].strip()
    if remaining:
        chunks.append(remaining)
    
    return chunks


def split_spotlight_table(table: dict, footnotes: dict, threshold: int) -> list[str]:
    """Split a spotlight observation table into chunks.
    
    Each table entry (applicable_standard + observation pair) or table row 
    is a potential split point.
    """
    if "entries" in table:
        # Observation tables with applicable_standard / observation pairs
        chunks = []
        current_parts = []
        current_text = ""
        
        # Include the percentage row table if present as header context
        header = table.get("title", "")
        
        for entry in table["entries"]:
            entry_text = f"Applicable Standard or Rule:\n{entry['applicable_standard']}\n\nPCAOB Observation:\n{entry['observation']}"
            combined = current_text + ("\n\n" if current_text else "") + entry_text
            combined_with_fn = attach_footnotes(combined, footnotes)
            
            if current_text and count_tokens(combined_with_fn) > threshold:
                # Adding this entry would exceed threshold — finalize current
                if current_text.strip():
                    chunks.append(current_text.strip())
                current_text = entry_text
            else:
                current_text = combined
        
        if current_text.strip():
            chunks.append(current_text.strip())
        
        return chunks
    
    elif "rows" in table:
        # Data tables (like Figure 3 percentages) — keep as one chunk
        header_row = " | ".join(table.get("headers", []))
        rows = [" | ".join(row) for row in table["rows"]]
        table_text = f"{table.get('title', '')}\n{header_row}\n" + "\n".join(rows)
        return [table_text.strip()]
    
    else:
        # Description-only tables (like Figure 2)
        desc = table.get("description", table.get("title", ""))
        return [desc.strip()] if desc.strip() else []


# ---------------------------------------------------------------------------
# Main chunking
# ---------------------------------------------------------------------------

def chunk_section(section: dict, all_sections: list, footnotes: dict, 
                  doc_type: str, doc_metadata: dict, threshold: int) -> list[dict]:
    """Chunk a single section and return a list of chunk dicts with metadata."""
    
    heading_chain = build_heading_chain(section, all_sections)
    content = section.get("content", "")
    chunks = []
    
    # Build base metadata for all chunks from this section
    base_meta = {
        "heading": section["heading"],
        "heading_chain": heading_chain,
        "parent": section.get("parent"),
        "level": section.get("level"),
        "document_type": doc_type,
        "source_title": doc_metadata.get("title", ""),
        "source_url": doc_metadata.get("url", ""),
    }
    
    # If a standard/rule number is in the metadata, include it
    if "standard_number" in doc_metadata:
        base_meta["standard_number"] = doc_metadata["standard_number"]
    
    # --- Chunk the main content ---
    if content.strip():
        content_with_fn = attach_footnotes(content, footnotes)
        
        if count_tokens(content_with_fn) <= threshold:
            # Fits in one chunk
            chunks.append({
                "text": content_with_fn,
                "metadata": {**base_meta, "chunk_type": "content"}
            })
        else:
            # Need to split
            if doc_type == "standard":
                split_texts = split_standards(content, footnotes, threshold)
            else:
                # rules, bulletins, spotlights — split at paragraphs
                split_texts = split_at_paragraphs(content, footnotes, threshold)
            
            for i, chunk_text in enumerate(split_texts):
                chunk_with_fn = attach_footnotes(chunk_text, footnotes)
                chunks.append({
                    "text": chunk_with_fn,
                    "metadata": {**base_meta, "chunk_type": "content", "chunk_part": i + 1}
                })
    
    # --- Chunk sidebars ---
    for sidebar in section.get("sidebars", []):
        sidebar_text = f"{sidebar['title']}\n\n{sidebar['content']}"
        sidebar_with_fn = attach_footnotes(sidebar_text, footnotes)
        chunks.append({
            "text": sidebar_with_fn,
            "metadata": {**base_meta, "chunk_type": "sidebar", "sidebar_title": sidebar["title"]}
        })
    
    # --- Chunk tables ---
    for table in section.get("tables", []):
        if doc_type == "spotlight" and "entries" in table:
            # Spotlight observation tables — may need splitting
            table_chunks = split_spotlight_table(table, footnotes, threshold)
            for i, chunk_text in enumerate(table_chunks):
                chunk_with_fn = attach_footnotes(chunk_text, footnotes)
                meta = {**base_meta, "chunk_type": "observation_table", "table_title": table.get("title", "")}
                if len(table_chunks) > 1:
                    meta["chunk_part"] = i + 1
                chunks.append({"text": chunk_with_fn, "metadata": meta})
        else:
            # Data tables — keep as one chunk with parent heading
            table_texts = split_spotlight_table(table, footnotes, threshold)
            for t_text in table_texts:
                if t_text.strip():
                    chunk_with_fn = attach_footnotes(t_text, footnotes)
                    chunks.append({
                        "text": chunk_with_fn,
                        "metadata": {**base_meta, "chunk_type": "table", "table_title": table.get("title", "")}
                    })
    
    return chunks


def chunk_document(filepath: str, threshold: int = THRESHOLD) -> list[dict]:
    """Chunk an entire PCAOB JSON document.
    
    Returns a list of chunk dicts, each with 'text' and 'metadata'.
    """
    with open(filepath) as f:
        data = json.load(f)
    
    metadata = data.get("metadata", {})
    footnotes = data.get("footnotes", {})
    doc_type = metadata.get("document_type", "unknown")
    sections = data.get("content", [])
    
    all_chunks = []
    
    for section in sections:
        section_chunks = chunk_section(
            section=section,
            all_sections=sections,
            footnotes=footnotes,
            doc_type=doc_type,
            doc_metadata=metadata,
            threshold=threshold
        )
        all_chunks.extend(section_chunks)
    
    return all_chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_chunk_stats(chunks: list[dict]):
    """Print summary statistics about the chunks."""
    token_counts = [count_tokens(c["text"]) for c in chunks]
    
    print(f"\n{'='*60}")
    print(f"Chunking Results")
    print(f"{'='*60}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Token counts — min: {min(token_counts)}, max: {max(token_counts)}, "
          f"avg: {sum(token_counts) / len(token_counts):.0f}")
    
    over_threshold = sum(1 for t in token_counts if t > THRESHOLD)
    if over_threshold:
        print(f"WARNING: {over_threshold} chunks exceed {THRESHOLD} token threshold")
    
    print(f"\nChunks by type:")
    type_counts = {}
    for c in chunks:
        ct = c["metadata"].get("chunk_type", "unknown")
        type_counts[ct] = type_counts.get(ct, 0) + 1
    for ct, count in sorted(type_counts.items()):
        print(f"  {ct}: {count}")
    
    print(f"\nFirst 5 chunks preview:")
    for i, chunk in enumerate(chunks[:5]):
        tokens = count_tokens(chunk["text"])
        heading = chunk["metadata"].get("heading_chain", "")
        chunk_type = chunk["metadata"].get("chunk_type", "")
        print(f"\n  [{i+1}] {heading} ({chunk_type}, {tokens} tokens)")
        preview = chunk["text"][:150].replace('\n', ' ')
        print(f"      {preview}...")


def main():
    parser = argparse.ArgumentParser(description="Chunk PCAOB JSON content for vector store ingestion.")
    parser.add_argument("path", help="Path to a JSON file or directory of JSON files")
    parser.add_argument("--all", action="store_true", help="Process all JSON files in directory recursively")
    parser.add_argument("--threshold", type=int, default=THRESHOLD, help=f"Token threshold (default: {THRESHOLD})")
    parser.add_argument("--output", "-o", default="../data/pcaob_chunks.json",
                        help="Output JSON file for chunks (default: data/pcaob_chunks.json)")
    
    args = parser.parse_args()
    path = Path(args.path)
    
    if path.is_file():
        files = [path]
    elif path.is_dir() and args.all:
        files = sorted(path.rglob("*.json"))
        # Skip index.json or other non-content files
        files = [f for f in files if f.name != "index.json"]
    else:
        parser.error(f"Path {path} is not a file. Use --all to process a directory.")
        return
    
    all_chunks = []
    
    for filepath in files:
        print(f"\nProcessing: {filepath}")
        chunks = chunk_document(str(filepath), threshold=args.threshold)
        all_chunks.extend(chunks)
        print(f"  → {len(chunks)} chunks")
    
    print_chunk_stats(all_chunks)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_chunks, f, indent=2)
    print(f"\nChunks written to: {output_path}")


if __name__ == "__main__":
    main()