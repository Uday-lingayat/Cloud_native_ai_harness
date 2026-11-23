import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    max_retries: int
    timeout_s: float

    @classmethod
    def load(cls, env_file: Path = Path(".env")) -> "LLMSettings":
        # .env.example uses one KEY=value per line. Process settings take priority.
        values = {}
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and key.strip().startswith("LLM_"):
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    values[key.strip()] = value
        values.update(os.environ)
        settings = cls(
            values.get("LLM_PROVIDER", "mock").strip(),
            values.get("LLM_BASE_URL", "").strip(),
            values.get("LLM_MODEL", "").strip(),
            values.get("LLM_API_KEY", "").strip(),
            int(values.get("LLM_MAX_RETRIES", "3")),
            float(values.get("LLM_TIMEOUT_S", "30")),
        )
        if (
            settings.max_retries < 0
            or not math.isfinite(settings.timeout_s)
            or settings.timeout_s <= 0
        ):
            raise ValueError(
                "LLM_MAX_RETRIES must be nonnegative and LLM_TIMEOUT_S finite and positive"
            )
        return settings

    def validate_endpoint(self) -> None:
        url = urlsplit(self.base_url)
        local_http = url.scheme == "http" and url.hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if (
            not url.hostname
            or not (url.scheme == "https" or local_http)
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "LLM_BASE_URL must be an HTTPS endpoint or local HTTP endpoint"
            )
        if not self.model or not self.api_key:
            raise ValueError(
                "Set LLM_MODEL and LLM_API_KEY for the compatible provider"
            )
