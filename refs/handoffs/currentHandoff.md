---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next bounded checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## 2026-09-18 - Job Scout reflection intent correction #66 implemented; backups #65 remain next

Issue #66 is the bounded Job Scout follow-up justified by the final accepted provider-observability run. Run `5d3f2ad8-2c01-4dde-b640-0ae467585d35` still spent a real public-search request on `"Human-Centered Design company" High Point, NC jobs careers`, while durable reflection history contained off-target suggestions such as internships and design workshops. This was treated as a reflection/strategy-semantics defect, not a provider, scheduler, ranking, or request-budget problem.

Implementation checkpoints `e66220efe2e46bd9da0dd0180d45993879af9900`, `98165cd09478038f70441312b27f5fef0cf1ebc5`, and `b142119747fde9bc050230cdfd8acdd47e8e8859` establish:

- capability phrases remain valid `domain_capability` evidence but are no longer converted automatically into invented `"... company"` employer archetypes;
- the general source-aware query portfolio no longer manufactures `local_employer` strategies from capability terms; local-employer acquisition remains owned by the accepted market-reference lane using explicit employer-list/headquarters anchors;
- query linting rejects stale/malformed local-employer anchors, non-role activities such as workshops/courses/events, and clearly entry-level/internship anchors when configured evidence requests senior/director-level work;
- reflected `employer_archetype` values must be grounded in explicit career evidence rather than synthesized by the LLM;
- employer-archetype coverage gaps are now requested-vs-observed and no longer recycle every zero-yield historical label into fresh reflection pressure;
- reflection contract v3 tells the manager-routed model to preserve career level, avoid non-role activity suggestions, and treat capability phrases as capabilities unless employer-archetype evidence is explicit;
- legitimate adjacent-role and domain exploration remains admissible, and no provider policy, scheduler weight, cooldown, request cap, scoring rule, manager schema, or core authority boundary changed.

Temporary bounded validation passed focused Ruff, `tests/test_job_scout_query_portfolio.py`, and initialized refs validation before generated source-catalog refresh `dff3084f8c1661a6dfdfb2e2c8c5a1b15cf0ea56`. Application version remains `0.12.31`; database schema remains 15.

Issue #65, `[Core] Add manager-owned backup and pre-migration snapshot foundation`, remains the next overall bounded core slice after this Job Scout closeout.

## 2026-09-18 - Resource profiles #64 implemented; backups #65 next

Issue #64 implements the manager-owned reusable resource-profile foundation in `0.12.31`; database schema advances from 14 to 15.

Implementation checkpoint `7281c49799bac21a6dab6083c7b6d988b95e27ae`, lint correction `6735debe949dbb4db73b10114988a98ef4f2786a`, and generated-artifact checkpoint `41d09d070a7fabb0a3fda3e68d743a53452b28de` establish:

- durable named manager-owned resource profiles plus one selected global profile and a stable `manager-default` fallback;
- deterministic effective resolution: explicit manager session/run override > selected named profile > manager default > built-in safe fallback;
- positive-only validation with no zero/negative value interpreted as unlimited;
- real enforcement only for existing runtime seams: `max_requests`, `max_llm_calls`, and `max_parallel_work`;
- persisted and inspectable but explicitly unenforced memory, VRAM, queue-depth, and exploration ceilings;
- cloud-spend ceilings reported as `unenforced_no_authority`; a profile never grants cloud purchasing/spend authority;
- sessions freeze profile ID, explicit overrides, effective limits, enforcement state, and the existing enforceable `resource_policy`;
- session-created module runs receive the resolved enforceable budget;
- direct runs default to the selected manager profile when no legacy budget is supplied;
- task/module `configuration` cannot raise manager-owned run ceilings;
- resource profiles remain independent of module permission approval and Code Shop project/action authority or manager risk evaluation.

Bounded validation run `35370973810` passed on `6735debe949dbb4db73b10114988a98ef4f2786a`: source catalog 219 files / 1837 symbols, 11 OKF indexes, initialized refs validation, 7,055-character Agent Academy context check, Ruff, 33 focused tests, 301 total Python tests, desktop web, and desktop Rust/Tauri all green. The helper then refreshed deterministic discovery artifacts and self-removed at `41d09d070a7fabb0a3fda3e68d743a53452b28de`. Application/desktop versioning was then advanced consistently to `0.12.31`; closeout catalog/handoff-index refresh landed at `7cd76e51ff43ebcd7188ee9c3cd0cd422b418f70`. Final standard CI run `35372662394` is green on exact code/version closeout head `b309c52cfb2e5f5dae6629f1642b25edfa0349a3` across Python, desktop web, and desktop Rust/Tauri, with 301 Python tests passing.

Issue #65, `[Core] Add manager-owned backup and pre-migration snapshot foundation`, is the next bounded Increment 14 slice. Keep backup/snapshot responsibilities distinct from update download/staging/apply/rollback and from arbitrary filesystem authority.

## 2026-09-18 - Module permission review #63 implemented; resource profiles #64 next

Issue #63 implements the first manager-owned install/update permission-review foundation in `0.12.30`; database schema advances from 13 to 14.

Implementation checkpoint `4a2ad34772668334cf0e0e74106d60ed71d4e392`, compatibility-test corrections through `ceb710fc35398718366a43ab6d4576a8c3117216`, and generated-artifact checkpoint `7345692fc40e385c57536fd7c44fd49ee6f9e12a` establish:

