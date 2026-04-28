"""LoanLens — PDF Report Endpoint"""
import logging
from fastapi import APIRouter
from fastapi.responses import Response
from app.services.pdf_report import PDFReportRequest, build_pdf_bytes, build_html_fallback

logger = logging.getLogger("loanlens.api.report")
router = APIRouter()


@router.post("/report/pdf")
async def generate_pdf(req: PDFReportRequest):
    """Generate and return a PDF evidence report."""
    logger.info(f"[{req.session_id}] Generating PDF report...")
    try:
        pdf_bytes = build_pdf_bytes(req)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="loanlens-{req.session_id}.pdf"'
            },
        )
    except ImportError:
        logger.warning("WeasyPrint not available — returning HTML fallback")
        html = build_html_fallback(req)
        return Response(
            content=html.encode("utf-8"),
            media_type="text/html",
            headers={
                "Content-Disposition": f'attachment; filename="loanlens-{req.session_id}.html"'
            },
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        html = build_html_fallback(req)
        return Response(content=html.encode("utf-8"), media_type="text/html")