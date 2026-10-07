#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

from topology import MonitoringTopo

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CONTROL_PORT = 8765

net = None
traffic_client = None
traffic_server = None


def ping_all():
    hosts = ["h1", "h2", "h3", "h4"]

    results = []

    for source in hosts:
        src = net.get(source)

        for destination in hosts:
            if source == destination:
                continue

            dst = net.get(destination)

            result = src.cmd(
                f"ping -c 1 -W 1 {dst.IP()}"
            )

            success = "1 packets transmitted, 1 received" in result

            results.append({
                "source": source,
                "destination": destination,
                "success": success
            })

    successful = sum(1 for item in results if item["success"])

    return {
        "message": f"Ping completed: {successful}/{len(results)} successful",
        "results": results
    }


def start_traffic():

    global traffic_client
    global traffic_server

    if traffic_client is not None and traffic_client.poll() is None:
        return {
            "message": "Traffic is already running."
        }

    h1 = net.get("h1")
    h2 = net.get("h2")

    traffic_server = h2.popen(
        ["iperf", "-s", "-u"],
        stdout=open("/tmp/iperf_server.log", "w"),
        stderr=open("/tmp/iperf_server_error.log", "w")
    )

    traffic_client = h1.popen(
        [
            "iperf",
            "-c", h2.IP(),
            "-u",
            "-b", "9M",
            "-t", "3600"
        ],
        stdout=open("/tmp/iperf_client.log", "w"),
        stderr=open("/tmp/iperf_client_error.log", "w")
    )

    return {
        "message": "UDP traffic started: h1 → h2 at approximately 9 Mbps."
    }


def stop_traffic():

    global traffic_client
    global traffic_server

    stopped = False

    if traffic_client is not None:
        if traffic_client.poll() is None:
            traffic_client.terminate()
            stopped = True

    if traffic_server is not None:
        if traffic_server.poll() is None:
            traffic_server.terminate()
            stopped = True

    traffic_client = None
    traffic_server = None

    return {
        "message": "Traffic stopped." if stopped else "No active traffic found."
    }


def link_down():

    net.configLinkStatus("s1", "s2", "down")

    return {
        "message": "Link s1 ↔ s2 is DOWN."
    }


def link_up():

    net.configLinkStatus("s1", "s2", "up")

    return {
        "message": "Link s1 ↔ s2 is UP."
    }


class ControlHandler(BaseHTTPRequestHandler):

    def send_json(self, status, data):

        body = json.dumps(data).encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def do_POST(self):

        routes = {
            "/ping-all": ping_all,
            "/traffic/start": start_traffic,
            "/traffic/stop": stop_traffic,
            "/link/down": link_down,
            "/link/up": link_up,
        }

        action = routes.get(self.path)

        if action is None:
            self.send_json(
                404,
                {"error": "Unknown control command"}
            )
            return

        try:

            result = action()

            self.send_json(
                200,
                result
            )

        except Exception as exc:

            self.send_json(
                500,
                {"error": str(exc)}
            )

    def log_message(self, format, *args):
        return


def start_control_server():

    server = ThreadingHTTPServer(
        ("127.0.0.1", CONTROL_PORT),
        ControlHandler
    )

    info(
        f"\n*** Dashboard control server listening on "
        f"127.0.0.1:{CONTROL_PORT}\n\n"
    )

    server.serve_forever()


def start_network():

    global net

    topo = MonitoringTopo()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653
    )

    net.start()

    control_thread = threading.Thread(
        target=start_control_server,
        daemon=True
    )

    control_thread.start()

    info("\n*** Network started\n")
    info("*** Ryu controller: 127.0.0.1:6653\n")
    info("*** Dashboard control: 127.0.0.1:8765\n")
    info("*** Hosts: h1 h2 h3 h4 srv\n")
    info("*** Type 'exit' to stop the network.\n\n")

    CLI(net)

    stop_traffic()
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    start_network()