- deterministic normalization of manifest permission requests and version-specific review rows keyed by module, version, and permission fingerprint;
- durable pending / approved / denied decisions with actor and provenance;
- no synthetic review for modules that declare no permissions;
- fresh modules with unapproved required permissions remain paused and cannot be enabled until those exact declared permissions are approved;
- optional permission denial may preserve operational admission when all required permissions are approved;
- identical permission sets may carry forward prior decisions into a new version-specific review with explicit carry-forward provenance, while any changed permission fingerprint creates a new pending review;
- schema-14 migration creates explicit `schema14_migration` provenance for compatible permissions already in use by an installed pre-schema-14 module rather than treating official-module trust as approval;
- undeclared permissions cannot be approved, and requests classified as prohibited external action cannot be approved by the permission-review API;
- minimal manager APIs expose review inspection and per-permission approve/deny operations;
- permission approval remains separate from built-in trust and does not bypass Code Shop project/action authority or manager risk evaluation.

Bounded validation run `35363736308` passed on `ceb710fc35398718366a43ab6d4576a8c3117216`: source catalog 212 files / 1792 symbols, 11 OKF indexes, initialized refs validation, 7,054-character Agent Academy context check, Ruff, 27 focused tests, 297 total Python tests, desktop web, and desktop Rust/Tauri all green. The validation helper then refreshed deterministic discovery artifacts and self-removed at `7345692fc40e385c57536fd7c44fd49ee6f9e12a`. Application/desktop versioning was then advanced consistently to `0.12.30`; closeout catalog refresh landed at `496c72118b71a65e4ee825bf11c71078be191274`. Final standard CI run `35365855258` is green on exact code/version closeout head `c054ae965755912575ba314e5eeca69fe92ab083` across Python, desktop web, and desktop Rust/Tauri.

Issue #64, `[Core] Add manager-owned reusable resource profile foundation`, is the next bounded Increment 14 slice. Keep resource ceilings manager-owned; profiles must not become a permission, authority, cloud-spend, or speculative hardware-autotuning mechanism.

## 2026-09-18 - Morning summary #62 implemented; permission review #63 next

Issue #62 implements the first generic manager-owned morning-summary projection in `0.12.29`; database schema remains 13.

Implementation checkpoint `66bee379efc7ba41c5fe17a0a9a7c129522c5467`, lint correction `8e1914fe2d88f47f47bf1ba3dc63801cb6de5b63`, and generated-artifact checkpoint `4841ea65b3b98a562bad73a5d2f0e73ef83b3ca8` establish:

- explicit required `starts_at` / `ends_at` summary windows using half-open `[start, end)` semantics;
- read-only completed, failed, degraded, blocked, review, and Model Lab comparison evidence only where durable records support those categories;
- stable `source_type` / `source_id` attribution and module attribution where present in durable source data;
- open Attention/Review items linked directly rather than copied into a second queue;
- durable run, terminal queue-failure, Model Lab result, and Code Shop attempt evidence without payload-heavy narrative generation;
- explicit exclusion of volatile module-supervisor degradation from the durable summary;
- deterministic empty-window, mixed-evidence, out-of-window, restart, and no-mutation regressions.

Bounded validation passed with source catalog 206 files / 1750 symbols, 11 OKF indexes, initialized refs validation, Agent Academy context checks, Ruff, 20 focused tests, 290 total Python tests, desktop web, and desktop Rust/Tauri all green. Final standard CI run `35360119430` is green on exact `dev` head `804e13d41d24e15d53da6f56e3d6229571a6d40c` across Python, desktop web, and desktop Rust.

Issue #63, `[Core] Add install-time module permission review foundation`, is the next bounded slice. Keep permission approval distinct from module trust and from Code Shop/action authority; no authenticated connector, credential, external-write, marketplace, or polished permission-UI expansion belongs in that slice.


## 2026-09-18 - Attention/Review #61 implemented; morning summary #62 next

Issue #61 implements the first generic manager-owned human-attention primitive in `0.12.28` / schema 13.

Implementation checkpoint `dd58e0c338afea5a066efcc8f663d47cd878f048` plus generated-artifact checkpoint `bbdae93b3cce5f04efa02b3783bebb625fd47ab3` establish:

- durable generic `attention` and `review` items with manager-owned identity, state, context, allowed dispositions, validation/downstream meaning, dependency keys, and audit history;
- idempotent module submission;
- explicit resolve/dismiss transitions and history;
- dependency-local blocking rather than module/project-wide blocking;
- minimal manager APIs for create/list/read/resolve/dismiss/history and dependency-block inspection;
- Code Shop escalation linkage to exactly one manager Attention item while preserving the Code Shop escalation record;
- a safety regression proving module-supplied Attention content cannot grant Code Shop authority;
- a liveness regression proving an unrelated synthetic run remains admissible while an Attention dependency is open.

Code Shop bounded-failure escalation now leaves an enabled project enabled and marks the specific engineering task `escalation_recommended`; the linked Attention dependency `code_shop:task:<task_id>` carries the human-decision block.

