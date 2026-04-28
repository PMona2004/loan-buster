"""
LoanLens - /analyze API Endpoint
Orchestrates: upload -> extract -> APR -> RBI check -> verdict -> response
"""
import logging
import time
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import AnalysisResult, ExtractedLoanData, RecomputeRequest
from app.services.apr_engine import (
    _normalize_to_annual,
    _resolve_interest_type,
    compute_apr,
    compute_predatory_score,
    format_multiplier,
    get_severity,
)
from app.services.gemini_extraction import GeminiExtractionService
from app.services.rbi_checker import check_rbi_compliance, count_violations
from app.services.verdict_service import VerdictService

logger = logging.getLogger("loanlens.api.analyze")
router = APIRouter()

# Singletons
_extractor = None
_verdict_svc = None

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB
CRITICAL_WARNING_FIELDS = [
    "principal_amount",
    "loan_tenure_days",
    "stated_interest_rate",
    "total_repayment_amount",
]


def _get_unresolved_critical_fields(extracted: ExtractedLoanData) -> list[str]:
    unresolved = []
    for field in CRITICAL_WARNING_FIELDS:
        value = getattr(extracted, field, None)
        if field == "loan_tenure_days":
            if value is None or value <= 0:
                unresolved.append(field)
        elif field in {"principal_amount", "total_repayment_amount"}:
            if value is None or value <= 0:
                unresolved.append(field)
        elif value is None:
            unresolved.append(field)
    return unresolved


def get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = GeminiExtractionService()
    return _extractor


def get_verdict_svc():
    global _verdict_svc
    if _verdict_svc is None:
        _verdict_svc = VerdictService()
    return _verdict_svc


def _build_extraction_warnings(extracted: ExtractedLoanData) -> list[str]:
    unresolved_critical_fields = _get_unresolved_critical_fields(extracted)
    if not unresolved_critical_fields:
        return []

    warnings = []
    if extracted.extraction_confidence.value == "low":
        warnings.append(
            "Low confidence extraction - document may be blurry or partially readable. "
            "Results may be incomplete. Try a clearer scan."
        )

    warnings.append(
        f"Could not reliably extract: {', '.join(unresolved_critical_fields[:5])}"
    )

    return warnings


async def _build_analysis_result(
    *,
    session_id: str,
    extracted: ExtractedLoanData,
    start_time: float,
) -> AnalysisResult:
    extraction_warnings = _build_extraction_warnings(extracted)

    logger.info(f"[{session_id}] Step 2: APR computation...")
    apr_breakdown = compute_apr(extracted)

    actual_apr = None
    declared_apr = None
    apr_multiplier = None

    if apr_breakdown:
        actual_apr = apr_breakdown.effective_apr_compound or apr_breakdown.effective_apr_simple

        declared_apr = extracted.apr_stated_in_document
        if not declared_apr and extracted.stated_interest_rate:
            itype = _resolve_interest_type(
                extracted.stated_interest_rate, extracted.stated_interest_type
            )
            declared_apr, _ = _normalize_to_annual(extracted.stated_interest_rate, itype)

        apr_multiplier = format_multiplier(actual_apr, declared_apr)

    logger.info(f"[{session_id}] Step 3: RBI check...")
    rbi_rules = check_rbi_compliance(extracted)
    violations_count, violations_summary = count_violations(rbi_rules)

    severity, severity_color = "unknown", "#888888"
    pred_score = None
    if actual_apr is not None:
        severity, severity_color = get_severity(actual_apr, declared_apr)
        pred_score = compute_predatory_score(
            actual_apr=actual_apr,
            violations_count=violations_count,
            fee_deduction_trap=apr_breakdown.fee_deduction_trap if apr_breakdown else False,
            is_short_tenure=apr_breakdown.is_short_tenure if apr_breakdown else False,
        )

    logger.info(f"[{session_id}] Step 4: Verdict generation...")
    verdict = await get_verdict_svc().generate_verdict(
        lender_name=extracted.lender_name,
        apr_breakdown=apr_breakdown,
        declared_apr=declared_apr,
        actual_apr=actual_apr,
        violations_count=violations_count,
        violations_summary=violations_summary,
        severity=severity,
    )

    elapsed = round(time.time() - start_time, 2)
    try:
        apr_str = f"{float(actual_apr):.1f}%" if actual_apr is not None else "N/A"
    except (TypeError, ValueError):
        apr_str = "N/A"
    logger.info(
        f"[{session_id}] Done in {elapsed}s | "
        f"APR: {apr_str} | Violations: {violations_count} | Severity: {severity}"
    )

    extractor_instance = get_extractor()
    gemini_model_name = str(extractor_instance.model.model_name)

    return AnalysisResult(
        session_id=session_id,
        extracted=extracted,
        extraction_warnings=extraction_warnings,
        apr_breakdown=apr_breakdown,
        declared_apr=round(declared_apr, 2) if declared_apr is not None else None,
        actual_apr=round(actual_apr, 2) if actual_apr is not None else None,
        apr_multiplier=apr_multiplier,
        rbi_rules=rbi_rules,
        violations_count=violations_count,
        violations_summary=violations_summary,
        verdict=verdict,
        severity=severity,
        severity_color=severity_color,
        predatory_score=pred_score,
        processing_time_seconds=elapsed,
        gemini_model_used=gemini_model_name,
    )


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_loan(file: UploadFile = File(...)):
    """
    Upload a loan agreement (PDF or image).
    Returns complete analysis: extraction, APR, RBI violations, multilingual verdict.
    """
    start = time.time()
    session_id = str(uuid.uuid4())[:8]
    logger.info(f"[{session_id}] New: {file.filename} | {file.content_type}")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Upload PDF or image (JPG/PNG/WebP).",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum 15MB.")
    if len(file_bytes) < 500:
        raise HTTPException(status_code=400, detail="File too small - may be corrupted.")

    logger.info(f"[{session_id}] Step 1: Extraction ({len(file_bytes) // 1024}KB)...")
    try:
        extracted = await get_extractor().extract_from_file(
            file_bytes, content_type, file.filename or "document"
        )
    except Exception as e:
        logger.error(f"[{session_id}] Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Document extraction failed: {str(e)}")

    return await _build_analysis_result(
        session_id=session_id,
        extracted=extracted,
        start_time=start,
    )


@router.post("/analyze/recompute", response_model=AnalysisResult)
async def recompute_analysis(req: RecomputeRequest):
    """Recompute APR, RBI checks, and verdict from extracted fields only."""
    start = time.time()
    session_id = req.session_id or str(uuid.uuid4())[:8]
    logger.info(f"[{session_id}] Recompute request received")

    extracted = req.extracted.model_copy(deep=True)
    if req.loan_tenure_days is not None:
        extracted.loan_tenure_days = req.loan_tenure_days
        extracted.unclear_fields = [
            field for field in extracted.unclear_fields if field != "loan_tenure_days"
        ]

    return await _build_analysis_result(
        session_id=session_id,
        extracted=extracted,
        start_time=start,
    )
