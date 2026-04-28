"""
Predatory Score + Verdict Fallback — Unit Tests
Identified by graphify DFS + claude-flow task tracking:
  task-1777312211761: compute_predatory_score() community 0, zero tests.
  VerdictService._fallback() — only safety net when Gemini fails, zero tests.
"""
import pytest
from app.services.apr_engine import compute_predatory_score, format_multiplier
from app.services.verdict_service import VerdictService


# ── compute_predatory_score ───────────────────────────────────────────────────

class TestPredatoryScore:
    """Graphify: compute_predatory_score has 22 inbound edges but no test community."""

    # APR component thresholds (0-60 pts)
    def test_apr_above_200_gives_60_apr_points(self):
        score = compute_predatory_score(actual_apr=250, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 60

    def test_apr_101_gives_45_apr_points(self):
        score = compute_predatory_score(actual_apr=101, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 45

    def test_apr_61_gives_30_apr_points(self):
        score = compute_predatory_score(actual_apr=61, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 30

    def test_apr_37_gives_15_apr_points(self):
        score = compute_predatory_score(actual_apr=37, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 15

    def test_apr_below_36_gives_0_apr_points(self):
        score = compute_predatory_score(actual_apr=20, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 0

    # Violations component (0-25 pts, capped)
    def test_5_violations_gives_25_violation_points(self):
        score = compute_predatory_score(actual_apr=0, violations_count=5,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 25

    def test_10_violations_still_capped_at_25_pts(self):
        score = compute_predatory_score(actual_apr=0, violations_count=10,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 25  # min(50, 25) = 25

    def test_1_violation_gives_5_pts(self):
        score = compute_predatory_score(actual_apr=0, violations_count=1,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 5

    # Flag bonuses
    def test_fee_deduction_trap_adds_10_pts(self):
        base = compute_predatory_score(actual_apr=50, violations_count=0,
                                       fee_deduction_trap=False, is_short_tenure=False)
        with_trap = compute_predatory_score(actual_apr=50, violations_count=0,
                                            fee_deduction_trap=True, is_short_tenure=False)
        assert with_trap - base == 10

    def test_short_tenure_adds_5_pts(self):
        base = compute_predatory_score(actual_apr=50, violations_count=0,
                                       fee_deduction_trap=False, is_short_tenure=False)
        with_short = compute_predatory_score(actual_apr=50, violations_count=0,
                                             fee_deduction_trap=False, is_short_tenure=True)
        assert with_short - base == 5

    # Ceiling
    def test_max_score_capped_at_100(self):
        score = compute_predatory_score(actual_apr=500, violations_count=20,
                                        fee_deduction_trap=True, is_short_tenure=True)
        assert score == 100

    # Clean loan
    def test_clean_low_apr_loan_scores_zero(self):
        score = compute_predatory_score(actual_apr=18, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 0

    # Boundary: exactly at thresholds
    def test_apr_exactly_200_gives_45_not_60(self):
        """200 is NOT > 200, so it falls into the >100 bracket."""
        score = compute_predatory_score(actual_apr=200, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 45

    def test_apr_exactly_36_gives_0_apr_points(self):
        """36 is NOT > 36."""
        score = compute_predatory_score(actual_apr=36, violations_count=0,
                                        fee_deduction_trap=False, is_short_tenure=False)
        assert score == 0


# ── VerdictService._fallback ──────────────────────────────────────────────────

class TestVerdictFallback:
    """
    claude-flow task: VerdictService._fallback is the only safety net if Gemini fails.
    It's never tested. If it's broken, every user with a complex loan gets a crash.
    """

    def setup_method(self):
        # VerdictService.__init__ calls genai.configure — mock the key to avoid import error
        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")

    def _make_service(self):
        # Bypass real genai init by patching at class level
        import unittest.mock as mock
        with mock.patch("google.generativeai.configure"), \
             mock.patch("google.generativeai.GenerativeModel"):
            svc = VerdictService()
        return svc

    def test_predatory_severity_fallback_contains_cms_link(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=5, severity="predatory")
        assert "cms.rbi.org.in" in result.english
        assert "14448" in result.english

    def test_severe_severity_fallback_contains_cms_link(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=3, severity="severe")
        assert "cms.rbi.org.in" in result.english
        assert "14448" in result.english

    def test_predatory_fallback_includes_violation_count(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=7, severity="predatory")
        assert "7" in result.english

    def test_safe_severity_returns_generic_verdict(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=0, severity="safe")
        assert "cms.rbi.org.in" in result.english
        # Should NOT mention 14448 in the safe/generic branch
        assert "14448" not in result.english

    def test_fallback_returns_all_three_languages(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=2, severity="caution")
        assert result.english and len(result.english) > 0
        assert result.hindi and len(result.hindi) > 0
        assert result.kannada and len(result.kannada) > 0

    def test_predatory_hindi_contains_rbi_reference(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=4, severity="predatory")
        assert "RBI" in result.hindi or "cms.rbi.org.in" in result.hindi

    def test_predatory_kannada_contains_cms_link(self):
        svc = self._make_service()
        result = svc._fallback(violations_count=4, severity="predatory")
        assert "cms.rbi.org.in" in result.kannada
