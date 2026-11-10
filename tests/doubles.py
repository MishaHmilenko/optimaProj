"""Hand-written test doubles for IDisplayer, following the three
categories from the practical:

  * FakeDisplayer - simplest working implementation: does nothing.
  * StubDisplayer - configurable: raises for messages containing a
    given trigger, so we can test how callers react to failures.
  * MockDisplayer - a stub that also records every call, so tests can
    assert how many times (and with what) it was invoked.
"""

from __future__ import annotations

from infra import IDisplayable, IDisplayer


class FakeDisplayer(IDisplayer):
    def display(self, item: IDisplayable) -> None:
        pass


class StubDisplayer(IDisplayer):
    def __init__(self, fail_on: str | None = None) -> None:
        self._fail_on = fail_on

    def display(self, item: IDisplayable) -> None:
        if self._fail_on is not None and self._fail_on in item.to_display():
            raise RuntimeError(f"Display failed for: {item.to_display()}")


class FakeHttpClient:
    """IHttpClient double: serves canned JSON by URL and records calls.
    Raises RemoteServiceError for URLs it doesn't know, like a 404."""

    def __init__(self, responses: dict | None = None) -> None:
        self.responses = dict(responses or {})
        self.requested: list[str] = []

    def get_json(self, url: str):
        from infra import RemoteServiceError

        self.requested.append(url)
        if url not in self.responses:
            raise RemoteServiceError(f"404 for {url}")
        return self.responses[url]


class MockDisplayer(StubDisplayer):
    def __init__(self, fail_on: str | None = None) -> None:
        super().__init__(fail_on)
        self.messages: list[str] = []

    @property
    def call_count(self) -> int:
        return len(self.messages)

    def display(self, item: IDisplayable) -> None:
        self.messages.append(item.to_display())
        super().display(item)
