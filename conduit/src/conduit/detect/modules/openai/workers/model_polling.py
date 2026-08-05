"""ModelPollingWorker: detect disappeared / newly missing models via API snapshot."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from conduit.detect.modules.openai.models_legacy import ChangeType, RawSignal, Severity
from conduit.detect.modules.openai.workers.base import Worker, data_dir, fixtures_dir

MODELS_URL = "https://api.openai.com/v1/models"

# Known replacements when a snapshot model vanishes
KNOWN_REPLACEMENTS = {
    "gpt-4-0613": "gpt-4o",
    "gpt-3.5-turbo-0301": "gpt-4o-mini",
    "text-davinci-003": "gpt-3.5-turbo-instruct",
}


def _model_ids(payload: dict[str, Any]) -> set[str]:
    return {item["id"] for item in payload.get("data", []) if "id" in item}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_live_models(api_key: str) -> dict[str, Any] | None:
    try:
        resp = httpx.get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


class ModelPollingWorker(Worker):
    name = "ModelPollingWorker"

    def run(self) -> list[RawSignal]:
        snapshot_path = data_dir() / ".models-snapshot.json"
        fixture_current = fixtures_dir() / "models" / "current_models.json"

        previous = _load_json(snapshot_path) if snapshot_path.is_file() else {"data": []}

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        current: dict[str, Any] | None = None
        if api_key:
            current = _fetch_live_models(api_key)
        if current is None:
            current = _load_json(fixture_current)

        prev_ids = _model_ids(previous)
        curr_ids = _model_ids(current)
        removed = sorted(prev_ids - curr_ids)

        signals: list[RawSignal] = []
        for model_id in removed:
            replacement = KNOWN_REPLACEMENTS.get(model_id)
            signals.append(
                RawSignal(
                    vendor="openai",
                    change_type=ChangeType.MODEL_REMOVED,
                    severity=Severity.CRITICAL,
                    affected_pattern=model_id,
                    replacement_pattern=replacement,
                    source_url=MODELS_URL,
                    description=(
                        f"Model {model_id} disappeared from /v1/models "
                        f"(replacement hint: {replacement or 'unknown'})"
                    ),
                )
            )

        # Persist updated snapshot for next run (fixture or live)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "object": "list",
            "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": current.get("data", []),
        }
        # Do not overwrite the committed baseline during unit tests unless asked
        if os.environ.get("UPDATE_MODEL_SNAPSHOT", "").strip() in {"1", "true", "yes"}:
            snapshot_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

        return signals