Bounded validation run `35356015569` was green: source catalog 200 files / 1729 symbols, 11 OKF indexes, initialized refs validation, Agent Academy context validation, Ruff, 17 focused tests, 287 total Python tests, desktop web build, and desktop Rust/Tauri check all passed. Final exact-head standard CI run `35357211859` is green on `87c979f203a6bffd1a106157f07c826f6d55bd50`: source catalog 200 files / 1729 symbols, 11 OKF indexes, initialized refs validation, 6,300-character agent-context check, 287 Python tests, desktop web, and desktop Rust/Tauri all passed.

Issue #62, `[Core] Add manager morning summary foundation`, is the next bounded slice. It is read-only reporting over durable manager-owned evidence; scheduled delivery, external messaging/connectors, UI polish, and automatic remediation remain deferred.


## 2026-09-18 - Code Shop foundation implemented; Attention/Review #61 next

Code Shop Issue #54 is implemented as the second first-party reference-module foundation. Implementation checkpoint `6112a760cdb00821c5fdefdeff695b7a46559076` plus generated-artifact checkpoint `4f90c65bb7cfb260f795d27b8c0bc4cbf1df7c0f` establish:

- built-in official module `code_shop` with manager-derived trust provenance and stable storage namespace `code_shop`;
- GitHub-authoritative project identity behind a manager connector contract, with durable project lifecycle and synchronized metadata;
- machine-local checkout links that require approved-root containment and a matching GitHub remote identity;
- explicit project action authority `allow | ask | deny`, optional branch/path scope, separate manager risk findings, and durable authority decisions;
- model-blind engineering capabilities for architecture planning, decomposition, implementation, debugging, review, and research;
- typed privileged-execution requests with a deterministic no-op host only; production shell, GitHub mutation, hosted runners, deployment, credential mutation, and destructive Git remain deferred;
- durable engineering tasks, attempts/outcomes, escalations, and automatic bounded-failure escalation;
- minimal manager APIs plus a supervised Code Shop worker that may submit model-blind task capability requests but cannot directly execute privileged actions.

The database schema advances from 11 to 12 and the public application version advances to `0.12.27`. Bounded validation passed deterministic source/OKF/ref checks, Agent Academy context generation, Ruff, 20 focused tests, and the full 284-test Python suite. Final exact-head standard CI run `35354405129` passed on `adb4074a44cfc551641ab05942706cbfbfabf628`: source catalog 194 files / 1701 symbols, 11 OKF indexes, initialized refs validation, 6,283-character agent-context check, 284 Python tests, desktop web build, and desktop Rust/Tauri check all green.

Issue #61, `[Core] Add manager-owned Attention and Review queue foundation`, is the next bounded slice. It should turn Code Shop's domain-specific escalation into a generic manager-owned human-attention primitive while preserving dependency-local blocking and avoiding connector/permission expansion in the same slice.


## 2026-09-17 - Issue #60 accepted; Code Shop #54 next

Exact-runtime acceptance run `5d3f2ad8-2c01-4dde-b640-0ae467585d35` completed successfully through planned `admission_draining` on Git `0169e148de9b56e571c525a6a920bed654e7c303`. Runtime identity is explicit: `uses_checkout_source=true`, the module resolved from `D:\\Apps\\Nerve-Center\\src`, and the managed API used the same checkout source root.

The five-minute gate consumed 67 / 150 requests and 7 / 30 LLM calls, completed four full scores with zero failures, executed four ordinary public searches, returned 21 public-search results, completed 51 / 54 source scans, and recorded no failed public-search request. The new run-scoped `public_search_attempt_evidence` is decisive:

- four actual public-search calls are present;
- all four selected `duckduckgo_html`;
- all four used `search_transport=network`;
- all four completed with `status=succeeded`;
- every row records `search_provider_fallback_used=false`;
- no current-run DDG challenge occurred;
- aggregate `search_provider_fallbacks=0` exactly matches the per-search evidence.

This is the truthful no-fallback case Issue #60 was created to make observable. No Bing request was required, and no network work should be forced solely to make a fallback counter nonzero. Deterministic regressions already cover challenge -> provider cooldown -> later Bing fallback behavior; this live gate proves the report can distinguish provider, transport, status, and fallback accounting in the real runtime. Issue #60 is closed as completed.

Do not reopen Job Scout provider policy, query semantics, scoring, scheduler weights, cooldown duration, request caps, extraction rules, or add a third provider without new contradictory evidence.

The next active bounded slice is Code Shop Issue #54, `[Code Shop] Establish safe orchestration foundation`.


## 2026-09-17 - Issue #57 accepted; provider evidence follow-up #60

Exact-runtime run `8b646b11-d5ba-4725-991c-5eb2eb36c36a` completed successfully via planned `admission_draining` on Git `5155a82099c516eb403630fa72d30b297062a154` with checkout-source identity proven. It used 55 / 150 requests and 5 / 30 LLM calls, completed five full scores with zero failures, completed 31 / 33 source scans, returned 73 public-search results, inspected 319 postings, retained four opportunities, and resolved three career sources.

The decisive Issue #57 acceptance condition is now satisfied: six normalized civic/PDF-OCR `local_employer_deepen` strategies executed through ordinary location-free employer-career search, and the attachment-backed `City of High Point` hypothesis returned public career results and resolved three career sources. Issue #57 is closed as completed.

