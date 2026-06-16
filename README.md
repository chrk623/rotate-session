# rotate-session

`rotate-session` is a small Python package for HTTP requests with retry support and optional proxy rotation.

## Installation

```bash
pip install rotate-session
```

## Features

- Retry failed requests with configurable attempts and wait time
- Rotate across a list of proxies automatically on retry
- Fetch proxy lists from Webshare
- Use plain `requests`-style proxies when provider integration is not needed

## Quick start

```python
from rotate_session import RotateSession

session = RotateSession()
response = session.get("https://httpbin.org/get", timeout=20)
print(response.status_code)
```

## Configure retries

```python
from rotate_session import RetryConfig, RotateSession

retry = RetryConfig(max_retries=5, wait_secs=2)
session = RotateSession(retry_config=retry)
```

## Use your own proxy list

```python
from rotate_session import ProxyConfig, RotateSession

proxy_config = ProxyConfig(
    proxies=[
        {"http": "http://user:pass@1.2.3.4:8080", "https": "http://user:pass@1.2.3.4:8080"},
        {"http": "http://user:pass@5.6.7.8:8080", "https": "http://user:pass@5.6.7.8:8080"},
    ]
)

session = RotateSession(proxy_config=proxy_config)
response = session.get("https://httpbin.org/ip", timeout=20)
print(response.text)
```

## Use Webshare as proxy provider

```python
from rotate_session import ProxyConfig, ProxyProvider, RotateSession

proxy_config = ProxyConfig(
    provider=ProxyProvider.WEBSHARE,
    api_key="YOUR_WEBSHARE_API_KEY",
)

session = RotateSession(
    proxy_config=proxy_config,
    proxies_fetch_params={"country_codes": ["US"], "mode": "direct"},
)

response = session.get("https://httpbin.org/ip", timeout=20)
print(response.text)
```

## Notes

- Logging, documentation and README were generated with AI.
