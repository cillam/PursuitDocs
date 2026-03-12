"""
PCAOB JSON Data Validator

Validates and visualizes the structure of scraped PCAOB content JSON files.

Usage:
    python validate_pcaob.py <path>           # Validate a single JSON file
    python validate_pcaob.py <directory>       # Validate all JSON files in directory
    python validate_pcaob.py --all             # Validate everything in data/pcaob_content/

Examples:
    python validate_pcaob.py ../data/pcaob_content/standards/AS_1000.json
    python validate_pcaob.py ../data/pcaob_content/standards/
    python validate_pcaob.py --all
"""

import json
import sys
import os
import re
import numpy as np
from pathlib import Path


BASE_DIR = os.path.join("..", "data", "pcaob_content")


# --- Validation Checks ---

def validate_required_fields(data, filepath):
    """Check that every JSON has required top-level fields."""
    errors = []
    required_top = ["metadata", "content", "footnotes"]
    for field in required_top:
        if field not in data:
            errors.append(f"Missing top-level field: {field}")

    if "metadata" in data:
        required_meta = ["title", "url", "document_type", "scraped_at"]
        for field in required_meta:
            if field not in data["metadata"]:
                errors.append(f"Missing metadata field: {field}")

    if "content" in data:
        for i, section in enumerate(data["content"]):
            required_section = ["heading", "parent", "level", "content"]
            for field in required_section:
                if field not in section:
                    errors.append(f"Section [{i}] missing field: {field}")

    return errors


def validate_no_empty_sections(data, filepath):
    """Check for sections with no content."""
    warnings = []
    if "content" not in data:
        return warnings

    for i, section in enumerate(data["content"]):
        content = section.get("content", "")
        has_tables = bool(section.get("tables", []))
        has_sidebars = bool(section.get("sidebars", []))
        if not content and not has_tables and not has_sidebars:
            warnings.append(f"Section [{i}] \"{section.get('heading', 'unknown')}\" has no content")

    return warnings


def validate_footnote_refs(data, filepath):
    """Check that all footnote_refs reference a footnote that exists."""
    errors = []
    if "content" not in data or "footnotes" not in data:
        return errors

    footnote_keys = set(data["footnotes"].keys())

    for i, section in enumerate(data["content"]):
        refs = section.get("footnote_refs", [])
        for ref in refs:
            if ref not in footnote_keys:
                errors.append(f"Section [{i}] \"{section.get('heading', '')}\" references footnote {ref} which doesn't exist")

        # Also check tables and sidebars for footnote_refs
        for table in section.get("tables", []):
            for ref in table.get("footnote_refs", []):
                if ref not in footnote_keys:
                    errors.append(f"Section [{i}] table \"{table.get('title', '')}\" references footnote {ref} which doesn't exist")
            for entry in table.get("entries", []):
                for ref in entry.get("footnote_refs", []):
                    if ref not in footnote_keys:
                        errors.append(f"Section [{i}] table entry references footnote {ref} which doesn't exist")

        for sidebar in section.get("sidebars", []):
            for ref in sidebar.get("footnote_refs", []):
                if ref not in footnote_keys:
                    errors.append(f"Section [{i}] sidebar \"{sidebar.get('title', '')}\" references footnote {ref} which doesn't exist")

    return errors


def validate_no_inline_footnotes(data, filepath):
    """Check for inline footnote numbers left in content text (e.g., 'users1in')."""
    warnings = []
    if "content" not in data:
        return warnings

    # Pattern: word character, digit(s), word character — no spaces
    pattern = re.compile(r"[a-zA-Z]\d+[a-zA-Z]")

    for i, section in enumerate(data["content"]):
        content = section.get("content", "")
        matches = pattern.findall(content)
        # Filter out legitimate patterns like "AS2101", "QC20", "S2", etc.
        suspicious = [m for m in matches if not re.match(r"^[A-Z]+\d+", m)]
        if suspicious:
            warnings.append(f"Section [{i}] \"{section.get('heading', '')}\" may have inline footnote numbers: {suspicious[:5]}")

    return warnings


