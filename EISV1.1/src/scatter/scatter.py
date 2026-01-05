from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QThread, pyqtSignal
from scatter.scatter_widget import Ui_Form as Ui_Scatter
import configparser
from opcua_connect.OPCUAConnection import OPCUAConnectionManager


class ScatterControl(QWidget):
    def __init__(self, parent):
        super(ScatterControl, self).__init__(parent)
        self.client = None
        self.ui = Ui_Scatter()
        self.ui.setupUi(parent)
        # 读取配置文件
        path = r'config\opcua_node.ini'
        self.config = configparser.ConfigParser()
        self.config.read(path, encoding='utf-8')

        # 创建状态监听线程
        self.listener_thread = StatusListenerThread()
        # 连接信号与槽
        self.listener_thread.update_heart_signal.connect(self.update_heart)
        self.listener_thread.update_position_signal.connect(self.update_position1)
        self.listener_thread.update_error_code_signal.connect(self.update_error_code)
        self.listener_thread.update_is_moving_signal.connect(self.update_is_moving)
        self.listener_thread.update_error_status_signal.connect(self.update_error_status)
        self.ui.pushButton_next_position.clicked.connect(self.move_next)
        self.listener_thread.client_signal.connect(self.create_client)
        # 启动监听线程
        # self.listener_thread.start()

    def update_heart(self, heart_status):
        # 心跳
        self.ui.lineEdit_heart.setText(heart_status)

    def update_position1(self, current_position):
        # 当前位置
        self.ui.lineEdit_position.setText(current_position)

    def update_error_code(self, error_code):
        # 错误代码
        self.ui.lineEdit_errorcode.setText(error_code)

    def update_is_moving(self, status):
        if status:
            self.ui.label_sport.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
        else:
            self.ui.label_sport.setStyleSheet("background-color: #FF0000;border-radius: 15px;")

    def update_error_status(self, status):
        if status:
            self.ui.label_error.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
        else:
            self.ui.label_error.setStyleSheet("background-color: #FF0000;border-radius: 15px;")

    # 散射体运动到下一位置
    def move_next(self):
        try:
            self.client. \
                get_node(f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_MoveNext')}").set_value(True)
            # self.ui.lineEdit_position.setText("9999")
        except Exception as e:
            print(e)

    def create_client(self, client):
        self.client = client

    def close_thread(self):
        print("关闭窗口")
        # 在关闭窗口时停止线程，断开连接
        if self.listener_thread and self.listener_thread.isRunning():
            self.listener_thread.stop()  # 停止线程
            self.listener_thread.wait()  # 等待线程退出
        OPCUAConnectionManager.close_all()


class StatusListenerThread(QThread):
    # 定义信号，用来向主线程发送数据
    update_heart_signal = pyqtSignal(str)
    update_position_signal = pyqtSignal(str)
    update_error_code_signal = pyqtSignal(str)
    update_error_status_signal = pyqtSignal(bool)
    update_is_moving_signal = pyqtSignal(bool)
    client_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super(StatusListenerThread, self).__init__(parent)
        self._running = True  # 添加标志位控制线程是否继续运行
        self.url = None
        self.conn = None
        self.client = None
        # 读取配置文件
        path = r'config\opcua_node.ini'
        self.config = configparser.ConfigParser()
        self.config.read(path, encoding='utf-8')

    def run(self):
        try:
            # self.url = "opc.tcp://10.0.30.98:8888"
            self.url = self.config.get('Room1', 'OPCUA_SERVER_SCATTER')
            self.conn = OPCUAConnectionManager.get_connection(self.url)
            self.client = self.conn.get_client()
            self.client_signal.emit(self.client)
            # 一直监听并获取数据
            while self._running:
                try:
                    # 心跳
                    node_id = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_Heartbeat')}"
                    current_heart = self.client.get_node(node_id).get_value()
                    self.update_heart_signal.emit(str(current_heart))
                    # 获取当前位置
                    node_id = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_Position')}"
                    current_position = self.client.get_node(node_id).get_value()
                    self.update_position_signal.emit(str(current_position))
                    position_node1 = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_Position')}"
                    position_node2 = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_MoveNext')}"
                    if current_position != self.client.get_node(position_node1).get_value():
                        self.client.get_node(position_node2).set_value(False)
                    # 获取错误代码
                    error_node = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_ErrorCode')}"
                    error_code = self.client.get_node(error_node).get_value()
                    self.update_error_code_signal.emit(str(error_code))
                    # 获取运动状态
                    move_node = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_IsMoving')}"
                    is_moving = self.client.get_node(move_node).get_value()
                    self.update_is_moving_signal.emit(is_moving)
                    # 获取错误状态
                    status_node = f"ns = 2; s = {self.config.get('Room1Scatter', 'Scatter_ErrorStatus')}"
                    error_status = self.client.get_node(status_node).get_value()
                    self.update_error_status_signal.emit(error_status)

                except Exception as e:
                    print(f"读取节点失败 {self.url}: {e}")
                    OPCUAConnectionManager.close_connection(self.url)
                    self.client = self.conn.get_client()
                finally:
                    self.msleep(1000)
        except Exception as e:
            print(f"初始连接散射体异常：{e}")

    def stop(self):
        """ 停止线程的循环 """
        self._running = False