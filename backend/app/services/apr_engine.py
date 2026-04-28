"""
LoanLens — APR Computation Engine
Merged best of both agents:
- Simple APR: (total_cost / principal) × (365 / days) × 100
- IRR-based compound APR: per RBI KFS Circular April 2024 methodology
- Smart interest type heuristic when Gemini returns UNKNOWN
- Fee deduction trap detection
- Short-tenure flagging
Pure Python + numpy. Zero AI. Fully deterministic. Unit-testable.
"""
import logging
from typing import Optional

import numpy as np
import numpy_financial as npf

from app.models.schemas import ExtractedLoanData, APRBreakdown, InterestType

logger = logging.getLogger("loanlens.apr")

SHORT_TENURE_DAYS = 30


# ── Public API ────────────────────────────────────────────────────────────────

def compute_apr(extracted: ExtractedLoanData) -> Optional[APRBreakdown]:
    """
    Compute APR from extracted loan data.
    Returns None if principal or tenure is missing.
    """
    principal = extracted.principal_amount
    tenure_days = extracted.loan_tenure_days

    if not principal or not tenure_days or principal <= 0 or tenure_days <= 0:
        logger.warning("APR computation skipped — missing principal or tenure")
        return None

    # 1. Normalize interest rate to annual
    stated_rate = extracted.stated_interest_rate or 0.0
    interest_type = _resolve_interest_type(stated_rate, extracted.stated_interest_type)
    stated_rate_annual, stated_type_label = _normalize_to_annual(stated_rate, interest_type)

    # 2. Compute total interest
    total_interest = _compute_interest(principal, stated_rate, interest_type, tenure_days)

    repayment = principal + total_interest

    # If document states total repayment, that cash-flow figure wins over formula interest.
    if extracted.total_repayment_amount and extracted.total_repayment_amount > principal:
        implied_interest = extracted.total_repayment_amount - principal
        if abs(implied_interest - total_interest) > 0.01:
            logger.info(
                f"Using document total repayment: interest={implied_interest:.0f} "
                f"(vs computed {total_interest:.0f})"
            )
        total_interest = implied_interest
        repayment = extracted.total_repayment_amount

    # 3. Aggregate fees
    processing_fee = _resolve_processing_fee(extracted)
    insurance_premium = extracted.insurance_premium or 0.0
    gst_on_fees = extracted.gst_on_fees or 0.0

    # Estimate GST if not stated but fees exist
    if gst_on_fees == 0 and (processing_fee + insurance_premium) > 0:
        gst_on_fees = (processing_fee + insurance_premium) * 0.18
        logger.info(f"GST estimated at 18% on fees: ₹{gst_on_fees:.0f}")

    # Per RBI KFS Circular: APR excludes contingent charges (EMI Bounce, Penal, Foreclosure).
    # Only mandatory, unconditional charges count toward APR.
    CONTINGENT_KEYWORDS = {
        "bounce", "penal", "penalty", "foreclosure", "prepayment",
        "late", "overdue", "default", "legal", "recall"
    }
    other_charges = sum(
        (c.amount or 0.0) for c in extracted.other_mandatory_charges
        if not any(kw in (c.name or "").lower() or kw in (c.description or "").lower()
                   for kw in CONTINGENT_KEYWORDS)
    )

    total_cost = total_interest + processing_fee + insurance_premium + gst_on_fees + other_charges

    # 4. Simple APR
    effective_apr_simple = (total_cost / principal) * (365 / tenure_days) * 100

    # 5. IRR-based compound APR (per RBI KFS methodology)
    effective_apr_compound = _compute_irr_apr(
        principal=principal,
        processing_fee=processing_fee,
        insurance_premium=insurance_premium,
        gst=gst_on_fees,
        other=other_charges,
        total_interest=total_interest,
        tenure_days=tenure_days,
    )

    # 6. Fee deduction trap detection
    fee_deduction_trap = False
    actual_disbursed = extracted.disbursed_amount
    if actual_disbursed and actual_disbursed < principal:
        # other_charges here should include doc fee (mandatory, unconditional)
        disclosed_fees = processing_fee + insurance_premium + gst_on_fees + other_charges
        unexplained_deduction = (principal - actual_disbursed) - disclosed_fees
        # Threshold: >150 to avoid false positives from rounding and GST estimation
        if unexplained_deduction > 150:
            fee_deduction_trap = True
            logger.info(
                f"Fee deduction trap: got ₹{actual_disbursed:.0f}, "
                f"pay interest on ₹{principal:.0f}"
            )

    # 7. Short tenure
    is_short = tenure_days < SHORT_TENURE_DAYS
    annualization_note = None
    if is_short:
        if actual_disbursed and repayment > 0:
            total_borrowing_cost = repayment - actual_disbursed
            annualization_note = (
                f"This is a {tenure_days}-day loan. You receive ₹{actual_disbursed:,.0f} "
                f"and repay ₹{repayment:,.0f}, so the total borrowing cost is "
                f"₹{total_borrowing_cost:,.0f}. Annualizing a {tenure_days}-day loan "
                f"with that cost produces an extremely high APR."
            )
        else:
            annualization_note = (
                f"This is a {tenure_days}-day loan. Total borrowing cost is "
                f"₹{total_cost:,.0f} on ₹{principal:,.0f} principal. "
                f"Annualizing a {tenure_days}-day loan with that cost produces "
                f"an extremely high APR."
            )

    display_apr_capped = False
    capped_simple = min(effective_apr_simple, 9999.0)
    if capped_simple != effective_apr_simple:
        display_apr_capped = True

    capped_compound = None
    if effective_apr_compound is not None:
        capped_compound = min(effective_apr_compound, 9999.0)
        if capped_compound != effective_apr_compound:
            display_apr_capped = True

    return APRBreakdown(
        principal=principal,
        tenure_days=tenure_days,
        stated_rate_annual=round(stated_rate_annual, 2),
        stated_rate_type=stated_type_label,
        total_interest=round(total_interest, 2),
        processing_fee=round(processing_fee, 2),
        insurance_premium=round(insurance_premium, 2),
        gst_on_fees=round(gst_on_fees, 2),
        other_charges=round(other_charges, 2),
        total_cost=round(total_cost, 2),
        effective_apr_simple=round(capped_simple, 2),
        effective_apr_compound=round(capped_compound, 2) if capped_compound is not None else None,
        is_short_tenure=is_short,
        annualization_note=annualization_note,
        actual_disbursed=actual_disbursed,
        fee_deduction_trap=fee_deduction_trap,
        display_apr_capped=display_apr_capped,
    )


