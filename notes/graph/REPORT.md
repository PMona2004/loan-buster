# Graph Report - loan lens  (2026-04-26)

## Corpus Check
- 26 files · ~24,929 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 234 nodes · 562 edges · 13 communities detected
- Extraction: 42% EXTRACTED · 58% INFERRED · 0% AMBIGUOUS · INFERRED: 328 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 21|Community 21]]

## God Nodes (most connected - your core abstractions)
1. `ExtractedLoanData` - 98 edges
2. `InterestType` - 77 edges
3. `APRBreakdown` - 31 edges
4. `compute_apr()` - 22 edges
5. `ExtractionConfidence` - 21 edges
6. `OtherCharge` - 20 edges
7. `_build_analysis_result()` - 17 edges
8. `GeminiExtractionService` - 17 edges
9. `analyze_loan()` - 16 edges
10. `TestAPREngine` - 14 edges

## Surprising Connections (you probably didn't know these)
- `test_synthetic()` --calls--> `ExtractedLoanData`  [INFERRED]
  src\backend\validate_day1.py → src\backend\app\models\schemas.py
- `test_synthetic()` --calls--> `compute_apr()`  [INFERRED]
  src\backend\validate_day1.py → src\backend\app\services\apr_engine.py
- `Test APR computation on known values — no API key needed.` --uses--> `ExtractedLoanData`  [INFERRED]
  backend\validate_day1.py → src\backend\app\models\schemas.py
- `Test APR computation on known values — no API key needed.` --uses--> `InterestType`  [INFERRED]
  backend\validate_day1.py → src\backend\app\models\schemas.py
- `get_extractor()` --calls--> `GeminiExtractionService`  [INFERRED]
  src\backend\app\api\analyze.py → src\backend\app\services\gemini_extraction.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (37): analyze_loan(), _build_analysis_result(), _build_extraction_warnings(), get_extractor(), _get_unresolved_critical_fields(), get_verdict_svc(), LoanLens — /analyze API Endpoint Orchestrates: upload → extract → APR → RBI che, Upload a loan agreement (PDF or image).     Returns complete analysis: extractio (+29 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (43): LoanLens — APR Computation Engine Merged best of both agents: - Simple APR: (t, Returns (severity_label, hex_color).     Considers both absolute APR and the ga, Returns (severity_label, hex_color).     Considers both absolute APR and the ga, Returns (severity_label, hex_color).     Considers both absolute APR and the ga, Calculates a single 0-100 predatory risk score for the loan.     Higher = more, Calculates a single 0-100 predatory risk score for the loan.     Higher = more, Calculates a single 0-100 predatory risk score for the loan.     Higher = more, How many times more than declared? e.g. 3.1 = '3.1× more than told'. (+35 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (32): _apply_post_parse_fallbacks(), _clean_json(), _extract_tenure_days_from_snippet(), GeminiExtractionService, _merge_extractions(), _parse_response(), _pdf_to_images(), LoanLens — Gemini Vision Extraction Service Best of both agents: - PyMuPDF mul (+24 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (20): compute_apr(), _compute_interest(), _compute_irr_apr(), _normalize_to_annual(), _resolve_interest_type(), _resolve_processing_fee(), make_loan(), LoanLens — APR Engine Unit Tests (2 new edge cases) Run: pytest tests/ -v  Co (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (9): buildExplanations(), ConfidenceModule(), ExplainBlock(), extractTenureCandidateDays(), fmt(), fmtINR(), getUnresolvedCriticalFields(), ResultsScreen() (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.23
Nodes (11): build_html_fallback(), build_pdf_bytes(), _fmt_inr(), PDFReportRequest, LoanLens — PDF Evidence Report Generator Produces a downloadable, printable PDF, Render HTML report and convert to PDF via WeasyPrint., Return HTML if WeasyPrint unavailable., _render_html() (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.31
Nodes (4): get_severity(), Gap >= 5pp or multiplier >= 1.5x should upgrade safe → caution., Multiplier >= 2.0x should upgrade caution → predatory., TestSeverity

### Community 7 - "Community 7"
Cohesion: 0.5
Nodes (4): _evaluate_quality(), Test APR computation on known values — no API key needed., test_synthetic(), test_with_file()

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (4): BaseSettings, Config, Loan Buster — App Configuration, Settings

### Community 9 - "Community 9"
Cohesion: 0.6
Nodes (2): format_multiplier(), TestMultiplier

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (1): Pytest configuration — ensures 'app.*' imports resolve correctly. Without this f

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (1): Quick Day 2 test: send a real PDF to /api/v1/analyze

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): The complete payload returned to the frontend after analysis.

## Knowledge Gaps
- **14 isolated node(s):** `Pytest configuration — ensures 'app.*' imports resolve correctly. Without this f`, `Quick Day 2 test: send a real PDF to /api/v1/analyze`, `Loan Buster — FastAPI Backend AI Predatory Lending Decoder · Solution Challenge`, `Config`, `Loan Buster — App Configuration` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 9`** (5 nodes): `format_multiplier()`, `TestMultiplier`, `.test_multiplier_computed()`, `.test_no_declared_returns_none()`, `.test_zero_declared_returns_none()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 10`** (2 nodes): `conftest.py`, `Pytest configuration — ensures 'app.*' imports resolve correctly. Without this f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (2 nodes): `test_day2.py`, `Quick Day 2 test: send a real PDF to /api/v1/analyze`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `The complete payload returned to the frontend after analysis.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExtractedLoanData` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 6`, `Community 7`, `Community 9`?**
  _High betweenness centrality (0.359) - this node is a cross-community bridge._
- **Why does `InterestType` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 6`, `Community 7`, `Community 9`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `PDFReportRequest` connect `Community 5` to `Community 0`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 95 inferred relationships involving `ExtractedLoanData` (e.g. with `Test APR computation on known values — no API key needed.` and `LoanLens — /analyze API Endpoint Orchestrates: upload → extract → APR → RBI che`) actually correct?**
  _`ExtractedLoanData` has 95 INFERRED edges - model-reasoned connections that need verification._
- **Are the 74 inferred relationships involving `InterestType` (e.g. with `Test APR computation on known values — no API key needed.` and `LoanLens — APR Computation Engine Merged best of both agents: - Simple APR: (t`) actually correct?**
  _`InterestType` has 74 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `APRBreakdown` (e.g. with `LoanLens — APR Computation Engine Merged best of both agents: - Simple APR: (t` and `Compute APR from extracted loan data.     Returns None if principal or tenure i`) actually correct?**
  _`APRBreakdown` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `compute_apr()` (e.g. with `test_synthetic()` and `_build_analysis_result()`) actually correct?**
  _`compute_apr()` has 15 INFERRED edges - model-reasoned connections that need verification._