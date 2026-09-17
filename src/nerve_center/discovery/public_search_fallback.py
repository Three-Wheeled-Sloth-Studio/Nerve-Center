"""Bounded parsers for ordinary-public search fallback transports."""

from __future__ import annotations

from html.parser import HTMLParser


class BingSearchResultParser(HTMLParser):
    """Capture result-title links from Bing's public HTML result list only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._result_li_depth = 0
        self._in_heading = False
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "li":
            classes = set((values.get("class") or "").split())
            if self._result_li_depth:
                self._result_li_depth += 1
            elif "b_algo" in classes:
                self._result_li_depth = 1
            return
        if not self._result_li_depth:
            return
        if tag == "h2":
            self._in_heading = True
            return
        if tag == "a" and self._in_heading and self._href is None:
            href = values.get("href")
            if href:
                self._href = href
                self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            title = " ".join("".join(self._parts).split())
            if title:
                self.anchors.append((self._href, title))
            self._href = None
            self._parts = []
            return
        if not self._result_li_depth:
            return
        if tag == "h2":
            self._in_heading = False
        elif tag == "li":
            self._result_li_depth -= 1
            if self._result_li_depth == 0:
                self._in_heading = False
                self._href = None
                self._parts = []
