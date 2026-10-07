"""
Actual performance measurement helpers.

No benchmark values are fabricated here. Measurements are collected from the
machine/Mininet experiment and written to CSV for later comparison.
"""

from __future__ import annotations

import csv
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone


@dataclass
class Measurement:
    scenario: str
    routing: str
    timestamp: str
    latency_ms: float | None = None
    throughput_mbps: float | None = None
    packet_loss_pct: float | None = None
    utilization_pct: float | None = None
    detection_time_ms: float | None = None
    recovery_time_ms: float | None = None


def ping_host(host: str, count: int = 5, timeout: int = 2) -> tuple[float | None, float | None]:
    """Return (average_latency_ms, packet_loss_pct). Uses system ping."""
    if count < 1:
        raise ValueError("count must be >= 1")

    command = ["ping", "-c", str(count), "-W", str(timeout), host]
    # Windows fallback
    if __import__("platform").system().lower().startswith("win"):
        command = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]

    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=count * (timeout + 2))
    except (OSError, subprocess.TimeoutExpired):
        return None, None

    output = completed.stdout + "\n" + completed.stderr

    loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*(?:packet )?loss", output, re.I)
    latency_match = re.search(r"(?:=\s*[\d.]+\s*/\s*[\d.]+\s*/\s*[\d.]+\s*/|Average\s*=\s*)([\d.]+)", output, re.I)

    loss = float(loss_match.group(1)) if loss_match else None
    latency = float(latency_match.group(1)) if latency_match else None
    return latency, loss


def append_measurement(csv_file: str | Path, measurement: Measurement):
    path = Path(csv_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(measurement)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def make_measurement(
    scenario: str,
    routing: str,
    latency_ms: float | None = None,
    throughput_mbps: float | None = None,
    packet_loss_pct: float | None = None,
    utilization_pct: float | None = None,
    detection_time_ms: float | None = None,
    recovery_time_ms: float | None = None,
) -> Measurement:
    return Measurement(
        scenario=scenario,
        routing=routing,
        timestamp=datetime.now(timezone.utc).isoformat(),
        latency_ms=latency_ms,
        throughput_mbps=throughput_mbps,
        packet_loss_pct=packet_loss_pct,
        utilization_pct=utilization_pct,
        detection_time_ms=detection_time_ms,
        recovery_time_ms=recovery_time_ms,
    )
