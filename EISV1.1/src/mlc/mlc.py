import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QBrush, QPen, QColor
import configparser
from opcua import ua
from opcua_connect.OPCUAConnection import OPCUAConnection, OPCUAConnectionManager
from mlc.mlc_widget_1 import Ui_Form as MlcButtonUI
from mlc.mlc_widget_2 import SingleBarWidget, CustomSpinBox, MlcInfo
COUNT = 0  # 设置全局变量，当前选中光栅序号


class MLC(QWidget):
    def __init__(self, parent=None):
        super(MLC, self).__init__(parent)
        self.client = None
        self.mlc_info = MlcInfo()
        self.mwidget = QWidget()
        self.button_ui = MlcButtonUI()
        self.button_ui.setupUi(self.mwidget)
        self.button_widget = CustomSpinBox()
        self.bar_widget = SingleBarWidget()

        # 读取配置文件
        path = r'config\opcua_node.ini'
        self.config = configparser.ConfigParser()
        self.config.read(path, encoding='utf-8')
        # 创建状态监听线程
        self.listener_thread = StatusListenerThread()

        # 连接点击按钮事件
        self.button_widget.button1.clicked.connect(self.stepByLeft)
        self.button_widget.button2.clicked.connect(self.stepByRight)
        self.button_widget.button.clicked.connect(self.get_mlc_data)
        self.button_widget.button_load_current.clicked.connect(self.load_mlc)
        self.listener_thread.update_status.connect(self.listen_mlc_status)
        self.button_ui.pushButton_init.clicked.connect(self.mlc_init)
        self.button_ui.pushButton_move_position.clicked.connect(self.move_position)
        self.listener_thread.update_mlc.connect(self.update_mlc)
        self.button_ui.pushButton_stop.clicked.connect(self.mlc_stop)
        self.listener_thread.client_signal.connect(self.create_client)
        # 启动监听线程
        # self.listener_thread.start()

    def stepByLeft(self):
        try:
            # 只下发数据，不重绘光栅
            if COUNT < 34:
                self.mlc_ui.spin_box.stepBy(-1)  # 减少值
                data = self.mlc_ui.spin_box.value()
                self.mlc_info.x_coordinate[COUNT] = data
            if 34 <= COUNT < 68:
                self.mlc_ui.spin_box.stepBy(1)  # 增加值
                data = self.mlc_ui.spin_box.value()
                self.mlc_info.y_coordinate[COUNT - 34] = data
            temp_value = ua.Variant(self.mlc_info.x_coordinate + self.mlc_info.y_coordinate, ua.VariantType.Float)
            self.client.\
                get_node(f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Data')}").\
                set_value(temp_value)
        except Exception as e:
            print(e)

    def stepByRight(self):
        if COUNT < 34:
            self.mlc_ui.spin_box.stepBy(1)  # 增加值
            data = self.mlc_ui.spin_box.value()
            self.mlc_info.x_coordinate[COUNT] = data
        if 34 <= COUNT < 68:
            self.mlc_ui.spin_box.stepBy(-1)  # 减少值
            data = self.mlc_ui.spin_box.value()
            self.mlc_info.y_coordinate[COUNT - 34] = data
        data_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Data')}"
        temp_value = ua.Variant(self.mlc_info.x_coordinate + self.mlc_info.y_coordinate, ua.VariantType.Float)
        self.client.get_node(data_node).set_value(temp_value)

    # 根据opcua节点数据重绘光栅
    def update_mlc(self, index, data):
        try:
            if index < 34:
                self.mlc_info.temp_x[index] = data
            if 34 <= index < 68:
                self.mlc_info.temp_y[index - 34] = data
            self.update()  # 重新绘制
        except Exception as e:
            print(e)

    # 获取光栅数据
    def get_mlc_data(self):
        data = self.mlc_ui.spin_box.value()
        if COUNT < 34:
            self.mlc_ui.rectangles[COUNT]['rect'].setWidth(data)
        if 34 <= COUNT < 68:
            self.mlc_ui.rectangles[COUNT]['rect'].setX(812 - data)
            self.mlc_ui.rectangles[COUNT]['rect'].setWidth(data)
        self.update()

    # 加载当前光栅数据
    def load_mlc(self):
        try:
            # 下发更新后光栅数据
            temp_value = ua.Variant(self.mlc_info.x_coordinate + self.mlc_info.y_coordinate, ua.VariantType.Float)
            self.client.\
                get_node(f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Data_Acq')}").\
                set_value(temp_value)
        except Exception as e:
            print(e)

    def listen_mlc_status(self, list_status):
        try:
            # 心跳
            self.button_ui.lineEdit_heart.setText(str(list_status[0]))
            # 连接状态
            if list_status[1]:
                self.button_ui.label_connect.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_connect.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            if list_status[2]:
                self.button_ui.label_IsReady.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_IsReady.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            if list_status[3]:
                self.button_ui.label_IsMoving.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_IsMoving.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            if list_status[4]:
                self.button_ui.label_ErrorA.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_ErrorA.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            if list_status[5]:
                self.button_ui.label_ErrorB.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_ErrorB.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            if list_status[6]:
                self.button_ui.label_RunTimeout.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_RunTimeout.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            self.button_ui.lineEdit_blockstep_id.setText(str(list_status[7]))
            self.button_ui.lineEdit_blockleaf_id.setText(str(list_status[8]))
            # 错误状态......
            if list_status[9]:
                self.button_ui.label_error.setStyleSheet("background-color: #00FF00;border-radius: 15px;")
            else:
                self.button_ui.label_error.setStyleSheet("background-color: #FF0000;border-radius: 15px;")
            self.button_ui.lineEdit_errorcode.setText(str(list_status[10]))
        except Exception as e:
            print(e)

    def mlc_init(self):
        try:
            init_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Init')}"
            self.client.get_node(init_node).set_value(True)
        except Exception as e:
            print(f"光栅初始化失败：{e}")

    def move_position(self):
        try:
            move_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Move_Position')}"
            self.client.get_node(move_node).set_value(True)
        except Exception as e:
            print(f"光栅移动位置失败：{e}")

    def mlc_stop(self):
        try:
            stop_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Stop')}"
            self.client.get_node(stop_node).set_value(True)
        except Exception as e:
            print(f"光栅停止失败：{e}")


    def create_client(self, client):
        self.client = client

    def close_thread(self):
        print("MLC窗口关闭")
        # 在关闭窗口时停止线程，断开连接
        if self.listener_thread and self.listener_thread.isRunning():
            self.listener_thread.stop()  # 停止线程
            self.listener_thread.wait()  # 等待线程退出
        OPCUAConnectionManager.close_all()


class StatusListenerThread(QThread):
    # 定义信号，用来向主线程发送数据
    update_status = pyqtSignal(list)
    update_mlc = pyqtSignal(int, float)
    client_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super(StatusListenerThread, self).__init__(parent)
        self._running = True  # 添加标志位控制线程是否继续运行
        self.flag = True # 判断是否第一次绘制
        self.client = None
        self.conn = None
        # 读取配置文件
        path = r'config\opcua_node.ini'
        self.config = configparser.ConfigParser()
        self.config.read(path, encoding='utf-8')
        self.mlc_info = MlcInfo()

    def run(self):
        try:
            # url = "opc.tcp://10.0.30.98:8888"
            url = self.config.get('Room1', 'OPCUA_SERVER_MLC')
            self.conn = OPCUAConnectionManager.get_connection(url)
            self.client = self.conn.get_client()
            # 下发当前光栅数据
            temp_value = ua.Variant(self.mlc_info.x_coordinate + self.mlc_info.y_coordinate, ua.VariantType.Float)
            self.client.\
                get_node(f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Data')}").\
                set_value(temp_value)
            self.client_signal.emit(self.client)
            list_status = []
            # 一直监听并获取数据
            while self._running:
                try:
                    list_status.clear()
                    # 心跳
                    heart_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Heartbeat')}"
                    current_heart = self.client.get_node(heart_node).get_value()
                    list_status.append(current_heart)
                    # 连接状态
                    connect_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Connect')}"
                    current_connect = self.client.get_node(connect_node).get_value()
                    list_status.append(current_connect)
                    # 是否运动完成
                    isready_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_IsReady')}"
                    mlc_isready = self.client.get_node(isready_node).\
                        get_value()
                    list_status.append(mlc_isready)
                    # 叶片是否运动中
                    moving_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_IsMoving')}"
                    mlc_ismoving = self.client.get_node(moving_node).get_value()
                    list_status.append(mlc_ismoving)
                    # 红外A错误
                    errora_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_ErrorA')}"
                    mlc_errora = self.client.get_node(errora_node).get_value()
                    list_status.append(mlc_errora)
                    # 红外B错误
                    errorb_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_ErrorB')}"
                    mlc_errorb = self.client.get_node(errorb_node).get_value()
                    list_status.append(mlc_errorb)
                    # 运动超时
                    time_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_RunTimeout')}"
                    run_timeout = self.client.get_node(time_node).get_value()
                    list_status.append(run_timeout)
                    # 卡涩步进电机
                    step_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_BlockStepID')}"
                    block_step_id = self.client.get_node(step_node).get_value()
                    list_status.append(block_step_id)
                    # 卡涩叶片
                    leaf_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_BlockLeafID')}"
                    block_Leaf_id = self.client.get_node(leaf_node).get_value()
                    list_status.append(block_Leaf_id)
                    # 错误状态
                    status_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_ErrorStatus')}"
                    error_status = self.client.get_node(status_node).get_value()
                    list_status.append(error_status)
                    # 错误代码
                    code_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_ErrorCode')}"
                    error_code = self.client.get_node(code_node).get_value()
                    list_status.append(error_code)
                    self.update_status.emit(list_status)
                    # 获取当前构型
                    data_acq_node = f"ns = 2; s = {self.config.get('Room1MLC', 'MLC_Data_Acq')}"
                    current_mlc_data = self.client.get_node(data_acq_node).get_value()
                    temp_list = list(map(float, self.mlc_info.x_coordinate + self.mlc_info.y_coordinate))
                    for idx, (value1, value2) in enumerate(zip(current_mlc_data, temp_list)):
                        if self.flag:
                            self.update_mlc.emit(idx, value1)
                        else:
                            if math.isclose(value1, value2, rel_tol=1e-9, abs_tol=1e-9) is False:
                                self.update_mlc.emit(idx, value1)
                    self.flag = False
                except Exception as e:
                    OPCUAConnectionManager.close_connection(url)
                    self.client = self.conn.get_client()
                    print(f"监控报错{e}")
                finally:
                    self.msleep(1000)
        except Exception as e:
            print(f"初始连接光栅异常：{e}")

    def stop(self):
        # 停止线程的循环
        self._running = False