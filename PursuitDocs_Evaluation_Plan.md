# PursuitDocs — Evaluation Plan

## Purpose

This document defines the evaluation strategy for PursuitDocs. The goal is to measure the quality of three components — the Reviewer agent, the Drafter agent's revision quality, and the Parser — using a combination of automated metrics and structured manual review.

The evaluation framework is informed by Anthropic's guidance on agent evaluation (see: [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)) and adapted for PursuitDocs' specific architecture: an LLM pipeline with a bounded revision loop over regulatory content.

---

## What We're Evaluating

### 1. Reviewer Agent — Independence Issue Detection

The reviewer is PursuitDocs' core judgment layer. It reads a proposal transmittal letter and identifies language that could compromise auditor independence under PCAOB standards. This is a classification problem with known ground truth.

**Key questions:**
- Does the reviewer catch all planted independence issues? (Recall)
- Does it avoid flagging clean, professional language? (Precision)
- Does it cite the correct PCAOB standard for each finding? (Citation quality)
- Are its results consistent across multiple runs? (Stability)

### 2. Drafter Agent — Revision Quality

When the reviewer flags issues, the drafter revises the letter. The evaluation checks whether revisions actually fix the problems without introducing new ones or degrading the letter's quality.

**Key questions:**
- Was the flagged language removed or meaningfully changed?
- Did the revision preserve the letter's professional tone and persuasive intent?
- Did the revision introduce any new independence concerns?

### 3. Parser — RFP Field Extraction

The parser extracts five structured fields from RFPs with varying formats. Some fields have objectively correct answers (addressee name); others are judgment calls (summary, background).

**Key questions:**
- Are structured fields (addressee, deadline) extracted correctly?
- Are open-ended fields (summary, background, purpose) complete and accurate?
- Does the parser correctly reject RFPs not for financial statement audits?

---

## Evaluation Datasets

### Synthetic Proposal Letters (Reviewer + Drafter)

10–15 proposal transmittal letters, purpose-built to test the reviewer. Each letter is annotated with ground truth using the schema below. The set includes:

- **Letters with planted issues** — covering all independence categories at varying difficulty levels (easy, medium, hard). Some letters have multiple co-occurring issues.
- **Clean letters** — professional proposal language that should NOT be flagged. These test for false positives.
- **Borderline letters** — language that sounds potentially problematic but is appropriate in context. These test the reviewer's judgment.

#### Ground Truth Annotation Schema

Each annotation entry in a letter's ground truth file describes one phrase — either a planted issue or a known clean phrase:

```json
{
  "letter_id": "letter_01",
  "annotations": [
    {
      "id": "letter_01_issue_01",
      "flagged_text": "personal attention and responsiveness",
      "is_issue": true,
      "independence_category": "objectivity",
      "contextual_reasoning": "Implies a special relationship prioritizing the client's comfort over professional impartiality. An auditor's role is to serve the public interest, not to provide personalized attention.",
      "pcaob_reference": "PCAOB Rule 3520 — Auditor Independence",
      "difficulty": "hard"
    },
    {
      "id": "letter_01_clean_01",
      "flagged_text": "deep expertise in municipal finance",
      "is_issue": false,
      "independence_category": null,
      "contextual_reasoning": "Describing relevant qualifications is standard and appropriate in a proposal letter. This does not imply a personal stake or compromised objectivity.",
      "pcaob_reference": null,
      "difficulty": null
    }
  ]
}
```

#### Independence Categories (from Reviewer System Prompt)

These are the categories the reviewer is prompted to check. Each planted issue maps to one of these:

| Category | Description | Example Flags |
|---|---|---|
| **Objectivity** | Language suggesting the auditor will act in the client's interest rather than the public interest; promises of outcomes; personal relationship language | "personal attention," "mutual benefit," "aligned interests," "guaranteed" |
| **Prohibited relationships** | Management advisory functions; making decisions for the client; blurring auditor/management roles | "guide your team," "we'll handle your compliance decisions" |
| **Financial interests** | Contingent fees; indemnification; fees framed as investment | "the audit will pay for itself," "we share in the outcome" |
| **Scope boundaries** | Overpromising deliverables; advocating for the client; commitments that could block adverse opinions | "protect your interests," "ensure a favorable result" |

#### Difficulty Levels

