"""
LoanLens — Gemini Vision Extraction Service
Best of both agents:
- PyMuPDF multi-page PDF rendering at 2× resolution (Agent 2)
- Robust JSON parsing + fallback (Agent 1)
- Multi-page merge with first-non-null wins (Agent 2)
"""
import json
import base64
import asyncio
import logging
import re
from typing import Optional

import google.generativeai as genai

from app.models.schemas import (
    ExtractedLoanData, ExtractionConfidence, InterestType, OtherCharge
)
from app.core.config import settings

logger = logging.getLogger("loanlens.extraction")

EXTRACTION_PROMPT = """You are a financial document analyst specializing in Indian lending regulations and RBI compliance.

Analyze the provided loan agreement document and extract ALL financial terms. Return ONLY valid JSON — no markdown fences, no explanation text.

{
  "lender_name": "string or null",
  "nbfc_registration_number": "string or null",
  "principal_amount": number_or_null,
  "stated_interest_rate": number_or_null,
  "stated_interest_type": "flat|reducing|monthly|annual|unknown",
  "loan_tenure_days": integer_or_null,
  "processing_fee_amount": number_or_null,
  "processing_fee_percentage": number_or_null,
  "insurance_premium": number_or_null,
  "gst_on_fees": number_or_null,
  "other_mandatory_charges": [
    {"name": "string", "amount": number_or_null, "percentage": number_or_null, "description": "string or null"}
  ],
  "disbursed_amount": number_or_null,
  "total_repayment_amount": number_or_null,
  "kfs_present": true_or_false_or_null,
  "apr_stated_in_document": number_or_null,
  "repayment_via_bank_transfer": true_or_false_or_null,
  "cooling_off_period_days": integer_or_null,
  "prepayment_terms": "string or null",
  "penal_charges": "string or null",
  "grievance_officer_contact": "string or null",
  "upfront_fee_before_disbursement": true_or_false_or_null,
  "extraction_confidence": "high|medium|low",
  "unclear_fields": ["list of field names that could not be reliably extracted"],
  "raw_text_snippet": "first 300 characters of the main readable text"
}

CRITICAL RULES:
1. Use null (NOT 0, NOT empty string) for any field not present in the document.
2. stated_interest_rate: extract EXACTLY as stated. If "2% per month" → rate=2.0, type="monthly".
3. List ALL charges under other_mandatory_charges (stamp duty, documentation fee, NACH/ECS fee, etc.).
4. For tenure: convert to days. 1 month = 30 days, 1 year = 365 days.
5. If you see EMI amounts, infer total_repayment_amount = EMI × number_of_months.
6. Set extraction_confidence=high only when document is clearly readable with all key fields present.
7. Return ONLY valid JSON. Absolutely nothing else before or after."""


def _pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """Render each PDF page to PNG at 2× resolution using PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        mat = fitz.Matrix(2.0, 2.0)  # 2× resolution for better OCR
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def _clean_json(raw: str) -> str:
    """Strip markdown fences and whitespace from Gemini response."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _safe_interest_type(value) -> InterestType:
    try:
        return InterestType(str(value).lower())
    except (ValueError, TypeError):
        return InterestType.UNKNOWN


def _safe_confidence(value) -> ExtractionConfidence:
    try:
        return ExtractionConfidence(str(value).lower())
    except (ValueError, TypeError):
        return ExtractionConfidence.LOW


def _extract_tenure_days_from_snippet(raw_text_snippet: Optional[str]) -> Optional[int]:
    """Fallback parser for short-tenure phrases like '0 months (14 days)'."""
    if not raw_text_snippet:
        return None

    text = raw_text_snippet.lower()

    parenthetical_match = re.search(r"\((\d{1,4})\s+days?\)", text)
    if parenthetical_match:
        return _to_int(parenthetical_match.group(1))

    plain_match = re.search(r"\b(\d{1,4})\s+days?\b", text)
    if plain_match:
        return _to_int(plain_match.group(1))

    return None


