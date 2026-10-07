import json
import time
from datetime import datetime

from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.topology import event
from ryu.topology.api import get_switch

ALERT_FILE = "alerts.jsonl"      # same file used by monitor.py


class LinkAlerts(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(LinkAlerts, self).__init__(*args, **kwargs)
        # Links currently down: link key -> time it went down
        self.down_links = {}

    @staticmethod
    def _link_key(link):
        # A physical link shows up as two directed links (s1->s3 and s3->s1).
        # Sorting the two ends makes both directions produce the same key.
        a = (link.src.dpid, link.src.port_no)
        b = (link.dst.dpid, link.dst.port_no)
        return tuple(sorted([a, b]))

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):
        key = self._link_key(ev.link)
        (sw_a, port_a), (sw_b, port_b) = key

        # Ignore events caused by a switch disconnecting (e.g. Mininet exiting)
        connected = {sw.dp.id for sw in get_switch(self, None)}
        if sw_a not in connected or sw_b not in connected:
            return

        # Second direction of the same failure -> already reported
        if key in self.down_links:
            return

        self.down_links[key] = time.time()
        self._raise_alert("LINK_DOWN", sw_a, port_a, sw_b, port_b)

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):
        key = self._link_key(ev.link)
        (sw_a, port_a), (sw_b, port_b) = key

        # Only links that were down can come "back up". This also ignores the
        # normal link discovery at startup and the second direction of a link.
        went_down_at = self.down_links.pop(key, None)
        if went_down_at is None:
            return

        downtime = round(time.time() - went_down_at, 1)
        self._raise_alert("LINK_UP", sw_a, port_a, sw_b, port_b,
                          downtime_s=downtime)

    def _raise_alert(self, alert_type, sw_a, port_a, sw_b, port_b,
                     downtime_s=None):
        link = f"s{sw_a}<->s{sw_b}"

        extra = ""
        if downtime_s is not None:
            extra = f" - was down for {downtime_s} s"

        print(
            f"\n[ALERT] {alert_type} on {link} "
            f"(s{sw_a} port {port_a} <-> s{sw_b} port {port_b}){extra}\n"
        )

        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "type": alert_type,
            "link": link,
            "switch": sw_a,
            "port": port_a,
            "peer_switch": sw_b,
            "peer_port": port_b,
        }

        if downtime_s is not None:
            record["downtime_s"] = downtime_s

        with open(ALERT_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
