from pathlib import Path

path = Path(__file__).with_name("patch_public_search_fallback_once.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '        warnings: list[str] = []\\n        try:\\n',
    '        warnings: list[str] = []\\n        search_provider = ""\\n        search_provider_fallback_used = False\\n        try:\\n',
)
'''
new = '''replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '        query = _strategy_query(strategy)\\n        warnings: list[str] = []\\n        try:\\n',
    '        query = _strategy_query(strategy)\\n        warnings: list[str] = []\\n        search_provider = ""\\n        search_provider_fallback_used = False\\n        try:\\n',
)
'''
if old not in text:
    raise RuntimeError("discovery-loop patch preparation anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

test_path = Path(__file__).resolve().parents[1] / "tests/test_live_runner_progress.py"
test_text = test_path.read_text(encoding="utf-8")
test_old = '''            "search_requests_completed": 0,\n            "search_requests_failed": 0,\n            "search_results_returned": 0,\n'''
test_new = '''            "search_requests_completed": 0,\n            "search_requests_failed": 0,\n            "search_provider_fallbacks": 0,\n            "search_results_returned": 0,\n'''
if test_old not in test_text:
    raise RuntimeError("live-runner fallback telemetry test anchor not found")
test_path.write_text(test_text.replace(test_old, test_new, 1), encoding="utf-8")
print("public search patch helper prepared")