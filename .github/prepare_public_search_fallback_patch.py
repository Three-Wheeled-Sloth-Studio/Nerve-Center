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
print("public search patch helper prepared")