| Level | Description | Example |
|---|---|---|
| **Easy** | Obvious independence violation; most reviewers would catch it | "We guarantee a clean audit opinion" |
| **Medium** | Recognizable with audit knowledge but not immediately obvious | "Our audit will benefit your organization" |
| **Hard** | Subtle language that sounds professional but implies compromised independence | "Personal attention and responsiveness" |

### Annotated Test RFPs (Parser)

4–6 real RFPs already downloaded as test data. Each will be manually annotated with expected parser output for all five fields:

```json
{
  "rfp_id": "rfp_hermon_me",
  "source_file": "test_rfps/hermon_maine.pdf",
  "expected": {
    "proposal_instructions": {
      "instructions": "...",
      "submission_deadline": "March 15, 2026"
    },
    "purpose_and_services": "...",
    "entity_background": "...",
    "addressee": {
      "name": "...",
      "title": "...",
      "organization": "...",
      "address": "...",
      "phone": "...",
      "email": "..."
    },
    "summary": "..."
  }
}
```

### Reviewer Finding + Letter Pairs (Drafter Revision)

For drafter revision evaluation, we need input pairs: a letter with known issues plus the reviewer's findings for those issues. These can come from two sources:

- **Synthetic pairs** — hand-crafted letter + findings where we control both sides
- **Harvested pairs** — take a synthetic letter, run the reviewer, and use its actual output as the findings input (only for cases where the reviewer correctly identified the issues)

---

## Grading Strategy

### Grader Types

Following the framework from Anthropic's eval guidance, we use three types of graders:

| Type | Use Case | Implementation |
|---|---|---|
| **Code-based** | Precision/recall on flagged text, field exact match, flagged-text-removed checks | Python functions comparing outputs to ground truth |
| **LLM-based** | Citation relevance, semantic similarity for open-ended fields, revision quality assessment | Claude API calls with structured rubrics |
| **Human** | Calibration of LLM graders, review of edge cases, final quality assessment on a sample | Structured rubric with scoring criteria |

### Reviewer Graders

**1. Category-Level Detection (code-based)**

For each independence category present in a letter's ground truth, did the reviewer find *any* issue in that category?

- **True Positive:** Ground truth has an issue in category X, reviewer flagged something in category X
- **True Negative:** Ground truth has no issues in category X, reviewer did not flag anything in category X
- **False Positive:** Ground truth has no issues in category X, reviewer flagged something in category X
- **False Negative:** Ground truth has an issue in category X, reviewer did not flag anything in category X

Metrics: precision, recall, F1 per category and overall.

**2. Exact-Text Detection (code-based)**

For each specific planted phrase, did the reviewer flag that exact text (or a close match — e.g., substring or fuzzy match above a threshold)?

Metrics: precision, recall, F1 at the phrase level.

**3. Citation Quality (LLM-based)**

For each reviewer finding that matches a ground truth issue, is the cited PCAOB standard relevant to the independence concern?

Rubric for the LLM grader:
- **Correct:** The cited standard directly addresses the type of independence concern identified
- **Partially correct:** The cited standard is related but not the most relevant standard
- **Incorrect:** The cited standard does not relate to the concern

**4. False Positive Analysis (code-based + manual)**

For clean letters and borderline phrases, count and categorize any false positives. Manual review to determine whether each false positive is a genuine grading disagreement (reasonable to flag) or a clear miss.

### Drafter Revision Graders

**1. Flagged Text Removed (code-based)**

For each finding in the input, check whether the flagged text still appears in the revised letter. Simple string matching (exact or fuzzy).

Metric: removal rate (percentage of flagged phrases successfully removed or meaningfully changed).

**2. Meaning and Tone Preserved (LLM-based)**

An LLM grader compares the original and revised letters against a rubric:
- Does the revised letter maintain the same persuasive intent?
- Does it still address the RFP's requirements?
- Is the professional tone preserved?
- Are the replacement phrases appropriate and natural?

Scoring: 1–5 scale per dimension.

**3. No New Issues Introduced (automated)**

Run the reviewer agent on the revised letter. Any findings that don't correspond to findings from the original review are potential new issues introduced by the revision. Flag these for manual review.

### Parser Graders

**1. Structured Field Match (code-based)**

Exact match (or normalized match) for:
- Addressee: name, title, organization, address, phone, email
- Submission deadline

Metric: accuracy per field across all test RFPs.

**2. Open-Ended Field Quality (LLM-based)**

