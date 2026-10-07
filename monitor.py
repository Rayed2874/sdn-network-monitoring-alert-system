import json
import time
from datetime import datetime

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub

from events import EventCongestion
from network_config import LINK_NAMES


POLL_INTERVAL = 2
LINK_CAPACITY_BPS = 10_000_000
MIN_PRINT_BPS = 10_000

PRINT_STATS = True

ALERT_THRESHOLD = 80.0
CLEAR_THRESHOLD = 60.0
SUSTAIN_POLLS = 2

ALERT_FILE = "alerts.jsonl"




class PortMonitor(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PortMonitor, self).__init__(*args, **kwargs)

        self.datapaths = {}
        self.previous = {}

        self.high_count = {}
        self.alerting = set()

        self.dashboard_stats = {
            "timestamp": None,
            "switches": {},
            "telemetry": {},
            "alerts": []
        }

        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            print(f"[MONITOR] Switch s{datapath.id} connected")

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            print(f"[MONITOR] Switch s{datapath.id} disconnected")

    def _monitor(self):

        while True:

            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)

            hub.sleep(POLL_INTERVAL)

    def _request_stats(self, datapath):

        parser = datapath.ofproto_parser

        req = parser.OFPPortStatsRequest(
            datapath,
            0
        )

        datapath.send_msg(req)
        flow_req = parser.OFPFlowStatsRequest(datapath=datapath)
        datapath.send_msg(flow_req) 

    @set_ev_cls(ofp_event.EventOFPPortStatsReply,
                MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id

        for stat in ev.msg.body:

            port_no = stat.port_no

            if port_no == ofproto_v1_3.OFPP_LOCAL:
                continue

            key = (dpid, port_no)

            rx_bytes = stat.rx_bytes
            tx_bytes = stat.tx_bytes

            rx_packets = stat.rx_packets
            tx_packets = stat.tx_packets

            rx_dropped = stat.rx_dropped
            tx_dropped = stat.tx_dropped

            now = time.time()

            previous = self.previous.get(key)

            self.previous[key] = (
                now,
                rx_bytes,
                tx_bytes,
                rx_packets,
                tx_packets,
                rx_dropped,
                tx_dropped
            )

            if previous is None:
                continue

            (
                prev_time,
                prev_rx,
                prev_tx,
                prev_rx_packets,
                prev_tx_packets,
                prev_rx_dropped,
                prev_tx_dropped
            ) = previous

            elapsed = now - prev_time

            rx_packet_delta = rx_packets - prev_rx_packets
            tx_packet_delta = tx_packets - prev_tx_packets

            rx_drop_delta = rx_dropped - prev_rx_dropped
            tx_drop_delta = tx_dropped - prev_tx_dropped

            packet_delta = rx_packet_delta + tx_packet_delta
            drop_delta = rx_drop_delta + tx_drop_delta

            interval_drop_rate = (
                (drop_delta / (packet_delta + drop_delta)) * 100
                if (packet_delta + drop_delta) > 0
                else 0.0
            ) 

            if elapsed <= 0:
                continue

            rx_bps = (
                (rx_bytes - prev_rx) * 8
            ) / elapsed

            tx_bps = (
                (tx_bytes - prev_tx) * 8
            ) / elapsed

            rx_util = (
                rx_bps / LINK_CAPACITY_BPS
            ) * 100

            tx_util = (
                tx_bps / LINK_CAPACITY_BPS
            ) * 100

            link_name = LINK_NAMES.get(
                key,
                f"s{dpid}:port{port_no}"
            )

            # Always update dashboard data
            self.dashboard_stats["switches"].setdefault(
                f"s{dpid}",
                {}
            )

            self.dashboard_stats["switches"][f"s{dpid}"][link_name] = {
                "rx_mbps": round(rx_bps / 1_000_000, 3),
                "tx_mbps": round(tx_bps / 1_000_000, 3),
                "rx_utilization": round(rx_util, 2),
                "tx_utilization": round(tx_util, 2),
                "rx_packets": rx_packet_delta,
                "tx_packets": tx_packet_delta,
                "dropped_packets": drop_delta,
                "drop_rate": round(interval_drop_rate, 3)
            }

            self._write_dashboard_stats()

            # Only print stats when traffic is significant
            if PRINT_STATS:
                if (
                    rx_bps >= MIN_PRINT_BPS
                    or tx_bps >= MIN_PRINT_BPS
                ):
                    print(
                        f"[STATS] {link_name} | "
                        f"RX: {rx_bps / 1_000_000:.2f} Mbps "
                        f"({rx_util:.1f}%) | "
                        f"TX: {tx_bps / 1_000_000:.2f} Mbps "
                        f"({tx_util:.1f}%) | "
                        f"Packets RX/TX: "
                        f"{rx_packet_delta}/{tx_packet_delta} | "
                        f"Drops: {drop_delta} | "
                        f"Drop Rate: "
                        f"{interval_drop_rate:.2f}%"
                    )

            self._check_congestion(
                dpid,
                port_no,
                tx_util
            )

    def _check_congestion(
        self,
        dpid,
        port_no,
        utilization
    ):

        key = (dpid, port_no)

        if utilization >= ALERT_THRESHOLD:

            self.high_count[key] = (
                self.high_count.get(key, 0) + 1
            )

            if (
                self.high_count[key] >= SUSTAIN_POLLS
                and key not in self.alerting
            ):

                self.alerting.add(key)

                self._raise_alert(
                    "CONGESTION",
                    dpid,
                    port_no,
                    utilization
                )

        elif utilization < CLEAR_THRESHOLD:

            self.high_count[key] = 0

            if key in self.alerting:

                self.alerting.remove(key)

                self._raise_alert(
                    "CLEARED",
                    dpid,
                    port_no,
                    utilization
                )

    def _raise_alert(
        self,
        alert_type,
        dpid,
        port_no,
        utilization
    ):

        link_name = LINK_NAMES.get(
            (dpid, port_no),
            f"s{dpid}:port{port_no}"
        )

        timestamp = datetime.now().isoformat()

        record = {
            "time": timestamp,
            "type": alert_type,
            "link": link_name,
            "switch": dpid,
            "port": port_no,
            "utilization": round(utilization, 2)
        }

        self.dashboard_stats["alerts"].append(record)

        # Keep only the latest 20 alerts for the dashboard
        self.dashboard_stats["alerts"] = \
            self.dashboard_stats["alerts"][-20:]

        self._write_dashboard_stats()

        print(
            f"[ALERT] {alert_type} | "
            f"{link_name} | "
            f"utilization={utilization:.1f}%"
        )

        with open(ALERT_FILE, "a") as f:
            f.write(
                json.dumps(record) + "\n"
            )

        # Send congestion information directly
        # to the controller application.
        if alert_type in ("CONGESTION", "CLEARED"):

            self.send_event("NetworkMonitor", 
                EventCongestion(
                    dpid,
                    port_no,
                    utilization
                )
            )
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        datapath = ev.msg.datapath
        dpid = datapath.id

        for stat in ev.msg.body:

            # Only monitor learned forwarding flows
            if stat.cookie != 0x1:
                continue

            flow = {
                "timestamp": time.time(),
                "dpid": dpid,
                "priority": stat.priority,
                "packet_count": stat.packet_count,
                "byte_count": stat.byte_count,
                "duration_sec": stat.duration_sec,
                "match": str(stat.match),
            }

            print(
                f"[FLOW STATS] "
                f"s{dpid} | "
                f"packets={stat.packet_count} | "
                f"bytes={stat.byte_count} | "
                f"priority={stat.priority}"
            )

            with open("flow_stats.jsonl", "a") as file:
                file.write(json.dumps(flow) + "\n")
    def _write_dashboard_stats(self):
        self.dashboard_stats["timestamp"] = time.time()

        with open("dashboard_stats.json", "w") as file:
            json.dump(
                self.dashboard_stats,
                file,
                indent=2
            )