The run reported `search_provider_fallbacks=0`, but audit of the runtime path exposed an accounting/observability gap rather than evidence for another discovery-policy change. `LocationAwareJobScoutDiscoveryLoop.cycle` predated the fallback counter and did not aggregate it, and the live report could not distinguish reusable search-cache results from fresh provider transport. Issue #60 owns the bounded correction: preserve DDG primary/Bing fallback behavior, expose one run-scoped evidence row per actual public-search call with provider/fallback/cache-vs-network status, and carry fallback counts through the location-aware runtime cycle.

Do not retune search wording, scoring, scheduler weights, cooldown duration, extraction rules, or request caps from this evidence. The low-intent `Human-Centered Design company` Wikipedia references are a separate relevance-quality observation if they persist.


## 2026-09-17 - Bounded public-search fallback checkpoint

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

## Current state

- Work directly on `dev`; do not create a feature branch or PR unless explicitly requested.
- Application version is `0.12.29`.
- Agent Academy alignment baseline is `e4118f96cc0138490b950402ba711399580ee854`; bounded source discovery, handoff required reads, capability-aware sub-agent guidance, and source-modularity rules are now part of Nerve Center's engineering contract.
- The current local-acquisition implementation checkpoint is `fe1608e5e7bc4f309d8a823340f78200a9886ba6`. Exact-runtime gates are pinned to the checkout source; clean employer deepening and truthful provider-challenge accounting are proven; DuckDuckGo challenge state now opens a bounded provider circuit breaker so later strategies can use Bing public HTML without adding a same-strategy retry. Targeted validation passed in workflow `35270065108`; full helper-free exact-head CI is required before the next live gate.
- Issue #57 and Issue #60 are closed as completed. Code Shop Issue #54 is implemented; core Attention/Review Issue #61 is the next active bounded slice.
- Job Scout remains an iterative market-research loop: `expand -> converge -> deepen -> reflect -> re-expand`. Discovery optimizes recall; ranking/scoring provides precision.
- Extracted employer names are hypotheses only. They must pass through ordinary public search and official-career resolution before becoming durable company/location evidence.
- No named employer, city, or region exception exists in production logic.

## Completed Issue #57 behavior

The accepted behavior now includes:

1. intent-pure, revisioned market queries and intent-aware civic-reference selection;
2. civic HR/self-employment exclusion unless employer-landscape evidence is also present;
3. a six-candidate ranked fallback pool with hard two-inspection and three-network-fetch ceilings;
4. current-run-scoped reference audit evidence;
5. extensionless PDF/XLSX routing by normalized response `Content-Type`, with requested/final redirect provenance and a four-megabyte response cap;
6. local OCR for image-only PDFs, limited to four pages and a 1,600-pixel long edge, followed by the existing ranked-employer structural parser and 12-candidate cap;
7. bounded runner tolerance for up to three consecutive status-poll timeouts;
8. normalized evidence semantics: `employer_evidence_authority=civic` and `employer_evidence_medium=attachment`, with a bounded migration for old `civic_attachment` hypotheses;
9. a reserved scheduler slot for both old and normalized civic attachment employer hypotheses;
10. employer deepening resolves the canonical career surface without a location term, while preserving civic location evidence for downstream validation;
11. direct-career and sitemap URL qualification uses discrete route evidence rather than substring matches such as `career-advice` or `job-interview`;
12. sitemap child registration defaults to 50 and is hard-capped at 250; source-only expansion without postings is down-weighted rather than rewarded;
13. durable search-cache rows are reclassified through current URL policy before use, so stale classifications cannot recreate rejected editorial sources;
14. employer-career resolution uses a bounded three-query sequence (`careers`, `official careers`, `employment opportunities`) only when earlier results contain no direct employer/ATS surface;
15. all public-search strategies are deduplicated by compiled `(source_path, query)` identity while their raw civic/OCR provenance rows remain durable;
16. tenant-keyed shared career-portal listing routes remain aggregator evidence, and aggregator-only companies are excluded from employer revisit scheduling;
17. regional alias probes receive protected scheduler capacity only for first-pass coverage. After a regional probe has executed once, it remains eligible through normal learned-weight, exploration-floor, and cooldown selection but no longer owns a guaranteed slot;
18. local-employer reference queries preserve exact discovery intent with quoted employer phrases, regional probes cover common public regional vocabulary, and the evidence extractors recognize broader generic regional-organization and employer-list heading forms without named-market exceptions.
19. changed local/regional query semantics advance the durable market-reference revision, and canonical public-search dedup prefers that current revision so stale strategy identities cannot mask new behavior behind prior-run cooldown history.
20. reserved acquisition lanes may displace excess company revisits while preserving one revisit, and HTML employer-list parsing rejects shallow navigation/social labels before they become employer hypotheses.
21. live acceptance gates pin the repository `src` tree for both the runner and managed API and record the resolved module path plus Git SHA, so runtime/code identity is explicit rather than inferred from the application version.
22. persisted non-attachment `local_employer_deepen` strategies are schedulable only when they carry the current `employer_landscape_v2` evidence revision; legacy and normalized attachment/PDF-OCR evidence remains eligible.
23. canonical deepening resolves equivalent durable employer hypotheses by evidence-semantics priority so normalized attachment/current-revision evidence outranks older legacy PDF/OCR rows before cooldown is applied; DuckDuckGo bot/challenge HTML is reported as challenged rather than cached as a legitimate zero-result search, while ordinary empty HTML remains non-challenged.
24. ordinary-public search uses a durable one-hour provider circuit breaker: a DuckDuckGo challenge ends the current strategy, later strategies may use Bing public HTML while DuckDuckGo cools, each strategy still consumes only one search request, ordinary empty DuckDuckGo results do not rotate providers, and provider/fallback telemetry is durable in the live audit surface.

