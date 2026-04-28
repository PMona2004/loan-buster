from app.models.schemas import ExtractedLoanData
from app.services.gemini_extraction import (
    _apply_post_parse_fallbacks,
    _extract_tenure_days_from_snippet,
    _merge_extractions,
)


def test_extract_tenure_days_from_parenthetical_phrase():
    assert _extract_tenure_days_from_snippet("0 months (14 days)") == 14


def test_apply_post_parse_fallbacks_sets_tenure_and_clears_unclear_flag():
    extracted = ExtractedLoanData(
        loan_tenure_days=None,
        raw_text_snippet="Loan duration: 0 months (14 days)",
        unclear_fields=["loan_tenure_days", "processing_fee_percentage"],
    )

    resolved = _apply_post_parse_fallbacks(extracted)

    assert resolved.loan_tenure_days == 14
    assert "loan_tenure_days" not in resolved.unclear_fields
    assert "processing_fee_percentage" in resolved.unclear_fields


def test_merge_extractions_prefers_highest_total_repayment_amount():
    first = ExtractedLoanData(
        principal_amount=5000.0,
        total_repayment_amount=5019.0,
    )
    second = ExtractedLoanData(
        principal_amount=5000.0,
        total_repayment_amount=5105.0,
    )

    merged = _merge_extractions([first, second])

    assert merged.total_repayment_amount == 5105.0
