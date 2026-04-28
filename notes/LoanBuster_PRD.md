# Loan Buster — Product Requirements Document
**Track:** Unbiased AI Decision (Open Innovation)
**SDGs:** 1 · 10 · 16
**Solo Dev | Backend-focused | 8-day MVP**

---

## 1. Problem Statement

Millions of Indians borrow from digital lending apps. A loan advertised at "2% per month" routinely becomes >30% APR once processing fees (3–5%), insurance premiums (2–3%), GST on fees (18%), prepayment penalties, and late-fee compounding are factored in.

The loan agreement disclosing all of this is 12–20 pages of legal English. The borrower — often in financial distress, often semi-literate in English and not understanding finanical terms used — signs it without understanding what they agreed to.

RBI's Fair Practice Code (updated 2025) and Digital Lending Directions (2025) *require* lenders to disclose actual APR in a Key Fact Statement (KFS) before the borrower signs. Hundreds of apps violate this. Nobody can prove it — because computing the real APR from a legal PDF requires a Chartered Accountant.

**Loan Buster eliminates that asymmetry.** Point your phone at any loan document. Get the real cost in 60 seconds, in your language, with RBI violations flagged — exportable as a PDF you can submit to the RBI Ombudsman.

**The one-sentence problem:** Borrowers are legally protected from predatory lending, but they can't read the 20-page proof that they're being cheated.

---

## 2. Solution Overview

Loan Buster is a web app (mobile-responsive) that:

1. Accepts a loan agreement as a **photo, scanned image, or PDF**
2. Uses **Gemini Vision** to extract every fee, charge, rate, and term from the document
3. Runs a **deterministic Python APR engine** to compute the actual annualized cost
4. Checks extracted data against a **RBI Fair Practice Code rule set** (21 checkable rules)
5. Generates a **multilingual verdict** (English, Hindi, Kannada) via Gemini
6. Produces a **downloadable PDF evidence report** with the math, violations, and borrower rights

### What makes it novel
Existing tools (Bankrate APR calculator, MoneyView, KreditBee in-app disclosures) all require the user to *already know* the numbers and input them manually. **Loan Buster extracts the numbers from the document the borrower already received.** The gap is document intelligence + financial computation + legal cross-referencing, combined into one consumer-facing flow. No such tool exists.

---

## 3. Unique Selling Proposition

> "You don't need a CA. You don't need a lawyer. Photograph your loan agreement. Loan Buster tells you in Kannada if you're being cheated — and gives you the paperwork to prove it."

**Differentiators vs. existing tools:**
- **vs. APR calculators**: They need manual input. Loan Buster extracts from document.
- **vs. RBI awareness campaigns**: They explain rights in theory. Loan Buster applies them to your specific document.
- **vs. enterprise compliance tools**: They help lenders stay compliant. Loan Buster protects borrowers.
- **vs. loan aggregators (Paisabazaar, BankBazaar)**: They show you new loans. Loan Buster audits the one you already have.

---

## 4. Features (MVP Scope)

### Core (must ship by Day 7)
| Feature | Description |
|---|---|
| Document Upload | PDF or image (JPG/PNG) upload, max 10MB |
| AI Extraction | Gemini Vision extracts all fees, rates, charges, tenure, principal |
| APR Engine | Deterministic Python computation of effective annualized APR |
| RBI Compliance Checker | 21-rule checklist against RBI Fair Practice Code 2025 |
| Verdict Screen | Side-by-side: declared rate vs actual APR, violation badges |
| Multilingual Output | English + Hindi + Kannada verdict, 1–2 sentences each |
| PDF Report | Downloadable evidence report with math, violations, borrower rights, Ombudsman contact |

