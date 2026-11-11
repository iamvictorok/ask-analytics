import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
import tempfile
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env file to the repository root so settings resolve identically
# regardless of the process working directory (systemd units, tests run from
# subdirs, etc.) instead of a CWD-relative lookup that silently falls back to
# defaults.
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class SettingsBase(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

logger = logging.getLogger("dhis2_analyst.config")


class Settings(SettingsBase):
    # standalone: own login (access code + JWT).
    # dhis2:      clients send a DHIS2 Personal Access Token (validated via /api/me).
    # route:      only requests proxied by a DHIS2 Route that carry the shared
    #             route key are accepted (the DHIS2 app / App Hub mode).
    # combined:   standalone + dhis2, plus route requests when ROUTE_SHARED_KEY is set.
    deployment_mode: Literal["standalone", "dhis2", "route", "combined"] = "standalone"

    # The DHIS2 instance the backend reads data from. No default instance is
    # assumed: set it to your own server (or a public play instance for demos).
    dhis2_base_url: str = ""
    dhis2_service_account_user: str = ""
    dhis2_service_account_pass: str = ""
    # Server-side Personal Access Token for a (read-only) DHIS2 account. Used
    # for data/metadata calls when the request carries no per-user token
    # (route mode). Preferred over the username/password pair.
    dhis2_pat: str = ""

    # DHIS2 Route mode. The DHIS2 admin configures the Route with an
    # "api-headers" auth entry: <ROUTE_KEY_HEADER>: <ROUTE_SHARED_KEY>.
    # DHIS2 stores it encrypted and adds it server-side; the browser never sees it.
    route_shared_key: str = ""
    route_key_header: str = "X-Route-Key"
    # DHIS2 adds the calling username in this header on every routed request.
    route_user_header: str = "X-Forwarded-User"
    # Failover: comma-separated instances tried in order (first = primary).
    # Empty -> just DHIS2_BASE_URL. The first that passes its health check
    # serves requests; the header dot shows live (primary) or fallback.
    dhis2_base_urls: str = ""
    # auto: serve the committed demo snapshot when every instance is down.
    # off: never use the snapshot. always: snapshot only (offline rehearsal).
    # Default off: the bundled snapshot is public demo data and must never
    # stand in for a real instance. The hosted demo sets it to auto explicitly.
    dhis2_snapshot_mode: Literal["auto", "off", "always"] = "off"
    dhis2_snapshot_path: str = ""          # default: backend/demo_snapshot/dhis2_snapshot.json
    dhis2_snapshot_record_path: str = ""   # set only when recording a new snapshot
    dhis2_health_interval_seconds: int = 60
    dhis2_health_timeout_seconds: float = 8.0

    # mock | openai | anthropic | ollama | azure | cohere | gemini.
    # Defaults to "mock" so the app boots without external credentials (and so
    # importing the app never raises a bare ValidationError before the friendly
    # startup checks can run).
    llm_provider: str = "mock"
    llm_model: str = "gpt-4o"           # model string passed to LiteLLM
    llm_api_key: str = ""
    # Self-hosted / local models: any OpenAI-compatible endpoint works, e.g.
    #   LLM_PROVIDER=ollama  LLM_MODEL=ollama/llama3.1  LLM_BASE_URL=http://ollama:11434
    #   LLM_PROVIDER=openai  LLM_MODEL=openai/<model>    LLM_BASE_URL=http://vllm:8000/v1
    llm_base_url: str = ""
    llm_timeout_seconds: int = 30
    # Transient-error resilience (503 "high demand", 429, timeouts): retry the
    # primary model with backoff, then try each fallback model in order.
    # Comma-separated LiteLLM model strings; empty = provider default (gemini:
    # gemini/gemini-flash-lite-latest). Set to "none" to disable fallbacks.
    llm_fallback_models: str = ""
    llm_transient_retries: int = 2
    llm_retry_backoff_seconds: float = 2.0
    # Whole-answer time budget (seconds) for the LLM calls of one chat request.
    # A DHIS2 Route cuts the response at its timeout (max 60 s) and buffers
    # it, so in route mode every answer must finish before that. When the
    # budget runs out, remaining LLM steps are skipped (keyword intent
    # classifier, data-only answer) instead of the Route returning a 504.
    # 0 = auto: 45 s in route/combined-with-route mode, unlimited otherwise.
    # Negative = always unlimited.
    answer_time_budget_seconds: float = 0.0

    # Embedding model
    embedding_provider: str = "mock"    # mock | openai | cohere | ollama
    embedding_model: str = "text-embedding-3-small"

    # Tavily web enrichment
    tavily_api_key: str = ""
    tavily_endpoint: str = ""           # set for SearxNG-compatible self-hosted alternative
    tavily_trusted_domains: str = "who.int,cdc.gov,afro.who.int,unicef.org,.gov"

    # Feature flags
    evidence_fusion: bool = True
    audit_web_search: bool = True
    enable_direct_sql: bool = False

    # Storage and sessions
    database_url: str = "sqlite+aiosqlite:///./dhis2_analyst.db"
    redis_url: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_expire_seconds: int = 3600
    # Standalone mode: if set, /auth/login only accepts this password (any
    # username). Leave empty for local use; SET IT for any hosted demo, or
    # anyone with the URL can log in and spend the LLM quota.
    standalone_access_code: str = ""
    # Refuse to start in standalone mode without STANDALONE_ACCESS_CODE.
    # Defaults to on automatically when running on Render (RENDER=true).
    require_access_code: bool = False

    # File storage
    temp_file_dir: str = "/tmp/dhis2_analyst"
    max_file_age_seconds: int = 3600
    max_file_size_bytes: int = 52_428_800  # 50 MB

    # Rate limiting
    rate_limit_rpm: int = 60            # requests per minute per user/IP
    # Trust X-Forwarded-For for the client IP (enable ONLY behind a proxy you
    # control — clients can otherwise spoof the header to dodge rate limits).
    trust_proxy_headers: bool = False

    # CORS — include both Vite dev port and direct backend port
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8000,http://localhost:8000"

    # Query safety
    metadata_confidence_threshold: float = 0.82
    max_rows: int = 10_000
    sql_timeout_seconds: int = 10

    @property
    def temp_path(self) -> Path:
        raw = self.temp_file_dir
        path = Path(raw)
        # Platform-aware: Unix-style /tmp/ path on Windows → use tempfile.gettempdir()
        if raw.startswith("/tmp/") and os.name == "nt":
            path = Path(tempfile.gettempdir()) / raw.split("/tmp/", 1)[1]
        elif raw.startswith("/tmp/") and not Path("/tmp").exists():
            path = Path(tempfile.gettempdir()) / raw.split("/tmp/", 1)[1]
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def trusted_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.tavily_trusted_domains.split(",") if d.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.database_url or "postgres" in self.database_url



    @property
    def has_dhis2_credentials(self) -> bool:
        """Server-side DHIS2 credentials (PAT or service account) are configured."""
        return bool(self.dhis2_pat or self.dhis2_service_account_user)

    @property
    def route_mode_enabled(self) -> bool:
        """Requests proxied by a DHIS2 Route (with the shared key) are accepted."""
        if self.deployment_mode == "route":
            return True
        return self.deployment_mode == "combined" and bool(self.route_shared_key)

    @property
    def effective_answer_budget(self) -> float | None:
        """Seconds one chat answer may spend on LLM calls, or None (no limit)."""
        if self.answer_time_budget_seconds < 0:
            return None
        if self.answer_time_budget_seconds > 0:
            return float(self.answer_time_budget_seconds)
        return 45.0 if self.route_mode_enabled else None

    @property
    def is_hosted(self) -> bool:
        return self.require_access_code or os.environ.get("RENDER", "").lower() == "true"

    def startup_checks(self) -> None:
        """Hard-fail on insecure or incomplete configuration.

        The ``mock`` provider is exempt: it runs entirely locally (deterministic
        classifier + canned generation) so it needs neither LLM credentials nor
        a production JWT secret, which is what makes the shipped ``.env.example``
        runnable out of the box.
        """
        if (
            self.is_hosted
            and self.deployment_mode in {"standalone", "combined"}
            and not self.standalone_access_code.strip()
        ):
            logger.critical(
                "FATAL: hosted deployment without STANDALONE_ACCESS_CODE — anyone "
                "with the URL could log in and spend the LLM quota. Set "
                "STANDALONE_ACCESS_CODE (or unset REQUIRE_ACCESS_CODE for local use)."
            )
            sys.exit(1)

        if self.deployment_mode == "route":
            if len(self.route_shared_key.strip()) < 32:
                logger.critical(
                    "FATAL: DEPLOYMENT_MODE=route needs ROUTE_SHARED_KEY (at least 32 "
                    "characters, e.g. `openssl rand -hex 32`). Put the same value in the "
                    "DHIS2 Route's api-headers auth."
                )
                sys.exit(1)
            if not self.dhis2_base_url.strip():
                logger.critical("FATAL: DEPLOYMENT_MODE=route needs DHIS2_BASE_URL (your DHIS2 server).")
                sys.exit(1)
            if not self.has_dhis2_credentials:
                logger.warning(
                    "route mode without DHIS2_PAT or service-account credentials: the "
                    "assistant cannot read DHIS2 data until one is set."
                )

        if self.llm_provider == "mock":
            logger.warning(
                "llm_provider=mock — running with the deterministic local "
                "classifier and canned generation. Set a real LLM_PROVIDER for production."
            )
            return

        if not self.llm_api_key and not self.llm_base_url:
            logger.critical(
                "FATAL: No LLM credentials configured. "
                "Set LLM_API_KEY or LLM_BASE_URL (for Ollama) in .env."
            )
            sys.exit(1)

        if self.jwt_secret == "change-me-in-production" and self.deployment_mode != "route":
            logger.critical(
                "FATAL: JWT_SECRET is still the default value. "
                "Set a strong, unique JWT_SECRET in .env before deploying."
            )
            sys.exit(1)

    def log_resolved_settings(self) -> None:
        """Log resolved non-secret settings at startup for observability."""
        logger.info(
            "settings_resolved",
            extra={
                "deployment_mode": self.deployment_mode,
                "llm_provider": self.llm_provider,
                "llm_model": self.llm_model,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "evidence_fusion": self.evidence_fusion,
                "enable_direct_sql": self.enable_direct_sql,
                "database_type": "postgres" if self.is_postgres else "sqlite",
                "rate_limit_rpm": self.rate_limit_rpm,
                "max_rows": self.max_rows,
                "cors_origins": self.cors_origin_list,
                "temp_path": str(self.temp_path),
                "dhis2_base_url": self.dhis2_base_url,
                "has_tavily_key": bool(self.tavily_api_key),
                "has_dhis2_credentials": self.has_dhis2_credentials,
                "route_mode": self.route_mode_enabled,
            },
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
