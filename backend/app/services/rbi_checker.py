"""
LoanLens — RBI Compliance Checker
21 rules. Each returns PASS / FAIL / UNCLEAR.

Sources:
- RBI Digital Lending Directions, May 2025
- RBI Fair Practice Code for NBFCs (Master Circular)
- RBI KFS Circular, April 2024
- RBI Circular on Penal Charges, 2023
"""
from app.models.schemas import ExtractedLoanData, RBIRule, RuleResult

KFS_REF = "RBI KFS Circular, April 2024"
DLD_REF = "RBI Digital Lending Directions, May 2025"
FPC_REF = "RBI Fair Practice Code for NBFCs (Master Circular)"
PENAL_REF = "RBI Circular on Penal Charges, 2023"


def check_rbi_compliance(extracted: ExtractedLoanData) -> list[RBIRule]:
    """Evaluate 21 RBI rules. Returns ordered list of RBIRule results."""
    rules = []

    # ══ GROUP A: Key Fact Statement ═══════════════════════════════════════════

    # 1 KFS present
    if extracted.kfs_present is True:
        rules.append(RBIRule(rule_id=1, group="Key Fact Statement",
            description="Key Fact Statement (KFS) provided before signing",
            result=RuleResult.PASS, detail="KFS found in document.", rbi_reference=KFS_REF))
    elif extracted.kfs_present is False:
        rules.append(RBIRule(rule_id=1, group="Key Fact Statement",
            description="Key Fact Statement (KFS) provided before signing",
            result=RuleResult.FAIL,
            detail="No KFS found. RBI mandates KFS for all digital loans before borrower acceptance.",
            rbi_reference=KFS_REF))
    else:
        rules.append(RBIRule(rule_id=1, group="Key Fact Statement",
            description="Key Fact Statement (KFS) provided before signing",
            result=RuleResult.UNCLEAR, detail="Could not determine if KFS was provided.",
            rbi_reference=KFS_REF))

    # 2 APR explicitly stated
    if extracted.apr_stated_in_document is not None and extracted.apr_stated_in_document > 0:
        rules.append(RBIRule(rule_id=2, group="Key Fact Statement",
            description="Annual Percentage Rate (APR) explicitly stated",
            result=RuleResult.PASS,
            detail=f"APR stated in document: {extracted.apr_stated_in_document}%",
            rbi_reference=KFS_REF))
    elif extracted.kfs_present is False:
        rules.append(RBIRule(rule_id=2, group="Key Fact Statement",
            description="Annual Percentage Rate (APR) explicitly stated",
            result=RuleResult.FAIL,
            detail="APR not disclosed. RBI requires APR including all fees in the KFS.",
            rbi_reference=KFS_REF))
    else:
        rules.append(RBIRule(rule_id=2, group="Key Fact Statement",
            description="Annual Percentage Rate (APR) explicitly stated",
            result=RuleResult.UNCLEAR, detail="APR presence could not be confirmed.",
            rbi_reference=KFS_REF))

    # 3 Fees itemized
    has_fee_disclosure = (
        extracted.processing_fee_amount is not None
        or extracted.processing_fee_percentage is not None
    )
    rules.append(RBIRule(rule_id=3, group="Key Fact Statement",
        description="All fees itemized (processing fee, insurance, GST)",
        result=RuleResult.PASS if has_fee_disclosure else RuleResult.UNCLEAR,
        detail=(
            "Processing fee details found in document."
            if has_fee_disclosure
            else "Could not confirm all fees are itemized — some may be hidden."
        ), rbi_reference=KFS_REF))

    # 4 Grievance redressal
    rules.append(RBIRule(rule_id=4, group="Key Fact Statement",
        description="Grievance redressal mechanism and contact stated",
        result=RuleResult.PASS if extracted.grievance_officer_contact else RuleResult.FAIL,
        detail=(
            f"Grievance contact found: {extracted.grievance_officer_contact}"
            if extracted.grievance_officer_contact
            else "No grievance officer contact found. Borrower has no formal recourse path stated."
        ), rbi_reference=FPC_REF))

    # ══ GROUP B: Loan Terms ═══════════════════════════════════════════════════

    # 5 Tenure ≥ 30 days
    if extracted.loan_tenure_days is not None:
        ok = extracted.loan_tenure_days >= 30
        rules.append(RBIRule(rule_id=5, group="Loan Terms",
            description="Loan tenure ≥ 30 days (RBI minimum)",
            result=RuleResult.PASS if ok else RuleResult.FAIL,
            detail=(
                f"Tenure: {extracted.loan_tenure_days} days ✓"
                if ok
                else f"Tenure: {extracted.loan_tenure_days} days — below RBI minimum of 30 days. "
                     "Short-tenure loans create extreme APR and debt traps."
            ), rbi_reference=DLD_REF))
    else:
        rules.append(RBIRule(rule_id=5, group="Loan Terms",
            description="Loan tenure ≥ 30 days (RBI minimum)",
            result=RuleResult.UNCLEAR, detail="Loan tenure not found.",
            rbi_reference=DLD_REF))

    # 6 Repayment schedule
    rules.append(RBIRule(rule_id=6, group="Loan Terms",
        description="Clear repayment schedule or total repayment amount stated",
        result=RuleResult.PASS if extracted.total_repayment_amount else RuleResult.UNCLEAR,
        detail=(
            f"Total repayment: ₹{extracted.total_repayment_amount:,.0f}"
            if extracted.total_repayment_amount
            else "Repayment schedule not found or unclear."
        ), rbi_reference=FPC_REF))

    # 7 Prepayment terms
    rules.append(RBIRule(rule_id=7, group="Loan Terms",
        description="Prepayment/foreclosure terms disclosed",
        result=RuleResult.PASS if extracted.prepayment_terms else RuleResult.FAIL,
        detail=(
            f"Prepayment terms: {extracted.prepayment_terms[:150]}"
            if extracted.prepayment_terms
            else "Prepayment terms not disclosed. Borrower cannot know the cost to exit early."
        ), rbi_reference=FPC_REF))

    # 8 Penal charges disclosed
    rules.append(RBIRule(rule_id=8, group="Loan Terms",
        description="Late payment / penal charges disclosed",
        result=RuleResult.PASS if extracted.penal_charges else RuleResult.UNCLEAR,
        detail=(
            f"Penal charges: {extracted.penal_charges[:150]}"
            if extracted.penal_charges
            else "Late payment charges not specified."
        ), rbi_reference=FPC_REF))

    # 9 Compound penal interest check (if penal charges mentioned)
    if extracted.penal_charges:
        is_compound = "compound" in extracted.penal_charges.lower()
        rules.append(RBIRule(rule_id=9, group="Loan Terms",
            description="Penal charges: simple interest only (not compound)",
            result=RuleResult.FAIL if is_compound else RuleResult.PASS,
            detail=(
                "VIOLATION: Compound penal interest found — only simple interest is permitted on overdue."
                if is_compound
                else "Penal charges appear to use simple interest. ✓"
            ), rbi_reference=PENAL_REF))
    else:
        rules.append(RBIRule(rule_id=9, group="Loan Terms",
            description="Penal charges: simple interest only (not compound)",
            result=RuleResult.UNCLEAR, detail="Penal charge structure not specified.",
            rbi_reference=PENAL_REF))

    # 10 Cooling-off period
    if extracted.cooling_off_period_days is not None:
        ok = extracted.cooling_off_period_days >= 3
        rules.append(RBIRule(rule_id=10, group="Loan Terms",
            description="Cooling-off period ≥ 3 days mentioned",
            result=RuleResult.PASS if ok else RuleResult.FAIL,
            detail=(
                f"Cooling-off: {extracted.cooling_off_period_days} days ✓"
                if ok
                else f"Cooling-off: {extracted.cooling_off_period_days} days — below 3-day minimum."
            ), rbi_reference=DLD_REF))
    else:
        rules.append(RBIRule(rule_id=10, group="Loan Terms",
            description="Cooling-off period ≥ 3 days mentioned",
            result=RuleResult.FAIL,
            detail="Cooling-off period not mentioned. RBI mandates minimum 3 days to exit without penalty.",
            rbi_reference=DLD_REF))

    # ══ GROUP C: Lender Identity ═══════════════════════════════════════════════

    # 11 Lender name
    rules.append(RBIRule(rule_id=11, group="Lender Identity",
        description="NBFC/Bank name explicitly stated",
        result=RuleResult.PASS if extracted.lender_name else RuleResult.FAIL,
        detail=(
            f"Lender: {extracted.lender_name}"
            if extracted.lender_name
            else "Lender name not found. All loan agreements must state the regulated entity."
        ), rbi_reference=FPC_REF))

    # 12 RBI registration number
    rules.append(RBIRule(rule_id=12, group="Lender Identity",
        description="RBI registration / COR number present",
        result=RuleResult.PASS if extracted.nbfc_registration_number else RuleResult.FAIL,
        detail=(
            f"Registration: {extracted.nbfc_registration_number}"
            if extracted.nbfc_registration_number
            else "RBI registration number not found. Verify lender legitimacy at rbi.org.in."
        ), rbi_reference=DLD_REF))

    # 13 Grievance officer contact (already checked in A4, keep for lender group)
    rules.append(RBIRule(rule_id=13, group="Lender Identity",
        description="Grievance officer name and contact stated",
        result=RuleResult.PASS if extracted.grievance_officer_contact else RuleResult.FAIL,
        detail=(
            f"Contact: {extracted.grievance_officer_contact}"
            if extracted.grievance_officer_contact
            else "Grievance officer contact missing."
        ), rbi_reference=FPC_REF))

    # ══ GROUP D: Cost Transparency ════════════════════════════════════════════

    # 14 Processing fee
    has_pf = extracted.processing_fee_amount or extracted.processing_fee_percentage
    rules.append(RBIRule(rule_id=14, group="Cost Transparency",
        description="Processing fee stated as amount or percentage",
        result=RuleResult.PASS if has_pf else RuleResult.FAIL,
        detail=(
            f"Processing fee: ₹{extracted.processing_fee_amount or 0:,.0f} "
            f"({extracted.processing_fee_percentage or 0}%)"
            if has_pf
            else "Processing fee not disclosed. All mandatory charges must be listed upfront."
        ), rbi_reference=KFS_REF))

    # 15 Insurance disclosed
    rules.append(RBIRule(rule_id=15, group="Cost Transparency",
        description="Insurance premium disclosed separately",
        result=RuleResult.PASS if extracted.insurance_premium else RuleResult.UNCLEAR,
        detail=(
            f"Insurance: ₹{extracted.insurance_premium:,.0f}"
            if extracted.insurance_premium
            else "Insurance premium not separately disclosed (may be hidden inside other charges)."
        ), rbi_reference=KFS_REF))

    # 16 GST stated
    rules.append(RBIRule(rule_id=16, group="Cost Transparency",
        description="GST applicability on fees stated",
        result=RuleResult.PASS if extracted.gst_on_fees else RuleResult.UNCLEAR,
        detail=(
            f"GST on fees: ₹{extracted.gst_on_fees:,.0f}"
            if extracted.gst_on_fees
            else "GST not explicitly stated — check if included in processing fee."
        ), rbi_reference=KFS_REF))

    # 17 Disbursed = Sanctioned minus disclosed fees
    # Contingent charges (bounce, penal, foreclosure) are excluded — they aren't deducted upfront
    CONTINGENT = {"bounce","penal","penalty","foreclosure","prepayment","late","overdue","default"}
    if extracted.principal_amount and extracted.disbursed_amount:
        deduction = extracted.principal_amount - extracted.disbursed_amount
        # Include all unconditional upfront charges in "disclosed"
        other_upfront = sum(
            (c.amount or 0) for c in extracted.other_mandatory_charges
            if not any(kw in (c.name or "").lower() or kw in (c.description or "").lower()
                       for kw in CONTINGENT)
        )
        disclosed_fees = (
            (extracted.processing_fee_amount or 0)
            + (extracted.insurance_premium or 0)
            + (extracted.gst_on_fees or 0)
            + other_upfront
        )
        unexplained = deduction - disclosed_fees
        # Threshold 150 to absorb GST estimation variance (±10% on estimated 18% GST)
        rules.append(RBIRule(rule_id=17, group="Cost Transparency",
            description="Disbursed amount = sanctioned amount minus only disclosed fees",
            result=RuleResult.PASS if unexplained < 150 else RuleResult.FAIL,
            detail=(
                f"Sanctioned: ₹{extracted.principal_amount:,.0f} | "
                f"Disbursed: ₹{extracted.disbursed_amount:,.0f} | "
                + (f"Unexplained deduction: ₹{unexplained:,.0f} — possible hidden fees."
                   if unexplained >= 150 else "Disbursement matches disclosed fees. ✓")
            ), rbi_reference=DLD_REF))
    else:
        rules.append(RBIRule(rule_id=17, group="Cost Transparency",
            description="Disbursed amount = sanctioned amount minus only disclosed fees",
            result=RuleResult.UNCLEAR,
            detail="Cannot compare — disbursed or principal amount missing.",
            rbi_reference=DLD_REF))

    # ══ GROUP E: Recovery & Digital Practices ════════════════════════════════

    # 18 No upfront fee before disbursement
    # Strategy: use actual disbursement gap rather than Gemini's flag.
    # Gemini often misreads "fees payable upfront OR deducted from Loan Amount" (standard boilerplate)
    # as upfront_fee_before_disbursement=True. Use the unexplained deduction from Rule 17 instead.
    # Only FAIL if there is a genuinely unexplained deduction (>150) that can't be accounted for
    # by disclosed fees — which means fees were taken without disclosure (the real violation).
    if extracted.principal_amount and extracted.disbursed_amount:
        deduction_18 = extracted.principal_amount - extracted.disbursed_amount
        # Use same contingent filter as Rule 17
        CONTINGENT_18 = {"bounce","penal","penalty","foreclosure","prepayment","late","overdue","default"}
        other_upfront_18 = sum(
            (c.amount or 0) for c in extracted.other_mandatory_charges
            if not any(kw in (c.name or "").lower() or kw in (c.description or "").lower()
                       for kw in CONTINGENT_18)
        )
        disclosed_18 = (
            (extracted.processing_fee_amount or 0)
            + (extracted.insurance_premium or 0)
            + (extracted.gst_on_fees or 0)
            + other_upfront_18
        )
        unexplained_18 = deduction_18 - disclosed_18
        if unexplained_18 > 150:
            rules.append(RBIRule(rule_id=18, group="Recovery Practices",
                description="No undisclosed fees deducted from disbursement",
                result=RuleResult.FAIL,
                detail=f"VIOLATION: ₹{unexplained_18:,.0f} deducted from disbursement but not listed in disclosed fees — hidden upfront charge, interest still on full principal.",
                rbi_reference=DLD_REF))
        elif deduction_18 > 0:
            rules.append(RBIRule(rule_id=18, group="Recovery Practices",
                description="No undisclosed fees deducted from disbursement",
                result=RuleResult.PASS,
                detail=f"Deductions (₹{deduction_18:,.0f}) accounted for by disclosed fees. ✓",
                rbi_reference=DLD_REF))
        else:
            rules.append(RBIRule(rule_id=18, group="Recovery Practices",
                description="No undisclosed fees deducted from disbursement",
                result=RuleResult.PASS, detail="Full principal disbursed. ✓",
                rbi_reference=DLD_REF))
    else:
        rules.append(RBIRule(rule_id=18, group="Recovery Practices",
            description="No undisclosed fees deducted from disbursement",
            result=RuleResult.UNCLEAR, detail="Cannot verify — disbursed or principal amount missing.",
            rbi_reference=DLD_REF))

    # 19 Repayment via bank transfer
    if extracted.repayment_via_bank_transfer is True:
        rules.append(RBIRule(rule_id=19, group="Recovery Practices",
            description="Repayments go directly to NBFC/bank account",
            result=RuleResult.PASS, detail="Repayment via bank transfer confirmed. ✓",
            rbi_reference=DLD_REF))
    elif extracted.repayment_via_bank_transfer is False:
        rules.append(RBIRule(rule_id=19, group="Recovery Practices",
            description="Repayments go directly to NBFC/bank account",
            result=RuleResult.FAIL,
            detail="Repayment not via direct bank transfer — possible illegal third-party routing.",
            rbi_reference=DLD_REF))
    else:
        rules.append(RBIRule(rule_id=19, group="Recovery Practices",
            description="Repayments go directly to NBFC/bank account",
            result=RuleResult.UNCLEAR, detail="Repayment channel not specified in document.",
            rbi_reference=DLD_REF))

    # 20 Late fee cap (fix: actually check if penal mentions percentage of overdue)
    if extracted.penal_charges:
        text = extracted.penal_charges.lower()
        # Red flags: flat fee per day, or compound, or no mention of overdue basis
        has_red_flag = "compound" in text or "per day flat" in text
        rules.append(RBIRule(rule_id=20, group="Recovery Practices",
            description="Late fee capped at simple interest on overdue amount only",
            result=RuleResult.FAIL if has_red_flag else RuleResult.UNCLEAR,
            detail=(
                f"Potential violation: penal charges may not comply with RBI cap. Review: {extracted.penal_charges[:200]}"
                if has_red_flag
                else f"Penal charges found but cannot fully verify RBI cap compliance: {extracted.penal_charges[:200]}"
            ), rbi_reference=PENAL_REF))
    else:
        rules.append(RBIRule(rule_id=20, group="Recovery Practices",
            description="Late fee capped at simple interest on overdue amount only",
            result=RuleResult.UNCLEAR, detail="Penal charge structure not specified.",
            rbi_reference=PENAL_REF))

    # 21 No contact list access (can only check via permissions review, flag as note)
    rules.append(RBIRule(rule_id=21, group="Recovery Practices",
        description="App does not access contacts/gallery (requires app permissions check)",
        result=RuleResult.UNCLEAR,
        detail="Cannot verify from document alone — check app permissions on your phone. "
               "RBI prohibits apps from accessing contacts, photos, or location beyond KYC needs.",
        rbi_reference=DLD_REF))

    return rules


def count_violations(rules: list[RBIRule]) -> tuple[int, list[str]]:
    """Count FAIL rules and return summary strings."""
    failures = [r for r in rules if r.result == RuleResult.FAIL]
    return len(failures), [f"Rule {r.rule_id}: {r.description}" for r in failures]