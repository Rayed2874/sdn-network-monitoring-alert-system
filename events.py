from ryu.controller import event


class EventCongestion(event.EventBase):

    def __init__(self, dpid, port, utilization):
        super(EventCongestion, self).__init__()

        self.dpid = dpid
        self.port = port
        self.utilization = utilization