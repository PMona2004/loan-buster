import { useState, useRef, useCallback, useEffect } from "react";

const rawApiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const API_URL = rawApiUrl.replace(/\/+$/, "").endsWith("/api/v1")
  ? rawApiUrl.replace(/\/+$/, "")
  : `${rawApiUrl.replace(/\/+$/, "")}/api/v1`;

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg: "#080808",
  surface: "#111111",
  surfaceHover: "#161616",
  border: "#1e1e1e",
  borderStrong: "#2a2a2a",
  red: "#E53935",
  redDim: "#E5393520",
  orange: "#FF9800",
  green: "#4CAF50",
  purple: "#9C27B0",
  blue: "#1E88E5",
  textPrimary: "#F0EEE8",
  textSecondary: "#888",
  textMuted: "#777",
};

// ─── Utilities ────────────────────────────────────────────────────────────────
const fmt = (n, dec = 1) => (n != null ? Number(n).toFixed(dec) : "—");
const fmtINR = (n) =>
  n != null ? `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";
const severityColor = (s) =>
  ({ safe: C.green, caution: C.orange, predatory: C.red, severe: C.purple }[s] || C.textMuted);
const ruleColor = (r) =>
  ({ pass: C.green, fail: C.red, unclear: C.textMuted }[r] || C.textMuted);
const extractTenureCandidateDays = (rawTextSnippet) => {
  if (!rawTextSnippet) return null;
  const parenthetical = rawTextSnippet.match(/\((\d{1,4})\s+days?\)/i);
  if (parenthetical) return Number(parenthetical[1]);
  const plain = rawTextSnippet.match(/\b(\d{1,4})\s+days?\b/i);
  return plain ? Number(plain[1]) : null;
};
const getUnresolvedCriticalFields = (data) => {
  const extracted = data?.extracted || {};
  return CRITICAL_FIELDS.filter((field) => {
    const value = extracted[field];
    if (field === "loan_tenure_days") return value == null || Number(value) <= 0;
    if (field === "principal_amount" || field === "total_repayment_amount") {
      return value == null || Number(value) <= 0;
    }
    return value == null;
  });
};

// ─── Global CSS ───────────────────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Syne:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; -webkit-font-smoothing: antialiased; }
  body { background: ${C.bg}; color: ${C.textPrimary}; font-family: 'Inter', system-ui, sans-serif; min-height: 100vh; }

  .mono { font-family: 'DM Mono', 'Courier New', monospace; }
  .syne { font-family: 'Syne', sans-serif; }

  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }
  @keyframes scanPulse { 0%, 100% { opacity: 0.6; transform: scaleX(0.3); } 50% { opacity: 1; transform: scaleX(1); } }

  .spin { animation: spin 0.9s linear infinite; }
  .fade-up { animation: fadeUp 0.45s cubic-bezier(0.22,1,0.36,1) both; }
  .fade-up-1 { animation-delay: 0.05s; }
  .fade-up-2 { animation-delay: 0.12s; }
  .fade-up-3 { animation-delay: 0.2s; }
  .fade-up-4 { animation-delay: 0.28s; }
  .fade-up-5 { animation-delay: 0.36s; }

  .drop-zone { transition: border-color 0.2s ease, background 0.2s ease; }
  .drop-zone.over { border-color: ${C.red} !important; background: ${C.redDim} !important; }

  .rule-row { transition: background 0.12s; }
  .rule-row:hover { background: rgba(255,255,255,0.025); }

  button { cursor: pointer; font-family: 'Inter', sans-serif; }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  a { color: inherit; }

  ::-webkit-scrollbar { width: 3px; height: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 2px; }

  @media (max-width: 640px) {
    .apr-grid { grid-template-columns: 1fr !important; }
    .stats-row { flex-direction: column !important; gap: 16px !important; }
  }
`;

