from monitoring.telemetry_store import TelemetryStore, UDPReceiver


OUTPUT_FILE = "/home/rayed/sdn-person3-monitoring/data/udp_telemetry.jsonl"

store = TelemetryStore(OUTPUT_FILE)

receiver = UDPReceiver(
    store,
    host="0.0.0.0",
    port=9999
)

print("UDP telemetry receiver listening on 0.0.0.0:9999")

try:
    receiver.serve_forever()
except KeyboardInterrupt:
    receiver.stop()
    print("\nUDP receiver stopped.")