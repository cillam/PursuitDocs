# PursuitDocs — Independence Standards Sources

Sources for the Reviewer agent's knowledge base. These documents define what constitutes an independence concern and provide real-world examples of violations.

---

## Primary Sources (PCAOB — Public Materials)

### PCAOB Spotlight: Inspection Observations Related to Auditor Independence
Real inspection findings from 2021-2023 including indemnification clauses, contingent fees, and prohibited services found in engagement letters. Best single source for concrete examples.
- PDF: https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/auditor-independence-spotlight.pdf

### PCAOB Ethics & Independence Rules (Rules 3520–3526)
The actual rules on auditor independence, contingent fees, tax services, prohibited non-audit services, and audit committee communications.
- Web: https://pcaobus.org/oversight/standards/ethics-independence-rules

### PCAOB ET Section 101 — Independence
Detailed interpretations of what impairs independence, including management roles, financial interests, non-audit services, and employment relationships.
- Web: https://pcaobus.org/oversight/standards/ethics-independence-rules/details/ET101

### PCAOB Auditing Standards (Full Booklet)
Complete set of PCAOB auditing standards including AS 1000 (general responsibilities) and independence requirements.
- PDF: https://pcaobus.org/standards/auditing/documents/auditing_standards_audits_fybeginning_on_or_after_december_15_2024.pdf

---

## Secondary Sources (Analysis & Examples)

### SEC Rule 2-01 Non-Audit Services FAQ (via PwC Viewpoint)
Q&A on prohibited services and independence impairment scenarios. Includes specific examples of bookkeeping, translation services, and proposing on prohibited services.
- Web: https://viewpoint.pwc.com/dt/us/en/sec/sec_faqs/sec_faqs_US/auditor_independence_US/E-Non-audit-services.html

### CPA Journal — Independence Matters (2023)
Real SEC enforcement cases with analysis. Includes the EY/Sealed Air case and discussion of the SEC's general standard on independence.
- Web: https://www.cpajournal.com/2023/04/03/independence-matters/

### CPA Journal — ICYMI Independence Matters (2024)
Updated enforcement cases and analysis of independence violations.
- Web: https://www.cpajournal.com/2024/12/06/icymi-independence-matters/

### PCAOB Speech — Rethinking Relevance, Credibility and Transparency
Discussion of cultural independence issues, cross-selling pressures, and the conflict inherent in the auditor being paid by the client.
- Web: https://pcaobus.org/news-events/speeches/speech-detail/rethinking-the-relevance-credibility-and-transparency-of-audits_310

### University of Illinois — Independence Education Materials
Case studies and examples designed for teaching auditor independence concepts. Includes a fictional firm (Meridien) with detailed scenarios.
- PDF: https://giesbusiness.illinois.edu/docs/default-source/default-document-library/centers/cprbs/cs2-independence-alert.pdf

### Lexology — PCAOB Spotlight on Auditor Independence (Analysis)
Summary and analysis of the PCAOB Spotlight with considerations for audit committees.
- Web: https://www.lexology.com/library/detail.aspx?g=7eb7b600-f3d8-4686-86a9-9cfd4c019356

### King & Spalding — PCAOB Sanctions PwC for Independence Violations
Analysis of the 2024 PwC enforcement action related to joint business relationships and failure to consult on independence matters.
- Web: https://www.kslaw.com/blog-posts/pcaob-sanctions-us-audit-firm-for-violations-of-quality-control-standards-concerning-policies-and-procedures-related-to-independence

---

## Key Independence Concern Categories

Based on these sources, the Reviewer agent should flag language in the following categories:

1. **Indemnification clauses** — Firm limiting its liability or client agreeing to hold the firm harmless
2. **Contingent fees** — Fees tied to audit outcomes or findings
3. **Prohibited non-audit services** — Offering bookkeeping, financial statement preparation, internal audit outsourcing, valuation, or system design alongside the audit
4. **Language suggesting lack of objectivity** — "Mutually beneficial," "favorable outcomes," guaranteeing a clean opinion, emphasizing closeness of relationship
5. **Blurring auditor/management roles** — Offering to make management decisions, design internal controls, or take responsibility for financial reporting
6. **Financial interests** — Any language suggesting the firm has a financial stake in the client beyond audit fees
7. **General standard violation** — Any language that would cause a reasonable investor to conclude the auditor is not capable of exercising objective and impartial judgment

---

## Notes

- **Safe to ingest into RAG:** PCAOB public materials and SEC rules/releases (federal government, public domain)
- **Do NOT ingest:** PwC Viewpoint, CPA Journal articles, University of Illinois materials, Lexology, King & Spalding — these are copyrighted third-party analysis
- **Secondary sources are for reference, not the pipeline** — used to understand the domain and design better prompts for the reviewer agent, but their text will not be in the vector store