def _apply_post_parse_fallbacks(extracted: ExtractedLoanData) -> ExtractedLoanData:
    """Resolve small deterministic extraction gaps without another model call."""
    if extracted.loan_tenure_days is None:
        fallback_tenure_days = _extract_tenure_days_from_snippet(extracted.raw_text_snippet)
        if fallback_tenure_days is not None:
            extracted.loan_tenure_days = fallback_tenure_days
            extracted.unclear_fields = [
                field for field in extracted.unclear_fields if field != "loan_tenure_days"
            ]

    return extracted


def _parse_response(raw_text: str) -> ExtractedLoanData:
    """Parse Gemini JSON response into ExtractedLoanData."""
    try:
        cleaned = _clean_json(raw_text)
        data = json.loads(cleaned)
        logger.info(f"Extraction confidence: {data.get('extraction_confidence', 'unknown')}")

        charges = []
        for c in data.get("other_mandatory_charges", []) or []:
            if isinstance(c, dict):
                charges.append(OtherCharge(
                    name=c.get("name", "Unknown charge"),
                    amount=_to_float(c.get("amount")),
                    percentage=_to_float(c.get("percentage")),
                    description=c.get("description"),
                ))

        extracted = ExtractedLoanData(
            lender_name=data.get("lender_name"),
            nbfc_registration_number=data.get("nbfc_registration_number"),
            principal_amount=_to_float(data.get("principal_amount")),
            stated_interest_rate=_to_float(data.get("stated_interest_rate")),
            stated_interest_type=_safe_interest_type(data.get("stated_interest_type")),
            loan_tenure_days=_to_int(data.get("loan_tenure_days")),
            processing_fee_amount=_to_float(data.get("processing_fee_amount")),
            processing_fee_percentage=_to_float(data.get("processing_fee_percentage")),
            insurance_premium=_to_float(data.get("insurance_premium")),
            gst_on_fees=_to_float(data.get("gst_on_fees")),
            other_mandatory_charges=charges,
            disbursed_amount=_to_float(data.get("disbursed_amount")),
            total_repayment_amount=_to_float(data.get("total_repayment_amount")),
            kfs_present=data.get("kfs_present"),
            apr_stated_in_document=_to_float(data.get("apr_stated_in_document")),
            repayment_via_bank_transfer=data.get("repayment_via_bank_transfer"),
            cooling_off_period_days=_to_int(data.get("cooling_off_period_days")),
            prepayment_terms=data.get("prepayment_terms"),
            penal_charges=data.get("penal_charges"),
            grievance_officer_contact=data.get("grievance_officer_contact"),
            upfront_fee_before_disbursement=data.get("upfront_fee_before_disbursement"),
            extraction_confidence=_safe_confidence(data.get("extraction_confidence")),
            unclear_fields=data.get("unclear_fields", []) or [],
            raw_text_snippet=data.get("raw_text_snippet"),
        )
        return _apply_post_parse_fallbacks(extracted)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}\nRaw (first 500): {raw_text[:500]}")
        return ExtractedLoanData(
            extraction_confidence=ExtractionConfidence.LOW,
            unclear_fields=["json_parse_error"],
        )
    except Exception as e:
        logger.error(f"Response parsing error: {e}", exc_info=True)
        return ExtractedLoanData(
            extraction_confidence=ExtractionConfidence.LOW,
            unclear_fields=["parsing_error"],
        )


