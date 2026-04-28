"""
Loan Buster - PDF Evidence Report Generator
Produces a downloadable, printable PDF for RBI Ombudsman filing.
Uses WeasyPrint with an HTML template.
"""
import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("loanbuster.pdf")


class PDFReportRequest(BaseModel):
    session_id: str
    lender_name: Optional[str] = None
    principal: Optional[float] = None
    tenure_days: Optional[int] = None
    declared_apr: Optional[float] = None
    actual_apr: Optional[float] = None
    violations_count: int = 0
    violations_summary: list[str] = Field(default_factory=list)
    processing_fee: Optional[float] = None
    insurance_premium: Optional[float] = None
    gst_on_fees: Optional[float] = None
    other_charges: Optional[float] = None
    total_cost: Optional[float] = None
    severity: str = "unknown"
    verdict_english: Optional[str] = None
    verdict_hindi: Optional[str] = None
    verdict_kannada: Optional[str] = None
    is_short_tenure: bool = False
    fee_deduction_trap: bool = False
    apr_compound: Optional[float] = None


_SEVERITY_COLORS = {
    "safe": "#4CAF50",
    "caution": "#FF9800",
    "predatory": "#F44336",
    "severe": "#9C27B0",
}

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'IBM Plex Serif', Georgia, serif; font-size: 11pt; color: #111; line-height: 1.65; background: white; }}
  .page {{ padding: 2.2cm 2.5cm; }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #111; padding-bottom: 14px; margin-bottom: 24px; }}
  .logo {{ font-size: 22pt; font-weight: 700; letter-spacing: -0.03em; }}
  .logo .red {{ color: #E53935; }}
  .header-meta {{ text-align: right; font-size: 9pt; color: #777; line-height: 1.5; }}
  h2 {{ font-size: 12pt; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: #444; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin: 28px 0 14px; }}
  .apr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
  .apr-card {{ border: 1px solid #ddd; border-radius: 6px; padding: 18px 20px; }}
  .apr-label {{ font-size: 9pt; color: #888; text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 6px; }}
  .apr-number {{ font-size: 34pt; font-weight: 700; line-height: 1; }}
  .apr-sub {{ font-size: 9pt; color: #999; margin-top: 4px; }}
  .declared .apr-number {{ color: #555; }}
  .actual .apr-number {{ color: {severity_color}; }}
  .actual {{ background: {severity_color}08; border-color: {severity_color}40; }}
  .multiplier-bar {{ background: {severity_color}10; border: 1px solid {severity_color}30; border-radius: 4px; padding: 10px 16px; margin-bottom: 16px; font-size: 12pt; color: #333; }}
  .multiplier-bar strong {{ color: {severity_color}; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 10.5pt; margin: 10px 0; }}
  th {{ background: #111; color: white; padding: 8px 12px; text-align: left; font-size: 9.5pt; letter-spacing: 0.03em; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  .total-row td {{ font-weight: 700; border-top: 2px solid #111; background: white !important; }}
  .mono {{ font-family: 'IBM Plex Mono', monospace; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 9pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; background: {severity_color}; color: white; }}
  .violation {{ background: #fff5f5; border-left: 3px solid #E53935; padding: 8px 12px; margin: 6px 0; border-radius: 0 4px 4px 0; }}
  .violation .vname {{ font-weight: 700; color: #C62828; font-size: 10.5pt; }}
  .verdict-block {{ border: 1px solid #ddd; border-left: 4px solid {severity_color}; border-radius: 0 6px 6px 0; padding: 14px 18px; margin: 10px 0; }}
  .verdict-lang {{ font-size: 9pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #888; font-family: 'IBM Plex Mono', monospace; margin-bottom: 6px; }}
  .rights-box {{ background: #E8F5E9; border: 1px solid #C8E6C9; border-radius: 6px; padding: 14px 18px; margin: 10px 0; }}
  .rights-box li {{ margin: 5px 0; font-size: 10.5pt; }}
  .ombudsman-box {{ background: #E3F2FD; border: 1px solid #BBDEFB; border-radius: 6px; padding: 14px 18px; margin: 10px 0; }}
  .ombudsman-box strong {{ color: #1565C0; }}
  .trap-warning {{ background: #FFF3E0; border: 1px solid #FFE0B2; border-radius: 4px; padding: 10px 14px; font-size: 10pt; color: #E65100; margin: 10px 0; }}
  .footer {{ margin-top: 40px; border-top: 1px solid #ddd; padding-top: 12px; font-size: 8pt; color: #aaa; text-align: center; line-height: 1.5; }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div>
      <div class="logo">Loan<span class="red">Buster</span></div>
      <div style="font-size:9pt;color:#888;margin-top:3px">AI Predatory Lending Decoder - Evidence Report</div>
    </div>
    <div class="header-meta">
      Generated: {generated_at}<br>
      Session: {session_id}<br>
      <span class="badge">{severity_upper}</span>
    </div>
  </div>

  <h2>1. Interest Rate Analysis</h2>
  <div class="apr-grid">
    <div class="apr-card declared">
      <div class="apr-label">What they told you</div>
      <div class="apr-number">{declared_str}</div>
      <div class="apr-sub">Declared / Stated APR</div>
    </div>
    <div class="apr-card actual">
      <div class="apr-label">What you're actually paying</div>
      <div class="apr-number">{actual_str}</div>
      <div class="apr-sub">Effective APR - all fees included</div>
    </div>
  </div>

  {multiplier_bar}

  <p style="font-size:10pt;color:#666;margin-bottom:6px">
    Lender: <strong>{lender_name}</strong> &nbsp;|&nbsp;
    Principal: <strong class="mono">Rs {principal}</strong> &nbsp;|&nbsp;
    Tenure: <strong>{tenure_days} days</strong>
  </p>

  {fee_trap_warning}
  {short_tenure_note}

  <h2>2. Cost Breakdown</h2>
  <table>
    <tr><th>Cost Component</th><th style="text-align:right">Amount (Rs)</th></tr>
    <tr><td>Principal (Loan Amount)</td><td class="mono" style="text-align:right">{principal}</td></tr>
    <tr><td>Total Interest Charged</td><td class="mono" style="text-align:right">{total_interest}</td></tr>
    <tr><td>Processing Fee</td><td class="mono" style="text-align:right">{processing_fee}</td></tr>
    <tr><td>Insurance Premium</td><td class="mono" style="text-align:right">{insurance_premium}</td></tr>
    <tr><td>GST on Fees</td><td class="mono" style="text-align:right">{gst_on_fees}</td></tr>
    <tr><td>Other Charges</td><td class="mono" style="text-align:right">{other_charges}</td></tr>
    <tr class="total-row"><td>TOTAL COST OF BORROWING</td><td class="mono" style="text-align:right;color:{severity_color}">{total_cost}</td></tr>
  </table>
  {irr_note}

  <h2>3. RBI Compliance - {violations_count} Violation(s)</h2>
  {violations_html}

  <h2>4. Plain Language Verdict</h2>
  {verdicts_html}

  <h2>5. Your Rights as a Borrower</h2>
  <div class="rights-box">
    <ul style="padding-left:18px">
      <li>You are entitled to a <strong>Key Fact Statement (KFS)</strong> before signing any digital loan - showing the full APR and all charges.</li>
      <li>You have a <strong>minimum 3-day cooling-off period</strong> to cancel the loan by repaying only the principal and proportionate interest.</li>
      <li>Lenders <strong>cannot access your phone contacts, gallery, or location</strong> beyond what is strictly needed for KYC.</li>
      <li>All repayments must go <strong>directly to the NBFC/Bank account</strong> - never to a third-party app or wallet.</li>
      <li>Recovery agents <strong>cannot call before 8am or after 7pm</strong>. Harassment is a criminal offence under IPC.</li>
      <li>You can file a complaint with the <strong>RBI Ombudsman for free</strong> - no lawyer needed. Compensation up to Rs 20 lakh.</li>
    </ul>
  </div>

  <h2>6. File a Complaint</h2>
  <div class="ombudsman-box">
    <strong>RBI Integrated Ombudsman Scheme</strong><br>
    Portal: <strong>cms.rbi.org.in</strong> &nbsp;|&nbsp; Toll-free: <strong>14448</strong> (Mon-Fri, 9am-5pm)<br>
    Covers: digital lending complaints, hidden charges, harassment, data misuse.<br><br>
    <strong>Attach this Loan Buster report as evidence when filing.</strong> Include screenshots of your loan agreement and any payment receipts.
  </div>

  <div class="footer">
    This report was generated by Loan Buster (Solution Challenge 2026 - SDG 1 - 10 - 16) using AI document analysis.<br>
    For informational purposes only. Not legal advice. Verify figures with a financial advisor before formal legal action.<br>
    Loan Buster does not retain your loan document after analysis.
  </div>

</div>
</body>
</html>"""


def build_pdf_bytes(req: PDFReportRequest) -> bytes:
    from weasyprint import HTML

    html = _render_html(req)
    return HTML(string=html).write_pdf()


def build_html_fallback(req: PDFReportRequest) -> str:
    return _render_html(req)


def _fmt_inr(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}"


def _render_html(req: PDFReportRequest) -> str:
    severity_color = _SEVERITY_COLORS.get(req.severity, "#888888")
    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p IST")

    declared_str = f"{req.declared_apr:.1f}%" if req.declared_apr is not None else "Not stated"
    actual_str = f"{req.actual_apr:.1f}%" if req.actual_apr is not None else "N/A"

    multiplier_bar = ""
    if req.declared_apr and req.actual_apr and req.declared_apr > 0:
        multiplier = round(req.actual_apr / req.declared_apr, 1)
        if multiplier > 1.3:
            multiplier_bar = (
                f'<div class="multiplier-bar">You are paying '
                f'<strong>{multiplier}x more</strong> than what was declared '
                f'({declared_str} declared vs {actual_str} actual).</div>'
            )

    fee_trap_warning = ""
    if req.fee_deduction_trap:
        fee_trap_warning = (
            '<div class="trap-warning"><strong>Fee Deduction Trap Detected:</strong> '
            'Fees were deducted from the disbursed amount, but interest is charged on the full principal. '
            'You received less money than the loan amount, but pay interest as if you received it all.</div>'
        )

    short_tenure_note = ""
    if req.is_short_tenure and req.tenure_days:
        short_tenure_note = (
            f'<div style="background:#fffde7;border:1px solid #f9e07a;border-radius:4px;'
            f'padding:10px 14px;font-size:10pt;color:#7a6000;margin:8px 0">'
            f'This is a {req.tenure_days}-day loan. APR is annualized for comparison - '
            f'extremely short-tenure loans always produce very high APR when annualized. '
            f'The absolute cash cost above is what matters most.</div>'
        )

    irr_note = ""
    if req.apr_compound is not None:
        irr_note = (
            f'<p style="font-size:9.5pt;color:#888;margin-top:6px">'
            f'IRR-based APR (per RBI KFS methodology): <strong class="mono">{req.apr_compound:.1f}%</strong></p>'
        )

    violations_html = ""
    for violation in req.violations_summary:
        violations_html += (
            f'<div class="violation"><div class="vname">- {violation}</div></div>'
        )
    if not violations_html:
        violations_html = '<p style="color:#4CAF50;font-weight:600">No clear violations detected.</p>'

    verdicts_html = ""
    if req.verdict_english:
        verdicts_html = (
            '<div class="verdict-block">'
            '<div class="verdict-lang">EN - English</div>'
            f'<div>{req.verdict_english}</div>'
            '</div>'
        )

    total_interest = max(
        0,
        (req.total_cost or 0)
        - (req.processing_fee or 0)
        - (req.insurance_premium or 0)
        - (req.gst_on_fees or 0)
        - (req.other_charges or 0),
    )

    return _HTML_TEMPLATE.format(
        severity_color=severity_color,
        generated_at=generated_at,
        session_id=(req.session_id[:16] if req.session_id and len(req.session_id) >= 16 else req.session_id),
        severity_upper=(req.severity or "unknown").upper(),
        declared_str=declared_str,
        actual_str=actual_str,
        multiplier_bar=multiplier_bar,
        lender_name=req.lender_name or "Not specified",
        principal=_fmt_inr(req.principal),
        tenure_days=req.tenure_days or "-",
        fee_trap_warning=fee_trap_warning,
        short_tenure_note=short_tenure_note,
        total_interest=_fmt_inr(total_interest),
        processing_fee=_fmt_inr(req.processing_fee),
        insurance_premium=_fmt_inr(req.insurance_premium),
        gst_on_fees=_fmt_inr(req.gst_on_fees),
        other_charges=_fmt_inr(req.other_charges),
        total_cost=_fmt_inr(req.total_cost),
        irr_note=irr_note,
        violations_count=req.violations_count,
        violations_html=violations_html,
        verdicts_html=verdicts_html,
    )
