import psutil


def get_cpu_usage():
    return psutil.cpu_percent(interval=None)


def get_memory_usage():
    memory = psutil.virtual_memory()
    return memory.percent


def get_network_stats():
    network = psutil.net_io_counters()

    return {
        "tx_packets": network.packets_sent,
        "rx_packets": network.packets_recv,
        "tx_bytes": network.bytes_sent,
        "rx_bytes": network.bytes_recv
    }