OCR is generic and structural. It requires employer-list heading evidence plus monotonic ranked rows. OCR output becomes `local_employer_deepen` work; it does not directly create companies.

## Implementation and validation

- `7af8cbb2902141736c9b07a8d6c48b1e7ad0990e`: extensionless supported-document routing and bounded polling recovery (`0.12.16`).
- `e6c36488314874261e30c0db65712aae83fb2fd7`: bounded local OCR and packaged runtime support (`0.12.17`).
- `b3902c8`: civic-attachment scheduler compatibility (`0.12.18`).
- `e6aac49`: split civic authority from attachment medium.
- `4f2bceb`: bounded migration of persisted combined-authority hypotheses (`0.12.19`).
- `ef8d61b`: location-free canonical employer career resolution and OCR word-boundary repair (`0.12.20`).
- `bf461c2`: discrete job-route qualification, bounded sitemap expansion, and posting-conditioned learning (`0.12.21`).
- `8877970`: authoritative cached-result reclassification (`0.12.22`).
- `33f5d3e`: bounded canonical employer-career query failback (`0.12.23`).
- `a41dce0`: compiled civic-employer query deduplication (`0.12.24`).
- `c24b44b`: generic shared-portal classification and aggregator-only revisit exclusion (`0.12.25`).
- `12ed92d`: compiled-query deduplication across all public-search revisions and provenance (`0.12.26`).
- `12a566f2661beee677a125e1236487d62d922ed4`: first-pass-only protected capacity for `regional_alias_probe` strategies.
- `f1f144e07cfe2ccc170f78313607f5d8b2f41e8c`: regression coverage proving initial regional coverage remains protected but the slot is released after the first attempt.
- `a1632ff3e497b5c699eb5d4ca12609430d215ba6`: refreshed deterministic source-catalog shards for the regional-saturation implementation/test changes.
- `708484842782fa91bc84a81fed6a72cec016e7a2`: expanded generic regional-organization and employer-list evidence patterns with deterministic regression coverage.
- `fa5cfd0f0558daab0b2a76a059679bf7db4c6b28`: clean local-acquisition implementation checkpoint after temporary helper cleanup.
- `5240bf5f820772277dfacba5a14c6ed6064c393a`: `market_reference_v6`, current-revision canonical preference for local/regional public-search identities, cooldown regression coverage, and refreshed deterministic source catalog.
- `857bbfae2a2822039956ffabcb336dac3b400a2c`: reserved acquisition lanes can displace excess company revisits while preserving one revisit; HTML employer-list parsing rejects shallow navigation/social labels; regression coverage and deterministic source catalog refreshed.
- `d71f316414f0de5a121f7359d87c53fba7b00d98`: live runner and managed API are pinned to the checkout `src` tree; live reports record `runtime_identity` with module path, source root, checkout-source flag, managed-API first path, and exact Git SHA.
- `8d7f9477caec1874d8cd5f81d1f6b709100f073d`: durable employer-landscape evidence revisioning; stale unversioned non-attachment deepening rows are excluded from scheduling, current evidence is preferred during canonical dedup, and legacy/normalized attachment/PDF-OCR evidence remains eligible. Targeted validation workflow `35256387208` passed Ruff, discovery-learning/loop tests, and deterministic source-catalog validation.
- `1c50972bbd84d072c3c21fa63a163770d26638c5`: equivalent `local_employer_deepen` strategies now use evidence-semantics priority during canonical public-search dedup, allowing normalized attachment/current evidence to bypass an older equivalent row's cooldown. `HttpFetcher` also detects DuckDuckGo bot/challenge response language without treating an ordinary empty DuckDuckGo HTML page as challenged. Targeted validation workflow `35262867619` passed Ruff, discovery-learning/connectors tests, and deterministic source-catalog validation.
- `fe1608e5e7bc4f309d8a823340f78200a9886ba6`: bounded ordinary-public provider fallback. DuckDuckGo challenge state is persisted for one hour; later strategies may select Bing public HTML while preserving one search request per strategy. Bing result-list parsing, tracking-URL normalization, provider/fallback attempt evidence, and aggregate `search_provider_fallbacks` telemetry are covered by focused regressions. Targeted workflow `35270065108` passed Ruff, 67 focused tests, source-catalog validation, and OKF validation.
- CI `35219112384` is green: refs/tracked paths, agent context, Ruff, packaging command, full Python tests, desktop web, and desktop Rust/Tauri all passed.
- The self-contained Windows backend builds and passes health, workspace, and module-runtime smoke tests. OCR increases the backend executable to about 155.8 MiB.

## Runtime evidence

Run `efd30156-4156-48cc-a731-e357cc4bcb29` (`0.12.16`) reached planned `admission_draining`: 99 requests, 27 LLM calls, 27 successful searches, 269 returned results, 19/19 full scores, and current-run-only reference evidence. It routed three extensionless PDFs through the parser but extracted zero candidates because the documents lacked text layers.

