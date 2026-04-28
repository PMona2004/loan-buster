"""
RBI Compliance Checker — Unit Tests
Identified as untested by graphify god-node audit:
  check_rbi_compliance() has 16 edges but ZERO test nodes connect to it directly.
  This file closes that gap.
"""
import pytest
from app.models.schemas import ExtractedLoanData, InterestType, OtherCharge
from app.services.rbi_checker import check_rbi_compliance, count_violations


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_clean_loan(**overrides) -> ExtractedLoanData:
    """A fully-compliant loan that should PASS most rules."""
    defaults = dict(
        lender_name="TestBank NBFC",
        nbfc_registration_number="N-14.03218",
        principal_amount=50000.0,
        loan_tenure_days=180,
        stated_interest_rate=18.0,
        stated_interest_type=InterestType.ANNUAL,
        total_repayment_amount=54500.0,
        disbursed_amount=49100.0,          # 900 deducted = fee below
        processing_fee_amount=900.0,
        processing_fee_percentage=None,
        insurance_premium=None,
        gst_on_fees=None,
        kfs_present=True,
        apr_stated_in_document=21.5,
        grievance_officer_contact="grievance@testbank.in | 1800-XXX-XXXX",
        prepayment_terms="Prepayment allowed after 3 EMIs. Zero foreclosure charges.",
        penal_charges="2% per month simple interest on overdue principal only.",
        cooling_off_period_days=7,
        repayment_via_bank_transfer=True,
        other_mandatory_charges=[],
        unclear_fields=[],
        raw_text_snippet="",
        extraction_confidence="high",
    )
    defaults.update(overrides)
    return ExtractedLoanData(**defaults)


def results_by_id(rules: list) -> dict:
    return {r.rule_id: r.result for r in rules}


# ── Group A: Key Fact Statement ───────────────────────────────────────────────

class TestGroupA:
    def test_kfs_present_passes_rule_1(self):
        rules = check_rbi_compliance(make_clean_loan(kfs_present=True))
        assert results_by_id(rules)[1] == "pass"

    def test_kfs_absent_fails_rule_1(self):
        rules = check_rbi_compliance(make_clean_loan(kfs_present=False))
        assert results_by_id(rules)[1] == "fail"

    def test_kfs_unknown_unclear_rule_1(self):
        rules = check_rbi_compliance(make_clean_loan(kfs_present=None))
        assert results_by_id(rules)[1] == "unclear"

    def test_apr_stated_passes_rule_2(self):
        rules = check_rbi_compliance(make_clean_loan(apr_stated_in_document=29.6))
        assert results_by_id(rules)[2] == "pass"

    def test_apr_not_stated_no_kfs_fails_rule_2(self):
        rules = check_rbi_compliance(make_clean_loan(
            apr_stated_in_document=None, kfs_present=False
        ))
        assert results_by_id(rules)[2] == "fail"

    def test_grievance_contact_passes_rule_4(self):
        rules = check_rbi_compliance(make_clean_loan(
            grievance_officer_contact="help@lender.com"
        ))
        assert results_by_id(rules)[4] == "pass"

    def test_no_grievance_contact_fails_rule_4(self):
        rules = check_rbi_compliance(make_clean_loan(
            grievance_officer_contact=None
        ))
        assert results_by_id(rules)[4] == "fail"


# ── Group B: Loan Terms ───────────────────────────────────────────────────────

class TestGroupB:
    def test_tenure_exactly_30_passes_rule_5(self):
        rules = check_rbi_compliance(make_clean_loan(loan_tenure_days=30))
        assert results_by_id(rules)[5] == "pass"

    def test_tenure_29_fails_rule_5(self):
        rules = check_rbi_compliance(make_clean_loan(loan_tenure_days=29))
        assert results_by_id(rules)[5] == "fail"

    def test_tenure_missing_unclear_rule_5(self):
        rules = check_rbi_compliance(make_clean_loan(loan_tenure_days=None))
        assert results_by_id(rules)[5] == "unclear"

    def test_compound_penal_fails_rule_9(self):
        rules = check_rbi_compliance(make_clean_loan(
            penal_charges="compound interest at 3% per month on overdue"
        ))
        assert results_by_id(rules)[9] == "fail"

    def test_simple_penal_passes_rule_9(self):
        rules = check_rbi_compliance(make_clean_loan(
            penal_charges="2% per month simple interest on overdue"
        ))
        assert results_by_id(rules)[9] == "pass"

    def test_no_penal_unclear_rule_9(self):
        rules = check_rbi_compliance(make_clean_loan(penal_charges=None))
        assert results_by_id(rules)[9] == "unclear"

    def test_cooling_off_exactly_3_passes_rule_10(self):
        rules = check_rbi_compliance(make_clean_loan(cooling_off_period_days=3))
        assert results_by_id(rules)[10] == "pass"

    def test_cooling_off_2_days_fails_rule_10(self):
        rules = check_rbi_compliance(make_clean_loan(cooling_off_period_days=2))
        assert results_by_id(rules)[10] == "fail"

    def test_no_cooling_off_mentioned_fails_rule_10(self):
        """Missing cooling-off should FAIL (strict — borrower right)."""
        rules = check_rbi_compliance(make_clean_loan(cooling_off_period_days=None))
        assert results_by_id(rules)[10] == "fail"


