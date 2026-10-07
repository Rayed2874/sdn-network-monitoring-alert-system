import json


def create_telemetry(host, seq, timestamp, cpu, memory,
                     tx_packets, rx_packets, tx_bytes, rx_bytes):

    telemetry = {
        "host": host,
        "seq": seq,
        "timestamp": timestamp,
        "cpu": cpu,
        "memory": memory,
        "tx_packets": tx_packets,
        "rx_packets": rx_packets,
        "tx_bytes": tx_bytes,
        "rx_bytes": rx_bytes
    }

    return json.dumps(telemetry)