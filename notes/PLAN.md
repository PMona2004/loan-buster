# Short-Sprint Explainability MVP for Loan Buster

## Summary
- Prioritize an explainability-first upgrade that makes the result feel human, trustworthy, and actionable without requiring a large backend redesign.
- Build on existing signals already in the app: `extraction_confidence`, `unclear_fields`, `raw_text_snippet`, RBI rule `detail`, and `rbi_reference`.
- Include a lightweight human-in-the-loop correction step only for low-confidence or missing important fields.
- Defer direct RBI submission; instead ship a complaint packet flow with prefilled text plus downloadable evidence once report rendering is stabilized.

## Key Changes
- **Human-readable cost explanation**
  - Add a new “What this means in real life” block on the results screen.
  - Translate APR into borrower language such as: “You repay about `1.2x` what was stated” or “You borrowed `₹35,000` but total borrowing cost is `₹4,487` before penalties.”
  - Use existing APR inputs and fee breakdown to generate 3-5 short explanation bullets rather than only percentages.
  - Add a “Where this came from” subsection under each explanation using extracted values already present in the response, for example lender name, APR stated, processing fee, total repayment.

- **Explainability-first traceability**
  - Add an evidence panel that maps each key claim to:
    - the document-derived field/value,
    - the plain-language interpretation,
    - the RBI rule or reference already returned by `rbi_rules`.
  - For the first sprint, traceability is field/rule based, not page-coordinate based.
  - Show source phrasing using existing `detail` strings and selected extracted values; do not attempt OCR bounding boxes in this phase.

- **Human-in-the-loop fallback**
  - Only trigger this flow when confidence is `low` or when critical fields needed for APR/RBI checks are missing or unclear.
  - Present a compact review card: “We could not reliably extract these fields. If they are present in your document, fill them in to improve the result.”
  - Restrict manual correction to a short list of high-impact fields:
    - principal amount
    - tenure days
    - stated interest rate/type
    - total repayment amount
    - processing fee
    - insurance premium
    - GST on fees
    - lender name
  - Keep user-entered values visually marked as “user-confirmed” so the result remains honest about what came from AI vs human correction.
  - Re-run APR and RBI checks from corrected values without re-uploading the document.

- **Extraction uncertainty UX**
  - Replace the current single warning line with a clearer confidence module:
    - overall confidence badge,
    - flagged fields list,
    - one-sentence explanation of what low confidence means,
    - entry point into manual review.
  - Treat “not extractable” and “not present in document” as separate states in the UI:
    - `unclear`: maybe present, AI could not verify
    - `missing`: likely not found in document
    - `user_confirmed`: supplied by borrower
  - Keep this as UI and response-interpretation logic unless backend changes are required to distinguish these states cleanly.

- **Complaint packet instead of direct RBI submission**
  - Do not attempt direct `cms.rbi.org.in` submission in this sprint.
  - Add a complaint-ready export flow that produces:
    - downloadable evidence report,
    - prefilled complaint text,
    - compact summary of lender, charges, suspicious mismatch, and RBI issues.
  - If PDF generation is still unreliable locally, fall back to HTML/text complaint packet rather than pretending submission is complete.
  - The CTA becomes “Prepare RBI Complaint Packet” rather than “Submit to RBI.”

## Public Interfaces / Types
- Extend `AnalysisResult` with a minimal explainability section, for example:
  - `explainability_summary: list[str]`
  - `key_findings: list[{label, value, explanation, source_type, source_value, rbi_reference}]`
  - `needs_user_review: bool`
  - `reviewable_fields: list[str]`
- Keep existing analysis request shape unchanged.
- Add an optional lightweight endpoint for corrected inputs only if needed for clean separation:
  - `POST /api/v1/analyze/recompute`
  - Input: `session_id` plus user-confirmed field overrides
  - Output: refreshed `AnalysisResult`
- Keep `POST /api/v1/report/pdf` but treat it as one export target within a broader complaint packet flow.

## Test Plan
- Result screen shows at least 3 human-readable explanation bullets for a normal successful analysis.
- Each key claim in the UI links to a concrete extracted value or RBI rule reference already returned by the backend.
- Low-confidence analysis shows confidence state, flagged fields, and manual review entry point.
- Manual correction of one missing financial field changes APR/compliance outputs without requiring a new upload.
- User-corrected values are visibly labeled and not confused with model-extracted values.
- High-confidence analyses do not force manual review.
- Complaint packet flow works even when PDF rendering falls back; user still gets complaint text and evidence content.
- Local PDF failure does not block complaint preparation.

## Assumptions
- Sprint target is a fast AI-prototyped MVP, not a production-grade audit trail system.
- Primary product goal is borrower trust and comprehension, not perfect extraction provenance.
- “Traceable to source” means traceable to extracted document fields and RBI rule references in this phase, not exact page highlights.
- Direct RBI submission is deferred because official integration certainty is low and current report generation needs stabilization first.
- Explainability is the main differentiator over a plain calculator: the app reads the agreement, surfaces hidden terms, and explains them in borrower language.