def get_severity(actual_apr: float, declared_apr: Optional[float] = None) -> tuple[str, str]:
    """
    Returns (severity_label, hex_color).
    Considers both absolute APR and the gap from declared APR.
    If lender declared X but charges significantly more, the severity upgrades.
    """
    # Base severity from absolute APR
    if actual_apr < 36:
        base = "safe"
    elif actual_apr <= 60:
        base = "caution"
    elif actual_apr <= 100:
        base = "predatory"
    else:
        base = "severe"

    # Gap-based upgrade: if lender understated APR by ≥5pp or 1.5x, upgrade by one level
    if declared_apr and declared_apr > 0 and actual_apr > declared_apr:
        gap_pp = actual_apr - declared_apr
        multiplier = actual_apr / declared_apr
        if (gap_pp >= 5 or multiplier >= 1.5) and base == "safe":
            base = "caution"
        elif multiplier >= 2.0 and base == "caution":
            base = "predatory"
        elif multiplier >= 3.0 and base == "predatory":
            base = "severe"

    colors = {
        "safe": "#4CAF50",
        "caution": "#FF9800",
        "predatory": "#F44336",
        "severe": "#9C27B0",
    }
    return base, colors[base]


def compute_predatory_score(actual_apr: float, violations_count: int, 
                             fee_deduction_trap: bool, is_short_tenure: bool) -> int:
    """
    Calculates a single 0-100 predatory risk score for the loan.
    Higher = more predatory.
    """
    score = 0
    # APR component (0-60 points)
    if actual_apr > 200: score += 60
    elif actual_apr > 100: score += 45
    elif actual_apr > 60: score += 30
    elif actual_apr > 36: score += 15
    
    # Violations (0-25 points)
    score += min(violations_count * 5, 25)
    
    # Flags (0-15 points)
    if fee_deduction_trap: score += 10
    if is_short_tenure: score += 5
    
    return min(score, 100)


