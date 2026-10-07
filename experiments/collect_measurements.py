"""
Minimal experiment helper.

Run this from the project root after starting Mininet/Ryu. It performs a real
ping and writes the measured latency/loss. Throughput, utilization, detection
and recovery times should be filled from the actual experiment outputs.
"""

import argparse

from monitoring.performance import append_measurement, make_measurement, ping_host


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="Mininet host IP/name to ping")
    parser.add_argument("--routing", choices=["static", "dynamic"], required=True)
    parser.add_argument("--scenario", default="baseline")
    parser.add_argument("--output", default="experiments/results/measurements.csv")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    latency, loss = ping_host(args.host, args.count)
    measurement = make_measurement(
        scenario=args.scenario,
        routing=args.routing,
        latency_ms=latency,
        packet_loss_pct=loss,
    )
    append_measurement(args.output, measurement)
    print(measurement)


if __name__ == "__main__":
    main()
