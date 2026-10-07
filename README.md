# SDN Person 3 — Monitoring, Anomaly Detection, Dashboard & Performance

This repository contains **Person 3's work** for the SDN network-monitoring
project.

## Responsibilities

- Correlate UDP telemetry with SDN/OpenFlow statistics.
- Detect high utilization, latency and packet-loss conditions.
- Flag combined conditions as possible network congestion.
- Provide a dashboard for network status and recent monitoring data.
- Collect real Mininet performance measurements.
- Support static-vs-dynamic routing comparison without fabricating results.

## Python version

Use **Python 3.12**.

## Architecture

```text
Person 1 UDP telemetry
        |
        v
monitoring/telemetry_store.py
        |
        +--------------------+
                             |
Ryu/OpenFlow statistics ---> monitoring/ryu_adapter.py
                             |
                             v
                    anomaly_detector.py
                             |
                             v
                      Dashboard (Flask)
                             |
                             v
                 experiments/results/*.csv
```

The existing Ryu controller remains responsible for controller decisions,
OpenFlow rules and rerouting. This repository is a monitoring/analytics layer;
it does not replace the controller.

## Thresholds

Default thresholds in `AnomalyDetector`:

| Metric | Warning | Critical |
|---|---:|---:|
| Utilization | >= 80% | >= 90% |
| Latency | >= 100 ms | >= 250 ms |
| Packet loss | >= 2% | >= 5% |

When at least two abnormal indicators are present, the detector also reports
`NETWORK_CONGESTION`.

These are analytics thresholds and can be adjusted for the team's experiment.

## Ryu integration

The adapter reads these files from the main Ryu project directory:

- `dashboard_stats.json`
- `alerts.jsonl`
- `flow_stats.jsonl`

If your team uses different paths or field names, update `RyuAdapter` or the
normalization layer rather than changing the Ryu controller logic.

## UDP telemetry

The receiver accepts JSON UDP datagrams on port `9999` by default.

Example payload:

```json
{
  "device": "s1",
  "latency_ms": 120,
  "packet_loss_pct": 3.5,
  "throughput_mbps": 42.0
}
```

The telemetry store writes records to `data/udp_telemetry.jsonl`.

## Start the dashboard

From the repository root:

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python dashboard/app.py
```

Linux/macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python dashboard/app.py
```

Open:

```text
http://127.0.0.1:5000
```

The dashboard can run even before Ryu/telemetry data exists; it will show empty
states until the real files/data arrive.

## Performance experiments

Do not put invented numbers into the results.

Example real measurement:

```bash
python experiments/collect_measurements.py \
  --host 10.0.0.2 \
  --routing static \
  --scenario baseline
```

Then repeat the same experiment using:

```bash
python experiments/collect_measurements.py \
  --host 10.0.0.2 \
  --routing dynamic \
  --scenario baseline
```

Throughput, utilization, anomaly-detection time and recovery time should be
recorded from the actual Mininet/Ryu experiment and added to the CSV.

## GitHub workflow

This repository is currently intended as Person 3's individual repository.
After the code is reviewed, the `person3/` directory can be copied/merged into
the team's main SDN repository without replacing the controller code.
