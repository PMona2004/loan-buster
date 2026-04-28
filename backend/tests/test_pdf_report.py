import pytest
from app.services.pdf_report import _render_html, PDFReportRequest

def test_pdf_render_html_safe():
    """Verify HTML generation for a safe loan without WeasyPrint dependency."""
    req = PDFReportRequest(
        session_id="test_session_123456789",
        lender_name="Safe Bank Ltd",
        principal=50000.0,
        tenure_days=365,
        declared_apr=12.0,
        actual_apr=12.5,
        violations_count=0,
        violations_summary=[],
        processing_fee=500.0,
        total_cost=56500.0,
        severity="safe",
        verdict_english="This loan appears safe.",
    )
    
    html = _render_html(req)
    
    # Assert correct content is in the HTML
    assert "Safe Bank Ltd" in html
    assert "12.0%" in html
    assert "12.5%" in html
    assert "This loan appears safe." in html
    assert "No clear violations detected." in html
    assert "#4CAF50" in html  # Safe color

def test_pdf_render_html_predatory():
    """Verify HTML generation for a predatory loan with violations."""
    req = PDFReportRequest(
        session_id="predatory_session_123456789",
        lender_name="Shark Apps",
        principal=10000.0,
        tenure_days=15,
        declared_apr=36.0,
        actual_apr=365.0,
        violations_count=2,
        violations_summary=["Missing Key Fact Statement", "Extremely High APR"],
        processing_fee=1500.0,
        total_cost=15000.0,
        severity="severe",
        verdict_english="DO NOT PROCEED. Predatory conditions found.",
        is_short_tenure=True,
        fee_deduction_trap=True
    )
    
    html = _render_html(req)
    
    assert "Shark Apps" in html
    assert "36.0%" in html
    assert "365.0%" in html
    assert "DO NOT PROCEED. Predatory conditions found." in html
    assert "Missing Key Fact Statement" in html
    assert "Extremely High APR" in html
    assert "Fee Deduction Trap Detected" in html
    assert "15-day loan" in html
    assert "#9C27B0" in html  # Severe color
