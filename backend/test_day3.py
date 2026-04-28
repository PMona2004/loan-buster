"""Quick Day 2 test: send a real PDF to /api/v1/analyze"""
import httpx
import json
import sys
import os

API = "http://localhost:8000/api/v1"

# Pick the first available test PDF
test_dir = os.path.join(os.path.dirname(__file__), "..", "test_sets_try")
pdfs = [f for f in os.listdir(test_dir) if f.endswith(".pdf")]
pdfs.sort(key=lambda f: os.path.getsize(os.path.join(test_dir, f)))

if not pdfs:
    print("No PDFs found in test_sets_try/")
    sys.exit(1)

pdf_name = "01_mPokket_SEVERE_microloan.pdf"
pdf_path = os.path.join(test_dir, pdf_name)
size_kb = os.path.getsize(pdf_path) // 1024

print(f"Testing: {pdf_name} ({size_kb}KB)")
print("=" * 60)

with open(pdf_path, "rb") as f:
    r = httpx.post(
        f"{API}/analyze",
        files={"file": (pdf_name, f, "application/pdf")},
        timeout=120,
    )

print(f"Status: {r.status_code}")

if r.status_code != 200:
    print(f"Error: {r.text[:500]}")
    sys.exit(1)

d = r.json()

print(f"\nSession:     {d.get('session_id')}")
print(f"Model:       {d.get('gemini_model_used')}")
print(f"Time:        {d.get('processing_time_seconds')}s")

ext = d.get("extracted", {})
print(f"\n--- Extraction ---")
print(f"Lender:      {ext.get('lender_name')}")
print(f"Principal:   {ext.get('principal_amount')}")
print(f"Rate:        {ext.get('stated_interest_rate')}% ({ext.get('stated_interest_type')})")
print(f"Tenure:      {ext.get('loan_tenure_days')} days")
print(f"Proc. fee:   {ext.get('processing_fee_amount')}")
print(f"Insurance:   {ext.get('insurance_premium')}")
print(f"GST:         {ext.get('gst_on_fees')}")
print(f"Disbursed:   {ext.get('disbursed_amount')}")
print(f"KFS present: {ext.get('kfs_present')}")
print(f"Confidence:  {ext.get('extraction_confidence')}")

apr = d.get("apr_breakdown", {})
if apr:
    print(f"\n--- APR ---")
    print(f"Simple:      {apr.get('effective_apr_simple')}%")
    print(f"Compound:    {apr.get('effective_apr_compound')}%")
    print(f"Total cost:  {apr.get('total_cost')}")
    print(f"Fee trap:    {apr.get('fee_deduction_trap')}")
    print(f"Short term:  {apr.get('is_short_tenure')}")

print(f"\n--- Result ---")
print(f"Declared APR: {d.get('declared_apr')}")
print(f"Actual APR:   {d.get('actual_apr')}")
print(f"Severity:     {d.get('severity')}")
print(f"Violations:   {d.get('violations_count')}")

for v in (d.get("violations_summary") or [])[:5]:
    print(f"  - {v}")

verdict = d.get("verdict", {})
en = verdict.get("english", "")
if en:
    print(f"\n--- Verdict (EN) ---")
    print(en[:400])

# Save full response
out_path = os.path.join(os.path.dirname(__file__), "last_analysis.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
print(f"\nFull response saved to: {out_path}")
