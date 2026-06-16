"""Webshare provider integration."""

import os
from typing import Any, Literal
from urllib.parse import urlencode

from loguru import logger
from requests import Session

from rotate_session.constants import (
    WEBSHARE_API_BASE,
    WEBSHARE_PROFILE_PATH,
    WEBSHARE_PROXY_LIST_PATH,
)


class Webshare:
    """Client wrapper for Webshare proxy APIs."""

    def __init__(self, api_key: str | None = None) -> None:
        """Create an authenticated Webshare session."""
        self.api_key = api_key or os.getenv("WEBSHARE_KEY")
        if not self.api_key:
            raise ValueError(
                "api key not provided and WEBSHARE_KEY is not set in environment"
            )

        self.session = Session()
        self.session.headers = {"Authorization": self.api_key}
        logger.debug("Initialized Webshare client.")

    def user_profile(self) -> dict[str, Any]:
        """Fetch current Webshare account profile."""
        response = self.session.get(f"{WEBSHARE_API_BASE}{WEBSHARE_PROFILE_PATH}")
        logger.debug("Fetched Webshare user profile.")
        return response.json()

    def fetch_proxies(
        self,
        country_codes: list[str] | None = None,
        mode: Literal["direct", "backbone"] = "direct",
    ) -> list[dict[str, Any]]:
        """Fetch all proxies with optional country filter and mode."""
        params: dict[str, str | int] = {
            "page": 1,
            "page_size": 100,
            "mode": mode,
            "ordering": "proxy_address",
        }
        if country_codes:
            params["country_code__in"] = ",".join(country_codes)

        fetch_url: str | None = (
            f"{WEBSHARE_API_BASE}{WEBSHARE_PROXY_LIST_PATH}?{urlencode(params)}"
        )
        proxies: list[dict[str, Any]] = []
        logger.info(
            "Fetching proxies from Webshare with mode={} and countries={}.",
            mode,
            country_codes or [],
        )

        while fetch_url is not None:
            response = self.session.get(fetch_url)
            payload = response.json()
            proxies.extend(payload["results"])
            fetch_url = payload["next"]
            logger.debug("Fetched page; running proxy count={}.", len(proxies))

        logger.info("Finished fetching proxies; total={}.", len(proxies))
        return proxies

    def fetch_proxies_dict(
        self,
        country_codes: list[str] | None = None,
        mode: Literal["direct", "backbone"] = "direct",
    ) -> list[dict[str, str]]:
        """Return proxies formatted for `requests.Session.proxies`."""
        proxies = self.fetch_proxies(country_codes=country_codes, mode=mode)
        proxy_mappings = [
            {
                "http": (
                    f"http://{item['username']}:{item['password']}@"
                    f"{item['proxy_address']}:{item['port']}"
                ),
                "https": (
                    f"http://{item['username']}:{item['password']}@"
                    f"{item['proxy_address']}:{item['port']}"
                ),
            }
            for item in proxies
        ]

        logger.debug(
            "Converted proxies to requests format; total={}.",
            len(proxy_mappings),
        )
        return proxy_mappings