Visual and parser inspection of the official High Point `2022 Largest Employers` PDF confirmed it is a one-page image-only employer table. The bounded OCR fallback extracted 12 hypotheses from that exact artifact, including `Volvo Group North America`, without a named-employer rule.

Run `48425240-38d6-431f-84b9-f92a57df5335` loaded `0.12.17`, created and persisted those 12 OCR employer hypotheses, and retained two roles with 10/10 successful full scores. A concurrent local validation process interrupted its managed API; the runner reported the failure truthfully. After resume it reached planned wind-down with 134 requests and 17 LLM calls. Treat it as acquisition evidence, not a clean end-to-end acceptance gate.

Run `d896ef7d-b671-4445-b02c-5f2a29e1488c` (`0.12.19`) proved scheduler reachability: three civic/OCR-derived `local_employer_deepen` attempts executed, 30/31 full scores completed with zero failures, and the run remained within budget. Location-heavy employer queries selected blocked aggregators, which led to the `0.12.20` canonical-career query correction.

Run `1c68afd8-26d1-4f40-9fee-bfe35e67cfef` (`0.12.20`) immediately exercised corrected queries such as `"High Point University" careers`. It was healthy through cycle 26 with 60 successful searches, 450 returned results, 12 companies, 36 career sources, five postings, one retained opportunity, and 26/26 successful scores. At cycle 27 a false company created from an editorial page expanded 250 sitemap article/image URLs and was incorrectly rewarded despite zero postings. The run was stopped at cycle 29.

The exact false RippleMatch graph was removed after a recoverable database backup: one company, 251 sources, 250 revisit strategies, two scans, and four evidence rows; it contained no jobs, provenance, or enrichment. A second evidence-defined quarantine disabled 746 historical sitemap-created JSON-LD sources that had neither discrete job-route evidence nor job provenance, and lowered their revisit strategies. No source with job provenance was touched.

Run `41270b53-6af3-475c-a528-5363016a1655` was the bounded `0.12.21` post-cleanup verification gate. It confirmed proportional source counts and posting-conditioned down-weighting, but also proved cached result classifications could bypass the new URL policy and recreate the rejected editorial company. It was stopped early; `0.12.22` made classification authoritative when cache rows are consumed.

Run `4633fbac-4c77-46cc-9411-cafd4b3915f8` (`0.12.22`) reached planned `admission_draining` with 50 requests, 13 LLM calls, 8/8 successful full scores, 16 searches, 132 results, two companies, two career sources, and four postings. Source growth stayed proportional and the stale RippleMatch result remained rejected. The result also identified weak chamber/directory identity resolution.

Run `1dc9b888-dfb7-4067-affe-b764446f5e0c` (`0.12.23`) reached planned wind-down with 47 requests, 24 LLM calls, 14/14 successful scores, 11 searches, 110 results, and no new companies or sources. Its 11 search attempts compiled to only eight unique queries, which led to compiled-query canonicalization.

Run `4d882157-ae48-477a-9139-aed0a2281816` (`0.12.24`) was stopped after a false shared career-portal company revisit expanded 50 sources with zero postings. Audit proved the full false graph had 304 sources, 303 revisit strategies, 46 scans, and zero jobs/provenance. It was removed after backup `nerve-center.pre-shared-portal-cleanup.20260915-154117.sqlite3`; foreign-key validation was clean. No named portal rule was added: `0.12.25` recognizes the generic tenant listing/print route shape and refuses employer revisit when a company's sources are aggregator-only.

Run `78b7e242-8aee-450f-a373-5f73600f8326` (`0.12.26`) is the final bounded pre-soak gate. It reached planned `admission_draining` with 59 requests, seven LLM calls, 5/5 successful full scores, 10 searches, 90 results, 38 successful source scans, 124 postings inspected, five retained roles, 12 evidence-backed employer hypotheses, and five career sources. All 10 public queries were unique, the shared-portal company remained absent, and source growth stayed proportional to posting yield.

The subsequent long soak was launched from pre-Agent-Academy-alignment head `ad34249`. The host rebooted during the run and Job Scout resumed correctly from durable state without requiring a restart. That is positive recovery evidence.

The completed long soak then reached planned wind-down cleanly at 10:52 PM EDT with no process or API listener left running. The exact run ID was not supplied with the final report, so none is inferred here. Final counts were:

- 1,574 / 3,000 requests;
- 159 / 500 LLM calls;
- 100 / 100 full scores, zero failures;
- 221 successful searches, zero failed;
- 674 search results returned;
- 732 postings inspected;
- six companies discovered;
- 18 retained opportunities;
- 87 requests per retained opportunity, improved from 365 in the previous soak;
- 102 intermittent monitoring timeouts, all recovered.

This clears general search reliability, scoring reliability, planned wind-down, and timeout recovery as active blockers. The remaining weakness is local acquisition: zero regional aliases and zero employer candidates. The location-family audit produced only two conditioned yields across 1,467 attempts while correctly down-weighting 200 poorly performing families.

## 30-minute local-acquisition gate

Run `2adf0558-f86f-4d03-8a8c-0a4477dd2dad` completed successfully at planned `admission_draining` after the requested 30-minute gate:

