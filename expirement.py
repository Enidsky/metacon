import subprocess
import os
import time
from tqdm import tqdm
from dowel import logger


class MmlinkLimitServer:
    def __init__(
        self,
        uplink_trace_file: str,
        downlink_trace_file: str,
        uplink_log_file: str,
        downlink_log_file: str,
    ):
        self.uplink_trace_file = uplink_trace_file
        self.downlink_trace_file = downlink_trace_file
        self.uplink_log_file = uplink_log_file
        self.downlink_log_file = downlink_log_file

        self._server = None
        self._client = None

    def start_server(self, port: int) -> str:
        logger.log("??????????????????!!?")
        self._server = subprocess.Popen(
            [
                "mm-link",
                self.uplink_trace_file,
                self.downlink_trace_file,
                "--uplink-log",
                self.uplink_log_file,
                "--downlink-log",
                self.downlink_log_file,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        
        # 如果启动错误，打印错误信息
        if self._server.poll() is not None:
            print("Error when start server.")
            print(self._server.stdout.read())
            print(self._server.stderr.read())
            return None
        logger.log("???????????????????")

        # 获取服务器的IP地址
        self._server.stdin.write(
            b"ip addr show ingress |  grep 'inet ' | awk '{print $2}' | cut -d/ -f1\n"
        )
        self._server.stdin.flush()
        server_ip = self._server.stdout.readline().decode("utf-8").strip()
        
        print(f"Server IP: {server_ip}")

        # 启动服务器
        self._server.stdin.write(f"python server.py {port}\n".encode())
        self._server.stdin.flush()

        return server_ip

    def start_client(self, server_ip: str, port: int):
        self._client = subprocess.Popen(
            ["python", "client.py", server_ip, str(port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        
    def print_server_output(self):
        if self._server:
            line = self._server.stdout.readline()
            while line:
                print(line)
                line = self._server.stdout.readline()
    
    def print_client_output(self):
        if self._client:
            line = self._client.stdout.readline()
            while line:
                print(line)
                line = self._client.stdout.readline()

    def clear(self):
        if self._server:
            self._server.terminate()
        if self._client:
            self._client.terminate()
        self._server = None
        self._client = None

    def __del__(self):
        self.clear()


if __name__ == "__main__":
    # mm-link /home/baihe/code/pantheon/src/experiments/12mbps.trace /home/baihe/code/pantheon/src/experiments/12mbps.trace --uplink-log=uplink.log --downlink-log=downlink.lo
    mls = MmlinkLimitServer(
        "12mbps.trace", "12mbps.trace", "uplink.log", "downlink.log"
    )
    server_ip = mls.start_server(3333)
    print(f"Server IP: {server_ip}")
    mls.start_client(server_ip, 3333)
    print("Client started.")
    for i in tqdm(range(1, 30)):
        # 模拟你的任务
        time.sleep(1)
