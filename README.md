# SDN Network Monitoring and Alert System

An SDN-based network monitoring system that combines **Mininet, Ryu, OpenFlow, UDP telemetry, network monitoring, and a Flask dashboard** to detect network failures and congestion, generate alerts, collect statistics, and automatically reroute traffic.

## Features

- Real-time network monitoring
- UDP-based host telemetry
- Link failure and recovery detection
- Congestion detection
- Automatic traffic rerouting
- Flow and port statistics
- Packet/drop monitoring
- Real-time alerts
- Web-based monitoring dashboard
- Mininet network control through an API

## System Architecture

```text
                  +------------------+
                  |    Dashboard     |
                  |    Flask + Web   |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Monitoring Layer |
                  | Alerts + Metrics |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  |  Ryu Controller  |
                  |  OpenFlow 1.3    |
                  +--------+---------+
                           |
                           v
              +--------------------------+
              |         Mininet          |
              |                          |
              |        s1                |
              |       /  \               |
              |     s2    s3             |
              |       \  /               |
              |        s4                |
              +--------------------------+
```

## Network Topology

```text
                 h1
                  |
                  s1
                /    \
               s2     s3
                \     /
                  s4
                / | \
               h2 h4 srv
```

### Hosts

| Host | IP Address |
|------|------------|
| h1 | 10.0.0.1 |
| h2 | 10.0.0.2 |
| h3 | 10.0.0.3 |
| h4 | 10.0.0.4 |
| srv | 10.0.0.100 |

The topology provides two paths:

```text
Primary:  s1 -> s2 -> s4
Backup:   s1 -> s3 -> s4
```

This redundancy allows traffic to be rerouted when a link fails.

## Technology Stack

- **Mininet** - Network emulation
- **Ryu** - SDN controller
- **OpenFlow 1.3** - Controller-switch communication
- **Open vSwitch** - Virtual switches
- **Python** - Controller, monitoring and automation
- **UDP** - Telemetry and traffic generation
- **Flask** - Web dashboard
- **NetworkX** - Dynamic path calculation
- **Git/GitHub** - Version control

## Project Components

### 1. UDP Telemetry

The telemetry component collects host-level information and sends it to a monitoring server using UDP.

```text
Mininet Host
     |
     | UDP Telemetry
     v
Telemetry Receiver
     |
     v
Monitoring Data
     |
     v
Dashboard
```

### 2. SDN Controller

The Ryu controller communicates with the Mininet Open vSwitch instances using OpenFlow 1.3.

It is responsible for:

- Network topology discovery
- Routing
- Flow installation
- Link failure detection
- Link recovery
- Dynamic rerouting

### 3. Monitoring and Dashboard

The monitoring layer collects:

- Port statistics
- Flow statistics
- Packet counts
- Byte counts
- Dropped packets
- Link utilization
- UDP telemetry

The Flask dashboard presents this information in a human-readable interface.

## Project Structure

```text
sdn-network-monitoring-alert-system/
|
├── controller.py
├── monitor.py
├── link_alerts.py
├── topology.py
├── mininet_control.py
|
├── telemetry/
│   └── agent.py
|
├── monitoring/
│   ├── anomaly_detector.py
│   └── run_udp_receiver.py
|
├── dashboard/
│   ├── app.py
│   ├── templates/
│   └── static/
|
├── experiments/
|
├── requirements.txt
├── README.md
└── .gitignore
```

Runtime-generated logs, telemetry files, and virtual environments are excluded from version control.

## Installation

Clone the repository:

```bash
git clone https://github.com/Rayed2874/sdn-network-monitoring-alert-system.git
cd sdn-network-monitoring-alert-system
```

Install the required system packages:

```bash
sudo apt update
sudo apt install mininet openvswitch-switch python3-pip python3-venv iperf
```

Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Running the System

### Step 1: Start the Ryu Controller

```bash
source .venv/bin/activate
ryu-manager --observe-links controller.py monitor.py link_alerts.py
```

The controller uses OpenFlow 1.3 and listens on port `6653`.

### Step 2: Start Mininet

Open another terminal:

```bash
cd ~/sdn-network-monitoring-alert-system
sudo python3 mininet_control.py
```

The Mininet control API runs on:

```text
127.0.0.1:8765
```

### Step 3: Start the Dashboard

Open another terminal:

```bash
cd ~/sdn-network-monitoring-alert-system
source .venv/bin/activate
python3 -m dashboard.app
```

Open the dashboard at:

```text
http://127.0.0.1:5000
```

## Mininet Control API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/ping-all` | Test connectivity |
| POST | `/traffic/start` | Start UDP traffic |
| POST | `/traffic/stop` | Stop UDP traffic |
| POST | `/link/down` | Simulate link failure |
| POST | `/link/up` | Restore link |

## Testing

### Connectivity Test

```bash
curl -X POST http://127.0.0.1:8765/ping-all
```

A successful test produces output similar to:

```text
Ping completed: 12/12 successful
```

### Generate Traffic

```bash
curl -X POST http://127.0.0.1:8765/traffic/start
```

Stop traffic:

```bash
curl -X POST http://127.0.0.1:8765/traffic/stop
```

Traffic generation is used to test utilization, congestion detection, flow statistics, and rerouting.

## Link Failure and Automatic Rerouting

The project contains redundant paths so that traffic can be rerouted when a link fails.

Normal path:

```text
h1 -> s1 -> s2 -> s4 -> h2
```

After the `s1-s2` path becomes unavailable:

```text
h1 -> s1 -> s3 -> s4 -> h2
```

The controller:

1. Detects the topology change.
2. Updates its topology information.
3. Calculates an available path.
4. Installs the required forwarding rules.
5. Redirects traffic through the alternate path.

The system has been tested with link failure, automatic rerouting, link recovery, and restored connectivity.

## Congestion Monitoring

The monitoring system checks switch port utilization and generates congestion alerts when utilization remains above the configured threshold.

Current monitoring configuration:

```text
Link capacity:      10 Mbps
Alert threshold:    80%
Clear threshold:    60%
Sustain polls:      2
```

Example:

```text
Traffic = 9.6 Mbps
Capacity = 10 Mbps

Utilization ≈ 96%
```

This can trigger a congestion alert.

## Alerts

The system supports:

```text
LINK_DOWN
LINK_UP
CONGESTION
CONGESTION_CLEARED
```

Example:

```json
{
  "time": "2026-10-01T11:11:40",
  "type": "CONGESTION",
  "link": "s4->h2",
  "switch": 4,
  "port": 1,
  "utilization": 96.4
}
```

## Monitoring Data

The system can generate runtime data such as:

```text
alerts.jsonl
flow_stats.jsonl
combined_monitoring.jsonl
udp_telemetry.jsonl
dashboard_stats.json
```

These files are generated during execution and are excluded from Git.

## Dashboard

The dashboard provides a single interface for monitoring and controlling the network.

It displays:

- Number of hosts
- Online hosts
- Active alerts
- Maximum utilization
- Link utilization
- Recent alerts
- UDP telemetry
- Flow statistics
- Packet statistics

It also provides controls for:

- Ping All
- Generate Traffic
- Stop Traffic
- Link Down
- Link Up

## Verification

The following functionality has been tested:

- Mininet topology startup
- Ryu controller connection
- OpenFlow 1.3 communication
- Host connectivity
- UDP traffic generation
- Link-down detection
- Link-up detection
- Congestion monitoring
- Alert generation
- Flow statistics collection
- UDP telemetry
- Dashboard monitoring
- Dashboard controls
- Automatic rerouting after link failure
- Connectivity recovery after link restoration

## Team Contributions

### Person 1 - UDP Telemetry

- UDP telemetry agent
- Host telemetry collection
- UDP receiver
- Telemetry data handling

### Person 2 - SDN / Mininet / Ryu

- Mininet topology
- Ryu SDN controller
- OpenFlow communication
- Routing
- Link failure and recovery
- Automatic rerouting
- Mininet control API
- Traffic generation

### Person 3 - Monitoring / Dashboard

- Network monitoring
- Port and flow statistics
- Congestion detection
- Alert generation
- Dashboard
- Monitoring analytics

## Future Improvements

- Machine-learning-based anomaly detection
- Historical monitoring graphs
- Database-backed storage
- Authentication and access control
- Larger network topologies
- QoS-aware routing
- Advanced traffic prediction
- Production SDN switch support

## Repository

**GitHub:**  
https://github.com/Rayed2874/sdn-network-monitoring-alert-system

## Conclusion

This project demonstrates how SDN can be used to build an automated network monitoring system. Mininet provides the network environment, Ryu provides centralized control and routing, UDP provides host telemetry, and the monitoring/dashboard layer provides visibility into network health.

The system can detect link failures and congestion, generate alerts, collect network statistics, and automatically reroute traffic when a network path becomes unavailable.