- 139 / 500 requests;
- 43 / 80 LLM calls;
- 25 / 25 full scores, zero failures;
- 25 successful public searches, zero failed, but zero results returned;
- 58 source scans completed and 71 known-company revisits;
- 96 strategy attempts;
- zero companies, career sources, postings, retained opportunities, regional aliases, employer candidates, or inspected employer-reference pages;
- 10 intermittent status-poll timeouts, all recovered;
- three low-marginal-yield backoffs.

The current-run strategy mix was 73 `legacy`, seven `employer_archetype`, seven `gap_reflection`, five `direct_role`, three `adjacent_role`, and one `domain_capability`. Critically, `local_employer` executed zero times and `regional_alias_probe` executed zero times. The gate therefore did not exercise the new local/regional query or extraction behavior.

Audit of durable selection showed the new query semantics were still using `market_reference_v5`. Prior v5 attempts remained inside the 24-hour cooldown, and canonical compiled-query dedup could retain the older identity even after a revision bump because equivalent queries were previously resolved oldest-first. This is a persistence/identity defect, not evidence that the regional first-pass reservation or general scheduler weights are wrong.

The bounded correction is `market_reference_v6` plus current-revision preference during canonical dedup for `local_employer` and `regional_alias_probe`. Unrelated public-search identities keep oldest-first canonicalization, and the 24-hour cooldown remains unchanged.
## 30-minute v6 acquisition gate

Run `14011cec-0ee2-4d63-b593-0dc7f318c832` completed successfully at planned `admission_draining` after the v6 identity correction:

- 133 / 500 requests;
- 43 / 80 LLM calls;
- duration and planned wind-down both completed without budget exhaustion;
- 21 current-run `local_employer` reference attempts across the bounded local market family;
- employer-reference pages were inspected and evidence-backed employer hypotheses were produced;
- the High Point civic `2022 Largest Employers` PDF was parsed through the existing bounded OCR path and yielded 12 employer-name hypotheses;
- all eight fresh `market_reference_v6` `regional_alias_probe` strategies remained at zero attempts;
- newly available `local_employer_deepen` hypotheses also received no current-run attempt.

This proves the v6 persistence/canonicalization correction worked for `local_employer`: the acquisition query/reference/extraction path is alive. It also isolates the next scheduler defect. In a four-slot wave, reserved non-company acquisition lanes could not displace any `company_revisit`, so multiple high-weight revisits could occupy the remaining capacity after local-employer reservation and starve both employer deepening and regional first-pass coverage.

The same run exposed an HTML extraction precision defect. One public Major Employers page produced 12 hypotheses from subordinate navigation/section labels such as `Strategic Location`, `Higher Education`, `Facebook`, and `LinkedIn`. Those are not accepted as employer truth. The working civic PDF/OCR path remains valid evidence and must not be weakened.

The bounded correction at `857bbfae...` allows a reserved non-company acquisition lane to replace an excess company revisit only when more than one revisit is selected, preserving one revisit lane. Regression coverage proves a four-slot wave can contain one company revisit plus `local_employer`, evidence-backed `local_employer_deepen`, and first-pass `regional_alias_probe`. HTML extraction now rejects shallow subordinate headings and generic social-navigation labels while structured JSON and PDF/OCR paths remain unchanged.

## Exact-runtime acquisition gate

Run `5ec24553-3886-45e6-a1d1-46ff38a169cc` reached planned `admission_draining` with 143 requests, 41 LLM calls, 25/25 successful full scores, 24 successful searches, 21 raw search results, 59 source scans, and 96 strategy attempts. Its mix was 72 legacy/revisit executions plus 24 `local_employer` executions, with zero `regional_alias_probe` and zero `local_employer_deepen`. All 21 raw local-employer results were ineligible, so no current-run employer hypothesis existed to deepen. Because that run did not record the imported backend source path or Git SHA, its apparent contradiction with the deterministic scheduler regression was not accepted as evidence to retune scheduler policy.

Checkpoint `d71f316...` made the gate self-verifying by forcing the checkout `src` tree to the front of both parent and managed-API import resolution and recording exact runtime identity.

Run `7e9184d1-30d7-4d25-8379-852b613d112f` then completed the requested five-minute diagnostic gate at planned `admission_draining` with 46 requests, seven LLM calls, four successful full scores, 25 completed searches, 16 completed source scans, five revisits, and 20 strategy attempts. Runtime identity proved the exact pulled checkout was executing: Git `8c61f2c75b69b39ec6a6eb7d121a8807f802de00`, `uses_checkout_source=true`, module `D:\Apps\Nerve-Center\src\nerve_center\__init__.py`, and managed API `PYTHONPATH` beginning at `D:\Apps\Nerve-Center\src`.

The scheduler result is decisive. Across all five cycles the four-slot portfolio was exactly one legacy/revisit, one fresh `market_reference_v6` `regional_alias_probe`, one `local_employer_deepen`, and one v6 `local_employer`. The regional first-pass reservation, local-employer reservation, employer-deepening reservation, and one-revisit preservation are therefore all proven live under the exact current runtime. Do not retune general scheduler weights, cooldowns, or request caps from this evidence.

The gate exposed a narrower persistence defect: all five deepening slots were consumed by old false HTML-derived hypotheses created before the current extractor precision rules (`In this section`, `Strategic Location`, `Transportation Infrastructure`, `Innovation & Research`, and `Vibrant Businesses Major Employers`). New extraction would no longer create these names, but the durable rows were still considered evidence-backed. Checkpoint `8d7f947...` versions current employer-landscape evidence as `employer_landscape_v2`, excludes stale unversioned non-attachment deepening rows from selection, preserves old and normalized attachment/PDF-OCR evidence, and prefers current evidence during compiled-query canonicalization.

