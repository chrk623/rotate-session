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

## Run multiple scrape targets

```python
import re

from rotate_session import RotateSessionMulti, ScrapeTarget


class QuotePageScraper(RotateSessionMulti):
    def extract_once(self, from_scrape, progress_text=""):
        quotes = re.findall(
            r'<span class="text" itemprop="text">(.*?)</span>',
            from_scrape.text,
        )
        return quotes[:3]


scraper = QuotePageScraper(
    targets=[
        ScrapeTarget(
            url="https://quotes.toscrape.com/page/1/",
            kwargs={"timeout": 20},
        ),
        ScrapeTarget(
            url="https://quotes.toscrape.com/page/2/",
            kwargs={"timeout": 20},
        ),
    ],
    global_params={"source": "quotes.toscrape.com"},
    num_threads=2,
)

results = scraper.run()
print(results)
```

`ScrapeTarget` is the default target model. The base
`scrape_once(session, target, progress_text="")` uses its `url`, optional
`params`, and optional request `kwargs`. It can also validate compatible
dictionaries with the same keys.

For custom target shapes, use dictionaries and override both hooks:

```python
import html
import re

from rotate_session import RotateSessionMulti


class QuoteTagScraper(RotateSessionMulti):
    def scrape_once(self, session, target, progress_text=""):
        response = session.get(
            f"{self.global_params['base_url']}/tag/{target['tag']}/",
            timeout=20,
        )
        return {"tag": target["tag"], "html": response.text}

    def extract_once(self, from_scrape, progress_text=""):
        quotes = re.findall(
            r'<span class="text" itemprop="text">(.*?)</span>',
            from_scrape["html"],
        )
        return {
            "tag": from_scrape["tag"],
            "quotes": [html.unescape(quote) for quote in quotes[:2]],
        }


scraper = QuoteTagScraper(
    targets=[
        {"tag": "love"},
        {"tag": "humor"},
    ],
    global_params={"base_url": "https://quotes.toscrape.com"},
    num_threads=2,
)

results = scraper.run()
print(results)
```

## Notes

- Logging, documentation and README were generated with AI.
