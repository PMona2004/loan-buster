#!/usr/bin/env python3
"""
LoanLens — Day 1 Validation Script
Run this BEFORE writing any more code.

Tests Gemini Vision extraction on a real loan document.
If this works → proceed with full build.
If it fails → add manual fallback form (see note at bottom).

Usage:
  set GEMINI_API_KEY=your-key-here          (Windows)
  export GEMINI_API_KEY="your-key-here"     (Linux/Mac)
  python validate_day1.py --file path/to/loan_agreement.pdf
  python validate_day1.py --file path/to/loan_screenshot.jpg
  python validate_day1.py --demo   # Uses a synthetic test case (no file needed)
"""

import argparse
import asyncio
import json
import os
import sys

# Ensure app.* imports resolve from this directory
sys.path.insert(0, os.path.dirname(__file__))

# ── Extraction prompt (same as production) ───────────────────────────────────

EXTRACTION_PROMPT = """
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
  "kfs_present": true,
  "apr_stated_in_document": 0,
  "repayment_via_bank_transfer": true,
  "cooling_off_period_days": 0,
  "prepayment_terms": "",
  "penal_charges": "",
  "grievance_officer_contact": "",
  "upfront_fee_before_disbursement": true,
  "extraction_confidence": "high|medium|low",
  "unclear_fields": []
}

Rules:
- If a field is not mentioned, set it to null (not 0)
- For interest rate: extract exactly as stated (monthly%, annual%, flat rate)
- List ALL charges found under other_mandatory_charges
- Set extraction_confidence based on document clarity
- Return only valid JSON. No explanation text.
"""


# ── Synthetic test: a known predatory loan structure ─────────────────────────

SYNTHETIC_TEST_TEXT = """
LOAN AGREEMENT

Lender: QuickCash Finance Pvt Ltd
Borrower: Test Borrower

Principal Amount: ₹50,000
Interest Rate: 2% per month (flat)
Loan Tenure: 90 days
Processing Fee: ₹2,500
Insurance Premium: ₹1,500
GST on Fees: ₹720
Total Amount Repayable: ₹57,720

No Key Fact Statement provided.
No cooling-off period mentioned.
Repayment via third-party UPI link.
"""


async def test_with_file(file_path: str):
    import google.generativeai as genai
    import base64

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable first.")
        sys.exit(1)

    genai.configure(api_key=api_key)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    content_type = "application/pdf" if file_path.endswith(".pdf") else "image/jpeg"
    print(f"Testing with: {file_path} ({len(file_bytes)/1024:.0f}KB, {content_type})")

    model = genai.GenerativeModel("gemini-1.5-flash")
    document_part = {
        "inline_data": {
            "mime_type": content_type,
            "data": base64.b64encode(file_bytes).decode("utf-8"),
        }
    }

    print("Sending to Gemini... (this takes 5–15 seconds)")
    response = model.generate_content(
        [document_part, EXTRACTION_PROMPT],
        generation_config=genai.GenerationConfig(temperature=0.0, max_output_tokens=2048),
    )

    raw = response.text.strip()
    print(f"\n── Raw Gemini Response ({len(raw)} chars) ──")
    print(raw[:1000])
    if len(raw) > 1000:
        print("... (truncated)")

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        print("\n── ✅ JSON Parsed Successfully ──")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        _evaluate_quality(data)
    except json.JSONDecodeError as e:
        print(f"\n── ❌ JSON Parse Failed: {e} ──")
        print("FALLBACK NEEDED: Add manual correction form to the frontend.")


def test_synthetic():
    """Test APR computation on known values — no API key needed."""
    print("Running synthetic test (no API needed)...")
    print(f"\nTest loan:\n{SYNTHETIC_TEST_TEXT}")

    # Import from the final app.* package structure
    from app.models.schemas import ExtractedLoanData, InterestType
    from app.services.apr_engine import compute_apr

    # Known-answer test: 2% monthly, ₹50K, 90 days, ₹4720 fees
    loan = ExtractedLoanData(
        principal_amount=50000,
        stated_interest_rate=2.0,
        stated_interest_type=InterestType.MONTHLY,
        loan_tenure_days=90,
        processing_fee_amount=2500,
        insurance_premium=1500,
        gst_on_fees=720,
    )
    result = compute_apr(loan)

    if result is None:
        print("\n❌ APR engine returned None — check principal/tenure inputs")
        return

    print(f"\n── APR Engine Result ──")
    print(f"Stated rate: 2% monthly → {result.stated_rate_annual:.1f}% annualized")
    print(f"APR Simple:   {result.effective_apr_simple:.1f}%  (expect ~62–66%)")
    if result.effective_apr_compound:
        print(f"APR Compound: {result.effective_apr_compound:.1f}%  (expect ~75–85%)")
    print(f"Total cost:   ₹{result.total_cost:,.0f}  (expect ~₹7,720)")
    print(f"\nCost breakdown:")
    print(f"  Interest:       ₹{result.total_interest:,.0f}")
    print(f"  Processing fee: ₹{result.processing_fee:,.0f}")
    print(f"  Insurance:      ₹{result.insurance_premium:,.0f}")
    print(f"  GST on fees:    ₹{result.gst_on_fees:,.0f}")
    print(f"  Other charges:  ₹{result.other_charges:,.0f}")

    # Assertions
    assert result.effective_apr_simple > 50, f"APR too low: {result.effective_apr_simple}"
    assert result.effective_apr_simple < 100, f"APR too high: {result.effective_apr_simple}"
    assert result.total_cost > 7000, f"Total cost too low: {result.total_cost}"
    assert result.total_cost < 9000, f"Total cost too high: {result.total_cost}"

    print("\n✅ APR engine working correctly — proceed with full build!")


def _evaluate_quality(data: dict):
    critical_fields = ["principal_amount", "stated_interest_rate", "loan_tenure_days"]
    found = [f for f in critical_fields if data.get(f) is not None]
    missing = [f for f in critical_fields if data.get(f) is None]

    print(f"\n── Extraction Quality ──")
    print(f"Critical fields found: {len(found)}/3 → {found}")
    if missing:
        print(f"Critical fields MISSING: {missing}")
        print("NOTE: Add a manual input form as fallback for missing fields.")
    else:
        print("✅ All critical fields extracted — proceed with full build!")

    print(f"Confidence: {data.get('extraction_confidence', 'unknown')}")
    unclear = data.get("unclear_fields", [])
    if unclear:
        print(f"Unclear fields: {unclear}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LoanLens Day 1 Validation")
    parser.add_argument("--file", help="Path to loan agreement PDF or image")
    parser.add_argument("--demo", action="store_true", help="Run synthetic test (no file/API needed)")
    args = parser.parse_args()

    if args.demo:
        test_synthetic()
    elif args.file:
        asyncio.run(test_with_file(args.file))
    else:
        print("Usage:")
        print("  python validate_day1.py --demo          # synthetic test, no API key needed")
        print("  python validate_day1.py --file loan.pdf # real document test")
