import sys
import asyncio
import time
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived


class EchoServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_bytes_received = 0
        self.last_time = time.time()
        self.last_bytes_received = 0

        # # 启动传输速率统计任务
        # asyncio.create_task(self.print_transfer_rate())

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print("Handshake completed!")

        elif isinstance(event, StreamDataReceived):
            self.total_bytes_received += len(event.data)
            print(f"Server received: {event.data.decode()}")

    async def print_transfer_rate(self):
        while True:
            await asyncio.sleep(1)  # 每秒运行一次
            current_time = time.time()
            elapsed_time = current_time - self.last_time
            if elapsed_time > 0:
                bytes_received = self.total_bytes_received - self.last_bytes_received
                rate = bytes_received / elapsed_time / 1024 / 1024 * 8
                print(f"Current transfer rate: {rate} Mbps")
                # 更新计数器和时间
                self.last_time = current_time
                self.last_bytes_received = self.total_bytes_received


async def main():
    # 解析命令行参数，支持指定端口
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <port>")
        return
    port = int(sys.argv[1])

    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain(certfile="/home/baihe/code/pyquic/cert.pem", keyfile="/home/baihe/code/pyquic/key.pem")
    configuration.congestion_control_algorithm = "cubic"

    server = await serve(
        "0.0.0.0",
        port,
        configuration=configuration,
        create_protocol=EchoServerProtocol,
    )

    try:
        await asyncio.Future()  # Run until interrupted
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())