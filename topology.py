from mininet.topo import Topo


class MonitoringTopo(Topo):

    def build(self):
        # Hosts: h1-h4 run telemetry agents, srv runs the monitoring server
        h1 = self.addHost('h1', ip='10.0.0.1/8')
        h2 = self.addHost('h2', ip='10.0.0.2/8')
        h3 = self.addHost('h3', ip='10.0.0.3/8')
        h4 = self.addHost('h4', ip='10.0.0.4/8')
        srv = self.addHost('srv', ip='10.0.0.100/8')

        # Switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        # Host links (switch ports are fixed on purpose)
        self.addLink(h1, s1, port2=1, bw=10)
        self.addLink(h3, s1, port2=4, bw=10)
        self.addLink(h2, s4, port2=1, bw=10)
        self.addLink(h4, s4, port2=4, bw=10)
        self.addLink(srv, s4, port2=5, bw=10)

        # Path 1: s1 - s2 - s4
        self.addLink(s1, s2, port1=2, port2=1, bw=10)
        self.addLink(s2, s4, port1=2, port2=2, bw=10)

        # Path 2: s1 - s3 - s4
        self.addLink(s1, s3, port1=3, port2=1, bw=10)
        self.addLink(s3, s4, port1=2, port2=3, bw=10)


topos = {
    'monitoring': lambda: MonitoringTopo()
}