### Phase 2 (post-challenge, future roadmap)
- Human-in-the-loop field correction for low-confidence extractions
- RBI Ombudsman complaint auto-draft with prefilled evidence
- Lender credibility score (pulls from RBI's DLA directory API)
- Community database of flagged loan agreements (anonymized)


---

## 5. User Flow

```
[User lands on Loan Buster] 
        ↓
[Upload loan agreement photo or PDF]
        ↓
[Loading screen: "Reading your document..."]
        ↓ (Gemini Vision OCR + extraction, ~8–15 sec)
[Extraction preview: fees table, confirm or manually correct any field]
        ↓
[APR Engine runs + RBI rule checker runs]
        ↓
[RESULTS SCREEN]
 ┌─────────────────────────────────┐
 │ 🔴 DECLARED: 24% APR            │
 │ ⚠️  ACTUAL: 71.4% APR           │
 │                                 │
 │ RBI Violations: 3 found         │
 │  ✗ No KFS provided              │
 │  ✗ APR not stated in agreement  │
 │  ✗ Loan tenure < 30 days        │
 │                                 │
 │ [EN] "You are paying 3× more..."│
 │ [HI] "आप 3 गुना अधिक चुका..."  │
 │ [KN] "ನೀವು 3 ಪಟ್ಟು ಹೆಚ್ಚು..."  │
 │                                 │
 │ [Download Evidence PDF]         │
 │ [Report to RBI Ombudsman]       │
 └─────────────────────────────────┘
```

---

## 6. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND                              │
│  React SPA (Lovable/v0 generated, hosted Firebase)      │
│  Upload → Loading → Results → Download                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS REST
┌──────────────────────▼──────────────────────────────────┐
│                  FASTAPI BACKEND                         │
│              (Cloud Run, free tier)                      │
│                                                          │
│  POST /analyze                                           │
│    1. File validation & preprocessing                    │
│    2. Gemini Vision API → extracted JSON                 │
│    3. APR Engine (Python, deterministic)                 │
│    4. RBI Rule Checker (21 rules)                        │
│    5. Gemini Flash → multilingual verdict                │
│    6. PDF Generator (WeasyPrint)                         │
│    7. Return full AnalysisResult JSON                    │
│                                                          │
│  GET /health                                             │
│  POST /report/pdf  (generate & return PDF bytes)         │
└──────┬────────────────┬────────────────┬────────────────┘
       │                │                │
┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
│ Gemini 1.5  │  │  Firebase   │  │  WeasyPrint │
│ Flash API   │  │  Storage    │  │  PDF Engine │
│ (Google AI) │  │  (files)    │  │  (in-proc)  │
└─────────────┘  └─────────────┘  └─────────────┘
```

### Key Design Decisions
- **No database for MVP**: Results returned as JSON, PDF generated on-the-fly. Firebase Storage only for uploaded files (deleted after 1 hour via lifecycle rule).
- **No user auth for MVP**: Stateless. Each upload gets a UUID session. Add Firebase Auth in Phase 2.
- **Data privacy**: Files deleted from storage after 60 minutes. No PII stored. Stated clearly in UI.
- **Gemini Flash not Pro**: 15× cheaper, fast enough for single document extraction.

---

## 7. RBI Rule Checker — 21 Rules

Based on RBI Digital Lending Directions 2025 + Fair Practice Code:

**Group A: Key Fact Statement (KFS)**
1. KFS present in document
2. APR explicitly stated in KFS
3. All fees itemized in KFS
4. Grievance redressal mechanism stated

**Group B: Loan Terms**
5. Loan tenure ≥ 30 days (RBI mandate)
6. Repayment schedule provided
7. Prepayment terms disclosed
8. Penal charges disclosed
9. Cooling-off period mentioned (3 days minimum)

**Group C: Lender Identity**
10. NBFC/Bank name explicitly stated
11. RBI registration number present
12. Physical address of lender provided
13. Grievance officer contact provided

**Group D: Cost Transparency**
14. Processing fee stated as % or absolute amount
15. Insurance premium disclosed separately
16. GST applicability stated
17. Disbursed amount = sanctioned amount (no deduction without consent)

**Group E: Recovery Practices**
18. No mention of contact list access (data collection)
19. Repayment via bank transfer only (no third-party)
20. Late fee cap compliance (≤ simple interest on overdue)
21. No upfront fee before disbursement

Each rule returns: PASS / FAIL / UNCLEAR (when document doesn't mention it)

---

## 8. APR Computation Engine

### Formula
```
Effective APR = (Total Cost of Loan / Principal) × (365 / Tenure in days) × 100

Total Cost = Total Interest + Processing Fee + Insurance Premium 
             + GST on Fees + Any Other Mandatory Charges

Note: If processing fee is deducted from disbursement but interest charged 
on full principal — this is captured as a separate calculation showing 
"effective principal received vs interest base"
```

### Edge Cases Handled
- Monthly rate → annualized (compound vs simple, both computed)
- Flat rate vs reducing balance (both computed, difference surfaced)
- Short-tenure loans (7–30 days): APR explodes — shown dramatically
- Fees deducted upfront vs collected separately

---

## 9. Tech Stack

| Layer | Technology | Cost |
|---|---|---|
| Backend API | FastAPI (Python 3.11) | Free |
| AI Extraction | Gemini 1.5 Flash (google-generativeai SDK) | Free tier |
| OCR fallback | Cloud Vision API | 300 units/month free |
| PDF Generation | WeasyPrint | Free |
| File Storage | Firebase Storage | Free (Spark plan) |
| Deployment | Cloud Run (GCP) | 2M req/month free |
| Frontend | React + Tailwind (Lovable-generated) | Free |
| Frontend hosting | Firebase Hosting | Free |
| Translation backup | Google Translate API | Free tier |

**Total infrastructure cost: ₹0**

---

## 10. 8-Day Implementation Plan

### Day 1 — Validate Core AI Assumption
- [ ] Find 3 real loan agreement PDFs (KreditBee, MoneyView, banned app screenshots from consumer forums)
- [ ] Test Gemini Vision extraction with the extraction prompt (see Appendix A)
- [ ] If works on 2/3 → proceed. If not → add manual correction form as fallback.
- [ ] Set up repo: `loanlens/` with `backend/`, `frontend/` structure
- [ ] `pip install fastapi uvicorn google-generativeai weasyprint python-multipart`

### Day 2 — Backend Skeleton
- [ ] FastAPI app with `/analyze` endpoint
- [ ] File upload handling (PDF + image)
- [ ] Gemini integration: send document bytes + extraction prompt, parse response JSON
- [ ] Basic error handling + logging
- [ ] Test: curl upload → get raw extracted JSON back

### Day 3 — APR Engine + RBI Checker
- [ ] `apr_engine.py`: deterministic APR computation from extracted fields
- [ ] `rbi_checker.py`: 21-rule evaluation, returns list of Pass/Fail/Unclear
- [ ] Unit tests for APR engine (edge cases: flat rate, short tenure, upfront fee deduction)
- [ ] Wire into `/analyze` endpoint

### Day 4 — Multilingual Output
- [ ] Gemini prompt for verdict generation (English + Hindi + Kannada)
- [ ] `AnalysisResult` Pydantic model: all fields typed, validated
- [ ] Full pipeline test: upload PDF → complete JSON result with all fields

### Day 5 — PDF Report Generator
- [ ] WeasyPrint HTML template for evidence report
- [ ] Sections: Summary, Fee Breakdown Table, APR Calculation Math, RBI Violations Checklist, Borrower Rights, Ombudsman Contact
- [ ] Expose as `POST /report/pdf` → returns PDF bytes

### Day 6 — Frontend (Lovable)
- [ ] Prompt Lovable with the UI spec (see Appendix B)
- [ ] Connect to backend API
- [ ] Upload flow → loading state → results screen → download button
- [ ] Mobile responsive (most users on phone)

### Day 7 — Deploy + Demo Video
- [ ] Dockerfile for Cloud Run
- [ ] `gcloud run deploy loanlens-api`
- [ ] Firebase Hosting for frontend
- [ ] Record 3-minute demo video:
  - 0:00 – Problem statement (60 sec, show real news headline about loan app suicides)
  - 1:00 – Live demo: upload real banned app loan agreement, show results screen
  - 2:00 – Download the PDF evidence report, show RBI Ombudsman section
  - 2:30 – Architecture slide
  - 2:50 – Impact + SDG alignment

### Day 8 — Submission Polish
- [ ] 10-slide project deck (template in Appendix C)
- [ ] GitHub README with setup instructions, architecture diagram, demo link
- [ ] Final submission on hack2skill portal

---

## 11. Presentation Deck Outline (10 Slides)

1. **The Hook** — 60 suicides. ₹9,200 crore lost. One photo changes everything.
2. **The Problem** — 47 crore borrowers. 18-page legal PDFs. Hidden APR of 300–700%.
3. **The Gap** — APR calculators need manual input. No tool reads the document for you.
4. **The Solution** — Loan Buster: photograph → extract → compute → expose.
5. **Live Demo Screenshot** — Before (confusing agreement) → After (clear verdict screen)
6. **How It Works** — Architecture diagram
7. **The RBI Angle** — 21-rule compliance checker. Legal protection made visible.
8. **SDG Alignment** — SDG 1 · 10 · 16 with specific metrics
9. **Tech Stack** — Gemini, Cloud Run, Firebase. Total cost: ₹0.
10. **Impact + Roadmap** — WhatsApp bot → 47 crore borrowers reachable

---

## Appendix A — Gemini Extraction Prompt

```
You are a financial document analyst specializing in Indian lending regulations.

Analyze the provided loan agreement document and extract the following in valid JSON:

{
  "lender_name": "",
  "nbfc_registration_number": "",
  "principal_amount": 0,
  "stated_interest_rate": 0,
  "stated_interest_type": "flat|reducing|monthly|annual",
  "loan_tenure_days": 0,
  "processing_fee_amount": 0,
  "processing_fee_percentage": 0,
  "insurance_premium": 0,
  "gst_on_fees": 0,
  "other_mandatory_charges": [],
  "disbursed_amount": 0,
  "total_repayment_amount": 0,
  "kfs_present": true|false,
  "apr_stated_in_document": 0,
  "repayment_via_bank_transfer": true|false,
  "cooling_off_period_days": 0,
  "prepayment_terms": "",
  "penal_charges": "",
  "grievance_officer_contact": "",
  "upfront_fee_before_disbursement": true|false,
  "extraction_confidence": "high|medium|low",
  "unclear_fields": []
}

Rules:
- If a field is not mentioned, set it to null (not 0)
- For interest rate: extract exactly as stated (monthly%, annual%, flat rate)
- List ALL charges found under other_mandatory_charges
- Set extraction_confidence based on document clarity
- List any fields you couldn't reliably extract in unclear_fields

Return only valid JSON. No explanation text.
```

## Appendix B — Key RBI References

- RBI Digital Lending Directions, 2025 (May 8, 2025) — supersedes 2022 Guidelines
- RBI Fair Practice Code for NBFCs (Master Circular)
- RBI Circular on KFS for Digital Loans (April 2024)
- RBI DLA Directory (operational July 2025) — verify NBFC registration
- RBI Ombudsman Scheme for Digital Transactions — consumer complaint path

---

*LoanBuster PRD v1.0 | Solution Challenge 2026 | Track: Unbiased AI Decision (Open Innovation)*
