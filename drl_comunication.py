import socket
import os
import time
import threading
import struct
import json
from queue import Queue


class DrlComunicationServer:
    def __init__(self, unix_socket_path: str):
        self.unix_socket_path = unix_socket_path
        self.inner_thread = None
        self.stop_event = threading.Event()
        self.ready_event = threading.Event()
        self.receive_queue = Queue(1)
        self.send_queue = Queue(1)

    def listen_and_handle_client(self):
        try:
            os.unlink(self.unix_socket_path)
        except FileNotFoundError:
            pass
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.unix_socket_path)
        self.server.listen(1)
        self.ready_event.set()
        client, _ = self.server.accept()
        client.settimeout(1.0)  # 设置超时

        while not self.stop_event.is_set():
            # 读取前四个字节，获取数据长度
            try:
                raw_msglen = client.recv(4)
            except socket.timeout:
                continue
            if not raw_msglen:
                break
            msglen = struct.unpack("!I", raw_msglen)[0]
            data = client.recv(msglen).decode()
            msg = json.loads(data)

            # 将消息放到接收队列
            self.receive_queue.put(msg)

            # 从发送队列取一个消息来进行响应
            response = self.send_queue.get()
            send_data = json.dumps(response)
            # 先发送四个字节数据长度
            msglen = struct.pack("!I", len(send_data))
            client.send(msglen)
            client.send(send_data.encode())

    def send(self, msg: dict):
        self.send_queue.put(msg)

    def receive(self) -> dict:
        res = self.receive_queue.get()
        print(f"Server received: {res}")
        return res

    def start_server(self):
        if self.inner_thread:
            return
        self.inner_thread = threading.Thread(target=self.listen_and_handle_client)
        self.inner_thread.start()
        while not self.ready_event.is_set():
            time.sleep(0.1)

    def stop_server(self):
        if self.inner_thread:
            self.stop_event.set()
            self.inner_thread.join()
            self.inner_thread = None


class DrlComunicationClient:
    def __init__(self, unix_socket_path: str):
        self.unix_socket_path = unix_socket_path
        self.client = None

    def is_connected(self):
        return self.client is not None

    def connect(self):
        self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client.connect(self.unix_socket_path)

    def send(self, msg):
        send_data = json.dumps(msg)
        msglen = struct.pack("!I", len(send_data))
        self.client.send(msglen)
        self.client.send(send_data.encode())

    def receive(self):
        # 读取前四个字节，获取数据长度
        raw_msglen = self.client.recv(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack("!I", raw_msglen)[0]
        data = self.client.recv(msglen).decode()
        return json.loads(data)

    def close(self):
        self.client.close()


# if __name__ == "__main__":
#     server = DrlComunicationServer("/tmp/drl_comunication")
#     server.start_server()

#     time.sleep(1)

#     client = DrlComunicationClient("/tmp/drl_comunication")
#     client.connect()

#     client.send({"msg": "hello"})
#     msg = server.receive()
#     print(f"Server received: {msg}")
#     server.send({"msg": "world"})
#     print(client.receive())

#     time.sleep(2)
#     client.send({"msg": "hello2"})
#     msg = server.receive()
#     print(f"Server received: {msg}")
#     server.send({"msg": "world2"})
#     print(client.receive())

#     server.stop_server()
#     client.close()
