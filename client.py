import asyncio
import sys
from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived
import meta_con

class EchoClientProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print("Handshake completed!")
            asyncio.ensure_future(self.send_data_loop())
        elif isinstance(event, StreamDataReceived):
            print(f"Client received: {event.data.decode()}")
            # stream_id = self._quic.get_next_available_stream_id()
            # self._quic.send_stream_data(stream_id, b"1111")

    async def send_data_loop(self):
        stream_id = self._quic.get_next_available_stream_id()
        # 发送 1400 字节的数据
        data = b"1" * 5000
        while True:
            self._quic.send_stream_data(stream_id, data)
            await asyncio.sleep(0.00001)

async def main():
    # 加一段逻辑，解析命令行参数，支持指定ip和端口
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <ip> <port>")
        return
    ip = sys.argv[1]
    port = int(sys.argv[2])
    configuration = QuicConfiguration(is_client=True)
    configuration.verify_mode = False
    configuration.congestion_control_algorithm = "meta_con"

    async with connect(
        ip,
        port,
        configuration=configuration,
        create_protocol=EchoClientProtocol,
    ) as protocol:
        print("Connected")
        await protocol.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())