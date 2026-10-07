"""
Read-only adapter for the existing Ryu project's JSON/JSONL outputs.

Expected files (paths are configurable):
  dashboard_stats.json
  alerts.jsonl
  flow_stats.jsonl
"""

from pathlib import Path
import json
from typing import Any


class RyuAdapter:
    def __init__(self, project_dir: str | Path = "."):
        self.project_dir = Path(project_dir)

    def _path(self, filename: str) -> Path:
        return self.project_dir / filename

    def _read_json(self, filename: str) -> dict[str, Any]:
        path = self._path(filename)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _read_jsonl(self, filename: str) -> list[dict[str, Any]]:
        path = self._path(filename)
        if not path.exists():
            return []
        rows = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            rows.append(value)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return rows

    def dashboard(self) -> dict[str, Any]:
        return self._read_json("dashboard_stats.json")

    def alerts(self) -> list[dict[str, Any]]:
        return self._read_jsonl("alerts.jsonl")

    def flow_stats(self) -> list[dict[str, Any]]:
        return self._read_jsonl("flow_stats.jsonl")

    def summary(self) -> dict[str, Any]:
        dashboard = self.dashboard()
        alerts = self.alerts()
        flows = self.flow_stats()
        return {
            "dashboard": dashboard,
            "alert_count": len(alerts),
            "flow_record_count": len(flows),
            "alerts": alerts[-20:],
            "flows": flows[-50:],
        }
