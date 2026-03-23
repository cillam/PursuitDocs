"""
reviewer.py

Reviews a proposal transmittal letter for auditor independence concerns.

Two-pass approach:
    Pass 1: Identify potential independence issues in the letter
    Pass 2: Retrieve PCAOB standards via RAG and attach citations to each finding

Inputs:
    - Draft letter (str): output from drafter.py

Output:
    {
        "findings": [
            {
                "flagged_text": "...",
                "reason": "...",
                "pcaob_citation": "...",
                "suggested_alternative": "..."
            }
        ],
        "status": "issues_found" | "clean"
    }

Usage (run from backend/):
    python -m graph.agents.reviewer <letter_file>
    python -m graph.agents.reviewer --text "Dear Ms. Cushman..."
"""

import argparse
import json
import os
import re

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.rag.retriever import get_collection, retrieve, format_chunks_for_prompt

ENV_LOC = '../../secrets/pursuitdocs/backend/.env'
MODEL = "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

PASS_1_SYSTEM = """You are an expert auditor independence reviewer. Your task is to review a proposal transmittal letter for potential auditor independence concerns under PCAOB standards.

Independence is the foundation of the audit profession. The auditor must maintain both independence in fact and independence in appearance. Any language in a proposal letter that could suggest the auditor lacks objectivity, has a personal stake in the engagement outcome, or prioritizes the client relationship over professional duty is a potential concern.

Review the letter for the following categories of independence issues:

OBJECTIVITY AND PROFESSIONAL SKEPTICISM:
- Language suggesting the auditor will act in the client's interest rather than the public interest
- Promises of specific outcomes or benefits from the audit
- Language implying a personal relationship or special treatment beyond professional service
- Words like "partner," "benefit," "personal attention," "mutual," "aligned interests"
- Any suggestion that the audit outcome is predetermined or guaranteed

PROHIBITED RELATIONSHIPS AND SERVICES:
- Language suggesting the auditor will provide management advisory functions
- Offering to make decisions on behalf of the client
- Blurring the line between auditor and management roles
- Suggesting ongoing consulting beyond the audit scope

FINANCIAL INTERESTS AND FEES:
- Contingent fee arrangements or language implying fees tied to outcomes
- Indemnification language
- Suggesting the audit fee is an investment that will pay for itself

SCOPE AND BOUNDARY ISSUES:
- Overpromising deliverables beyond what an independent auditor should offer
- Language suggesting the auditor will advocate for the client
- Commitments that could compromise the auditor's ability to issue an adverse opinion if warranted

For each concern you identify, provide:
1. flagged_text: The exact text from the letter that is problematic
2. reason: Why this language raises an independence concern
3. search_concept: A short phrase (2-5 words) describing the independence concept at issue, suitable for searching PCAOB standards (e.g., "auditor objectivity impartiality", "prohibited financial interest", "management advisory role")

If you find no independence concerns, respond with an empty findings list.

Respond ONLY with valid JSON matching this structure. Do not include any other text, markdown formatting, or code fences.

{
    "findings": [
        {
            "flagged_text": "...",
            "reason": "...",
            "search_concept": "..."
        }
    ]
}"""


PASS_2_SYSTEM = """You are an expert auditor independence reviewer. You previously reviewed a proposal transmittal letter and identified potential independence concerns. You have now been provided with relevant PCAOB standards and guidance for each finding.

Your task is to finalize each finding by:
1. Confirming or refining your reasoning based on the retrieved standards
2. Adding a specific PCAOB citation if the retrieved standards support the concern. If no retrieved standard directly addresses the concern, cite the most relevant standard and explain how the principle applies.
3. Suggesting alternative language that resolves the concern while maintaining the letter's professional tone

Do not drop a finding simply because the retrieved standards do not contain an exact match. If your original reasoning is sound and the concern reflects a genuine independence principle (objectivity, impartiality, appearance of independence), keep the finding and cite the closest applicable standard.

Respond ONLY with valid JSON matching this structure. Do not include any other text, markdown formatting, or code fences.

{
    "findings": [
        {
            "flagged_text": "...",
            "reason": "...",
            "pcaob_citation": "...",
            "suggested_alternative": "..."
        }
    ],
    "status": "issues_found"
}

If after reviewing the standards you determine none of your original findings reflect genuine independence concerns, respond with:

{
    "findings": [],
    "status": "clean"
}"""


# ---------------------------------------------------------------------------
# Review passes
# ---------------------------------------------------------------------------

