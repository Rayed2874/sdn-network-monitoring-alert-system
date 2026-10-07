import socket
import time
import sys 

from telemetry.protocol import create_telemetry
from telemetry import metrics


if len(sys.argv) >= 4:
    host_name = sys.argv[3]
else:
    host_name = "h1"

# Create UDP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

if len(sys.argv) >= 3:
    server_address = (sys.argv[1], int(sys.argv[2]))
else:
    server_address = ("127.0.0.1", 5000)

# Send telemetry continuously
seq = 1

while True:

    # Get real system metrics
    cpu = metrics.get_cpu_usage()
    memory = metrics.get_memory_usage()
    network = metrics.get_network_stats()

    # Create telemetry JSON
    telemetry = create_telemetry(
        host_name,
        seq,
        time.time(),
        cpu,
        memory,
        network["tx_packets"],
        network["rx_packets"],
        network["tx_bytes"],
        network["rx_bytes"]
    )

    # Send telemetry to server
    client_socket.sendto(telemetry.encode(), server_address)

    print(f"Sent: {telemetry}")

    time.sleep(1)
    seq += 1

# Close socket
client_socket.close()

print("Client finished.")