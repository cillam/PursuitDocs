# PursuitDocs

An AI-powered multi-agent system that automates the audit proposal letter process. PursuitDocs takes a Request for Proposal (RFP) for audit services, generates a compliant proposal letter, and iteratively reviews it for auditor independence issues against PCAOB standards.

## How It Works

1. **Upload an RFP** — Drop in a public RFP for audit services (PDF)
2. **Parser** — Extracts the text from the PDF, then uses an LLM to pull out the five things the drafter needs: proposal instructions, purpose/services requested, entity background, addressee, and an overall summary
3. **Drafter Agent** — Generates a proposal letter pulling from the parsed RFP, PCAOB independence standards, and the firm profile
4. **Reviewer Agent** — Scans the draft for independence concerns, flags issues with PCAOB citations and suggested alternatives
5. **Revision Loop** — The drafter revises based on findings, the reviewer checks again (max 3 iterations)
6. **Output** — Final proposal letter + structured change log + status (Ready for Review or Needs Revision)

A human always reviews the final letter. If the reviewer agent's checks pass, the letter is marked **Ready for Review**. If issues remain after 3 revision passes, the letter is marked **Needs Revision** — meaning the human reviewer needs to do additional work beyond a standard signoff.

## Why Two Agents?

PursuitDocs separates drafting and reviewing into distinct agents rather than handling both in a single prompt. This is a deliberate design choice rooted in how LLMs perform best — one focused task per agent.

LLMs are weak at self-critique. A model that just wrote a sentence is unlikely to flag that same sentence as problematic — it already decided the language was acceptable when it generated it. A separate reviewer agent with its own prompt and its own focus provides a genuine adversarial check, much like how a human writer and a human editor bring different eyes to the same document.

Separating the agents also makes the system independently testable and improvable. The reviewer can be evaluated on its own by giving it letters with known independence issues and measuring whether it catches them. The drafter can be evaluated on its own by checking whether its output is complete and well-structured. If one is underperforming, its prompt can be tuned without affecting the other. In a single-agent design, everything is coupled and diagnosing failures is harder.

Finally, the separation is what makes the change log possible. The structured record of what was flagged, why, what standard it violated, and how it was revised only exists because two agents are having a documented exchange. A single agent revising its own output produces no audit trail.

## Architecture

```
RFP (PDF upload)
    │
    ▼
┌──────────────────┐
│   PDF Extraction  │
│   (text from PDF) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Parser (LLM)    │── Extracts: instructions, purpose,
│                    │   background, addressee, summary
└────────┬─────────┘
         │
         ▼
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Firm Profile │     │ PCAOB Standards  │     │   Parsed RFP     │
│   (JSON)      │     │   (RAG)          │     │   (structured)   │
└──────┬───────┘     └────────┬─────────┘     └────────┬─────────┘
       │                      │                         │
       └──────────────┬───────┴─────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ Drafter Agent │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │Reviewer Agent │──── Flags issues w/ PCAOB citations
              └───────┬───────┘
                      │
                 Issues found?
                 /          \
               Yes           No
               /               \
              ▼                 ▼
        Drafter revises    ✅ Ready for Review
        (loop, max 3x)
              │
         Still issues
         after 3 loops?
              │
              ▼
     ⚠️ Needs Revision

Output: Final Letter + Change Log + Status
```

## Tech Stack

- **Agent Framework:** LangChain / LangGraph
- **Backend:** LangGraph Cloud (handles graph execution, state, and API)
- **Vector Store:** Chroma
- **LLM:** Claude API (Anthropic)
- **Frontend:** React (Vite) hosted on AWS Amplify
- **Knowledge Base:** PCAOB independence standards, firm profile

## Project Structure

```
pursuitdocs/
├── graph/
│   ├── graph.py                   # LangGraph graph definition + orchestration
│   ├── agents/
│   │   ├── drafter.py             # Drafter agent
│   │   └── reviewer.py           # Reviewer agent
│   ├── nodes/
│   │   └── parser.py              # PDF extraction + LLM-based RFP parsing
│   ├── rag/
│   │   └── retriever.py           # RAG retrieval from PCAOB standards
│   ├── utils/
│   │   └── changelog.py           # Change log generation
│   └── langgraph.json             # LangGraph Cloud deployment config
├── frontend/
│   ├── src/
│   │   ├── components/            # React components (upload, progress, results)
│   │   ├── services/              # LangGraph Cloud API client
│   │   └── utils/
│   ├── package.json
│   └── vite.config.js
├── data_processing/
│   ├── scrape_pcaob.py            # Scrapes PCAOB standards, rules, bulletins; downloads spotlight PDF
│   ├── validate_pcaob.py          # Data validation and structure visualization for scraped content
│   ├── ingest_pcaob.py            # PCAOB content ingestion into Chroma
│   └── create_vectorstore.py      # Chroma database creation
├── data/
│   ├── firm_profile.json          # Fake firm profile (PCAOB data structure)
│   ├── pcaob_content/             # Scraped PCAOB content (RAG source)
│   │   ├── index.json             # Master index of all content
│   │   ├── standards/             # Auditing standards (AS 1000–1305)
│   │   ├── rules/                 # Ethics & independence rules (Rule 3501–3526)
│   │   ├── bulletins/             # Investor bulletins
│   │   └── spotlights/            # PCAOB staff spotlights
│   └── test_rfps/                 # Public RFPs for testing
├── evaluation/
│   ├── synthetic_proposals/       # Annotated synthetic proposals for eval
│   └── eval_runner.py             # Evaluation scripts
├── README.md
├── .gitignore
└── requirements.txt
```

