"""
LoanLens — Data Models
All Pydantic models. Type-safe, serializable, validated.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class ExtractionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InterestType(str, Enum):
    FLAT = "flat"
    REDUCING = "reducing"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    UNKNOWN = "unknown"


class RuleResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNCLEAR = "unclear"


# ── Extraction ────────────────────────────────────────────────────────────────

class OtherCharge(BaseModel):
    name: str
    amount: Optional[float] = None
    percentage: Optional[float] = None
    description: Optional[str] = None


class ExtractedLoanData(BaseModel):
    """Raw data extracted from the loan document via Gemini Vision."""
    # Lender
    lender_name: Optional[str] = None
    nbfc_registration_number: Optional[str] = None

    # Core loan terms
    principal_amount: Optional[float] = None
    stated_interest_rate: Optional[float] = None
    stated_interest_type: InterestType = InterestType.UNKNOWN
    loan_tenure_days: Optional[int] = None
    disbursed_amount: Optional[float] = None
    total_repayment_amount: Optional[float] = None

    # Fees
    processing_fee_amount: Optional[float] = None
    processing_fee_percentage: Optional[float] = None
    insurance_premium: Optional[float] = None
    gst_on_fees: Optional[float] = None
    other_mandatory_charges: list[OtherCharge] = Field(default_factory=list)

    # RBI compliance indicators
    kfs_present: Optional[bool] = None
    apr_stated_in_document: Optional[float] = None
    repayment_via_bank_transfer: Optional[bool] = None
    cooling_off_period_days: Optional[int] = None
    prepayment_terms: Optional[str] = None
    penal_charges: Optional[str] = None
    grievance_officer_contact: Optional[str] = None
    upfront_fee_before_disbursement: Optional[bool] = None

    # Extraction metadata
    extraction_confidence: ExtractionConfidence = ExtractionConfidence.LOW
    unclear_fields: list[str] = Field(default_factory=list)
    raw_text_snippet: Optional[str] = None


# ── APR ───────────────────────────────────────────────────────────────────────

class APRBreakdown(BaseModel):
    """Full APR computation result."""
    principal: float
    tenure_days: int
    stated_rate_annual: float           # Normalized to annual for display
    stated_rate_type: str               # e.g. "monthly (annualized)"

    # Cost components
    total_interest: float
    processing_fee: float
    insurance_premium: float
    gst_on_fees: float
    other_charges: float
    total_cost: float                   # Sum of all above

    # APR results — both methods
    effective_apr_simple: float         # (total_cost / principal) × (365 / days) × 100
    effective_apr_compound: Optional[float] = None  # IRR-based per RBI KFS methodology

    # Diagnostic flags
    is_short_tenure: bool = False
    annualization_note: Optional[str] = None
    actual_disbursed: Optional[float] = None
    fee_deduction_trap: bool = False    # Fees deducted but interest charged on full principal
    display_apr_capped: bool = False


# ── RBI Rules ─────────────────────────────────────────────────────────────────

class RBIRule(BaseModel):
    rule_id: int
    group: str
    description: str
    result: RuleResult
    detail: Optional[str] = None
    rbi_reference: Optional[str] = None


# ── Verdict ───────────────────────────────────────────────────────────────────

class MultilingualVerdict(BaseModel):
    english: str
    hindi: str
    kannada: str


# ── Final AnalysisResult ──────────────────────────────────────────────────────

class AnalysisResult(BaseModel):
    """The complete payload returned to the frontend after analysis."""
    session_id: str

    # Extraction
    extracted: ExtractedLoanData
    extraction_warnings: list[str] = Field(default_factory=list)

    # APR
    apr_breakdown: Optional[APRBreakdown] = None
    declared_apr: Optional[float] = None       # From document or naive annualization of stated rate
    actual_apr: Optional[float] = None         # Best available APR (compound if possible, else simple)
    apr_multiplier: Optional[float] = None     # actual / declared

    # RBI
    rbi_rules: list[RBIRule] = Field(default_factory=list)
    violations_count: int = 0
    violations_summary: list[str] = Field(default_factory=list)

    # Verdict
    verdict: Optional[MultilingualVerdict] = None
    severity: str = "unknown"           # safe | caution | predatory | severe
    severity_color: str = "#888888"
    predatory_score: Optional[int] = None

    # Meta
    processing_time_seconds: Optional[float] = None
    gemini_model_used: str = "gemini-1.5-flash"


class RecomputeRequest(BaseModel):
    """Recompute analysis from extracted data with optional tenure override."""
    session_id: Optional[str] = None
    extracted: ExtractedLoanData
    loan_tenure_days: Optional[int] = None
