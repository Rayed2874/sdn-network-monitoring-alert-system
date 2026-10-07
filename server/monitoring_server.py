import socket
import json
import time
import os
import sys


# Server address
if len(sys.argv) >= 3:
    server_address = (sys.argv[1], int(sys.argv[2]))
else:
    server_address = ("127.0.0.1", 5000)


# Create UDP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind socket
server_socket.bind(server_address)

# Wait up to 1 second for a packet
server_socket.settimeout(1)

print(
    f"Monitoring server is waiting for telemetry "
    f"on {server_address}..."
)

# Store latest telemetry from each host
host_states = {}


def save_telemetry_state():

    state = {
        "updated": time.time(),
        "hosts": host_states
    }

    # Write to temporary file first
    temp_file = "telemetry_state.json.tmp"

    with open(temp_file, "w") as file:
        json.dump(state, file, indent=4)

    # Replace old file with completed file
    os.replace(temp_file, "telemetry_state.json")


try:

    while True:

        try:
            # Receive UDP message
            data, address = server_socket.recvfrom(4096)

        except socket.timeout:

            # Check for silent hosts
            current_time = time.time()

            for host in host_states:

                last_seen = host_states[host]["last_seen"]

                if current_time - last_seen > 5:
                    host_states[host]["status"] = "silent"

            save_telemetry_state()

            continue

        try:
            # Convert JSON data to Python dictionary
            telemetry = json.loads(data.decode())

            # Required telemetry fields
            required_fields = [
                "host",
                "seq",
                "timestamp",
                "cpu",
                "memory",
                "tx_packets",
                "rx_packets",
                "tx_bytes",
                "rx_bytes"
            ]

            # Check for missing fields
            missing_fields = [
                field for field in required_fields
                if field not in telemetry
            ]

            if missing_fields:

                print(
                    f"Invalid telemetry from {address}: "
                    f"missing fields {missing_fields}"
                )

                continue

            # Get host name
            host = telemetry["host"]

            if host:

                # Check duplicate/out-of-order sequence numbers
                if host in host_states:

                    last_seq = host_states[host]["seq"]

                    if telemetry["seq"] <= last_seq:

                        print(
                            f"Ignoring duplicate/out-of-order telemetry "
                            f"from {host}: "
                            f"seq={telemetry['seq']}, "
                            f"last_seq={last_seq}"
                        )

                        continue

                    # Detect missing sequence numbers
                    if telemetry["seq"] > last_seq + 1:

                        lost = telemetry["seq"] - last_seq - 1

                        host_states[host]["lost_datagrams"] += lost

                        print(
                            f"Detected {lost} lost datagram(s) "
                            f"from {host}"
                        )

                else:

                    # First packet from this host
                    host_states[host] = {
                        "lost_datagrams": 0,
                        "received_datagrams": 0
                    }

                # Count valid packet
                host_states[host]["received_datagrams"] += 1

                # Calculate packet loss percentage
                lost_datagrams = host_states[host]["lost_datagrams"]
                received_datagrams = host_states[host]["received_datagrams"]

                total_expected = received_datagrams + lost_datagrams

                if total_expected > 0:

                    loss_pct = (
                        lost_datagrams / total_expected
                    ) * 100

                else:

                    loss_pct = 0

                # Store latest telemetry
                host_states[host].update(telemetry)

                # Store packet-loss information
                host_states[host]["lost_datagrams"] = lost_datagrams
                host_states[host]["loss_pct"] = round(loss_pct, 2)

                # Mark host as online
                host_states[host]["status"] = "online"

                # Update last seen time
                host_states[host]["last_seen"] = time.time()

                # Save telemetry state
                save_telemetry_state()

                # Display received telemetry
                print(f"Received telemetry from {host}:")
                print(host_states[host])

                print("Current host states:")
                print(host_states)

        except json.JSONDecodeError:

            print("Received invalid JSON data.")

except KeyboardInterrupt:

    print("\nMonitoring server stopped.")

finally:

    server_socket.close()