def format_multiplier(actual: float, declared: Optional[float]) -> Optional[float]:
    """How many times more than declared? e.g. 3.1 = '3.1× more than told'."""
    if not declared or declared <= 0:
        return None
    return round(actual / declared, 1)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_interest_type(rate: float, stated_type: InterestType) -> InterestType:
    """
    If Gemini returned UNKNOWN, apply heuristic:
    - rate <= 5 -> almost certainly monthly (Indian microloans use 1–4%)
    - rate > 5 -> almost certainly annual
    """
    if stated_type != InterestType.UNKNOWN:
        return stated_type
    if rate <= 0:
        return InterestType.ANNUAL
    if rate <= 5:
        logger.info(f"Rate {rate}% assumed monthly (heuristic: rate <= 5)")
        return InterestType.MONTHLY
    logger.info(f"Rate {rate}% assumed annual (heuristic: rate > 5)")
    return InterestType.ANNUAL


def _normalize_to_annual(rate: float, interest_type: InterestType) -> tuple[float, str]:
    """Convert stated rate to annualized equivalent for display purposes."""
    if interest_type == InterestType.MONTHLY:
        return rate * 12, "monthly (×12 annualized)"
    elif interest_type == InterestType.FLAT:
        return rate, "flat annual"
    elif interest_type == InterestType.REDUCING:
        return rate, "reducing balance annual"
    elif interest_type == InterestType.ANNUAL:
        return rate, "annual"
    else:
        return rate, "unknown type"


def _compute_interest(
    principal: float,
    rate: float,
    interest_type: InterestType,
    tenure_days: int,
) -> float:
    """Compute total interest charge based on interest type."""
    if rate <= 0:
        return 0.0

    if interest_type == InterestType.MONTHLY:
        months = tenure_days / 30.44  # More accurate average
        return principal * (rate / 100) * months

    elif interest_type == InterestType.FLAT:
        return principal * (rate / 100) * (tenure_days / 365)

    elif interest_type == InterestType.REDUCING:
        monthly_rate = (rate / 100) / 12
        n_months = tenure_days / 30.44
        if monthly_rate == 0:
            emi = principal / max(n_months, 1)
        else:
            emi = principal * monthly_rate / (1 - (1 + monthly_rate) ** -n_months)
        return (emi * n_months) - principal

    elif interest_type == InterestType.ANNUAL:
        return principal * (rate / 100) * (tenure_days / 365)

    else:
        # Fallback: annual simple
        return principal * (rate / 100) * (tenure_days / 365)


def _resolve_processing_fee(extracted: ExtractedLoanData) -> float:
    """Prefer absolute amount; fallback to % of principal."""
    if extracted.processing_fee_amount:
        return extracted.processing_fee_amount
    if extracted.processing_fee_percentage and extracted.principal_amount:
        return (extracted.processing_fee_percentage / 100) * extracted.principal_amount
    return 0.0


def _compute_irr_apr(
    principal: float,
    processing_fee: float,
    insurance_premium: float,
    gst: float,
    other: float,
    total_interest: float,
    tenure_days: int,
) -> Optional[float]:
    """
    IRR-based APR per RBI KFS Circular April 2024.
    - EMI loans (tenure > 45 days): uses npf.irr on monthly cash flows, then
      compounds to annual: ((1 + monthly_irr)^12 - 1) * 100
    - Bullet/short-term loans: analytical 2-cash-flow solution.
    Returns annualized rate as percentage, or None on failure.
    """
    try:
        upfront_costs = processing_fee + insurance_premium + gst + other
        net_disbursed = principal - upfront_costs
        if net_disbursed <= 0:
            logger.warning("IRR skipped: net disbursed <= 0 (fees exceed principal)")
            return None

        repayment = principal + total_interest

        if tenure_days > 45:
            # EMI loan: build monthly cash flow array and solve with npf.irr
            months = max(1, round(tenure_days / 30.44))
            emi = repayment / months
            cash_flows = [-net_disbursed] + [emi] * months
            monthly_irr = npf.irr(cash_flows)
            if monthly_irr is None or np.isnan(monthly_irr) or monthly_irr <= 0:
                return None
            # Compound to annual per RBI KFS methodology
            irr_annual = ((1 + monthly_irr) ** 12 - 1) * 100
            return irr_annual
        else:
            # Bullet/payday loan: analytical 2-cash-flow IRR
            ratio = repayment / net_disbursed
            if ratio <= 0:
                return None
            irr_annual = (ratio ** (365 / tenure_days) - 1) * 100
            return irr_annual

    except Exception as e:
        logger.warning(f"IRR computation failed: {e}")
        return None