# ── Group C: Lender Identity ─────────────────────────────────────────────────

class TestGroupC:
    def test_lender_name_present_passes_rule_11(self):
        rules = check_rbi_compliance(make_clean_loan(lender_name="TestNBFC Ltd"))
        assert results_by_id(rules)[11] == "pass"

    def test_lender_name_missing_fails_rule_11(self):
        rules = check_rbi_compliance(make_clean_loan(lender_name=None))
        assert results_by_id(rules)[11] == "fail"

    def test_registration_number_present_passes_rule_12(self):
        rules = check_rbi_compliance(make_clean_loan(nbfc_registration_number="N-12.00001"))
        assert results_by_id(rules)[12] == "pass"

    def test_no_registration_fails_rule_12(self):
        rules = check_rbi_compliance(make_clean_loan(nbfc_registration_number=None))
        assert results_by_id(rules)[12] == "fail"


# ── Group D: Cost Transparency ────────────────────────────────────────────────

class TestGroupD:
    def test_disbursement_matches_disclosed_fees_passes_rule_17(self):
        """900 deducted, 900 processing fee disclosed → PASS."""
        rules = check_rbi_compliance(make_clean_loan(
            principal_amount=50000,
            disbursed_amount=49100,
            processing_fee_amount=900,
        ))
        assert results_by_id(rules)[17] == "pass"

    def test_unexplained_deduction_over_150_fails_rule_17(self):
        """1500 deducted but only 200 disclosed → 1300 unexplained → FAIL."""
        rules = check_rbi_compliance(make_clean_loan(
            principal_amount=50000,
            disbursed_amount=48500,
            processing_fee_amount=200,
            insurance_premium=None,
            gst_on_fees=None,
        ))
        assert results_by_id(rules)[17] == "fail"

    def test_disbursement_data_missing_unclear_rule_17(self):
        rules = check_rbi_compliance(make_clean_loan(
            disbursed_amount=None
        ))
        assert results_by_id(rules)[17] == "unclear"


# ── Group E: Recovery Practices ──────────────────────────────────────────────

class TestGroupE:
    def test_hidden_fee_deduction_fails_rule_18(self):
        """Unexplained deduction > 150 → undisclosed upfront fee → FAIL."""
        rules = check_rbi_compliance(make_clean_loan(
            principal_amount=30000,
            disbursed_amount=28000,   # 2000 deducted
            processing_fee_amount=500,  # only 500 disclosed
            insurance_premium=None,
            gst_on_fees=None,
        ))
        assert results_by_id(rules)[18] == "fail"

    def test_full_disbursement_passes_rule_18(self):
        rules = check_rbi_compliance(make_clean_loan(
            principal_amount=30000,
            disbursed_amount=30000,
            processing_fee_amount=0,
        ))
        assert results_by_id(rules)[18] == "pass"

    def test_repayment_bank_transfer_true_passes_rule_19(self):
        rules = check_rbi_compliance(make_clean_loan(repayment_via_bank_transfer=True))
        assert results_by_id(rules)[19] == "pass"

    def test_repayment_not_bank_transfer_fails_rule_19(self):
        rules = check_rbi_compliance(make_clean_loan(repayment_via_bank_transfer=False))
        assert results_by_id(rules)[19] == "fail"

    def test_repayment_unspecified_unclear_rule_19(self):
        rules = check_rbi_compliance(make_clean_loan(repayment_via_bank_transfer=None))
        assert results_by_id(rules)[19] == "unclear"

    def test_rule_21_always_unclear(self):
        """App permissions cannot be verified from document alone."""
        rules = check_rbi_compliance(make_clean_loan())
        assert results_by_id(rules)[21] == "unclear"


# ── count_violations helper ───────────────────────────────────────────────────

class TestCountViolations:
    def test_fully_compliant_loan_zero_violations(self):
        rules = check_rbi_compliance(make_clean_loan())
        count, summaries = count_violations(rules)
        # Clean loan may still have UNCLEAR rules but should have 0 FAILs
        assert count == 0
        assert summaries == []

    def test_bad_loan_has_multiple_violations(self):
        """A loan with no KFS, no lender name, compound penal should have ≥3 violations."""
        rules = check_rbi_compliance(make_clean_loan(
            kfs_present=False,
            lender_name=None,
            nbfc_registration_number=None,
            penal_charges="compound interest charged",
            cooling_off_period_days=None,
            grievance_officer_contact=None,
        ))
        count, summaries = count_violations(rules)
        assert count >= 3
        assert all(s.startswith("Rule") for s in summaries)

    def test_returns_21_rules_total(self):
        rules = check_rbi_compliance(make_clean_loan())
        assert len(rules) == 21