# --- Quality Stats ---

def check_quality(data):
    """Print quality statistics about the content."""
    sections = data.get("content", [])
    footnotes = data.get("footnotes", {})

    print("\n  Section Counts by Level:")
    for level in range(1, 5):
        count = len([s for s in sections if s.get("level") == level])
        if count > 0:
            print(f"    Level {level}: {count}")

    print(f"\n  Total sections: {len(sections)}")
    print(f"  Total footnotes: {len(footnotes)}")

    content_lengths = []
    for s in sections:
        total_len = len(s.get("content", ""))
        for table in s.get("tables", []):
            # Count headers/rows
            for row in table.get("rows", []):
                total_len += sum(len(cell) for cell in row)
            for entry in table.get("entries", []):
                total_len += len(entry.get("applicable_standard", ""))
                total_len += len(entry.get("observation", ""))
        for sidebar in s.get("sidebars", []):
            total_len += len(sidebar.get("content", ""))
        content_lengths.append(total_len)

    empty_count = len([s for s in sections
                       if not s.get("content", "")
                       and not s.get("tables", [])
                       and not s.get("sidebars", [])])
    if content_lengths:
        print(f"\n  Content Length Stats (including tables/sidebars):")
        print(f"    Min: {min(content_lengths)}")
        print(f"    Max: {max(content_lengths)}")
        print(f"    Average: {np.mean(content_lengths):.0f}")
        print(f"    Truly empty sections: {empty_count}")

    # Footnote ref coverage
    sections_with_refs = 0
    for s in sections:
        has_refs = bool(s.get("footnote_refs", []))
        if not has_refs:
            for table in s.get("tables", []):
                if table.get("footnote_refs", []):
                    has_refs = True
                    break
                for entry in table.get("entries", []):
                    if entry.get("footnote_refs", []):
                        has_refs = True
                        break
                if has_refs:
                    break
        if not has_refs:
            for sidebar in s.get("sidebars", []):
                if sidebar.get("footnote_refs", []):
                    has_refs = True
                    break
        if has_refs:
            sections_with_refs += 1
    print(f"\n  Sections with footnote refs: {sections_with_refs}/{len(sections)}")


# --- Structure Visualization ---

def print_structure(data):
    """Print indented outline of the document structure."""
    sections = data.get("content", [])
    title = data.get("metadata", {}).get("title", "Unknown")

    print(f"\n  Indented Structure:")
    print(f"  {title}")

    for section in sections:
        level = section.get("level", 1)
        heading = section.get("heading", "unknown")
        content_len = len(section.get("content", ""))
        refs = section.get("footnote_refs", [])
        tables = section.get("tables", [])

        # Collect all refs including from table entries
        all_refs = list(refs)
        for table in tables:
            all_refs.extend(table.get("footnote_refs", []))
            for entry in table.get("entries", []):
                all_refs.extend(entry.get("footnote_refs", []))

        ref_str = f" [fn: {','.join(all_refs)}]" if all_refs else ""
        table_str = f" [{len(tables)} table(s)]" if tables else ""
        sidebars = section.get("sidebars", [])
        sidebar_str = f" [{len(sidebars)} sidebar(s)]" if sidebars else ""
        len_str = f" ({content_len} chars)"

        if level == 1 and heading != title:
            print(f"\n  ● {heading}{len_str}{ref_str}{table_str}{sidebar_str}")
        elif level == 2:
            print(f"    ├── {heading}{len_str}{ref_str}{table_str}{sidebar_str}")
        elif level == 3:
            print(f"    │   └── {heading}{len_str}{ref_str}{table_str}{sidebar_str}")



# --- Main ---