// ─── Priority 1: Explanation bullets ────────────────────────────────────────
function buildExplanations(data) {
  const bd = data.apr_breakdown;
  if (!bd) return [];
  const bullets = [];
  const actualDisbursed = bd.actual_disbursed ?? data.extracted?.disbursed_amount;
  const totalRepayment = data.extracted?.total_repayment_amount;

  if (actualDisbursed != null && totalRepayment != null && totalRepayment >= actualDisbursed) {
    const totalBorrowingCost = totalRepayment - actualDisbursed;
    bullets.push(
      `You receive ${fmtINR(actualDisbursed)} and repay ${fmtINR(totalRepayment)} — total borrowing cost is ${fmtINR(totalBorrowingCost)}.`
    );
  } else if (bd.principal != null && bd.total_cost != null) {
    bullets.push(
      `Total borrowing cost is ${fmtINR(bd.total_cost)} on a principal of ${fmtINR(bd.principal)}.`
    );
  }
  if (data.declared_apr != null && data.actual_apr != null && data.actual_apr > data.declared_apr) {
    const mult = (data.actual_apr / data.declared_apr).toFixed(1);
    bullets.push(
      `Your lender declared ${fmt(data.declared_apr, 1)}% APR. The true cost including all fees is ${fmt(data.actual_apr, 1)}% — you are paying ${mult}× what was stated.`
    );
  }
  if (bd.fee_deduction_trap && bd.actual_disbursed != null && bd.processing_fee != null) {
    bullets.push(
      `Processing fee of ${fmtINR(bd.processing_fee)} was deducted before disbursement, but interest was charged on the full ${fmtINR(bd.principal)}.`
    );
  }
  if (bd.is_short_tenure && bd.tenure_days != null) {
    if (actualDisbursed != null && totalRepayment != null && totalRepayment >= actualDisbursed) {
      const totalBorrowingCost = totalRepayment - actualDisbursed;
      bullets.push(
        `This is a ${bd.tenure_days}-day loan. You receive ${fmtINR(actualDisbursed)} and repay ${fmtINR(totalRepayment)}, so the total borrowing cost is ${fmtINR(totalBorrowingCost)}. Annualizing that short-term cost produces an extreme APR.`
      );
    } else {
      bullets.push(
        `This is a ${bd.tenure_days}-day loan. Total borrowing cost is ${fmtINR(bd.total_cost)}, and annualizing that short-term cost produces an extreme APR.`
      );
    }
  }
  return bullets;
}

function ExplainBlock({ data }) {
  const sc = severityColor(data.severity);
  const bullets = buildExplanations(data);
  if (!bullets.length) return null;
  return (
    <div className="fade-up" style={{ margin: "14px 0", background: `${sc}0a`, border: `1px solid ${sc}28`, borderRadius: 8, padding: "14px 18px" }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: sc, fontFamily: "'DM Mono',monospace", marginBottom: 10 }}>
        What this means in real life
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {bullets.map((b, i) => (
          <li key={i} style={{ display: "flex", gap: 10, fontSize: 13, color: "#d0ccc5", lineHeight: 1.6 }}>
            <span style={{ color: sc, flexShrink: 0, marginTop: 2 }}>›</span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Priority 3: Confidence Module ───────────────────────────────────────────
const CRITICAL_FIELDS = ["principal_amount", "loan_tenure_days", "stated_interest_rate", "total_repayment_amount"];
const FIELD_LABELS = {
  principal_amount: "Principal Amount",
  loan_tenure_days: "Loan Tenure",
  stated_interest_rate: "Interest Rate",
  total_repayment_amount: "Total Repayment",
  processing_fee_amount: "Processing Fee",
  gst_on_fees: "GST on Fees",
  insurance_premium: "Insurance Premium",
  nbfc_registration_number: "NBFC Registration",
  repayment_via_bank_transfer: "Repayment Channel",
  penal_charges: "Penal Charges",
};

function ConfidenceModule({ data }) {
  const conf = data.extracted?.extraction_confidence;
  const critical = getUnresolvedCriticalFields(data);

  if (critical.length === 0) return null;

  const isLow = conf === "low" || critical.length > 0;
  const color = isLow ? C.red : C.orange;
  const icon = isLow ? "🔴" : "🟡";
  const label = isLow
    ? "Low confidence — some critical fields could not be read"
    : "Medium confidence — some fields unverified";

  return (
    <div className="fade-up fade-up-1" style={{ marginTop: 12, background: isLow ? "#180808" : "#141200", border: `1px solid ${color}30`, borderRadius: 8, padding: "12px 16px" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: critical.length > 0 ? 8 : 0 }}>
        <span style={{ fontSize: 12 }}>{icon}</span>
        <span style={{ fontSize: 12, color, fontWeight: 600 }}>{label}</span>
      </div>
      {critical.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 11, color: C.red, marginBottom: 3, fontWeight: 600 }}>Critical fields unresolved (affects APR accuracy):</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {critical.map(f => (
              <span key={f} style={{ fontSize: 10, background: `${C.red}18`, border: `1px solid ${C.red}30`, color: C.red, padding: "2px 8px", borderRadius: 3, fontFamily: "'DM Mono',monospace" }}>
                {FIELD_LABELS[f] || f}
              </span>
            ))}
          </div>
        </div>
      )}
      {isLow && (
        <div style={{ marginTop: 8, fontSize: 11, color: C.textMuted, lineHeight: 1.5 }}>
          ℹ APR results may be incomplete. Check your document and compare the cost breakdown against the original agreement.
        </div>
      )}
    </div>
  );
}

// ─── Small components ─────────────────────────────────────────────────────────

function Tag({ children, color = C.textMuted, solid = false }) {
  return (
    <span style={{
      display: "inline-block", fontSize: 10, fontWeight: 700,
      letterSpacing: "0.09em", textTransform: "uppercase",
      padding: "3px 9px", borderRadius: 3,
      border: `1px solid ${color}50`,
      color: solid ? "#fff" : color,
      background: solid ? color : `${color}14`,
      fontFamily: "'DM Mono', monospace",
    }}>
      {children}
    </span>
  );
}

function Rule({ children }) {
  return <div style={{ width: "100%", height: 1, background: C.border, margin: "24px 0" }} />;
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 600, letterSpacing: "0.14em",
      textTransform: "uppercase", color: C.textMuted,
      fontFamily: "'DM Mono', monospace", marginBottom: 14,
    }}>
      {children}
    </div>
  );
}

