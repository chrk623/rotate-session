"""Network utility helpers."""

from collections.abc import Mapping

import requests as rq

from rotate_session.constants import PUBLIC_IP_SERVICES


def my_ip(proxies: Mapping[str, str] | None = None) -> str:
    """Return public IP, optionally routed through proxies."""
    proxies_dict = dict(proxies or {})
    for service_url in PUBLIC_IP_SERVICES:
        response = rq.get(service_url, proxies=proxies_dict)
        if response.status_code == 200:
            return response.text.strip()
    raise RuntimeError("Failed to get public IP from all configured services.")
