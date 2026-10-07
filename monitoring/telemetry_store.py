"""
UDP JSON telemetry receiver for Person 1's telemetry stream.

The receiver accepts JSON datagrams and stores them as JSONL. It intentionally
uses tolerant field aliases so it can be adapted to the team's telemetry
format without changing the core dashboard.
"""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable


def normalize_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    def first(*keys):
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    result = dict(payload)
    result["timestamp"] = first("timestamp", "time") or datetime.now(timezone.utc).isoformat()
    result["device"] = first("device", "switch", "dpid", "host") or "unknown"
    result["latency_ms"] = first("latency_ms", "latency")
    result["packet_loss_pct"] = first("packet_loss_pct", "packet_loss", "loss_pct")
    result["throughput_mbps"] = first("throughput_mbps", "throughput", "mbps")
    return result


class TelemetryStore:
    def __init__(self, output_file: str | Path = "data/udp_telemetry.jsonl"):
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.latest: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = normalize_telemetry(payload)
        with self._lock:
            with self.output_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(item, separators=(",", ":")) + "\n")
            self.latest[str(item["device"])] = item
        return item

    def latest_values(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.latest.values())


class UDPReceiver:
    def __init__(
        self,
        store: TelemetryStore,
        host: str = "0.0.0.0",
        port: int = 9999,
        on_message: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.store = store
        self.host = host
        self.port = port
        self.on_message = on_message
        self._stop = threading.Event()

    def serve_forever(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))
        try:
            while not self._stop.is_set():
                try:
                    raw, _addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, dict):
                        continue
                    item = self.store.add(payload)
                    if self.on_message:
                        self.on_message(item)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
        finally:
            sock.close()

    def stop(self):
        self._stop.set()
