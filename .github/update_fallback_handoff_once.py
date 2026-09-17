from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "refs/handoffs/currentHandoff.md"
text = path.read_text(encoding="utf-8")
marker = "# Current Handoff\n\n"
section = """## 2026-09-17 - Bounded public-search fallback checkpoint

Live acceptance run `e107e4a4-5f1c-4cd0-806e-001b4c97fd3a` completed through planned `admission_draining` with 51 / 150 requests, 6 / 30 LLM calls, four full scores with zero scoring failures, and 31 / 31 source scans completed. The gate proves the previous two fixes are alive: clean `local_employer_deepen` work executed for `Volvo Group North America` (four public results) and `HAECO Americas` (eight public results), while DuckDuckGo bot/challenge responses surfaced as `challenged` instead of valid empty searches for Durham-Chapel Hill, Mount Airy, and Danville.

The remaining runtime limiter was transport rather than scheduler or scoring behavior: nine public-search attempts produced four completed searches, six failed/challenged attempts, and 15 returned results, with no new companies, career sources, postings, regional aliases, or employer candidates. Do not use that evidence to retune scoring, query semantics, scheduler capacity, cooldown policy, or request caps.

Implementation checkpoint `fe1608e5e7bc4f309d8a823340f78200a9886ba6` adds a bounded provider fallback:

- DuckDuckGo remains the primary ordinary-public search provider.
- A detected provider challenge records one-hour durable provider health/circuit-breaker state.
- The challenged strategy ends normally; there is no same-strategy retry and the existing one-request allowance per strategy is preserved.
- Later public-search strategies rotate to Bing public HTML while DuckDuckGo is cooling down.
- Successful non-empty cached results remain reusable during provider cooldown; ordinary empty DuckDuckGo HTML does not trigger provider rotation.
- Bing result extraction is limited to the normal result-list structure and Bing tracking URLs are normalized back to public target URLs.
- Attempt evidence records `search_provider` and `search_provider_fallback_used`; aggregate acquisition telemetry records `search_provider_fallbacks`.
- If Bing is also challenged it receives its own cooldown rather than silently adding another request or another provider.

Targeted workflow `35270065108` passed Ruff, 67 focused tests, deterministic source-catalog validation, and OKF index validation. The temporary patch helpers/workflow removed themselves before the implementation commit.

The next acceptance gate remains an isolated five-minute run. It should prove that, after a DuckDuckGo challenge, a later strategy uses `bing_html` with `search_provider_fallback_used=true` and aggregate `search_provider_fallbacks > 0`, while clean employer deepening and the protected local/regional acquisition lanes remain reachable. If Bing also challenges, diagnose provider transport before adding a third provider or changing discovery/scoring policy.

"""
if section.splitlines()[0] not in text:
    if marker not in text:
        raise RuntimeError("Current Handoff heading not found")
    text = text.replace(marker, marker + section, 1)
path.write_text(text, encoding="utf-8")
print("fallback handoff checkpoint inserted")
