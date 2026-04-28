"""
Loan Buster — FastAPI Backend
AI Predatory Lending Decoder · Solution Challenge 2026
"""
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.analyze import (
    analyze_loan,
    recompute_analysis,
    router as analyze_router,
)
from app.api.report import generate_pdf, router as report_router
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("loanlens")


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject standard security headers into every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


# ---------------------------------------------------------------------------
# Rate Limiter Middleware  (in-memory sliding window)
# ---------------------------------------------------------------------------
RATE_LIMIT = 10          # max requests per window
RATE_WINDOW_SECONDS = 60  # window size

# {ip: [timestamp, ...]}
_rate_buckets: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-IP rate limiter for the /api/v1/analyze endpoint."""

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit the heavy analysis endpoint
        if request.url.path.startswith("/api/v1/analyze"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            bucket = _rate_buckets[client_ip]

            # Prune old entries outside the window
            cutoff = now - RATE_WINDOW_SECONDS
            _rate_buckets[client_ip] = [t for t in bucket if t > cutoff]
            bucket = _rate_buckets[client_ip]

            if len(bucket) >= RATE_LIMIT:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too many requests",
                        "detail": f"Rate limit: {RATE_LIMIT} requests per {RATE_WINDOW_SECONDS}s. "
                                  "Please wait before retrying.",
                    },
                )
            bucket.append(now)

        return await call_next(request)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loan Buster API starting...")
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set — extraction will fail!")
    yield
    logger.info("Loan Buster API shutting down.")


app = FastAPI(
    title="Loan Buster API",
    description="AI-powered predatory lending decoder for Indian borrowers. "
                "Extracts hidden APR from loan documents and flags RBI violations.",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware order matters: outermost runs first
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/api/v1", tags=["Analysis"])
app.include_router(report_router, prefix="/api/v1", tags=["Report"])

# Backward-compatible aliases for older frontend builds that call unprefixed routes.
app.add_api_route("/analyze", analyze_loan, methods=["POST"], include_in_schema=False)
app.add_api_route(
    "/analyze/recompute",
    recompute_analysis,
    methods=["POST"],
    include_in_schema=False,
)
app.add_api_route("/report/pdf", generate_pdf, methods=["POST"], include_in_schema=False)


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "service": "Loan Buster API v1.0",
        "model": settings.GEMINI_MODEL,
        "environment": settings.ENVIRONMENT,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
