"""
LoanLens — APR Engine Unit Tests
Run: pytest tests/ -v

Covers: monthly rate, fee components, short tenure, fee deduction trap,
flat rate, reducing balance, IRR, missing data, severity, heuristic type inference.
"""
import pytest
from app.models.schemas import ExtractedLoanData, InterestType
from app.services.apr_engine import compute_apr, get_severity, format_multiplier


def make_loan(**kwargs) -> ExtractedLoanData:
    defaults = dict(
        principal_amount=50000.0,
        stated_interest_rate=2.0,
        stated_interest_type=InterestType.MONTHLY,
        loan_tenure_days=90,
        processing_fee_amount=2500.0,
        insurance_premium=1500.0,
        gst_on_fees=720.0,
    )
    defaults.update(kwargs)
    return ExtractedLoanData(**defaults)


class TestAPREngine:

    def test_basic_monthly_rate(self):
        """2% monthly = 24% stated annual — but with fees should be much higher."""
        loan = make_loan()
        result = compute_apr(loan)
        assert result is not None
        # Total cost: interest(3000) + pf(2500) + ins(1500) + gst(720) = 7720
        # Simple APR: (7720/50000) * (365/90) * 100 ≈ 62.6%
        assert result.effective_apr_simple > 50
        assert result.effective_apr_simple < 100

    def test_total_cost_components(self):
        """All fee components sum correctly."""
        loan = make_loan(
            principal_amount=100000.0,
            stated_interest_rate=2.0,
            stated_interest_type=InterestType.MONTHLY,
            loan_tenure_days=60,
            processing_fee_amount=5000.0,
            insurance_premium=2000.0,
            gst_on_fees=1260.0,
        )
        result = compute_apr(loan)
        assert result is not None
        # Interest: 100000 * 0.02 * (60/30.44) ≈ 3940
        # Total: ~3940 + 5000 + 2000 + 1260 = ~12200
        assert result.total_cost > 10000
        assert result.total_cost < 16000

    def test_short_tenure_flagged(self):
        """7-day loan should be flagged as short tenure and APR should be extreme."""
        loan = make_loan(loan_tenure_days=7)
        result = compute_apr(loan)
        assert result is not None
        assert result.is_short_tenure is True
        assert result.annualization_note is not None
        assert result.effective_apr_simple > 500

    def test_fee_deduction_trap(self):
        """Fees deducted from disbursement but interest on full principal → trap detected."""
        loan = make_loan(
            principal_amount=50000.0,
            disbursed_amount=45000.0,
            processing_fee_amount=2500.0,
            upfront_fee_before_disbursement=True,
        )
        result = compute_apr(loan)
        assert result is not None
        assert result.fee_deduction_trap is True

    def test_flat_rate_no_fees(self):
        """18% flat annual rate with no fees should give APR close to 18%."""
        loan = make_loan(
            stated_interest_rate=18.0,
            stated_interest_type=InterestType.FLAT,
            loan_tenure_days=365,
            processing_fee_amount=0.0,
            insurance_premium=0.0,
            gst_on_fees=0.0,
        )
        result = compute_apr(loan)
        assert result is not None
        assert abs(result.effective_apr_simple - 18.0) < 3

    def test_reducing_balance_less_than_flat(self):
        """Reducing balance interest should be less than flat for same rate."""
        loan_flat = make_loan(
            stated_interest_type=InterestType.FLAT,
            stated_interest_rate=24.0,
            loan_tenure_days=365,
            processing_fee_amount=0.0,
            insurance_premium=0.0,
            gst_on_fees=0.0,
        )
        loan_reducing = make_loan(
            stated_interest_type=InterestType.REDUCING,
            stated_interest_rate=24.0,
            loan_tenure_days=365,
            processing_fee_amount=0.0,
            insurance_premium=0.0,
            gst_on_fees=0.0,
        )
        flat = compute_apr(loan_flat)
        reducing = compute_apr(loan_reducing)
        assert flat is not None and reducing is not None
        assert reducing.total_interest < flat.total_interest

    def test_missing_principal_returns_none(self):
        """Should return None when principal is missing."""
        loan = ExtractedLoanData(loan_tenure_days=90)
        assert compute_apr(loan) is None

    def test_missing_tenure_returns_none(self):
        """Should return None when tenure is missing."""
        loan = ExtractedLoanData(principal_amount=50000.0)
        assert compute_apr(loan) is None

    def test_irr_compound_apr_computed(self):
        """IRR APR should be computed. For monthly-rate loans with fees it will be
        significantly higher than simple APR due to compounding — both are valid."""
        loan = make_loan(loan_tenure_days=180)
        result = compute_apr(loan)
        assert result is not None
        assert result.effective_apr_compound is not None
        # IRR-based compound rate is always >= simple rate (compounding amplifies cost)
        assert result.effective_apr_compound >= result.effective_apr_simple

    def test_heuristic_type_inference_monthly(self):
        """Rate <= 5 with UNKNOWN type should be treated as monthly."""
        loan = make_loan(
            stated_interest_rate=3.0,
            stated_interest_type=InterestType.UNKNOWN,
            processing_fee_amount=0.0,
            insurance_premium=0.0,
            gst_on_fees=0.0,
        )
        result = compute_apr(loan)
        assert result is not None
        # 3% monthly annualized = 36%, APR without fees should be near that
        assert result.stated_rate_annual == pytest.approx(36.0, abs=1)

    def test_display_apr_cap_flagged_for_extreme_short_tenure(self):
        """Extreme short-tenure loans should keep the cap flag for UI messaging."""
        loan = ExtractedLoanData(
            principal_amount=5000.0,
            stated_interest_rate=4.5,
            stated_interest_type=InterestType.MONTHLY,
            loan_tenure_days=14,
            processing_fee_amount=600.0,
            insurance_premium=150.0,
            gst_on_fees=108.0,
            disbursed_amount=4142.0,
            total_repayment_amount=5105.0,
        )
        result = compute_apr(loan)
        assert result is not None
        assert result.is_short_tenure is True
        assert result.display_apr_capped is True
        assert result.effective_apr_compound == pytest.approx(9999.0, abs=0.01)
        assert result.total_cost == pytest.approx(963.0, abs=0.01)
        assert result.annualization_note == (
            "This is a 14-day loan. You receive \u20b94,142 and repay \u20b95,105, "
            "so the total borrowing cost is \u20b9963. Annualizing a 14-day loan "
            "with that cost produces an extremely high APR."
        )


