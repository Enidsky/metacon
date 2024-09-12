from typing import Iterable

from aioquic.quic.packet_builder import QuicSentPacket
from aioquic.quic.congestion.base import QuicCongestionControl, register_congestion_control


class MetisCongestionControl(QuicCongestionControl):
    """
    New Reno congestion control.
    """

    def __init__(self, *, max_datagram_size: int) -> None:
        super().__init__(max_datagram_size=max_datagram_size)
        self._max_datagram_size = max_datagram_size
        self.congestion_window = max_datagram_size * 1
        print(f"congestion_window: {self.congestion_window}")

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes

    def on_packet_sent(self, *, packet: QuicSentPacket) -> None:
        self.bytes_in_flight += packet.sent_bytes

    def on_packets_expired(self, *, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes

    def on_packets_lost(self, *, now: float, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes

    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        pass
        # check whether we should exit slow start
        # if self.ssthresh is None and self._rtt_monitor.is_rtt_increasing(
        #     now=now, rtt=rtt
        # ):
        #     self.ssthresh = self.congestion_window


register_congestion_control("fix", MetisCongestionControl)
