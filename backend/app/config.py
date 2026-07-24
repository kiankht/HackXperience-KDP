import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
DEFAULT_AI_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_UPLOAD_BYTES = 10_485_760
DEFAULT_AUTO_CLAIM_SECONDS = 300
VALID_AI_MODES = {"auto", "real", "fallback"}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    ai_mode: str
    ai_timeout_seconds: float
    max_upload_bytes: int
    auto_claim_seconds: int = DEFAULT_AUTO_CLAIM_SECONDS

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv(override=False)
        mode = os.getenv("AI_MODE", "auto").strip().casefold()
        if mode not in VALID_AI_MODES:
            mode = "auto"
        try:
            timeout = max(1.0, float(os.getenv("AI_TIMEOUT_SECONDS", DEFAULT_AI_TIMEOUT_SECONDS)))
        except ValueError:
            timeout = DEFAULT_AI_TIMEOUT_SECONDS
        try:
            max_upload = max(1, int(os.getenv("MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES)))
        except ValueError:
            max_upload = DEFAULT_MAX_UPLOAD_BYTES
        try:
            auto_claim_seconds = max(10, int(os.getenv("AUTO_CLAIM_SECONDS", DEFAULT_AUTO_CLAIM_SECONDS)))
        except ValueError:
            auto_claim_seconds = DEFAULT_AUTO_CLAIM_SECONDS
        key = os.getenv("OPENAI_API_KEY", "").strip() or None
        return cls(
            openai_api_key=key,
            openai_model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL,
            ai_mode=mode,
            ai_timeout_seconds=timeout,
            max_upload_bytes=max_upload,
            auto_claim_seconds=auto_claim_seconds,
        )
