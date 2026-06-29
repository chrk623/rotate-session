"""Threaded scrape runner built on top of RotateSession."""

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, local
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from rotate_session.config import ProxyConfig, RetryConfig
from rotate_session.session import RotateSession


class ScrapeTarget(BaseModel):
    """Default target shape for `RotateSessionMulti`."""

    url: str
    params: dict[str, Any] | None = None
    kwargs: dict[str, Any] = Field(default_factory=dict)


Target = ScrapeTarget | dict[str, Any]


class RotateSessionMulti(RotateSession):
    """Subclassable multi-target scraper with rotate-session retries.

    Override `scrape_once` to change how each target is fetched and override
    `extract_once` to transform each fetched result.
    """

    def __init__(
        self,
        targets: Iterable[Target] | None = None,
        global_params: dict[str, Any] | None = None,
        num_threads: int = 1,
        proxy_config: ProxyConfig | None = None,
        proxies_fetch_params: dict[str, Any] | None = None,
        retry_config: RetryConfig | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the runner with optional targets and shared parameters."""
        super().__init__(
            proxy_config,
            proxies_fetch_params,
            retry_config,
            *args,
            **kwargs,
        )
        if num_threads < 1:
            raise ValueError("num_threads must be at least 1.")
        self.targets = list(targets or [])
        self.global_params = global_params if global_params is not None else {}
        self.num_threads = num_threads
        self._clone_count = 0
        self._clone_lock = Lock()

    @staticmethod
    def _target_label(target: Target) -> str:
        """Return a useful progress label for typed or custom targets."""
        if isinstance(target, ScrapeTarget):
            return target.url
        return str(target.get("url", target))

    def _clone_session(self) -> RotateSession:
        """Create a worker-local session with the same retry and proxy settings."""
        proxy_config = None
        if self._proxies_store:
            proxy_config = ProxyConfig(
                proxies=list(self._proxies_store),
                shuffle=False,
            )

        session = RotateSession(
            proxy_config=proxy_config,
            retry_config=self.retry_config,
        )
        if session._proxies_store:
            with self._clone_lock:
                proxy_index = self._clone_count % len(session._proxies_store)
                self._clone_count += 1
            session._proxy_index = proxy_index
            session.proxies = session._proxies_store[proxy_index]

        session.headers.update(self.headers)
        session.cookies.update(self.cookies)
        session.auth = self.auth
        session.verify = self.verify
        session.cert = self.cert
        session.trust_env = self.trust_env
        return session

    def scrape_once(
        self,
        session: RotateSession,
        target: Target,
        progress_text: str = "",
    ) -> Any:
        """Fetch one target. Subclasses can override this hook."""
        if progress_text:
            logger.info(progress_text)
        scrape_target = (
            target
            if isinstance(target, ScrapeTarget)
            else ScrapeTarget.model_validate(target)
        )
        request_kwargs = dict(scrape_target.kwargs)
        if scrape_target.params is not None:
            request_kwargs.setdefault("params", scrape_target.params)
        return session.get(scrape_target.url, **request_kwargs)

    def extract_once(self, from_scrape: Any, progress_text: str = "") -> Any:
        """Transform one scrape result. Subclasses can override this hook."""
        return from_scrape

    def _run_once(
        self,
        session: RotateSession,
        target: Target,
        index: int,
        total: int,
    ) -> Any:
        """Run scrape and extraction hooks for a single target."""
        target_label = self._target_label(target)
        progress_text = f"[{index + 1}/{total}] {target_label}"
        scraped = self.scrape_once(session, target, progress_text=progress_text)
        return self.extract_once(scraped, progress_text=progress_text)

    def run(
        self,
        targets: Iterable[Target] | None = None,
    ) -> list[Any]:
        """Scrape all targets and return extracted results in input order."""
        scrape_targets = list(targets) if targets is not None else self.targets
        if not scrape_targets:
            return []

        max_workers = min(self.num_threads, len(scrape_targets))
        if max_workers == 1:
            return [
                self._run_once(self, target, index, len(scrape_targets))
                for index, target in enumerate(scrape_targets)
            ]

        thread_state = local()
        worker_sessions: list[RotateSession] = []
        worker_sessions_lock = Lock()

        def get_worker_session() -> RotateSession:
            session = getattr(thread_state, "session", None)
            if session is None:
                session = self._clone_session()
                setattr(thread_state, "session", session)
                with worker_sessions_lock:
                    worker_sessions.append(session)
            return session

        def run_indexed(index: int, target: Target) -> Any:
            return self._run_once(
                get_worker_session(),
                target,
                index,
                len(scrape_targets),
            )

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(run_indexed, index, target)
                    for index, target in enumerate(scrape_targets)
                ]
                return [future.result() for future in futures]
        finally:
            for session in worker_sessions:
                session.close()