class TestSeverity:
    def test_safe_zone(self):
        assert get_severity(24.0, 24.0) == ("safe", "#4CAF50")

    def test_caution_zone(self):
        # 48% vs 42% declared: gap=6pp but multiplier=1.14x < 1.5x → stays caution
        assert get_severity(48.0, 42.0) == ("caution", "#FF9800")

    def test_predatory_zone(self):
        # 75% vs 70% declared: gap=5pp and multiplier=1.07x < 1.5x → stays predatory
        assert get_severity(75.0, 70.0) == ("predatory", "#F44336")

    def test_severe_zone(self):
        assert get_severity(150.0, 24.0) == ("severe", "#9C27B0")

    def test_gap_upgrade_safe_to_caution(self):
        """Gap >= 5pp or multiplier >= 1.5x should upgrade safe → caution."""
        # 30% actual vs 24% declared: multiplier = 1.25x, gap = 6pp → upgrade
        assert get_severity(30.0, 24.0) == ("caution", "#FF9800")

    def test_gap_upgrade_caution_to_predatory(self):
        """Multiplier >= 2.0x should upgrade caution → predatory."""
        # 50% actual vs 24% declared: multiplier = 2.08x → upgrade
        assert get_severity(50.0, 24.0) == ("predatory", "#F44336")


class TestMultiplier:
    def test_multiplier_computed(self):
        assert format_multiplier(72.0, 24.0) == pytest.approx(3.0)

    def test_no_declared_returns_none(self):
        assert format_multiplier(72.0, None) is None

    def test_zero_declared_returns_none(self):
        assert format_multiplier(72.0, 0.0) is None