For summary, background, and purpose fields, an LLM grader evaluates:
- **Completeness:** Does the extraction capture the key information from the source RFP?
- **Accuracy:** Is the extracted information factually correct relative to the source?
- **Separation:** Does each field contain only information appropriate to that field, without overlap?

Scoring: 1–5 scale per dimension per field.

**3. Rejection Accuracy (code-based)**

For any non-audit test documents included, verify the parser correctly identifies them as not applicable (returns "Not specified" for purpose_and_services, triggering the `is_audit_rfp` conditional edge).

---

## Trial Design

### Non-Determinism Handling

LLM outputs vary between runs. To measure consistency and get reliable metrics, each task runs multiple trials.

| Sub-Suite | Trials per Task | Rationale |
|---|---|---|
| Reviewer | 5 | Core evaluation target; needs strong signal on consistency |
| Drafter revision | 5 | Revision quality can vary significantly between runs |
| Parser | 3 | More deterministic; structured extraction varies less |

### Metrics Across Trials

For each task, report:
- **Per-trial results** — full grading output for each trial (stored in transcript)
- **pass@5 / pass@3** — did the agent succeed at least once across trials?
- **pass^5 / pass^3** — did the agent succeed on every trial? (Measures consistency)
- **Mean scores** — for LLM-graded dimensions (e.g., average citation quality across 5 trials)

---

## Model Comparison: Sonnet vs. Haiku

After completing the primary evaluation with Sonnet, re-run the reviewer and drafter sub-suites with Haiku. This quantifies the early qualitative decision to switch from Haiku to Sonnet.

**Comparison metrics:**
- Reviewer: precision, recall, F1 at both category and text level
- Reviewer: citation quality scores
- Drafter: removal rate, meaning/tone scores, new issues introduced
- Cost: total tokens and API cost per sub-suite
- Latency: average time per trial

---

## Execution Order

1. **Create the synthetic letter dataset** — Write 10–15 letters with annotations. Start with one pilot letter, run it through the reviewer manually, and verify the grading logic works before building the full set.
2. **Annotate the test RFPs** — Manually extract expected parser output for each of the 4–6 test RFPs.
3. **Build the evaluation harness** — Infrastructure to run tasks, manage trials, record transcripts, and pass outputs to graders. (See: PursuitDocs_Evaluation_Framework.md)
4. **Implement graders** — Code-based graders first (precision/recall, field matching), then LLM-based graders (citation quality, revision quality, field similarity).
5. **Run the primary evaluation** — All three sub-suites with Sonnet.
6. **Review transcripts** — Read trial transcripts to verify graders are working correctly and results are fair.
7. **Run model comparison** — Re-run reviewer and drafter sub-suites with Haiku.
8. **Document results** — Summary metrics, known gaps, and recommendations for prompt improvements.

---

## Known Test Cases

These are specific behaviors identified during development that the evaluation should capture:

| Behavior | Component | Status | Notes |
|---|---|---|---|
| "Personal attention" — reviewer misses this | Reviewer | Known miss | Hard difficulty; relationship language the reviewer consistently doesn't flag |
| Drafter fabricates experience | Drafter | Fixed via prompt | Guardrail added; evaluation should confirm it holds |
| Drafter restates RFP details | Drafter | Fixed via model switch | Haiku didn't follow this constraint; Sonnet does. Model comparison should confirm. |
| Reviewer drops findings when RAG doesn't match | Reviewer | Fixed via prompt | Pass 2 was dropping valid findings; prompt updated. Evaluation should verify. |

---

## Success Criteria

This is a portfolio/learning project, not a production system. The evaluation is valuable for demonstrating rigorous thinking about AI system quality, not for achieving perfect scores. That said, targets to aim for:

| Metric | Target | Rationale |
|---|---|---|
| Reviewer recall (category-level) | ≥ 80% | Should catch most planted issues |
| Reviewer precision (category-level) | ≥ 70% | Some false positives acceptable; human reviews everything |
| Reviewer citation quality (correct or partial) | ≥ 75% | RAG should surface relevant standards most of the time |
| Drafter flagged-text removal rate | ≥ 90% | Revisions should address what was flagged |
| Parser structured field accuracy | ≥ 85% | Addressee and deadline should be reliably correct |

Scores below these targets are useful findings, not failures — they identify where prompts or architecture need improvement.

---

*Last Updated: March 25, 2026*
