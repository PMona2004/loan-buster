"""
LoanLens — Multilingual Verdict Service
Gemini generates plain-language verdict in EN / HI / KN.
"""
import json
import logging
import re
from typing import Optional

import google.generativeai as genai

from app.models.schemas import MultilingualVerdict, APRBreakdown
from app.core.config import settings

logger = logging.getLogger("loanlens.verdict")

VERDICT_PROMPT = """You are a consumer protection expert helping Indian borrowers understand if they are being financially exploited.

LOAN ANALYSIS:
- Lender: {lender_name}
- Principal: ₹{principal:,.0f}
- Tenure: {tenure_days} days
- Declared/Stated APR: {declared_apr}%
- Actual effective APR (all fees included): {actual_apr}%
- Borrower pays {multiplier}× more than declared
- RBI violations found: {violations_count}
- Most serious violation: {top_violation}
- Severity classification: {severity}

Write a SHORT, direct verdict in all 3 languages (2–3 sentences each).
Rules:
- Be factual, not dramatic. State the actual numbers.
- If violations found, say this loan likely violates RBI regulations.
- End with exactly ONE specific action: file complaint at cms.rbi.org.in or call 14448.
- Hindi: use simple Devanagari, Class 8 reading level.
- Kannada: use simple Kannada script, plain spoken style.

Return ONLY this JSON, nothing else:
{{
  "english": "2-3 sentence verdict in plain English",
  "hindi": "2-3 sentence verdict in simple Hindi (Devanagari)",
  "kannada": "2-3 sentence verdict in simple Kannada (Kannada script)"
}}"""


class VerdictService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured on the server."
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def generate_verdict(
        self,
        lender_name: Optional[str],
        apr_breakdown: Optional[APRBreakdown],
        declared_apr: Optional[float],
        actual_apr: Optional[float],
        violations_count: int,
        violations_summary: list[str],
        severity: str,
    ) -> MultilingualVerdict:

        if not actual_apr:
            return self._fallback(violations_count, severity)

        multiplier = (
            round(actual_apr / declared_apr, 1)
            if declared_apr and declared_apr > 0 else "N/A"
        )
        top_violation = violations_summary[0] if violations_summary else "None detected"

        prompt = VERDICT_PROMPT.format(
            lender_name=lender_name or "Unknown Lender",
            principal=apr_breakdown.principal if apr_breakdown else 0,
            tenure_days=apr_breakdown.tenure_days if apr_breakdown else 0,
            declared_apr=round(declared_apr, 1) if declared_apr else "Not stated",
            actual_apr=round(actual_apr, 1),
            multiplier=multiplier,
            violations_count=violations_count,
            top_violation=top_violation,
            severity=severity.upper(),
        )

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=1024),
            )
            raw = response.text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            return MultilingualVerdict(
                english=data.get("english", ""),
                hindi=data.get("hindi", ""),
                kannada=data.get("kannada", ""),
            )
        except Exception as e:
            logger.error(f"Verdict generation failed: {e}", exc_info=True)
            return self._fallback(violations_count, severity)

    def _fallback(self, violations_count: int, severity: str) -> MultilingualVerdict:
        if severity in ("predatory", "severe"):
            return MultilingualVerdict(
                english=f"This loan has {violations_count} RBI compliance violations and an extremely high effective cost. Download the evidence report and file a complaint at cms.rbi.org.in or call 14448.",
                hindi=f"इस लोन में {violations_count} RBI उल्लंघन हैं और वास्तविक लागत बहुत अधिक है। साक्ष्य रिपोर्ट डाउनलोड करें और cms.rbi.org.in पर शिकायत करें या 14448 पर कॉल करें।",
                kannada=f"ಈ ಸಾಲದಲ್ಲಿ {violations_count} RBI ಉಲ್ಲಂಘನೆಗಳಿವೆ ಮತ್ತು ನಿಜವಾದ ವೆಚ್ಚ ತುಂಬಾ ಅಧಿಕ. ಪುರಾವೆ ವರದಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ ಮತ್ತು cms.rbi.org.in ನಲ್ಲಿ ದೂರು ನೀಡಿ ಅಥವಾ 14448 ಗೆ ಕರೆ ಮಾಡಿ.",
            )
        return MultilingualVerdict(
            english="Analysis complete. Review the APR breakdown and RBI compliance results. If you have concerns, contact the RBI Ombudsman at cms.rbi.org.in.",
            hindi="विश्लेषण पूर्ण। APR विवरण और RBI अनुपालन परिणाम देखें। शिकायत के लिए cms.rbi.org.in पर जाएं।",
            kannada="ವಿಶ್ಲೇಷಣೆ ಪೂರ್ಣ. APR ವಿವರ ಮತ್ತು RBI ಅನುಸರಣೆ ಫಲಿತಾಂಶ ಪರಿಶೀಲಿಸಿ. ದೂರಿಗೆ cms.rbi.org.in ಗೆ ಭೇಟಿ ನೀಡಿ.",
        )
