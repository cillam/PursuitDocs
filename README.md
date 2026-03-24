# PursuitDocs

PursuitDocs automates the financial statement audit proposal letter process. It takes a Request for Proposal (RFP) for audit services, generates a compliant proposal transmittal letter, and iteratively reviews it for auditor independence issues against PCAOB standards using a multi-step LLM pipeline with a bounded revision loop.

## How It Works

1. **Submit an RFP** — Provide a URL or upload a PDF of a public RFP for audit services
2. **Parser** — Extracts text from the document, then uses an LLM to pull out five structured fields: proposal instructions, submission deadline, purpose/services requested, entity background, addressee, and summary
3. **Drafter** — Generates a proposal transmittal letter from the parsed RFP and firm profile
4. **Reviewer** — Scans the draft for independence concerns, retrieves relevant PCAOB standards via RAG, and flags issues with citations and suggested alternatives
5. **Revision Loop** — The drafter revises based on findings, the reviewer checks again (max 3 iterations)
6. **Output** — Final proposal letter + structured change log + status (Ready for Review or Needs Revision)

A human always reviews the final letter. "Ready for Review" means the automated checks passed. "Needs Revision" means issues remain after 3 passes and the human reviewer needs to do additional work.

## Why a Drafter and a Reviewer?

PursuitDocs separates drafting and reviewing into distinct LLM steps. Keeping them separate means either agent's scope (from transmittal letter to full proposal) can change without affecting the other. A separate reviewer also provides a stronger adversarial check than asking the same model to critique its own output, and each agent can be tested and tuned independently.

The separation makes the change log a natural byproduct of the architecture; the structured record of what was flagged, why, and how it was revised emerges from the two agents having a documented exchange.

## Architecture

```
RFP (PDF upload or URL)
    │
    ▼
┌──────────────────┐
│  Parser (LLM)     │── Extracts: instructions, deadline,
│                    │   purpose, background, addressee, summary
└────────┬─────────┘
         │
         ▼
┌──────────────┐     ┌──────────────────┐
│  Firm Profile │     │   Parsed RFP     │
└──────┬───────┘     └────────┬─────────┘
       └──────────┬───────────┘
                  ▼
          ┌───────────────┐
          │    Drafter     │
          └───────┬───────┘
                  ▼
          ┌───────────────┐     ┌─────────────────┐
          │   Reviewer     │────→│ PCAOB Standards  │
          └───────┬───────┘     │   (Chroma RAG)   │
                  │             └─────────────────┘
             Issues found?
             /          \
           Yes           No
           /               \
          ▼                 ▼
    Drafter revises    ✅ Ready for Review
    (loop, max 3x)
          │
     Still issues?
          ▼
 ⚠️ Needs Revision

Output: Final Letter + Change Log + Status
```

## Tech Stack

| Component | Technology |
|---|---|
| Orchestration | LangChain / LangGraph |
| Backend | FastAPI + Mangum (AWS Lambda) |
| Vector store | Chroma |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | Claude Sonnet (Anthropic) |
| Frontend | React 18 (Vite) + TailwindCSS |
| Hosting | AWS Amplify (frontend) + API Gateway + Lambda (backend) |
| Storage | AWS S3 (Chroma DB, firm profile, temp file uploads) |
| Database | AWS DynamoDB (rate limiting, async job state) |
| Knowledge base | PCAOB independence standards |

## Project Structure

```
PursuitDocs/
├── backend/
│   ├── main.py                    # FastAPI application + Lambda handler (HTTP + async worker routing)
│   ├── backend_requirements.txt
│   └── graph/
│       ├── graph.py               # LangGraph graph definition + orchestration
│       ├── agents/
│       │   ├── drafter.py         # Drafter (initial draft + revisions)
│       │   └── reviewer.py        # Reviewer (two-pass with RAG)
│       ├── nodes/
│       │   └── parser.py          # PDF/HTML extraction + LLM-based RFP parsing
│       └── rag/
│           └── retriever.py       # Chroma retrieval interface
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── components/            # IntakeForm, ProgressIndicator, ResultsDisplay
│       └── services/              # Backend API client
├── data/
│   ├── firm_profile.json          # Synthetic firm profile
│   ├── engagement_team.json       # Synthetic engagement team profiles
│   ├── chroma_db/                 # PCAOB vector database
│   └── test_rfps/
├── data_processing/               # Scraping, chunking, and ingestion scripts
├── evaluation/                    # Synthetic proposals + eval scripts
├── Dockerfile
├── README.md
└── .gitignore
```

## Local Development

1. Create a `.env` file in the project root with your API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)

2. Start the backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

3. Start the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open http://localhost:5173

## Future Improvements

- Engagement team integration with real credentials replacing placeholders
- Drafter retrieval from firm profile — selective lookup based on RFP requirements instead of receiving the full profile
- Synthetic past engagements for the drafter to reference
- Pre-pursuit assessment advising partners on engagement fit
- Full proposal generation beyond the transmittal letter
- Multi-firm support with data isolation
- Reviewer feedback loop using few-shot examples from past corrections

## Evaluation (in progress)

The project will include an evaluation dataset of synthetic proposal letters annotated with independence concerns, reasoning, and PCAOB citations. This will be used to measure the reviewer's accuracy and the drafter's revision quality.


## PCAOB Standards Usage

This project references publicly available PCAOB standards and guidance for educational and demonstration purposes. Per the PCAOB's Terms of Use, PCAOB Public Materials are permitted for use, publication, display, and distribution. This project does not use AICPA-copyrighted interim standards.