function Spinner({ size = 18 }) {
  return (
    <div className="spin" style={{
      width: size, height: size,
      border: `2px solid ${C.border}`,
      borderTopColor: C.red,
      borderRadius: "50%",
      display: "inline-block",
      flexShrink: 0,
    }} />
  );
}

// ─── Screen 1: Upload ─────────────────────────────────────────────────────────
function UploadScreen({ onAnalyze, loading }) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [lang, setLang] = useState("en");
  const inputRef = useRef();

  const handleFile = (f) => {
    if (!f) return;
    const ok = ["application/pdf", "image/jpeg", "image/jpg", "image/png", "image/webp"];
    if (!ok.includes(f.type)) { alert("Upload a PDF or image (JPG/PNG/WebP)."); return; }
    if (f.size > 15 * 1024 * 1024) { alert("File too large. Max 15MB."); return; }
    setFile(f);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false);
    handleFile(e.dataTransfer.files?.[0]);
  }, []);

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>

      {/* Nav */}
      <div style={{ padding: "18px 24px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="syne" style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.02em" }}>
          Loan <span style={{ color: C.red }}>Buster</span>
        </div>
      </div>

      {/* Hero */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "48px 24px", maxWidth: 560, margin: "0 auto", width: "100%" }}>

        <div style={{ width: "100%", background: `${C.red}0c`, border: `1px solid ${C.red}28`, borderRadius: 6, padding: "10px 16px", marginBottom: 40, display: "flex", gap: 10 }}>
          <span style={{ color: C.red, fontSize: 13, flexShrink: 0, marginTop: 1 }}>▲</span>
          <div style={{ fontSize: 12, color: C.textSecondary, lineHeight: 1.55 }}>
            <strong style={{ color: C.red }}>Know before you pay.</strong> Lending apps hide 60–400% APR inside "processing fees" and "insurance." Loan Buster extracts your real cost from the agreement you already received.
          </div>
        </div>

        <h1 className="syne" style={{ fontSize: "clamp(26px, 6vw, 42px)", fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.03em", textAlign: "center", marginBottom: 12 }}>
          Is your loan<br /><span style={{ color: C.red }}>hiding something?</span>
        </h1>
        <p style={{ fontSize: 14, color: C.textSecondary, textAlign: "center", lineHeight: 1.65, marginBottom: 40 }}>
          Upload your loan agreement. Get the real APR, RBI violations,<br />and a downloadable evidence report in 60 seconds.
        </p>

        {/* Drop zone */}
        <div
          className={`drop-zone${dragging ? " over" : ""}`}
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onClick={() => !file && inputRef.current?.click()}
          style={{
            width: "100%", border: `1.5px dashed ${file ? C.green : C.borderStrong}`,
            borderRadius: 10, padding: "32px 24px", textAlign: "center",
            cursor: file ? "default" : "pointer",
            background: file ? `${C.green}08` : C.surface,
            marginBottom: 14, position: "relative",
          }}
        >
          {file ? (
            <div>
              <div style={{ fontSize: 26, marginBottom: 8, color: C.green }}>✓</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: C.green, marginBottom: 4, wordBreak: "break-all" }}>{file.name}</div>
              <div style={{ fontSize: 12, color: C.textMuted }}>{(file.size / 1024).toFixed(0)} KB</div>
              <button onClick={(e) => { e.stopPropagation(); setFile(null); }} style={{
                marginTop: 12, fontSize: 12, color: C.textMuted,
                background: "none", border: `1px solid ${C.border}`, padding: "4px 12px", borderRadius: 4,
              }}>Remove</button>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 28, marginBottom: 10, opacity: 0.35 }}>⬆</div>
              <div style={{ fontSize: 14, color: C.textSecondary, marginBottom: 4 }}>Drag & drop or click to upload</div>
              <div style={{ fontSize: 11, color: C.textMuted, fontFamily: "'DM Mono', monospace" }}>PDF · JPG · PNG · WebP · Max 15MB</div>
            </div>
          )}
          <input ref={inputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" style={{ display: "none" }} onChange={e => handleFile(e.target.files?.[0])} />
        </div>

        <button
          disabled={!file || loading}
          onClick={() => onAnalyze(file, lang)}
          style={{
            width: "100%", padding: "15px 24px",
            background: file && !loading ? C.red : "#333",
            color: file && !loading ? "#fff" : "#888",
            border: "none", borderRadius: 8,
            fontSize: 15, fontWeight: 600, fontFamily: "'Syne', sans-serif",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            transition: "background 0.2s", letterSpacing: "-0.01em",
          }}
        >
          {loading ? <><Spinner /> Analyzing...</> : "Analyze My Loan →"}
        </button>

        <div style={{ marginTop: 14, fontSize: 11, color: C.textMuted, textAlign: "center", lineHeight: 1.6 }}>
          Your document is deleted from our servers within 60 minutes.<br />
          We never store personal data or loan details.
        </div>
      </div>

      {/* Stats footer */}
      <div style={{ borderTop: `1px solid ${C.border}`, padding: "16px 24px" }}>
        <div className="stats-row" style={{ display: "flex", gap: 40, justifyContent: "center" }}>
          {[
            ["10M+", "Indians use instant loan apps"],
            ["30–40%", "Actual APR hidden by top apps"],
            ["21", "RBI rules we check"],
          ].map(([n, l]) => (
            <div key={n} style={{ textAlign: "center" }}>
              <div className="mono" style={{ fontSize: 15, fontWeight: 500, color: C.red }}>{n}</div>
              <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Screen 2: Loading ─────────────────────────────────────────────────────────
const STEPS = [
  "Reading your document...",
  "Extracting fees and charges...",
  "Computing real APR...",
  "Checking 21 RBI compliance rules...",
  "Generating multilingual verdict...",
];

function LoadingScreen() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep(s => Math.min(s + 1, STEPS.length - 1)), 4000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div className="syne" style={{ fontSize: 17, fontWeight: 800, marginBottom: 56, letterSpacing: "-0.02em" }}>
        Loan <span style={{ color: C.red }}>Buster</span>
      </div>

      <div style={{ position: "relative", width: 72, height: 72, marginBottom: 36 }}>
        <div className="spin" style={{ width: 72, height: 72, border: `2px solid ${C.border}`, borderTopColor: C.red, borderRadius: "50%", position: "absolute" }} />
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>🔍</div>
      </div>

      <div style={{ fontSize: 15, color: C.textPrimary, marginBottom: 8, textAlign: "center", minHeight: 24 }}>
        {STEPS[step]}
      </div>
      <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 32 }}>
        This usually takes 15–40 seconds
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        {STEPS.map((_, i) => (
          <div key={i} style={{
            width: i === step ? 20 : 6, height: 6, borderRadius: 3,
            background: i <= step ? C.red : C.border,
            transition: "all 0.35s",
          }} />
        ))}
      </div>
    </div>
  );
}

