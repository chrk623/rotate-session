"""Requests session with retry and optional proxy rotation."""

import random
from typing import Any

from loguru import logger
from requests import Response, Session
from tenacity import (
    Retrying,
    RetryCallState,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_fixed,
)

from rotate_session.config import ProxyConfig, ProxyProvider, RetryConfig
from rotate_session.providers.webshare import Webshare

ProxyMapping = dict[str, str]


class RotateSession(Session):
    """HTTP session with optional proxy rotation and retry support."""

    def __init__(
        self,
        proxy_config: ProxyConfig | None = None,
        proxies_fetch_params: dict[str, Any] | None = None,
        retry_config: RetryConfig | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize session with optional proxy source and retry strategy."""
        super().__init__(*args, **kwargs)
        self.proxy_config = proxy_config
        self._proxy_index = 0
        self._proxies_store: list[ProxyMapping] = []

        if proxy_config:
            self._proxies_store = self._load_proxies(
                proxy_config=proxy_config,
                proxies_fetch_params=proxies_fetch_params,
            )
            if proxy_config.shuffle:
                random.shuffle(self._proxies_store)
            if self._proxies_store:
                self.proxies = self._proxies_store[0]

        self.retry_config = retry_config or RetryConfig()
        self.retrier = Retrying(
            retry=retry_if_exception_type(Exception)
            | retry_if_result(self._should_retry_response),
            stop=stop_after_attempt(self.retry_config.max_retries),
            wait=wait_fixed(self.retry_config.wait_secs),
            before_sleep=self._on_retry_failure,
            retry_error_callback=self._on_retry_exhausted,
            reraise=True,
        )

    def _load_proxies(
        self,
        proxy_config: ProxyConfig,
        proxies_fetch_params: dict[str, Any] | None = None,
    ) -> list[ProxyMapping]:
        """Return proxies from user-supplied list or configured provider."""
        if proxy_config.proxies:
            logger.info(
                "Loaded {} user-supplied proxies.",
                len(proxy_config.proxies),
            )
            return proxy_config.proxies

        if proxy_config.provider == ProxyProvider.WEBSHARE:
            webshare = Webshare(api_key=proxy_config.api_key)
            fetch_params = proxies_fetch_params or {}
            proxies = webshare.fetch_proxies_dict(**fetch_params)
            logger.info("Loaded {} proxies from Webshare provider.", len(proxies))
            return proxies

        return []

    def _on_retry_failure(self, retry_state: RetryCallState) -> None:
        """Rotate proxy and log context before the next retry attempt."""
        method = str(retry_state.args[0]) if len(retry_state.args) > 0 else "UNKNOWN"
        url = str(retry_state.args[1]) if len(retry_state.args) > 1 else "UNKNOWN"
        reason = "unknown retry condition"

        if retry_state.outcome is not None:
            if retry_state.outcome.failed:
                exception = retry_state.outcome.exception()
                if exception is not None:
                    reason = f"exception {type(exception).__name__}: {exception}"
                else:
                    reason = "exception (details unavailable)"
            else:
                result = retry_state.outcome.result()
                if isinstance(result, Response):
                    reason = f"HTTP status code {result.status_code}"
                else:
                    reason = f"non-Response result type {type(result).__name__}"

        logger.warning(
            "Retrying request on attempt {} for {} {} due to {}; rotating proxy before retry.",
            retry_state.attempt_number,
            method,
            url,
            reason,
        )
        self._rotate_proxy()

    @staticmethod
    def _should_retry_response(response: Response) -> bool:
        """Retry when request result is not a 2xx HTTP status."""
        return not 200 <= response.status_code < 300

    @staticmethod
    def _on_retry_exhausted(retry_state: RetryCallState) -> Response:
        """Return last response on exhausted status retries; raise exhausted exceptions."""
        if retry_state.outcome is None:
            raise RuntimeError("Retry exhausted without an outcome.")

        if retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            if exception is None:
                raise RuntimeError("Retry exhausted with unknown exception state.")
            raise exception

        result = retry_state.outcome.result()
        if isinstance(result, Response):
            return result

        raise RuntimeError(
            f"Retry exhausted with unexpected result type {type(result).__name__}."
        )

    def _rotate_proxy(self) -> None:
        """Switch to the next proxy in the store (round-robin)."""
        if not self._proxies_store:
            logger.debug("No proxies available in store; skipping rotation.")
            return

        previous = self._proxy_index
        self._proxy_index = (self._proxy_index + 1) % len(self._proxies_store)
        self.proxies = self._proxies_store[self._proxy_index]
        logger.info(
            "Switched proxy from index {} to {}.",
            previous,
            self._proxy_index,
        )

    def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> Response:
        """Execute request through tenacity retrier."""
        return self.retrier(super().request, method, url, *args, **kwargs)
