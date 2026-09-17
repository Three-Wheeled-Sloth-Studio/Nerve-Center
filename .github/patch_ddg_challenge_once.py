from pathlib import Path

fetching_path = Path("src/nerve_center/discovery/fetching.py")
fetching = fetching_path.read_text(encoding="utf-8")
old = '''        challenged = response.status_code in {401, 403} and any(
            marker in lowered for marker in _CHALLENGE_MARKERS
        )
        if not challenged:
            challenged = any(marker in lowered for marker in _CHALLENGE_MARKERS)
'''
new = '''        challenged = any(marker in lowered for marker in _CHALLENGE_MARKERS)
        if not challenged and "duckduckgo" in lowered:
            challenged = any(
                marker in lowered
                for marker in (
                    "bots use",
                    "complete the following challenge",
                    "robot-detected",
                    "select all squares",
                )
            )
'''
if old not in fetching:
    raise SystemExit("challenge detection block not found")
fetching_path.write_text(fetching.replace(old, new, 1), encoding="utf-8")

connector_test_path = Path("tests/test_discovery_connectors.py")
connector_test = connector_test_path.read_text(encoding="utf-8")
ordinary_test = r'''


def test_http_fetcher_does_not_treat_ordinary_empty_duckduckgo_page_as_challenge() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>No results found for this search.</body></html>",
            headers={"content-type": "text/html; charset=UTF-8"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = asyncio.run(
        HttpFetcher(client=client).get(
            "https://html.duckduckgo.com/html/",
            params={"q": "example"},
        )
    )
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert response.challenged is False
'''
if "test_http_fetcher_does_not_treat_ordinary_empty_duckduckgo_page_as_challenge" not in connector_test:
    connector_test_path.write_text(
        connector_test.rstrip() + ordinary_test + "\n",
        encoding="utf-8",
    )
