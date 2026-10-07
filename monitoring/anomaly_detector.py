"""
Person 3 anomaly/correlation layer.

This module analyzes Ryu/OpenFlow statistics and UDP telemetry. It does NOT
perform controller rerouting; controller actions remain the responsibility of
the Ryu application.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Anomaly:
    timestamp: str
    device: str
    severity: str
    anomaly_type: str
    message: str
    utilization_pct: float | None = None
    latency_ms: float | None = None
    packet_loss_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AnomalyDetector:
    def __init__(
        self,
        utilization_warning: float = 80.0,
        utilization_critical: float = 90.0,
        latency_warning_ms: float = 100.0,
        latency_critical_ms: float = 250.0,
        loss_warning_pct: float = 2.0,
        loss_critical_pct: float = 5.0,
    ):
        self.utilization_warning = utilization_warning
        self.utilization_critical = utilization_critical
        self.latency_warning_ms = latency_warning_ms
        self.latency_critical_ms = latency_critical_ms
        self.loss_warning_pct = loss_warning_pct
        self.loss_critical_pct = loss_critical_pct

    @staticmethod
    def _num(data: dict, *keys: str) -> float | None:
        for key in keys:
            value = data.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        return None

    def analyze(self, data: dict[str, Any]) -> list[Anomaly]:
        now = datetime.now(timezone.utc).isoformat()
        device = str(data.get("device") or data.get("dpid") or data.get("switch") or "unknown")

        util = self._num(data, "utilization_pct", "utilization", "util_pct")
        latency = self._num(data, "latency_ms", "latency")
        loss = self._num(data, "packet_loss_pct", "packet_loss", "loss_pct")

        anomalies: list[Anomaly] = []

        if util is not None:
            if util >= self.utilization_critical:
                anomalies.append(Anomaly(
                    now, device, "CRITICAL", "HIGH_UTILIZATION",
                    f"Utilization is {util:.1f}% (critical threshold {self.utilization_critical:.1f}%).",
                    util, latency, loss))
            elif util >= self.utilization_warning:
                anomalies.append(Anomaly(
                    now, device, "WARNING", "HIGH_UTILIZATION",
                    f"Utilization is {util:.1f}% (warning threshold {self.utilization_warning:.1f}%).",
                    util, latency, loss))

        if latency is not None:
            if latency >= self.latency_critical_ms:
                anomalies.append(Anomaly(
                    now, device, "CRITICAL", "HIGH_LATENCY",
                    f"Latency is {latency:.1f} ms.",
                    util, latency, loss))
            elif latency >= self.latency_warning_ms:
                anomalies.append(Anomaly(
                    now, device, "WARNING", "HIGH_LATENCY",
                    f"Latency is {latency:.1f} ms.",
                    util, latency, loss))

        if loss is not None:
            if loss >= self.loss_critical_pct:
                anomalies.append(Anomaly(
                    now, device, "CRITICAL", "PACKET_LOSS",
                    f"Packet loss is {loss:.1f}%.",
                    util, latency, loss))
            elif loss >= self.loss_warning_pct:
                anomalies.append(Anomaly(
                    now, device, "WARNING", "PACKET_LOSS",
                    f"Packet loss is {loss:.1f}%.",
                    util, latency, loss))

        abnormal_count = sum(
            value is not None and threshold
            for value, threshold in (
                (util, util is not None and util >= self.utilization_warning),
                (latency, latency is not None and latency >= self.latency_warning_ms),
                (loss, loss is not None and loss >= self.loss_warning_pct),
            )
        )
        if abnormal_count >= 2:
            anomalies.append(Anomaly(
                now, device, "CRITICAL", "NETWORK_CONGESTION",
                "Multiple abnormal indicators suggest network congestion.",
                util, latency, loss))

        return anomalies
