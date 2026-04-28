# Loan Buster — V1 Prototype

> AI Predatory Lending Decoder · Solution Challenge 2026  
> Track: Unbiased AI Decision (Open Innovation) · SDGs: 1 · 10 · 16

---

## Status: Prototype / Architecture Planning

This commit represents the **Day 1 prototype phase** of Loan Buster — before a production backend existed. It captures the initial architecture planning, the product requirements document, and the Day 1 validation scripts used to verify the single most important assumption: **can Gemini Vision reliably extract financial data from real Indian loan PDFs?**

The answer was yes. This validated the entire system design.

---

## What's in This Version

```
TEST_CHECK/
├── LoanBuster_PRD.md       ← Full Product Requirements Document (v1.0)
├── validate_day1.py        ← Day 1 APR engine unit tests (no API key needed)
├── main.py                 ← Early single-file prototype (monolithic)
├── models.py               ← Initial Pydantic schema draft
└── multilingual.py         ← Early multilingual verdict prototype
```

---

## The Core Problem

47 crore Indians borrow from digital lending apps. A loan advertised at "2% per month" routinely becomes **60–150% APR** once processing fees (3–5%), insurance premiums (2–3%), GST (18%), and other charges are factored in.

The loan agreement disclosing all this is 12–20 pages of legal English. The borrower — often in financial distress, often semi-literate in English — signs it without understanding what they agreed to.

**RBI's Fair Practice Code (2025) requires lenders to disclose actual APR in a Key Fact Statement before signing. Hundreds of apps violate this. No tool could prove it — until now.**

---

## Architecture (Planned at V1)

```
User uploads loan agreement photo/PDF
          ↓
Gemini Vision extracts all fees, rates, charges, tenure
          ↓
Deterministic Python APR Engine (no AI, no rounding errors)
          ↓
21-Rule RBI Compliance Checker
          ↓
Multilingual verdict (English + Hindi + Kannada)
          ↓
Downloadable PDF evidence report
```

---

## Day 1 Validation Results

`validate_day1.py` runs purely on synthetic loan data — no API key needed. It proved:

| Test Case | Expected APR | Result |
|---|---|---|
| KreditBee-style loan (2% monthly flat, 270 days) | ~34-36% | ✅ Pass |
| mPokket-style microloan (3% monthly, 30 days) | ~110-130% | ✅ Pass |
| Education loan (10.5% annual reducing) | ~10-12% | ✅ Pass |
| Fee deduction trap detection | Flag raised | ✅ Pass |

---

## Tech Stack (Prototype Phase)

- **Python 3.12** — backend logic
- **Pydantic** — data validation and schema definition
- **google-generativeai** — Gemini API access
- **Planned:** FastAPI, WeasyPrint, React, Vite, Firebase, Cloud Run

---

## Why This Matters

The KreditBee test loan: **declared 29.64% APR, actual 34.87% APR**. The difference is ₹589 in fees deducted from disbursement but interest charged on the full ₹35,000 principal. A borrower cannot calculate this without a CA. Loan Buster can — in 60 seconds.

---

## Next: See V2 MVP

The production system is in `src/` (backend + frontend). See `README.md` for the full MVP.

---

*Loan Buster PRD v1.0 | Solution Challenge 2026 | Solo Dev | 8-day sprint*