All 25 public-search requests in this five-minute gate completed without provider failure but returned zero results. This is not yet enough to change query/provider policy because the immediately preceding gate returned 21 raw results. If another exact-head short gate repeats zero public results after the stale-evidence cleanup, investigate public-result provider/cache/query behavior before changing extraction or scoring.


## Post-evidence-revision five-minute gate

Run `6b582fdf-dba9-43fe-9929-576a97e6ffa8` completed the requested five-minute gate from exact checkout `267dd6c16cae70a942ca8e42131e8cf02604b41e`: `runtime_identity.uses_checkout_source=true`, the imported module resolved `D:\Apps\Nerve-Center\src`, and the managed API used that same source root. The run consumed 48 requests and seven LLM calls, completed five full scores with zero scoring failures, completed 31 source scans, and attempted 20 strategies across five cycles.

The stale HTML/navigation hypotheses were absent from current-run execution, confirming the `employer_landscape_v2` exclusion worked. However, no `local_employer_deepen` strategy executed even though the durable inventory still contained legitimate attachment/PDF-OCR employer hypotheses. Audit showed normalized attachment rows were being canonicalized against older equivalent PDF/OCR rows that were also considered current. Oldest-first tie resolution therefore retained the legacy row, and its prior attempt could place the canonical identity inside the 24-hour cooldown. This was a canonical persistence defect, not a scheduler-capacity defect.

The same run repeated the public-search anomaly: eight search requests completed, zero failed, and all eight returned zero results. With two consecutive exact-runtime short gates showing this pattern, provider handling became the next bounded investigation. DuckDuckGo bot/challenge HTML can return HTTP 200 and was previously indistinguishable from a valid empty result page in coverage accounting.

Checkpoint `1c50972...` addresses both findings without retuning scoring, query weights, scheduler allocation, cooldown duration, or request caps. Equivalent deepening strategies now compare evidence-semantics priority before age, so normalized attachment/current-revision evidence wins over an older equivalent legacy PDF/OCR row. Legacy attachment evidence remains eligible when no higher-priority equivalent exists. Shared HTTP acquisition now marks DuckDuckGo bot/challenge response language as challenged while a regression proves an ordinary empty DuckDuckGo HTML page remains non-challenged.

## Regional saturation checkpoint

The scheduler previously reserved one `regional_alias_probe` slot whenever any such strategy was eligible. In a four-strategy wave, that could become a permanent 25 percent capacity reservation even after regional vocabulary had already been sampled and marginal yield had fallen.

The accepted correction is structural rather than threshold-based: each regional probe may use the protected slot until its first execution. After that, it competes through the same durable learned weight, exploration floor, and cooldown rules as other discovery strategies. This keeps regional coverage reachable without making it a perpetual fixed tax on later waves. No named market, static saturation count, or region-specific exception was introduced.

The regression test proves both sides of the invariant: a never-attempted regional probe is included in the initial protected portfolio, and after one attempt it is no longer forced into the next four-strategy wave.

## Local acquisition correction

The current bounded correction addresses the newly isolated acquisition weakness without increasing request caps or changing general scoring/scheduler weights:

1. local-employer reference queries preserve exact intent with quoted phrases such as `"major employers"`, `"largest employers"`, and `"employer directory"`;
2. regional probes search common public regional vocabulary: `regional council`, `regional partnership`, and `council of governments`;
3. regional title extraction recognizes generic `Council of Governments`, `Planning Commission`, and `Development District` forms in addition to the prior `Regional Council/Partnership/Commission/Authority/Planning` forms;
4. civic employer-list heading extraction accepts common variants such as `Top 25 Private Employers`, `Leading Employers`, `Employer Directory`, and `Employer List`;
5. deterministic tests cover the broadened regional and employer-list evidence while preserving the rule that extracted names are hypotheses only.

No named company, city, or region exception was added. No extra network path or request allowance was added.

## Next bounded slice

Proceed with core Issue #63: install-time module permission review foundation.

The first slice should:

1. normalize declared module permissions deterministically;
2. persist exact module/version/permission-fingerprint review state and decision provenance;
3. leave built-in no-permission modules operable without synthetic approval records;
4. prevent unreviewed required permission changes from silently becoming operationally enabled;
5. expose minimal manager inspect/approve/deny APIs limited to permissions actually declared by the manifest;
6. invalidate stale approval when the version/permission request changes;
7. prove that permission approval cannot bypass Code Shop project/action authority or manager risk evaluation.

Explicitly defer authenticated/private connector implementation, credential storage/entry, external drafts/writes, third-party modules/marketplace, learned policy, and polished desktop permission UI.

## Required Reads For Next Slice

- `refs/handoffs/currentHandoff.md`
- `refs/handoffs/next-dev-prompt.md`
- Issue #63 and its latest comments
- `refs/planning/mvp-roadmap.md` around Increment 13
- source-catalog matches for module manifest permissions, module synchronization/lifecycle, persistence, manager API, and Code Shop authority boundaries

## Re-entry

```powershell
python scripts/agent_context.py --focus "module permission review install update manifest required approval lifecycle authority" --issue 63
```
