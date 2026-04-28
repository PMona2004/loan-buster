import json, httpx

with open("last_analysis.json", encoding="utf-8") as f:
    original = json.load(f)

payload = {
    "session_id": original["session_id"],
    "extracted": original["extracted"],
    "loan_tenure_days": 30
}

r = httpx.post("http://localhost:8000/api/v1/analyze/recompute", json=payload, timeout=60)
print("Recompute status:", r.status_code)
d = r.json()
print("New tenure used:   ", d["apr_breakdown"]["tenure_days"])
print("Original APR:      ", original["actual_apr"], "%")
print("Recomputed APR:    ", d["actual_apr"], "%")
print("Severity:          ", d["severity"])
print("tenure in unclear: ", "loan_tenure_days" in (d["extracted"].get("unclear_fields") or []))
print("PASS" if d["actual_apr"] != original["actual_apr"] else "FAIL - APR unchanged")
