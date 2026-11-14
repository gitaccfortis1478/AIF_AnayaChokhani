"""Validate deploy inputs and build the disposable catalogue index.

Run from backend/: uv run --no-sync python -m formaos.render_build
"""
from __future__ import annotations

import json
from pathlib import Path

from formaos.catalogue.index_catalogue import build_index
from formaos.room_dimensions import ROOM_DIMENSION_POLICY
from formaos.vastu.schema import load_rule_set


def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    catalogue = backend_root / "data/curated/abo_mvp_catalogue_with_images.csv"
    rules = backend_root / "data/vastu/vastu_rules_v1.json"
    for path in (catalogue, rules):
        if not path.is_file():
            raise RuntimeError(f"Missing deploy input: {path}. Include this file in Git before deploying.")
    load_rule_set(rules)
    assert ROOM_DIMENSION_POLICY["rooms"], "Room dimension policy is empty"
    summary = build_index(catalogue, backend_root / "data/vectorstores/chroma")
    if not summary["indexed_count"]:
        raise RuntimeError("The catalogue index contains no products")
    # Fail the build on import errors instead of waiting for server startup.
    from formaos.api.main import app
    assert any(route.path == "/api/health" for route in app.routes)
    print(json.dumps({"status": "ready", **summary}, indent=2))


if __name__ == "__main__":
    main()
