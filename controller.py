from events import EventCongestion
from network_config import HOST_PORTS
from ryu.base import app_manager
import json
import time
from datetime import datetime
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.topology import event
from ryu.topology.api import get_switch, get_link
import networkx as nx

# Label put on every forwarding rule the controller learns.
# It lets us delete exactly these rules later (and nothing else).
LEARNED_FLOW_COOKIE = 0x1

# Congestion handling settings
REROUTE_HOLDDOWN = 20    # minimum seconds between congestion reroutes
CONGESTION_MEMORY = 30   # seconds a congested link keeps being avoided


class NetworkMonitor(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkMonitor, self).__init__(*args, **kwargs)
        self.mac_to_port = {}          # MAC -> (switch ID, port)
        self.net = nx.DiGraph()        # switch topology
        self.broadcast_ports = {}      # spanning-tree ports per switch
        self.datapaths = {}            # switch ID -> connected switch
        self.have_learned_flows = False  # True once we installed learned rules
        self.congested_links = {}      # physical link -> time it was marked
        self.last_reroute = 0.0        # time of the last congestion reroute

    @set_ev_cls(EventCongestion)
    def congestion_handler(self, ev):

        # Find which neighboring switch is behind the congested port.
        neighbor = None

        if ev.dpid in self.net:
            for next_switch in self.net.successors(ev.dpid):
                port = self.net[ev.dpid][next_switch].get("port")
                if port == ev.port:
                    neighbor = next_switch
                    break

        # Host-facing ports cannot be rerouted.
        if neighbor is None:
            print(
                f"[CONGESTION EVENT] "
                f"s{ev.dpid} port {ev.port} "
                f"utilization={ev.utilization:.1f}% "
                f"(host-facing link)"
            )
            return

        link = frozenset((ev.dpid, neighbor))
        now = time.time()

        if ev.utilization >= 80.0:

            already_known = (
                link in self.congested_links
                and now - self.congested_links[link] <= CONGESTION_MEMORY
            )

            # (Re)start the memory timer for this link.
            self.congested_links[link] = now

            if already_known:
                return

            print(
                f"[CONGESTED LINK] "
                f"s{ev.dpid}<->s{neighbor} "
                f"utilization={ev.utilization:.1f}%"
            )

            since = now - self.last_reroute
            if since < REROUTE_HOLDDOWN:
                print(
                    f"[REROUTE] hold-down active "
                    f"({since:.0f} s since last reroute) - keeping current paths"
                )
                return

            # Existing learned flows may still use the congested link,
            # so remove them and let traffic be routed again.
            if self.have_learned_flows:
                self.last_reroute = now
                self.flush_learned_flows()

        elif ev.utilization < 60.0:

            # The link stays "avoided" until its memory time runs out.
            print(
                f"[CONGESTION CLEARED] "
                f"s{ev.dpid}<->s{neighbor} "
                f"utilization={ev.utilization:.1f}%"
            )

    # ---------------- Switch connection ----------------

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        print(f"Switch connected: {datapath.id}")

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]
        self.add_flow(datapath, 0, match, actions)

    # Keep track of which switches are connected
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    # ---------------- Topology discovery ----------------

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        self.update_topology()

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):
        # The LINK_UP alert is printed and saved by link_alerts.py.
        self.update_topology()

        # A new or returning link may offer a better path, so remove the old
        # rules and let traffic be routed again on the full topology.
        # (Skipped at startup, when no learned rules exist yet.)
        if self.have_learned_flows:
            self.flush_learned_flows()

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):
        # The LINK_DOWN alert itself is printed and saved by link_alerts.py.
        # Here we update the topology and remove rules that may now be stale.
        self.update_topology()
        self.flush_learned_flows()

    def update_topology(self):
        switches = get_switch(self, None)
        links = get_link(self, None)

        self.net.clear()

        for switch in switches:
            self.net.add_node(switch.dp.id)

        for link in links:
            self.net.add_edge(
                link.src.dpid,
                link.dst.dpid,
                port=link.src.port_no
            )

        # FIX 2: only use links that are known in BOTH directions
        undirected = nx.Graph()
        undirected.add_nodes_from(self.net.nodes)
        for u, v in self.net.edges():
            if self.net.has_edge(v, u):
                undirected.add_edge(u, v)

        tree = nx.minimum_spanning_tree(undirected)

        self.broadcast_ports.clear()
        for u, v in tree.edges():
            self.broadcast_ports.setdefault(u, []).append(self.net[u][v]['port'])
            self.broadcast_ports.setdefault(v, []).append(self.net[v][u]['port'])

        print("\nCurrent topology:")
        for src, dst, data in self.net.edges(data=True):
            print(f"  s{src} -> s{dst} (port {data['port']})")

        print("Broadcast tree:")
        for switch, ports in sorted(self.broadcast_ports.items()):
            print(f"  s{switch}: ports {ports}")

    # ---------------- Stale flow cleanup ----------------

    def flush_learned_flows(self):
        # Delete every rule carrying LEARNED_FLOW_COOKIE on every switch.
        # The "send to controller" rule and Ryu's own discovery rule have a
        # different cookie, so they are not touched.
        count = 0

        for dp in list(self.datapaths.values()):
            ofproto = dp.ofproto
            parser = dp.ofproto_parser

            mod = parser.OFPFlowMod(
                datapath=dp,
                cookie=LEARNED_FLOW_COOKIE,
                cookie_mask=0xFFFFFFFFFFFFFFFF,
                command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                match=parser.OFPMatch()
            )
            dp.send_msg(mod)
            count += 1

        self.have_learned_flows = False
        print(f"[CLEANUP] Deleted learned flows on {count} switches")
    
    def get_routing_path(self, src_dpid, dst_dpid):

        # Make a copy so the discovered topology is not modified.
        routing_graph = self.net.copy()
        now = time.time()

        # Remove links that are (recently) congested, in both directions.
        for link, marked_at in list(self.congested_links.items()):

            if now - marked_at > CONGESTION_MEMORY:
                continue

            switches = list(link)
            if len(switches) != 2:
                continue

            a, b = switches

            if routing_graph.has_edge(a, b):
                routing_graph.remove_edge(a, b)

            if routing_graph.has_edge(b, a):
                routing_graph.remove_edge(b, a)

        try:
            return nx.shortest_path(routing_graph, src_dpid, dst_dpid)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Every route is congested: use the full topology
            # instead of dropping the traffic.
            return nx.shortest_path(self.net, src_dpid, dst_dpid)

    # ---------------- Packet handling ----------------

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        src = eth.src
        dst = eth.dst

        # Ignore LLDP and IPv6 multicast
        if dst.startswith("01:80:c2"):
            return
        if dst.startswith("33:33"):
            return

        # FIX 1: learn a host's location ONLY on host-facing ports
        if in_port in self.host_ports(dpid):
            self.mac_to_port[src] = (dpid, in_port)

        print(f"Packet: {src} -> {dst} at s{dpid}, port {in_port}")

        # Broadcast / ARP
        if dst == "ff:ff:ff:ff:ff:ff":
            self.broadcast_packet(datapath, msg, in_port)
            return

        # Unknown destination
        if dst not in self.mac_to_port:
            print(f"Unknown destination {dst}, using broadcast tree")
            self.broadcast_packet(datapath, msg, in_port)
            return

        # Known destination
        dst_dpid, dst_port = self.mac_to_port[dst]

        if dpid == dst_dpid:
            out_port = dst_port
        else:
            try:
                path = self.get_routing_path(dpid, dst_dpid)
                print("Path:", " -> ".join(f"s{x}" for x in path))
                next_switch = path[1]
                out_port = self.net[dpid][next_switch]['port']
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                print(f"No path from s{dpid} to s{dst_dpid}")
                return

        actions = [parser.OFPActionOutput(out_port)]

        match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
        self.add_flow(datapath, 10, match, actions,
                      cookie=LEARNED_FLOW_COOKIE)
        self.have_learned_flows = True

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)

    # ---------------- Broadcast forwarding ----------------

    def broadcast_packet(self, datapath, msg, in_port):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        dpid = datapath.id

        ports = []

        for port in self.broadcast_ports.get(dpid, []):
            if port != in_port:
                ports.append(port)

        for port in self.host_ports(dpid):
            if port != in_port:
                ports.append(port)

        ports = list(set(ports))

        # FIX 3: debug print
        print(f"  s{dpid}: broadcast out ports {ports} (arrived on {in_port})")

        if not ports:
            return

        actions = [parser.OFPActionOutput(p) for p in ports]

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)

    # ---------------- Host-facing ports ----------------

    def host_ports(self, dpid):
        return list(HOST_PORTS.get(dpid, []))

    # ---------------- Install flow ----------------

    def add_flow(self, datapath, priority, match, actions, cookie=0):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            cookie=cookie,
            priority=priority,
            match=match,
            instructions=instructions
        )
        datapath.send_msg(mod)
