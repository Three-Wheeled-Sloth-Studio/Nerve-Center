from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "refs/handoffs/currentHandoff.md"
text = path.read_text(encoding="utf-8")
old_state = "- The current local-acquisition checkpoint is `1c50972bbd84d072c3c21fa63a163770d26638c5`. Exact-runtime gates are pinned to the checkout source; regional/local/deepening reservations are proven reachable; canonical deepening now prefers normalized attachment/current-revision evidence over older equivalent legacy rows; and DuckDuckGo bot/challenge HTML is classified as challenged instead of a valid zero-result search. Targeted validation passed in workflow `35262867619`; full clean-head CI is required before the next live gate."
new_state = "- The current local-acquisition implementation checkpoint is `fe1608e5e7bc4f309d8a823340f78200a9886ba6`. Exact-runtime gates are pinned to the checkout source; clean employer deepening and truthful provider-challenge accounting are proven; DuckDuckGo challenge state now opens a bounded provider circuit breaker so later strategies can use Bing public HTML without adding a same-strategy retry. Targeted validation passed in workflow `35270065108`; full helper-free exact-head CI is required before the next live gate."
if old_state not in text:
    raise RuntimeError("stale current-state checkpoint not found")
text = text.replace(old_state, new_state, 1)
old_behavior = "23. canonical deepening resolves equivalent durable employer hypotheses by evidence-semantics priority so normalized attachment/current-revision evidence outranks older legacy PDF/OCR rows before cooldown is applied; DuckDuckGo bot/challenge HTML is reported as challenged rather than cached as a legitimate zero-result search, while ordinary empty HTML remains non-challenged."
new_behavior = old_behavior + "\n24. ordinary-public search uses a durable one-hour provider circuit breaker: a DuckDuckGo challenge ends the current strategy, later strategies may use Bing public HTML while DuckDuckGo cools, each strategy still consumes only one search request, ordinary empty DuckDuckGo results do not rotate providers, and provider/fallback telemetry is durable in the live audit surface."
if old_behavior not in text:
    raise RuntimeError("completed-behavior checkpoint not found")
text = text.replace(old_behavior, new_behavior, 1)
old_impl = "- `1c50972bbd84d072c3c21fa63a163770d26638c5`: equivalent `local_employer_deepen` strategies now use evidence-semantics priority during canonical public-search dedup, allowing normalized attachment/current evidence to bypass an older equivalent row's cooldown. `HttpFetcher` also detects DuckDuckGo bot/challenge response language without treating an ordinary empty DuckDuckGo HTML page as challenged. Targeted validation workflow `35262867619` passed Ruff, discovery-learning/connectors tests, and deterministic source-catalog validation."
new_impl = old_impl + "\n- `fe1608e5e7bc4f309d8a823340f78200a9886ba6`: bounded ordinary-public provider fallback. DuckDuckGo challenge state is persisted for one hour; later strategies may select Bing public HTML while preserving one search request per strategy. Bing result-list parsing, tracking-URL normalization, provider/fallback attempt evidence, and aggregate `search_provider_fallbacks` telemetry are covered by focused regressions. Targeted workflow `35270065108` passed Ruff, 67 focused tests, source-catalog validation, and OKF validation."
if old_impl not in text:
    raise RuntimeError("implementation checkpoint not found")
text = text.replace(old_impl, new_impl, 1)
path.write_text(text, encoding="utf-8")
print("fallback handoff normalized")
