import threading
from opcua import Client


class OPCUAConnection:
    def __init__(self, server_url):
        self.server_url = server_url
        self.client = None
        self.lock = threading.Lock()  # 保证线程安全

    def connected(self):
        with self.lock:
            if self.client is None:  # 确保只有一个连接
                self.client = Client(self.server_url)
                try:
                    self.client.connect()
                    print(f"连接成功: {self.server_url}")
                except Exception as e:
                    print(f"连接失败 ({self.server_url}): {e}")
                    self.client = None
            else:
                try:
                    self.client.connect()
                    print(f"重新连接OPCUA成功: {self.server_url}")
                except Exception as e:
                    print(f"重新连接OPCUA失败 ({self.server_url}): {e}")
                    self.client = None

    def is_connected(self):
        with self.lock:
            if self.client is None:
                return False
            try:
                self.client.get_node("ns = 2;s = R1.Scatter.Heartbeat").get_value()  # 检查服务器状态节点
                return True
            except Exception:
                return False

    def disconnected(self):
        with self.lock:
            if self.client is not None:
                try:
                    self.client.disconnect()
                    print(f"Disconnected from OPC UA server: {self.server_url}")
                except Exception as e:
                    print(f"Failed to disconnect from OPC UA server ({self.server_url}): {e}")
                finally:
                    self.client = None

    def get_client(self):
        if self.client is None or not self.is_connected():
            print(f"正在连接OPCUA服务: {self.server_url}")
            self.connected()
        return self.client


class OPCUAConnectionManager:
    _connection_lock = threading.Lock()
    _connections = {}

    @classmethod
    def get_connection(cls, server_url):
        with cls._connection_lock:
            if server_url not in cls._connections:
                cls._connections[server_url] = OPCUAConnection(server_url)
            return cls._connections[server_url]

    @classmethod
    def close_all(cls):
        with cls._connection_lock:
            for conn in cls._connections.values():
                conn.disconnected()
            cls._connections.clear()

    @classmethod
    def close_connection(cls, server_url):
        with cls._connection_lock:
            if server_url in cls._connections:
                connection = cls._connections[server_url]
                connection.disconnected()
                del cls._connections[server_url]
                print(f"已断开与{server_url}的连接")
            else:
                print(f"没有找到与{server_url}的连接")