def validate_file(filepath):
    """Run all validations on a single JSON file."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*70}")
    print(f"  {filename}")
    print(f"{'='*70}")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ❌ Failed to load: {e}")
        return False

    doc_type = data.get("metadata", {}).get("document_type", "unknown")
    title = data.get("metadata", {}).get("title", "unknown")
    print(f"  Type: {doc_type}")
    print(f"  Title: {title}")

    # Run validations
    all_errors = []
    all_warnings = []

    print(f"\n  Validation Checks:")

    errors = validate_required_fields(data, filepath)
    all_errors.extend(errors)
    print(f"    {'❌' if errors else '✅'} Required fields ({len(errors)} issues)")

    warnings = validate_no_empty_sections(data, filepath)
    all_warnings.extend(warnings)
    print(f"    {'⚠️ ' if warnings else '✅'} No empty sections ({len(warnings)} issues)")

    errors = validate_footnote_refs(data, filepath)
    all_errors.extend(errors)
    print(f"    {'❌' if errors else '✅'} Footnote refs valid ({len(errors)} issues)")

    warnings_fn = validate_no_inline_footnotes(data, filepath)
    all_warnings.extend(warnings_fn)
    print(f"    {'⚠️ ' if warnings_fn else '✅'} No inline footnote numbers ({len(warnings_fn)} issues)")

    # Print details
    if all_errors:
        print(f"\n  ❌ ERROR DETAILS:")
        for err in all_errors:
            print(f"    • {err}")

    if all_warnings:
        print(f"\n  ⚠️  WARNING DETAILS:")
        for warn in all_warnings:
            print(f"    • {warn}")

    # Quality stats
    check_quality(data)

    # Structure
    print_structure(data)

    return len(all_errors) == 0


def validate_directory(dirpath):
    """Validate all JSON files in a directory."""
    json_files = sorted(Path(dirpath).glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {dirpath}")
        return

    print(f"\nValidating {len(json_files)} files in {dirpath}")

    results = {"pass": 0, "fail": 0}
    for filepath in json_files:
        passed = validate_file(str(filepath))
        if passed:
            results["pass"] += 1
        else:
            results["fail"] += 1

    print(f"\n{'='*70}")
    print(f"  SUMMARY: {results['pass']} passed, {results['fail']} failed out of {len(json_files)} files")
    print(f"{'='*70}")


def validate_all():
    """Validate everything in the PCAOB content directory."""
    for subdir in ["standards", "rules", "bulletins", "spotlights"]:
        dirpath = os.path.join(BASE_DIR, subdir)
        if os.path.isdir(dirpath):
            validate_directory(dirpath)

    # Also check the index
    index_path = os.path.join(BASE_DIR, "index.json")
    if os.path.exists(index_path):
        print(f"\n{'='*70}")
        print(f"  INDEX CHECK")
        print(f"{'='*70}")
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        print(f"  Total items in index: {index.get('total_items', 0)}")
        print(f"  Generated at: {index.get('generated_at', 'unknown')}")

        # Count by type
        items = index.get("items", [])
        types = {}
        for item in items:
            doc_type = item.get("document_type", "unknown")
            types[doc_type] = types.get(doc_type, 0) + 1
        print(f"  By type: {types}")

        # Check that every JSON file in the directories is in the index
        all_json_files = set()
        for subdir in ["standards", "rules", "bulletins", "spotlights"]:
            dirpath = os.path.join(BASE_DIR, subdir)
            if os.path.isdir(dirpath):
                for f in Path(dirpath).glob("*.json"):
                    all_json_files.add(f.name)

        indexed_files = set()
        for item in items:
            if "filename" in item:
                indexed_files.add(item["filename"])
            elif "standard_number" in item:
                indexed_files.add(item["standard_number"].replace(" ", "_") + ".json")
            elif "title" in item:
                indexed_files.add(re.sub(r"[^\w\s-]", "", item["title"]).strip().replace(" ", "_").lower() + ".json")

        missing_from_index = all_json_files - indexed_files
        if missing_from_index:
            print(f"\n  ⚠️  Files not in index: {missing_from_index}")
        else:
            print(f"\n  ✅ All files accounted for in index")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]

    if target == "--all":
        validate_all()
    elif os.path.isfile(target):
        validate_file(target)
    elif os.path.isdir(target):
        validate_directory(target)
    else:
        print(f"❌ Not found: {target}")
        sys.exit(1)
