import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_application_versions_stay_aligned() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cargo = tomllib.loads(
        (ROOT / "desktop" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    )
    package = json.loads((ROOT / "desktop" / "package.json").read_text(encoding="utf-8"))
    tauri = json.loads(
        (ROOT / "desktop" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    init_text = (ROOT / "src" / "nerve_center" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert match is not None

    versions = {
        pyproject["project"]["version"],
        cargo["package"]["version"],
        package["version"],
        tauri["version"],
        match.group(1),
    }
    assert len(versions) == 1, f"public application versions diverged: {sorted(versions)}"