## Knowledge Base

- **PCAOB Auditing Standards** — General auditing standards (AS 1000–1305) covering auditor responsibilities, audit risk, evidence, supervision, documentation, engagement quality review, and audit committee communications. Used by the drafter for completeness and by the reviewer for context.
- **PCAOB Ethics & Independence Rules** — Rules 3501–3526 covering auditor independence, contingent fees, tax services, audit committee pre-approval, and communication requirements. The core reference for the reviewer agent.
- **PCAOB Spotlights** — Staff publications highlighting real-world inspection observations, including the Auditor Independence Spotlight with common deficiencies, applicable standards, and good practices.
- **Investor Bulletins** — PCAOB publications on auditor professional responsibilities and ethics aimed at investors and audit committees.
- **Firm Profile** — A fictional mid-size audit firm (Fakerson, Madeup & Totallyriel LLP) modeled after the PCAOB AuditorSearch data dictionary
- **RFPs** — Real, publicly available RFPs from government agencies and municipalities requesting audit services

All PCAOB content is scraped, structured as JSON with section hierarchy and footnote references, and indexed in a master `index.json` manifest.

## Parser Output

The parser extracts five fields from each RFP:

- **Proposal Instructions** — How the proposal should be formatted and what to include
- **Purpose / Services Requested** — What services they need and for what entity
- **Background** — Description of the requesting entity (size, budget, structure, etc.)
- **Addressee** — Who the proposal should be directed to (name, title, address)
- **Summary** — High-level overview of the RFP, giving the drafter quick orientation on tone and emphasis

The parser uses LLM-based extraction rather than keyword matching or regex because government RFPs have no standard format. One RFP might label a section "Company Background," another might call it "Organization Description," and a third might bury the same information in a paragraph with no heading at all. The LLM extracts by meaning, which makes the parser robust to these variations without needing rules for every possible format.

This structured output is what the drafter agent works from — not the raw 100-page PDF.

## Change Log Output

Every iteration of the review loop is logged with:

- The specific flagged text
- Why it's an independence concern
- The relevant PCAOB standard/citation
- The suggested alternative language
- Whether the revision resolved the issue

This creates a full audit trail of the AI's own reasoning — transparent and reviewable by a human.

## Future Roadmap

- **Configurable rules per RFP** — Different RFPs may specify additional guidelines beyond PCAOB; allow users to upload supplementary rules
- **Full proposal generation** — Expand beyond the engagement letter to cover all essential sections (executive summary, scope, methodology, fees, timeline)
- **Proposal layout and formatting** — Automated section structure per Thomson Reuters pursuit framework
- **Delivery preparation** — Generate production-ready output in specified formats
- **Engagement team integration** — Replace template placeholders with actual team data from a firm directory
- **Multi-firm support** — Allow different firm profiles for different submissions
- **Model optimization** — The drafter's task (assembling structured inputs into a professional letter) is less reasoning-intensive than the reviewer's task (evaluating nuanced language against regulatory standards). A smaller, faster model (e.g., Claude Haiku) could potentially handle drafting while the reviewer runs on a more capable model (e.g., Claude Sonnet), reducing cost and latency without sacrificing review quality

### Multi-Firm Design Considerations

Supporting multiple firms introduces several challenges beyond swapping out a profile:

- **Data isolation** — Each firm's profile, documents, and generated proposals must be completely separated. Separate vector store collections per firm (rather than metadata filtering) to prevent any data leakage between firms.
- **Proposal differentiation** — Two firms responding to the same RFP should produce meaningfully different proposals. The firm profile provides baseline differentiation, but richer inputs would strengthen this:
  - **Firm style guide** — Tone, language preferences, and formatting conventions specific to each firm
  - **Golden example proposals** — Reference proposals per sector that demonstrate each firm's voice and approach, used as few-shot examples for the drafter
  - **Relevant past engagements** — Similar entities the firm has worked with, for credibility and tailoring
  - **Unique selling points** — Key differentiators the firm always wants highlighted

## Evaluation

The project includes an evaluation dataset of synthetic proposal letters annotated with:

- Independence concerns (flagged language)
- Reasoning for why the language is or isn't acceptable
- Relevant PCAOB citations

This is used to measure the reviewer agent's accuracy and the drafter's revision quality.

## License

MIT

## PCAOB Standards Usage

This project references publicly available PCAOB standards and guidance for educational and demonstration purposes. Per the PCAOB's Terms of Use, PCAOB Public Materials — including rules, standards, forms, releases, orders, guidance, and reports — are permitted for use, publication, display, and distribution. This project does not use AICPA-copyrighted interim standards.
