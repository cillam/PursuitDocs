"""
drafter.py

Generates a proposal transmittal letter from a parsed RFP and firm profile.

Inputs:
    - Parsed RFP (dict): output from parser.py
    - Firm profile (dict): loaded from firm_profile.json

Output:
    - A proposal transmittal letter (str)

The drafter does not consult PCAOB standards — it writes the best letter
it can from the RFP and firm profile. Independence review is the
reviewer agent's job.

Usage (run from backend/):
    python -m graph.agents.drafter <parsed_rfp.json> <firm_profile.json>
    python -m graph.agents.drafter --rfp-source <url_or_filepath> --firm-profile ../data/firm_profile.json
"""

import argparse
import json
import os
import re
from datetime import date

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

ENV_LOC = '../../secrets/pursuitdocs/backend/.env'
MODEL = "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert proposal writer for a public accounting firm. Your task is to draft a proposal transmittal letter responding to a Request for Proposal (RFP) for audit services.

A transmittal letter is the cover letter that accompanies a full proposal. It should:
- Be addressed to the contact person specified in the RFP
- Introduce the firm and express interest in providing the requested services
- Briefly highlight the firm's relevant qualifications and experience
- Reference the specific services requested in the RFP
- Demonstrate understanding of the requesting entity and its needs
- Note the firm's independence and objectivity
- Mention the engagement team using the placeholder names from the firm profile
- Close professionally with a call to action

Write the letter in a professional, confident, and persuasive tone. The goal is to win the engagement. Emphasize the firm's strengths that are most relevant to this specific RFP and entity. Do not mention industry specializations or experience areas that are not relevant to the RFP — only highlight what makes the firm a strong fit for this particular engagement. Do not hedge, qualify, or undercut the firm's capabilities. The letter should feel like it was written by a senior partner who genuinely wants this work.

Only claim qualifications, experience, and capabilities that are explicitly stated in the firm profile. Do not invent experience with specific industries, jurisdictions, software systems, or regulations unless the firm profile supports it. Where a specific example, past engagement, or client reference would strengthen the letter but is not available in the firm profile, insert a bracketed placeholder (e.g., [insert relevant past engagement], [insert client reference in similar industry]) so the partner can fill it in before sending.

Keep the letter concise. Do not repeat RFP details back to the reader — they already know what their RFP says. Do not list specific statutes, regulatory citations, fund names, deliverables, deadlines, copy counts, or other specifics pulled from the RFP. A brief reference to the type of work is fine (e.g., "municipal audit services"), but do not enumerate the scope. The letter should focus on why the firm is the right choice, not on restating what the client asked for.

Format the letter as a standard business letter — flowing paragraphs, no section headings, no bold text, no markdown formatting. This is a cover letter, not a report. The only exception is if the RFP's proposal instructions specifically request headings or a particular format, in which case follow those instructions.

When using initialisms, define them at first use (e.g., "Generally Accepted Auditing Standards (GAAS)") and use only the initialism thereafter. If a term appears only once in the letter, spell it out in full and do not define the initialism. This includes the firm's own name — introduce the firm by its full legal name first, then define the short name (e.g., "Fakerson, Madeup & Totallyriel LLP ("FMT LLP")") and use the short name thereafter.

If the RFP submission deadline has already passed, use the submission deadline date. Otherwise, date the letter with today's date, which will be provided in the prompt.

Use the engagement team placeholders exactly as they appear in the firm profile (e.g., [Engagement Partner First Name] [Engagement Partner Last Name]). These will be replaced with real names before sending.

ABSOLUTE DO NOTS:
- Do NOT fabricate experience, qualifications, or capabilities not explicitly stated in the firm profile.
- Do NOT list specific statutes, regulatory citations, or fund names from the RFP.
- Do NOT enumerate deliverables, deadlines, copy counts, or other RFP specifics.
- Do NOT use headings, bold text, or markdown formatting unless the RFP instructions require it.
- Do NOT mention industry specializations or experience areas that are not relevant to the RFP.
- Do NOT include any commentary, explanations, or metadata outside the letter itself.

