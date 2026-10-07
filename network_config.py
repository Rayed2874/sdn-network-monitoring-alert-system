# Shared description of the fixed network (used by controller.py and monitor.py)

# Switch ports that face hosts: switch id -> ports
HOST_PORTS = {
    1: [1, 4],       # h1, h3
    4: [1, 4, 5],    # h2, h4, srv
}

# host -> (switch, port, ip)
HOSTS = {
    "h1": (1, 1, "10.0.0.1"),
    "h2": (4, 1, "10.0.0.2"),
    "h3": (1, 4, "10.0.0.3"),
    "h4": (4, 4, "10.0.0.4"),
    "srv": (4, 5, "10.0.0.100"),
}

# (switch, port) -> what that port connects to
LINK_NAMES = {
    (1, 1): "s1->h1", (1, 2): "s1->s2", (1, 3): "s1->s3", (1, 4): "s1->h3",
    (2, 1): "s2->s1", (2, 2): "s2->s4",
    (3, 1): "s3->s1", (3, 2): "s3->s4",
    (4, 1): "s4->h2", (4, 2): "s4->s2", (4, 3): "s4->s3",
    (4, 4): "s4->h4", (4, 5): "s4->srv",
}
