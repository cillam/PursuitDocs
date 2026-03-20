"""
graph.py

LangGraph graph definition for PursuitDocs.

Pipeline: parser → drafter → reviewer → conditional revision loop

State flows through all nodes:
    - parsed_rfp: structured RFP data from the parser
    - firm_profile: firm profile dict
    - current_draft: the proposal transmittal letter
    - review_result: reviewer output (findings + status)
    - change_log: accumulated list of all findings across iterations
    - iteration: revision loop counter
    - status: "in_progress", "ready_for_review", or "needs_revision"

Usage (run from backend/):
    python -m graph <rfp_source> <firm_profile.json>
    python -m graph ../data/test_rfps/hermon.pdf ../data/firm_profile.json
"""

import argparse
import json
import operator
import os
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from graph.agents.drafter import draft_letter, revise_letter
from graph.agents.reviewer import review_letter
from graph.nodes.parser import parse

ENV_LOC = "../.env"
MAX_ITERATIONS = 3


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

class PursuitDocsState(TypedDict):
    # Inputs
    rfp_source: str
    firm_profile: dict

    # Parser output
    parsed_rfp: dict

    # Drafter output
    current_draft: str

    # Reviewer output
    review_result: dict

    # Accumulated across iterations
    change_log: Annotated[list, operator.add]
    iteration: int

    # Final status
    status: str


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def parser_node(state: PursuitDocsState) -> dict:
    """Extract structured data from the RFP."""
    print(f"\n{'='*60}")
    print("NODE: Parser")
    print(f"{'='*60}")

    parsed_rfp = parse(state["rfp_source"])

    print(f"Parser extracted {len(parsed_rfp)} fields")

    return {"parsed_rfp": parsed_rfp}


def drafter_node(state: PursuitDocsState) -> dict:
    """Draft or revise the proposal transmittal letter."""
    iteration = state.get("iteration", 0)

    print(f"\n{'='*60}")
    print(f"NODE: Drafter (iteration {iteration})")
    print(f"{'='*60}")

    if iteration == 0:
        # Initial draft
        letter = draft_letter(state["parsed_rfp"], state["firm_profile"])
    else:
        # Revision based on reviewer findings
        findings = state.get("review_result", {}).get("findings", [])
        letter = revise_letter(
            state["current_draft"],
            findings,
            state["parsed_rfp"],
            state["firm_profile"],
        )

    print(f"Draft length: {len(letter)} characters")

    return {"current_draft": letter}


def reviewer_node(state: PursuitDocsState) -> dict:
    """Review the current draft for independence concerns."""
    iteration = state.get("iteration", 0)

    print(f"\n{'='*60}")
    print(f"NODE: Reviewer (iteration {iteration})")
    print(f"{'='*60}")

    result = review_letter(state["current_draft"])

    findings = result.get("findings", [])
    print(f"Findings: {len(findings)}")

    # Add iteration number to each finding for the change log
    log_entries = []
    for finding in findings:
        log_entries.append({
            "iteration": iteration,
            **finding,
        })

    return {
        "review_result": result,
        "change_log": log_entries,
    }


def revision_check_node(state: PursuitDocsState) -> dict:
    """Increment the iteration counter."""
    return {"iteration": state.get("iteration", 0) + 1}


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------

def should_continue(state: PursuitDocsState) -> Literal["revise", "ready", "needs_revision"]:
    """Determine what happens after the reviewer runs.

    Returns:
        "revise" — issues found and iterations remaining, loop back to drafter
        "ready" — no issues found, letter is ready for human review
        "needs_revision" — issues remain after max iterations
    """
    review_status = state.get("review_result", {}).get("status", "clean")
    iteration = state.get("iteration", 0)

    if review_status == "clean":
        return "ready"
    elif iteration >= MAX_ITERATIONS:
        return "needs_revision"
    else:
        return "revise"


def set_ready(state: PursuitDocsState) -> dict:
    """Mark the letter as ready for human review."""
    print(f"\n{'='*60}")
    print("STATUS: Ready for Review")
    print(f"{'='*60}")
    return {"status": "ready_for_review"}


def set_needs_revision(state: PursuitDocsState) -> dict:
    """Mark the letter as needing additional human revision."""
    print(f"\n{'='*60}")
    print(f"STATUS: Needs Revision (issues remain after {MAX_ITERATIONS} iterations)")
    print(f"{'='*60}")
    return {"status": "needs_revision"}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Build and compile the PursuitDocs graph."""
    graph = StateGraph(PursuitDocsState)

    # Add nodes
    graph.add_node("parser", parser_node)
    graph.add_node("drafter", drafter_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("revision_check", revision_check_node)
    graph.add_node("set_ready", set_ready)
    graph.add_node("set_needs_revision", set_needs_revision)

    # Add edges
    graph.set_entry_point("parser")
    graph.add_edge("parser", "drafter")
    graph.add_edge("drafter", "reviewer")
    graph.add_edge("reviewer", "revision_check")

    # Conditional edge after revision check
    graph.add_conditional_edges(
        "revision_check",
        should_continue,
        {
            "revise": "drafter",
            "ready": "set_ready",
            "needs_revision": "set_needs_revision",
        },
    )

    graph.add_edge("set_ready", END)
    graph.add_edge("set_needs_revision", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the PursuitDocs pipeline on an RFP."
    )
    parser.add_argument(
        "rfp_source",
        help="URL or file path to an RFP (HTML page, PDF URL, or local PDF)",
    )
    parser.add_argument(
        "firm_profile",
        help="Path to the firm profile JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save full output to a JSON file",
    )

    args = parser.parse_args()

    load_dotenv(ENV_LOC)

    # Load firm profile
    with open(args.firm_profile) as f:
        firm_profile = json.load(f)

    # Build and run the graph
    app = build_graph()

    initial_state = {
        "rfp_source": args.rfp_source,
        "firm_profile": firm_profile,
        "parsed_rfp": {},
        "current_draft": "",
        "review_result": {},
        "change_log": [],
        "iteration": 0,
        "status": "in_progress",
    }

    print("\n" + "#" * 60)
    print("PURSUITDOCS PIPELINE")
    print("#" * 60)

    result = app.invoke(initial_state)

    # Display results
    print(f"\n\n{'#'*60}")
    print("FINAL OUTPUT")
    print(f"{'#'*60}")

    print(f"\nStatus: {result['status']}")
    print(f"Iterations: {result['iteration']}")
    print(f"Total findings across all iterations: {len(result['change_log'])}")

    print(f"\n{'='*60}")
    print("Final Letter")
    print(f"{'='*60}\n")
    print(result["current_draft"])

    if result["change_log"]:
        print(f"\n{'='*60}")
        print("Change Log")
        print(f"{'='*60}")
        print(json.dumps(result["change_log"], indent=2))

    if args.output:
        output = {
            "status": result["status"],
            "iterations": result["iteration"],
            "final_letter": result["current_draft"],
            "change_log": result["change_log"],
            "parsed_rfp": result["parsed_rfp"],
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nFull output saved to: {args.output}")


if __name__ == "__main__":
    main()
