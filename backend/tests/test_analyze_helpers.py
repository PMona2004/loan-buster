from app.models.schemas import ExtractedLoanData
from app.api.analyze import _build_extraction_warnings, _get_unresolved_critical_fields


def test_unresolved_critical_fields_only_include_truly_missing_values():
    extracted = ExtractedLoanData(
        principal_amount=5000.0,
        stated_interest_rate=4.5,
        loan_tenure_days=14,
        total_repayment_amount=5105.0,
        extraction_confidence="low",
        unclear_fields=[
            "principal_amount",
            "stated_interest_rate",
            "loan_tenure_days",
            "total_repayment_amount",
            "processing_fee_percentage",
        ],
    )

    unresolved = _get_unresolved_critical_fields(extracted)

    assert unresolved == []


def test_build_extraction_warnings_suppresses_stale_unclear_critical_fields():
    extracted = ExtractedLoanData(
        principal_amount=5000.0,
        stated_interest_rate=4.5,
        loan_tenure_days=14,
        total_repayment_amount=5105.0,
        extraction_confidence="low",
        unclear_fields=[
            "principal_amount",
            "stated_interest_rate",
            "loan_tenure_days",
            "total_repayment_amount",
        ],
    )

    warnings = _build_extraction_warnings(extracted)

    assert warnings == []


def test_build_extraction_warnings_only_mentions_actually_missing_critical_fields():
    extracted = ExtractedLoanData(
        principal_amount=5000.0,
        stated_interest_rate=4.5,
        loan_tenure_days=None,
        total_repayment_amount=5105.0,
        extraction_confidence="low",
        unclear_fields=[
            "loan_tenure_days",
            "processing_fee_percentage",
        ],
    )

    warnings = _build_extraction_warnings(extracted)

    assert len(warnings) == 2
    assert warnings[1] == "Could not reliably extract: loan_tenure_days"