def pass_1_identify(letter: str) -> tuple[list[dict], list]:
    """Pass 1: Identify potential independence concerns in the letter.

    Returns:
        A tuple of (findings list, message history for pass 2)
    """
    llm = ChatAnthropic(model=MODEL, temperature=0, max_tokens=4096)

    messages = [
        SystemMessage(content=PASS_1_SYSTEM),
        HumanMessage(content=f"Review this proposal transmittal letter for independence concerns:\n\n{letter}"),
    ]

    response = llm.invoke(messages)
    response_text = response.content.strip()

    # Clean markdown fences if present
    response_text = re.sub(r'^```json\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Pass 1 response as JSON: {e}\nResponse: {response_text[:500]}")

    # Build message history for pass 2
    message_history = messages + [AIMessage(content=response.content)]

    return parsed.get("findings", []), message_history


def pass_2_cite(
    findings: list[dict],
    message_history: list,
    collection,
) -> dict:
    """Pass 2: Retrieve PCAOB standards and attach citations to findings.

    Args:
        findings: List of findings from pass 1 (with search_concept)
        message_history: Full message history from pass 1
        collection: Chroma collection for RAG retrieval

    Returns:
        Final review output with citations and status
    """
    if not findings:
        return {"findings": [], "status": "clean"}

    llm = ChatAnthropic(model=MODEL, temperature=0, max_tokens=4096)

    # Retrieve relevant standards for each finding
    retrieval_sections = []
    for i, finding in enumerate(findings, 1):
        concept = finding.get("search_concept", "auditor independence")
        chunks = retrieve(concept, n_results=3, collection=collection)

        print(f"\n  Retrieval for finding {i} (concept: \"{concept}\"):")
        for j, chunk in enumerate(chunks, 1):
            print(f"    [{j}] {chunk['source_title']} {chunk['standard_number']} — {chunk['heading_chain'][:80]}")
            print(f"        Distance: {chunk['distance']:.4f}")

        retrieval_sections.append(f"STANDARDS FOR FINDING {i} (search: \"{concept}\"):")
        retrieval_sections.append(format_chunks_for_prompt(chunks))

    retrieved_context = "\n\n".join(retrieval_sections)

    # Continue the conversation from pass 1
    pass_2_message = HumanMessage(
        content=(
            "Here are the relevant PCAOB standards and guidance for each finding "
            "you identified. Review them and finalize your findings with specific "
            "citations and suggested alternatives. Drop any findings that are not "
            "supported by the retrieved standards.\n\n"
            f"{retrieved_context}"
        )
    )

    messages = [
        SystemMessage(content=PASS_2_SYSTEM),
        *message_history[1:],  # Skip original system message, keep human + AI
        pass_2_message,
    ]

    response = llm.invoke(messages)
    response_text = response.content.strip()

    # Clean markdown fences if present
    response_text = re.sub(r'^```json\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Pass 2 response as JSON: {e}\nResponse: {response_text[:500]}")

    return parsed


# ---------------------------------------------------------------------------
# Main review function
# ---------------------------------------------------------------------------

def review_letter(letter: str) -> dict:
    """Full review pipeline: identify concerns, retrieve standards, cite findings.

    Args:
        letter: The proposal transmittal letter text

    Returns:
        Dict with 'findings' list and 'status' ("issues_found" or "clean")
    """
    collection = get_collection()

    # Pass 1: Identify concerns
    print("Pass 1: Identifying independence concerns...")
    findings, message_history = pass_1_identify(letter)

    if not findings:
        print("No independence concerns found.")
        return {"findings": [], "status": "clean"}

    print(f"Found {len(findings)} potential concern(s):")
    for i, f in enumerate(findings, 1):
        print(f"\n  Finding {i}:")
        print(f"    Flagged: {f.get('flagged_text', '')[:100]}")
        print(f"    Reason: {f.get('reason', '')[:150]}")
        print(f"    Search concept: {f.get('search_concept', '')}")

    print("\nRetrieving PCAOB standards...")

    # Pass 2: Retrieve standards and attach citations
    print("Pass 2: Attaching PCAOB citations...")
    result = pass_2_cite(findings, message_history, collection)

    final_count = len(result.get("findings", []))
    print(f"Final findings after citation review: {final_count}")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Review a proposal transmittal letter for independence concerns."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "letter_file",
        nargs="?",
        help="Path to a text file containing the letter",
    )
    group.add_argument(
        "--text",
        help="The letter text directly (for quick testing)",
    )

    parser.add_argument(
        "--output", "-o",
        help="Save review output to a JSON file",
    )

    args = parser.parse_args()

    load_dotenv(ENV_LOC)

    # Load letter
    if args.text:
        letter = args.text
    else:
        with open(args.letter_file) as f:
            letter = f.read()

    # Run review
    result = review_letter(letter)

    print(f"\n{'='*60}")
    print("Review Output")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