Output only the letter text, ready to be placed on firm letterhead."""


# ---------------------------------------------------------------------------
# Letter generation
# ---------------------------------------------------------------------------

def build_prompt(parsed_rfp: dict, firm_profile: dict) -> str:
    """Build the human message content from the parsed RFP and firm profile.

    Formats both inputs clearly so the LLM can reference specific details.
    """
    sections = []

    # Today's date
    sections.append(f"TODAY'S DATE: {date.today().strftime('%B %d, %Y')}")

    # Parsed RFP
    sections.append("=== PARSED RFP ===")

    sections.append(f"ADDRESSEE:\n{json.dumps(parsed_rfp.get('addressee', {}), indent=2)}")
    sections.append(f"PURPOSE AND SERVICES REQUESTED:\n{parsed_rfp.get('purpose_and_services', 'Not specified')}")
    sections.append(f"ENTITY BACKGROUND:\n{parsed_rfp.get('entity_background', 'Not specified')}")
    # Parse proposal instructions (may be a dict with subfields or a plain string)
    pi = parsed_rfp.get('proposal_instructions', {})
    if isinstance(pi, dict):
        sections.append(f"PROPOSAL INSTRUCTIONS:\n{pi.get('instructions', 'Not specified')}")
        sections.append(f"SUBMISSION DEADLINE: {pi.get('submission_deadline', 'Not specified')}")
    else:
        sections.append(f"PROPOSAL INSTRUCTIONS:\n{pi}")
        sections.append("SUBMISSION DEADLINE: Not specified")
    sections.append(f"RFP SUMMARY:\n{parsed_rfp.get('summary', 'Not specified')}")

    # Firm profile
    sections.append("\n=== FIRM PROFILE ===")
    sections.append(json.dumps(firm_profile, indent=2))

    sections.append("\n=== TASK ===")
    sections.append("Draft a proposal transmittal letter based on the RFP and firm profile above.")

    return "\n\n".join(sections)


def draft_letter(parsed_rfp: dict, firm_profile: dict) -> str:
    """Generate a proposal transmittal letter.

    Args:
        parsed_rfp: Output from parser.py (dict with five fields)
        firm_profile: Firm profile loaded from JSON

    Returns:
        The transmittal letter as a string
    """
    llm = ChatAnthropic(model=MODEL, temperature=0.4, max_tokens=4096)

    prompt = build_prompt(parsed_rfp, firm_profile)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = llm.invoke(messages)

    return response.content.strip()


def revise_letter(
    current_draft: str,
    review_findings: list[dict],
    parsed_rfp: dict,
    firm_profile: dict,
) -> str:
    """Revise the letter based on reviewer findings.

    Called during the revision loop when the reviewer flags issues.

    Args:
        current_draft: The current version of the letter
        review_findings: List of dicts from the reviewer, each with:
            - flagged_text: The problematic text
            - reason: Why it's an issue
            - pcaob_citation: The relevant standard
            - suggested_alternative: Recommended replacement
        parsed_rfp: Original parsed RFP for context
        firm_profile: Firm profile for context

    Returns:
        The revised letter as a string
    """
    llm = ChatAnthropic(model=MODEL, temperature=0.3, max_tokens=4096)

    sections = []

    sections.append("=== CURRENT DRAFT ===")
    sections.append(current_draft)

    sections.append("\n=== REVIEWER FINDINGS ===")
    sections.append(
        "The following independence issues were flagged by the reviewer. "
        "Revise the letter to address each finding. Use the suggested "
        "alternatives where appropriate, but you may use different language "
        "as long as the independence concern is resolved."
    )
    for i, finding in enumerate(review_findings, 1):
        sections.append(f"Finding {i}:")
        sections.append(f"  Flagged text: {finding.get('flagged_text', '')}")
        sections.append(f"  Reason: {finding.get('reason', '')}")
        sections.append(f"  PCAOB citation: {finding.get('pcaob_citation', '')}")
        sections.append(f"  Suggested alternative: {finding.get('suggested_alternative', '')}")

    sections.append("\n=== ORIGINAL RFP CONTEXT ===")
    sections.append(f"PURPOSE AND SERVICES REQUESTED:\n{parsed_rfp.get('purpose_and_services', 'Not specified')}")
    sections.append(f"ENTITY BACKGROUND:\n{parsed_rfp.get('entity_background', 'Not specified')}")

    sections.append("\n=== FIRM PROFILE ===")
    sections.append(json.dumps(firm_profile, indent=2))

    sections.append("\n=== TASK ===")
    sections.append(
        "Revise the letter to resolve all flagged independence issues. "
        "Preserve the overall structure, tone, and content of the letter — "
        "only change what is necessary to address the findings. "
        "Output only the revised letter text."
    )

    revision_system = (
        "You are an expert proposal writer for a public accounting firm. "
        "You are revising a proposal transmittal letter based on feedback "
        "from an independence reviewer. Your goal is to resolve all flagged "
        "issues while maintaining a professional, confident tone. "
        "Do not add new independence issues in your revisions. "
        "Output only the revised letter text."
    )

    messages = [
        SystemMessage(content=revision_system),
        HumanMessage(content="\n\n".join(sections)),
    ]

    response = llm.invoke(messages)

    return response.content.strip()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Draft a proposal transmittal letter from a parsed RFP and firm profile."
    )

    # Two modes: pre-parsed JSON or raw RFP source
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "parsed_rfp_json",
        nargs="?",
        help="Path to a JSON file containing parsed RFP output from parser.py",
    )
    group.add_argument(
        "--rfp-source",
        help="URL or file path to an RFP (will run parser.py first)",
    )

    parser.add_argument(
        "firm_profile_json",
        nargs="?",
        default=None,
        help="Path to the firm profile JSON file",
    )
    parser.add_argument(
        "--firm-profile",
        default=None,
        help="Path to the firm profile JSON file (alternative to positional arg)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save the letter to a file",
    )

    args = parser.parse_args()

    load_dotenv(ENV_LOC)

    # Resolve firm profile path
    fp_path = args.firm_profile or args.firm_profile_json
    if not fp_path:
        print("❌ Error: Firm profile JSON is required.")
        exit(1)

    # Load firm profile
    with open(fp_path) as f:
        firm_profile = json.load(f)

    # Get parsed RFP — either from file or by running the parser
    if args.rfp_source:
        # Import and run parser
        from graph.nodes.parser import parse
        print(f"Running parser on: {args.rfp_source}")
        parsed_rfp = parse(args.rfp_source)
    else:
        with open(args.parsed_rfp_json) as f:
            parsed_rfp = json.load(f)

    print(f"\n{'='*60}")
    print("Parser Output")
    print(f"{'='*60}")
    print(json.dumps(parsed_rfp, indent=2))

    # Draft the letter
    print("Drafting proposal transmittal letter...")
    letter = draft_letter(parsed_rfp, firm_profile)

    print(f"\n{'='*60}")
    print("Proposal Transmittal Letter")
    print(f"{'='*60}\n")
    print(letter)

    if args.output:
        with open(args.output, "w") as f:
            f.write(letter)
        print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
