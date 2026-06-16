"""Configuration models for proxy and retry behavior."""

from enum import Enum
from typing import Self

from pydantic import BaseModel, model_validator


class ProxyProvider(str, Enum):
    """Supported external proxy providers."""

    WEBSHARE = "webshare"


class ProxyConfig(BaseModel):
    """Proxy source configuration.

    Provide either:
    - `provider` (+ provider-specific settings like `api_key`), or
    - explicit `proxies` in requests-compatible format.
    """

    provider: ProxyProvider | None = None
    api_key: str | None = None
    proxies: list[dict[str, str]] | None = None
    shuffle: bool = True

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        """Ensure exactly one proxy source is configured."""
        has_provider = self.provider is not None
        has_proxies = bool(self.proxies)

        if has_provider and has_proxies:
            raise ValueError("Provide either provider settings or proxies, not both.")
        if not has_provider and not has_proxies:
            raise ValueError("ProxyConfig requires either provider or proxies.")

        return self


class RetryConfig(BaseModel):
    """Retry strategy for requests executed by `RotateSession`."""

    max_retries: int = 3
    wait_secs: int = 1
