import runpy
from pathlib import Path

import pytest

_SMOKE = runpy.run_path(str(Path(__file__).parents[1] / "scripts/smoke_packaged_backend.py"))


@pytest.mark.parametrize("reason", ["no_configured_evidence_or_market", "unexpected_failure"])
def test_packaged_empty_workspace_requires_exact_no_work_reason(monkeypatch, reason):
    smoke = _SMOKE["smoke_module_runtime"]

    def request(path, method="GET", payload=None):
        if path == "/api/v1/runs":
            return {"id": "fixture"}
        if path == "/api/v1/runs/fixture":
            return {"status": "partial", "checkpoint": {"terminal_reason": reason}}
        return {"runtime": {"process_id": 123}}

    monkeypatch.setitem(smoke.__globals__, "request_json", request)
    if reason == "no_configured_evidence_or_market":
        smoke(1)
    else:
        with pytest.raises(SystemExit, match="did not stop explicitly"):
            smoke(1)
