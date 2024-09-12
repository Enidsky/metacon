import time
import schedule
from typing import Iterable
from aioquic.quic.packet_builder import QuicSentPacket
from aioquic.quic.congestion.base import (
    QuicCongestionControl,
    register_congestion_control,
)
from drl_comunication import DrlComunicationClient


class OnlineVarianceCalculator:
    def __init__(self, min_value: int = None, max_value: int = None):
        self.n = 0
        self.mean = 0
        self.M2 = 0
        self.sum = 0
        self._init_min_value = min_value
        self._init_max_value = max_value
        self.max_val = self._init_max_value
        self.min_val = self._init_min_value

    def reset(self):
        self.n = 0
        self.mean = 0
        self.M2 = 0
        self.sum = 0
        self.max_val = self._init_max_value
        self.min_val = self._init_min_value

    def update(self, x):
        # print(self.min_val, x, min(self.min_val, x))
        if self.min_val is None:
            self.min_val = x
        self.min_val = x if self.min_val is None else min(self.min_val, x)
        self.max_val = x if self.max_val is None else max(self.max_val, x)
        self.sum += x
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    def get_min(self):
        return 0 if self.min_val is None else self.min_val

    def get_max(self):
        return 0 if self.max_val is None else self.max_val

    def get_var(self):
        if self.n < 2:
            return 0
        return self.M2 / (self.n - 1)

    def get_avg(self):
        if self.n < 1:
            return 0
        return self.sum / self.n


class Observer:
    def __init__(self) -> None:
        # thr, thr_max, avg_delay, min_delay, loss, srtt, cwnd
        self.send_count = 0
        self.send_bytes = 0
        self.delay_calculator = OnlineVarianceCalculator()
        self.min_delay = 0
        self.thr_max = 0
        self.loss = 0
        self.srtt = 0
        self.cwnd = 0
        # 设置初始时间为当前时间
        self.start_time = time.time()

    def reset(self) -> None:
        self.send_count = 0
        self.send_bytes = 0
        self.loss = 0
        self.start_time = time.time()
        self.delay_calculator.reset()

    def on_packet_acked(self, *, packet: QuicSentPacket) -> None:
        self.send_bytes += packet.sent_bytes
        self.send_count += 1

    def on_packet_lost(self, *, packet: QuicSentPacket) -> None:
        self.loss += 1

    def on_rtt_measurement(self, *, rtt: float) -> None:
        self.srtt = 0.8 * self.srtt + 0.2 * rtt
        self.delay_calculator.update(rtt)

    def get_observation(self) -> Iterable[float]:
        end_time = time.time()
        duration = end_time - self.start_time
        if self.min_delay == 0 or self.delay_calculator.get_min() < self.min_delay:
            self.min_delay = self.delay_calculator.get_min()
        thr = self.send_bytes / duration
        if self.thr_max == 0 or thr > self.thr_max:
            self.thr_max = thr
        return [
            thr,
            self.thr_max,
            self.delay_calculator.get_avg(),
            self.min_delay,
            self.loss,
            self.srtt,
            self.cwnd,
        ]


class MetaConCongestionControl(QuicCongestionControl):
    """
    MetaCon congestion control algorithm based on MAMLPPO
    """

    def __init__(self, *, max_datagram_size: int) -> None:
        super().__init__(max_datagram_size=max_datagram_size)
        self._max_datagram_size = max_datagram_size
        self.initial_window = max_datagram_size * 10
        self.congestion_window = self.initial_window
        self.observer = Observer()
        self.observer.cwnd = self.initial_window
        self.job = schedule.every(1).seconds.do(self.perform_decision)
        self.drl_comunication_client = DrlComunicationClient("/tmp/drl_comunication")

    def perform_decision(self) -> float:
        observation = self.observer.get_observation()
        if not self.drl_comunication_client.is_connected():
            self.drl_comunication_client.connect()
        # 发送观测值到模型
        self.drl_comunication_client.send(
            {
                "observation": observation,
                "window": self.congestion_window
            }
        )
        # 从模型接收决策
        action_data = self.drl_comunication_client.receive()
        action = action_data.get("action", 0)
        new_cwnd = self.congestion_window * pow(2, action)
        print(f"action: {action}, new_cwnd: {new_cwnd}")
        self.congestion_window = max(self.initial_window, new_cwnd)
        self.observer.cwnd = self.congestion_window
        self.observer.reset()

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes
        self.observer.on_packet_acked(packet=packet)
        schedule.run_pending()

    def on_packet_sent(self, *, packet: QuicSentPacket) -> None:
        self.bytes_in_flight += packet.sent_bytes
        schedule.run_pending()

    def on_packets_expired(self, *, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes
            self.observer.on_packet_lost(packet=packet)

    def on_packets_lost(self, *, now: float, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes
            self.observer.on_packet_lost(packet=packet)
        schedule.run_pending()

    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        self.observer.on_rtt_measurement(rtt=rtt)
        schedule.run_pending()


register_congestion_control("meta_con", MetaConCongestionControl)