// ─── Screen 3: Results ─────────────────────────────────────────────────────────
function ResultsScreen({ data, preferredLang = "en", onReset, onRecompute }) {
  const langMap = { en: "english", hi: "hindi", kn: "kannada" };
  const [verdictLang, setVerdictLang] = useState(langMap[preferredLang] || "english");
  const [downloading, setDownloading] = useState(false);
  const [showAllRules, setShowAllRules] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [showTenureInput, setShowTenureInput] = useState(false);
  const [tenureValue, setTenureValue] = useState("");

  const sc = severityColor(data.severity);
  const verdictOptions = [
    { key: "english", label: "EN" },
    { key: "hindi", label: "HI" },
    { key: "kannada", label: "KN" },
  ];

  const downloadPDF = async () => {
    setDownloading(true);
    try {
      const bd = data.apr_breakdown || {};
      const body = {
        session_id: data.session_id,
        lender_name: data.extracted?.lender_name,
        principal: bd.principal || data.extracted?.principal_amount,
        tenure_days: bd.tenure_days || data.extracted?.loan_tenure_days,
        declared_apr: data.declared_apr,
        actual_apr: data.actual_apr,
        violations_count: data.violations_count,
        violations_summary: data.violations_summary,
        processing_fee: bd.processing_fee,
        insurance_premium: bd.insurance_premium,
        gst_on_fees: bd.gst_on_fees,
        other_charges: bd.other_charges,
        total_cost: bd.total_cost,
        severity: data.severity,
        verdict_english: data.verdict?.english,
        verdict_hindi: data.verdict?.hindi,
        verdict_kannada: data.verdict?.kannada,
        is_short_tenure: bd.is_short_tenure,
        fee_deduction_trap: bd.fee_deduction_trap,
        apr_compound: bd.effective_apr_compound,
      };
      const res = await fetch(`${API_URL}/report/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error("PDF generation requires Cloud Run or local GTK dependencies. It will work in production!");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `loan-buster-evidence-${data.session_id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message || "PDF generation failed. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  const bd = data.apr_breakdown;
  const tenureCandidateDays = extractTenureCandidateDays(data.extracted?.raw_text_snippet);
  const needsTenureReview = data.extracted?.loan_tenure_days == null
    && (data.extracted?.unclear_fields || []).includes("loan_tenure_days")
    && tenureCandidateDays != null;
  const actualDisbursed = bd?.actual_disbursed ?? data.extracted?.disbursed_amount;
  const totalRepayment = data.extracted?.total_repayment_amount;
  const feeDeductedUpfront = bd?.principal != null && actualDisbursed != null
    ? Math.max(0, bd.principal - actualDisbursed)
    : null;
  const showAprCapNote = data.actual_apr === 9999
    && bd?.display_apr_capped
    && bd?.is_short_tenure
    && feeDeductedUpfront != null;
  const failedRules = (data.rbi_rules || []).filter(r => r.result === "fail");
  const otherRules = (data.rbi_rules || []).filter(r => r.result !== "fail");
  const visibleRules = showAllRules ? data.rbi_rules || [] : [...failedRules, ...otherRules.slice(0, 3)];

  const submitTenureReview = async (days) => {
    setReviewLoading(true);
    try {
      await onRecompute({
        session_id: data.session_id,
        extracted: data.extracted,
        loan_tenure_days: days,
      });
      setShowTenureInput(false);
    } catch (e) {
      alert(e.message || "Could not recompute analysis.");
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 680, margin: "0 auto", padding: "0 16px 80px" }}>

      {/* Header */}
      <div style={{ padding: "18px 0", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${C.border}`, marginBottom: 28 }}>
        <div className="syne" style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.02em" }}>
          Loan <span style={{ color: C.red }}>Buster</span>
        </div>
        <button onClick={onReset} style={{ fontSize: 12, color: C.textMuted, background: "none", border: `1px solid ${C.border}`, padding: "6px 14px", borderRadius: 6, letterSpacing: "0.02em" }}>
          ← New Analysis
        </button>
      </div>

      {/* ── APR Block ── */}
      <div className="fade-up">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14, alignItems: "center" }}>
          <Tag color={sc} solid>{data.severity || "unknown"}</Tag>
          {data.violations_count > 0 && <Tag color={C.red}>{data.violations_count} RBI Violations</Tag>}
          {data.extracted?.lender_name && (
            <span style={{ fontSize: 12, color: C.textMuted }}>— {data.extracted.lender_name}</span>
          )}
        </div>

        <div className="apr-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 3, borderRadius: 10, overflow: "hidden", border: `1px solid ${C.border}`, marginBottom: 10 }}>
          <div style={{ background: C.surface, padding: "22px 20px", borderRight: `1px solid ${C.border}` }}>
            <div className="mono" style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
              What they told you
            </div>
            <div className="syne" style={{ fontSize: "clamp(32px, 7vw, 52px)", fontWeight: 800, color: C.textSecondary, lineHeight: 1 }}>
              {data.declared_apr != null ? `${fmt(data.declared_apr, 0)}%` : "—"}
            </div>
            <div style={{ fontSize: 11, color: C.textMuted, marginTop: 6 }}>Declared / Stated APR</div>
          </div>
          <div style={{ background: `${sc}10`, padding: "22px 20px" }}>
            <div className="mono" style={{ fontSize: 10, color: sc, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
              What you actually pay
            </div>
            <div className="syne" style={{ fontSize: "clamp(32px, 7vw, 52px)", fontWeight: 800, color: sc, lineHeight: 1 }}>
              {data.actual_apr != null ? `${fmt(data.actual_apr, 0)}%` : "—"}
            </div>
            <div style={{ fontSize: 11, color: sc, marginTop: 6, opacity: 0.7 }}>Effective APR — all fees included</div>
          </div>
        </div>

        {data.apr_multiplier && data.apr_multiplier > 1.3 && (
          <div style={{ background: `${C.red}0c`, border: `1px solid ${C.red}22`, borderRadius: 6, padding: "10px 16px", fontSize: 13, color: C.textSecondary }}>
            ⚠ You are paying <strong style={{ color: C.red }}>{data.apr_multiplier}×</strong> more than declared.
            {bd?.effective_apr_compound && (
              <span style={{ fontSize: 11, color: C.textMuted, marginLeft: 8 }}>
                (IRR method per RBI KFS: {fmt(bd.effective_apr_compound)}%)
              </span>
            )}
          </div>
        )}
        {showAprCapNote && (
          <div style={{ marginTop: 8, background: "#180808", border: `1px solid ${C.red}28`, borderRadius: 6, padding: "10px 16px", fontSize: 12, color: "#ffb3b1", lineHeight: 1.55 }}>
            {actualDisbursed != null && totalRepayment != null ? (
              <>9999% is the display cap. For this {bd.tenure_days}-day loan, {fmtINR(feeDeductedUpfront)} is deducted upfront, so you receive {fmtINR(actualDisbursed)} and repay {fmtINR(totalRepayment)}. That pushes the mathematical annualized IRR above the display range.</>
            ) : (
              <>9999% is the display cap. Based on this loan&apos;s tenure and upfront deductions, the mathematical annualized IRR exceeds the display range.</>
            )}
          </div>
        )}
      </div>

      {/* Priority 1: Explanation Block */}
      <ExplainBlock data={data} />

      {/* Priority 3: Confidence Module (replaces old single warning) */}
      <ConfidenceModule data={data} />

      {needsTenureReview && (
        <div className="fade-up fade-up-1" style={{ marginTop: 12, background: `${C.orange}10`, border: `1px solid ${C.orange}30`, borderRadius: 8, padding: "12px 16px" }}>
          <div style={{ fontSize: 12, color: C.textPrimary, lineHeight: 1.5, marginBottom: 10 }}>
            We found tenure as "{tenureCandidateDays} days" - is this correct?
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <button
              disabled={reviewLoading}
              onClick={() => submitTenureReview(tenureCandidateDays)}
              style={{
                padding: "8px 12px",
                background: C.orange,
                color: "#111",
                border: "none",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {reviewLoading ? "Recomputing..." : "Yes"}
            </button>
            <button
              disabled={reviewLoading}
              onClick={() => setShowTenureInput(s => !s)}
              style={{
                padding: "8px 12px",
                background: "transparent",
                color: C.textSecondary,
                border: `1px solid ${C.borderStrong}`,
                borderRadius: 6,
                fontSize: 12,
              }}
            >
              Enter correct value
            </button>
            {showTenureInput && (
              <>
                <input
                  value={tenureValue}
                  onChange={(e) => setTenureValue(e.target.value)}
                  placeholder="Days"
                  style={{
                    width: 90,
                    padding: "8px 10px",
                    background: C.surface,
                    color: C.textPrimary,
                    border: `1px solid ${C.borderStrong}`,
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
                <button
                  disabled={reviewLoading || !Number(tenureValue)}
                  onClick={() => submitTenureReview(Number(tenureValue))}
                  style={{
                    padding: "8px 12px",
                    background: C.red,
                    color: "#fff",
                    border: "none",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  Apply
                </button>
              </>
            )}
          </div>
        </div>
      )}

      <Rule />

      {/* ── Cost Breakdown ── */}
      {bd && (
        <div className="fade-up fade-up-2">
          <SectionLabel>Cost Breakdown</SectionLabel>
          <div style={{ background: C.surface, borderRadius: 8, overflow: "hidden", border: `1px solid ${C.border}`, marginBottom: 10 }}>
            {[
              ["Principal (Loan Amount)", fmtINR(bd.principal)],
              ["Total Interest Charged", fmtINR(bd.total_interest)],
              ["Processing Fee", fmtINR(bd.processing_fee)],
              ["Insurance Premium", fmtINR(bd.insurance_premium)],
              ["GST on Fees", fmtINR(bd.gst_on_fees)],
              ["Other Charges", fmtINR(bd.other_charges)],
            ].map(([label, val], i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSecondary }}>{label}</span>
                <span className="mono" style={{ color: C.textPrimary }}>{val}</span>
              </div>
            ))}
            <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", fontSize: 14, fontWeight: 600 }}>
              <span>Total Cost of Borrowing</span>
              <span className="mono" style={{ color: sc }}>{fmtINR(bd.total_cost)}</span>
            </div>
          </div>

          {bd.fee_deduction_trap && (
            <div style={{ marginTop: 8, background: "#180808", border: `1px solid ${C.red}28`, borderRadius: 6, padding: "10px 16px", fontSize: 12, color: "#ff8080", lineHeight: 1.55 }}>
              ⚠ <strong>Fee Deduction Trap:</strong> Fees deducted from your disbursement, but interest charged on full principal — you received {fmtINR(bd.actual_disbursed)} but pay interest on {fmtINR(bd.principal)}.
            </div>
          )}
          {bd.is_short_tenure && bd.annualization_note && (
            <div style={{ marginTop: 8, background: "#111000", border: "1px solid #2a2200", borderRadius: 6, padding: "10px 16px", fontSize: 12, color: "#a08800", lineHeight: 1.55 }}>
              ℹ {bd.annualization_note}
            </div>
          )}
        </div>
      )}

      <Rule />

      {/* ── RBI Rules ── */}
      <div className="fade-up fade-up-3">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <SectionLabel>RBI Compliance — {data.rbi_rules?.length || 0} Rules</SectionLabel>
          {failedRules.length > 0 && (
            <Tag color={C.red} solid>{failedRules.length} FAILED</Tag>
          )}
        </div>
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden" }}>
          {visibleRules.map((rule, i) => {
            const rc = ruleColor(rule.result);
            const icon = { pass: "✓", fail: "✗", unclear: "?" }[rule.result] || "?";
            return (
              <div key={i} className="rule-row" style={{ display: "flex", gap: 12, padding: "11px 16px", alignItems: "flex-start", borderBottom: i < visibleRules.length - 1 ? `1px solid ${C.border}` : "none" }}>
                <div style={{ width: 20, height: 20, borderRadius: "50%", background: `${rc}1a`, border: `1px solid ${rc}40`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: rc, flexShrink: 0, fontFamily: "'DM Mono'", marginTop: 1 }}>
                  {icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: C.textPrimary, lineHeight: 1.4 }}>{rule.description}</div>
                  {rule.detail && <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2, lineHeight: 1.5 }}>{rule.detail}</div>}
                  {rule.rbi_reference && (
                    <div style={{ fontSize: 10, color: C.textMuted, marginTop: 3, opacity: 0.7, fontStyle: "italic" }}>{rule.rbi_reference}</div>
                  )}
                </div>
                <div className="mono" style={{ fontSize: 9, color: rc, textTransform: "uppercase", letterSpacing: "0.08em", flexShrink: 0, marginTop: 2 }}>
                  {rule.result}
                </div>
              </div>
            );
          })}
        </div>
        {(data.rbi_rules || []).length > visibleRules.length && (
          <button onClick={() => setShowAllRules(true)} style={{ marginTop: 8, width: "100%", padding: "8px", background: "none", border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12, color: C.textMuted }}>
            Show all {data.rbi_rules.length} rules ↓
          </button>
        )}
      </div>

      <Rule />

      {/* ── Verdict ── */}
      {data.verdict && (
        <div className="fade-up fade-up-4">
          <SectionLabel>Plain Language Verdict</SectionLabel>
          <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
            {verdictOptions.map(({ key, label }) => (
              <button key={key} onClick={() => setVerdictLang(key)} style={{
                padding: "5px 12px", fontSize: 11, borderRadius: 4, fontFamily: "'DM Mono'", fontWeight: 600,
                border: `1px solid ${verdictLang === key ? sc : C.border}`,
                background: verdictLang === key ? `${sc}18` : "transparent",
                color: verdictLang === key ? sc : C.textMuted,
              }}>
                {label}
              </button>
            ))}
          </div>
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderLeft: `3px solid ${sc}`, borderRadius: "0 8px 8px 0", padding: "16px 20px", fontSize: 14, lineHeight: 1.75, color: C.textPrimary }}>
            {data.verdict[verdictLang] || "—"}
          </div>
        </div>
      )}

      {/* ── Actions — sticky on mobile ── */}
      <div className="fade-up fade-up-5" style={{ position: "sticky", bottom: 0, background: C.bg, paddingTop: 12, paddingBottom: 12, borderTop: `1px solid ${C.border}`, marginTop: 28 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button onClick={downloadPDF} disabled={downloading} style={{
            width: "100%", padding: "15px", background: C.red, color: "#fff",
            border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600,
            fontFamily: "'Syne'", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          }}>
            {downloading ? <><Spinner size={16} /> Generating PDF...</> : "⬇ Download Evidence Report (PDF)"}
          </button>
          <a href="https://cms.rbi.org.in" target="_blank" rel="noopener noreferrer" style={{
            display: "block", width: "100%", padding: "13px",
            border: `1px solid ${C.border}`, borderRadius: 8,
            fontSize: 13, color: C.textSecondary, textAlign: "center", textDecoration: "none",
          }}>
            File complaint at RBI Ombudsman → cms.rbi.org.in
          </a>
        </div>
        <div style={{ marginTop: 10, fontSize: 10, color: C.textMuted, textAlign: "center", lineHeight: 1.5 }}>
          RBI Ombudsman helpline: <strong style={{ color: C.textSecondary }}>14448</strong> (toll-free, Mon–Fri 9am–5pm)
        </div>
      </div>
    </div>
  );
}

// ─── Error Screen ─────────────────────────────────────────────────────────────
function ErrorScreen({ error, onReset }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, maxWidth: 480, margin: "0 auto" }}>
      <div style={{ fontSize: 36, marginBottom: 20 }}>⚠</div>
      <h2 className="syne" style={{ fontWeight: 700, marginBottom: 12, textAlign: "center" }}>Analysis Failed</h2>
      <p style={{ fontSize: 14, color: C.textSecondary, textAlign: "center", lineHeight: 1.65, marginBottom: 24 }}>
        {error || "Something went wrong. Try again with a clearer image or a different file."}
      </p>
      <button onClick={onReset} style={{ padding: "12px 28px", background: C.red, color: "#fff", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600 }}>
        Try Again
      </button>
    </div>
  );
}

// ─── App Root ─────────────────────────────────────────────────────────────────
export default function App() {
  const [screen, setScreen] = useState("upload");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lang, setLang] = useState("en");

  const handleAnalyze = async (file, selectedLang) => {
    setLang(selectedLang);
    setLoading(true);
    setScreen("loading");
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/analyze`, { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
      setScreen("results");
    } catch (e) {
      setError(e.message);
      setScreen("error");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setScreen("upload"); setResult(null); setError(null); setLoading(false);
  };

  const handleRecompute = async (payload) => {
    const res = await fetch(`${API_URL}/analyze/recompute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${res.status}`);
    }
    const data = await res.json();
    setResult(data);
    return data;
  };

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      {screen === "upload" && <UploadScreen onAnalyze={handleAnalyze} loading={loading} />}
      {screen === "loading" && <LoadingScreen />}
      {screen === "results" && result && <ResultsScreen data={result} preferredLang={lang} onReset={reset} onRecompute={handleRecompute} />}
      {screen === "error" && <ErrorScreen error={error} onReset={reset} />}
    </>
  );
}