def _merge_extractions(results: list[ExtractedLoanData]) -> ExtractedLoanData:
    """
    Merge multi-page extraction results.
    Strategy: first non-null value wins for scalar fields.
    Lists (charges, unclear_fields) are unioned.
    """
    if not results:
        return ExtractedLoanData()
    if len(results) == 1:
        return results[0]

    base = results[0]
    for r in results[1:]:
        for field_name in base.model_fields:
            current = getattr(base, field_name)
            candidate = getattr(r, field_name)
            # Skip lists and complex fields — handle separately
            if isinstance(current, list):
                continue
            if field_name == "total_repayment_amount":
                if current is None and candidate is not None:
                    setattr(base, field_name, candidate)
                elif current is not None and candidate is not None:
                    setattr(base, field_name, max(current, candidate))
                continue
            if current is None and candidate is not None:
                setattr(base, field_name, candidate)

        # Merge charges (deduplicate by name)
        if r.other_mandatory_charges:
            existing_names = {c.name for c in base.other_mandatory_charges}
            for c in r.other_mandatory_charges:
                if c.name not in existing_names:
                    base.other_mandatory_charges.append(c)

        # Merge unclear fields
        base.unclear_fields = list(set(base.unclear_fields + r.unclear_fields))

    # Best confidence across all pages
    confidences = [r.extraction_confidence for r in results]
    if ExtractionConfidence.HIGH in confidences:
        base.extraction_confidence = ExtractionConfidence.HIGH
    elif ExtractionConfidence.MEDIUM in confidences:
        base.extraction_confidence = ExtractionConfidence.MEDIUM

    return _apply_post_parse_fallbacks(base)


class GeminiExtractionService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured on the server."
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        logger.info(f"Gemini extraction initialized: {settings.GEMINI_MODEL}")

    async def extract_from_file(
        self,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> ExtractedLoanData:
        """Main entry point. Handles PDF (multi-page) or image."""
        logger.info(f"Extracting: {filename} | {content_type} | {len(file_bytes)} bytes")

        if content_type == "application/pdf":
            return await self._extract_from_pdf(file_bytes)
        else:
            return await self._extract_from_image(file_bytes, content_type)

    async def _extract_from_pdf(self, pdf_bytes: bytes) -> ExtractedLoanData:
        """Convert PDF pages to images using PyMuPDF, extract from each, merge."""
        try:
            images = _pdf_to_images(pdf_bytes)
            logger.info(f"PDF rendered to {len(images)} page image(s)")
        except Exception as e:
            logger.warning(f"PyMuPDF failed ({e}), falling back to raw PDF send")
            return await self._extract_raw_pdf(pdf_bytes)

        if len(images) == 1:
            return await self._extract_from_image(images[0], "image/png")

        # Multi-page: extract first 3 pages, merge
        results = []
        for i, img_bytes in enumerate(images[:3]):
            logger.info(f"Extracting page {i + 1}/{min(len(images), 3)}")
            try:
                result = await self._extract_from_image(img_bytes, "image/png")
                results.append(result)
            except Exception as e:
                logger.warning(f"Page {i + 1} extraction failed: {e}")

        if not results:
            return ExtractedLoanData(
                extraction_confidence=ExtractionConfidence.LOW,
                unclear_fields=["all_pages_failed"],
            )

        return _merge_extractions(results)

    async def _extract_raw_pdf(self, pdf_bytes: bytes) -> ExtractedLoanData:
        """Send PDF bytes directly to Gemini (fallback when PyMuPDF unavailable)."""
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        try:
            response = self.model.generate_content(
                [{"inline_data": {"mime_type": "application/pdf", "data": b64}}, EXTRACTION_PROMPT],
                generation_config=genai.GenerationConfig(temperature=0.0, max_output_tokens=8192, response_mime_type="application/json"),
            )
            return _parse_response(response.text)
        except Exception as e:
            logger.error(f"Raw PDF extraction failed: {e}")
            return ExtractedLoanData(
                extraction_confidence=ExtractionConfidence.LOW,
                unclear_fields=["raw_pdf_extraction_failed"],
            )

    async def _extract_from_image(self, image_bytes: bytes, content_type: str) -> ExtractedLoanData:
        """Send image to Gemini Vision and parse JSON response. Retries on 429."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        for attempt in range(3):  # max 3 retries
            try:
                response = self.model.generate_content(
                    [{"inline_data": {"mime_type": content_type, "data": b64}}, EXTRACTION_PROMPT],
                    generation_config=genai.GenerationConfig(
                        temperature=0.0, max_output_tokens=8192
                    ),
                )
                return _parse_response(response.text)
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait = 15 * (attempt + 1)  # 15s, then 30s
                    logger.warning(f"Rate limit hit, waiting {wait}s (attempt {attempt+1}/3)...")
                    await asyncio.sleep(wait)
                else:
                    raise
