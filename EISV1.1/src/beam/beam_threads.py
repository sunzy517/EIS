import math
import time
import ctypes
from PyQt5.QtCore import QThread, pyqtSignal
import configparser
from opcua_connect.OPCUAConnection import OPCUAConnectionManager
from opcua import ua


class BeamThread(QThread):
    spot_signal = pyqtSignal(int)
    layel_signal = pyqtSignal(int)
    total_spot_signal = pyqtSignal(int)
    ic1_signal = pyqtSignal(int)
    ic2_signal = pyqtSignal(int)
    ic3_signal = pyqtSignal(int)
    request_beam_signal = pyqtSignal(bool)

    def __init__(self, position_x, position_y, parent=None):
        super().__init__(parent)
        self.client_beam = None
        self.client_acs = None
        self._running = True
        self.position_x = position_x
        self.position_y = position_y
        self.PLLC_FLAG = False
        # 读取配置文件
        path = r'config\opcua_node.ini'
        self.config = configparser.ConfigParser()
        self.config.read(path, encoding='utf-8')

    def run(self):
        try:
            print("开始放束")
            scannedcount = 0
            # treat_info = TreatInfo()
            bd_ic_count_mark = 0
            mu_exchange_count = 0
            acs_start = True
            treat_info = TreatInfo()
            # url = "opc.tcp://10.0.30.98:8888"
            url_beam = self.config.get('Room1', 'OPCUA_SERVER_BEAM')
            url_acs = self.config.get('Room1', 'OPCUA_SERVER_ACS')
            conn_beam = OPCUAConnectionManager.get_connection(url_beam)
            conn_acs = OPCUAConnectionManager.get_connection(url_acs)
            self.client_beam = conn_beam.get_client()
            self.client_acs = conn_acs.get_client()

            # self.send_pssc_data(self.position_x[treat_info.current_layer], self.position_y[treat_info.current_layer])

            # 开始先下发start，acs返回start_ready
            if self.acs_ready("start") is False:
                print("ACS未就绪")
                return
            while self._running:
                try:
                    time.sleep(0.05)
                    print(f"第{treat_info.current_layer}层，第{scannedcount}点")
                    print(# f"当前层总剂量{treat_info.ic2_dose[treat_info.current_layer]}，"
                          f"当前点总剂量{treat_info.dose[treat_info.current_layer][scannedcount]}，"
                          f"当前层总点数{len(treat_info.dose[treat_info.current_layer])}，"
                          f"总层数{treat_info.layers}，当前层能量{treat_info.energy}")
                    # print(f"扫描铁：{self.position_x[treat_info.current_layer]}")
                    # 申请束流一层只能申请一个能量，当前层打完之后act_start==True，(ask_beam)调用ACS申请束流正常开始下一层
                    if acs_start:
                        # 给ACS节点写值，申请束流 STOP
                        if self.ask_beam(treat_info.current_layer) is not True:
                            # DDS节点写停止命令
                            dds_stop_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'Change_Layer')}"
                            temp_value = ua.Variant(9998, ua.VariantType.UInt16)
                            self.client_beam.get_node(dds_stop_node).set_value(temp_value)
                            treat_info.current_layer = 0
                            return# False
                        else:
                            # 初次给扫描铁下发数据
                            # self.send_pssc_data(self.position_x[treat_info.current_layer], self.position_y[treat_info.current_layer])
                            # self.send_pssc_data(self.position_y[treat_info.current_layer])
                            # 给FPGA下发当前层开始命令 START
                            layer_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'Change_Layer')}"
                            # TODO temp_value = ua.Variant(1, ua.VariantType.UInt16)
                            temp_value = ua.Variant(1, ua.VariantType.UInt32)
                            self.client_beam.get_node(layer_node).set_value(temp_value)
                            acs_start = False

                    # 监测急停
                    stop_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'WR_UINT16_CONTROLCOMMAND')}"
                    control_cmd = self.client_beam.get_node(stop_node).get_value()
                    if control_cmd != 112 and control_cmd != 212 and control_cmd != 312:
                        treat_info.current_layer = 0
                        return# False

                    # 获取IC1
                    ic1_node = f"ns = 2; s = {self.config.get('Room1IC1', 'R_SPOT_CURRENT_DOSEIC1')}"
                    bd_ic1count = self.client_beam.get_node(ic1_node).get_value()
                    temp_value = bd_ic1count - treat_info.ic1_count
                    self.ic1_signal.emit(bd_ic1count)
                    # 获取IC2
                    ic2_node = f"ns = 2; s = {self.config.get('Room1IC2', 'R_SPOT_CURRENT_DOSEIC2')}"
                    bd_ic2count = self.client_beam.get_node(ic2_node).get_value()
                    self.ic2_signal.emit(bd_ic2count)
                    # 写点索引，给TCS发送已扫描点个数
                    if scannedcount > 0:
                        if treat_info.current_layer == 0:
                            temp_value = ua.Variant(scannedcount + treat_info.spot_index - 1, ua.VariantType.UInt32)
                        else:
                            temp_value = ua.Variant(scannedcount, ua.VariantType.UInt32)
                    else:
                        temp_value = ua.Variant(0, ua.VariantType.UInt32)
                    spot_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'W_UINT32_CURRENTSPOTINDEX')}"
                    self.client_beam.get_node(spot_node).set_value(temp_value)
                    # TODO 做个简单测试，实际环境这里有值
                    treat_info.ic1_count = 0
                    print("判断换点")

                    # 当MU大于预设MU时并且束流结束（bd_iccount）不变化时，换点
                    if int(bd_ic1count) - int(treat_info.ic1_count) >= \
                            int(float(treat_info.dose[treat_info.current_layer][scannedcount])):
                        # 通过计数方式判断是否无粒子数变化
                        if bd_ic1count == bd_ic_count_mark:
                            mu_exchange_count += 1
                        else:
                            bd_ic_count_mark = bd_ic1count
                            mu_exchange_count = 0
                        if mu_exchange_count >= treat_info.SPOT_EXCHANGE_MAXNUM:
                            treat_info.ic1_count = bd_ic1count
                            mu_exchange_count = 0
                            # FPGA下发换点脉冲
                            scannedcount += 1
                        # 更新当前点数
                        self.spot_signal.emit(scannedcount)
                        # self.progressbar.staticPercentProgressBarSpot.setValue(scannedcount)

                    # 换层
                    print("判断换层")
                    if scannedcount >= int(treat_info.dose_count[treat_info.current_layer]):
                        # 给FPGA下发 STOP
                        # 此处current_layer当前层数递增，给板卡和ACS下发json文件中下一层数据
                        treat_info.current_layer += 1
                        # TODO temp_value = ua.Variant(9999, ua.VariantType.UInt16)
                        temp_value = ua.Variant(9999, ua.VariantType.UInt32)
                        change_layer_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'Change_Layer')}"
                        self.client_beam.get_node(change_layer_node).set_value(temp_value)
                        # 给ACS下发停束命令
                        # acs_stop_node = f"ns = 2; s = {self.config.get('Room1ACS', 'ACS_Control_Sequence')}"

                        # my_object = self.client_acs.get_root_node().get_child(["0:MyObject"])
                        # acs_control_sequence = my_object.get_child(["0:ACSControlSequence"])
                        # acs_control_sequence.set_value("stop")

                        # self.client_acs.get_node(acs_stop_node).set_value("stop")
                        if treat_info.current_layer + treat_info.layers_index >= treat_info.layers // 2:
                            # 此处添加返回信号
                            if self.acs_ready("stop") is False:
                                print("ACS停止失败")
                                ret = False
                            else:
                                ret = True
                            treat_info.current_layer = 0
                            OPCUAConnectionManager.close_connection(url_acs)
                            # OPCUAConnectionManager.close_connection(url_beam)
                            self._running = False
                            return
                        else:
                            # 写层预设剂量
                            temp_value = treat_info.ic2_dose[treat_info.current_layer]
                            temp_data = math.trunc(float(temp_value))  # 暂时去掉小数部分
                            temp_value = ua.Variant(temp_data, ua.VariantType.UInt32)
                            dose_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'W_UINT32_LAYER_PRESETMU')}"
                            self.client_beam.get_node(dose_node).set_value(temp_value)
                            # 换层后初始化点剂量，层MU，更新层号，点索引
                            scannedcount = 0
                            # 换层给扫描铁发值，x，y按照先后顺序发送，需要监测扫描铁数据，
                            # 需要线程锁，写的时候不能读，发完数据重新连接扫描铁，
                            # self.send_pssc_data(self.position_x[treat_info.current_layer],
                            #                     self.position_y[treat_info.current_layer])
                            # self.send_pssc_data(self.position_y[treat_info.current_layer])
                            # self.listen_pssc()

                            # TODO temp_value = ua.Variant(1, ua.VariantType.UInt16)
                            temp_value = ua.Variant(1, ua.VariantType.UInt32)
                            change_layer_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'Change_Layer')}"
                            self.client_beam.get_node(change_layer_node).set_value(temp_value)

                            # 换层成功，更新当前层总点数
                            self.total_spot_signal.emit(treat_info.dose_count[treat_info.current_layer])
                            # self.progressbar.staticPercentProgressBarLayer.\
                            #     setValue(treat_info.dose_count[treat_info.current_layer])
                            # 更新当前层
                            # self.layel_signal.emit(treat_info.current_layer + 1)
                            acs_start = True
                except Exception as e:
                    treat_info.current_layer = 0
                    OPCUAConnectionManager.close_connection(url_acs)
                    OPCUAConnectionManager.close_connection(url_beam)
                    print(f"放束过程报错：{e}")
                    return
            self.request_beam_signal.emit(True)
        except Exception as e:
            print(e)
            return

    def acs_ready(self, acs_status):
        # my_object = self.client_acs.get_root_node().get_child(["0:MyObject"])
        # acs_control_sequence = my_object.get_child(["0:ACSControlSequence"])
        # acs_control_sequence.set_value(acs_status)
        self.client_acs.get_node("ns = 2; s = R1.DDS.ErrorInfo").set_value(acs_status)
        while True:
            # acs_response = my_object.get_child(["0:ACSResponseSignal"]).get_value()
            acs_response = self.client_acs.get_node("ns = 2; s = R1.DDS.ControllerErrorInfo").get_value()
            cmd = acs_status + "_ready"
            if acs_response.find(cmd) != -1:
                ret = True
                break
            elif acs_response.find('timeout') != -1:
                ret = False
                break
            time.sleep(0.05)
        return ret

    def ask_beam(self, layer):
        try:
            print("调用ACS")
            treat_info = TreatInfo()
            acs_control = "1_" + str(treat_info.energy[layer])
            # 写入目标
            sequence_node = f"ns = 0; s = {self.config.get('Room1ACS', 'ACS_Control_Sequence')}"
            # self.client.get_node(sequence_node).set_value(acs_control)


            # 北大ACS节点读取方式
            '''
            my_object = self.client_acs.get_root_node().get_child(["0:MyObject"])
            acs_control_sequence = my_object.get_child(["0:ACSControlSequence"])
            acs_control_sequence.set_value(acs_control)
            '''
            # 办公室调试节点
            self.client_acs.get_node("ns = 2; s = R1.DDS.ErrorInfo").set_value(acs_control)


            self.layel_signal.emit(treat_info.current_layer + 1)
            cmd_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'WR_UINT16_CONTROLCOMMAND')}"
            signal_node = f"ns = 2; s = {self.config.get('Room1ACS', 'ACS_Response_Signal')}"
            while True:
                control_cmd = self.client_beam.get_node(cmd_node).get_value()
                # acs_response = self.client.get_node(signal_node).get_value()


                # 北大ACS节点读取方式
                '''
                acs_response = my_object.get_child(["0:ACSResponseSignal"]).get_value()
                '''
                # 办公室调试节点
                acs_response = self.client_acs.get_node("ns = 2; s = R1.DDS.ControllerErrorInfo").get_value()


                if control_cmd != 212 and control_cmd != 112 and control_cmd != 312:
                    ret = False
                    break
                # if acs_response.find('ready') != -1 and acs_response.find(acs_control) != -1:
                #     ret = True
                #     break
                cmd = acs_control + "_ready"
                if acs_response.find(cmd) != -1:
                    ret = True
                    break
                elif acs_response.find('timeout') != -1:
                    ret = False
                    break
                time.sleep(0.05)
            return ret
        except Exception as e:
            print(f"ask_beam: {e}")

    # 扫描铁数据下发
    def send_pssc_data(self, position_datax, position_datay):
        try:
            path = r'lib\Powerlib.dll'
            # 调用扫描铁协议库
            dll = ctypes.WinDLL(path)
            # 定义C函数的原型
            SOCKET = ctypes.c_int
            dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(SOCKET)]
            # dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int]
            dll.GetConnection.restype = ctypes.c_bool
            dll.WriteSpotDataToPower.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                                 SOCKET, ctypes.c_ulong]
            dll.WriteSpotDataToPower.restype = ctypes.c_bool
            dll.QueryStatus.argtypes = [SOCKET, ctypes.c_ulong]
            dll.QueryStatus.restype = ctypes.c_char_p  # 返回值为 const char* 类型
            dll.Statusstrfree.restype = ctypes.c_void_p

            sock_x = SOCKET()
            sock_y = SOCKET()
            sock_pointer_x = ctypes.byref(sock_x)
            sock_pointer_y = ctypes.byref(sock_y)
            # 连接x扫描铁
            if dll.GetConnection(0x0A00184F, 30000, sock_pointer_x):
            # if dll.GetConnection(0x0A814941, 30000, sock_pointer_x) and \
            #         dll.GetConnection(0x0A814941, 30000, sock_pointer_y):
                self.PLLC_FLAG = True
                print("x连接成功")
            else:
                self.PLLC_FLAG = False
                print("x连接失败！！！")
                return
            float_array_x = (ctypes.c_float * len(position_datax))(*position_datax)
            # print(position_datax)
            if dll.WriteSpotDataToPower(float_array_x, len(position_datax), sock_x, 79):
                print("x发送成功")
            else:
                print("x发送失败！！！")
            # 监控扫描铁数据
            result_x = dll.QueryStatus(sock_x, 79)
            if result_x is not None:
                print(result_x)
                result_x_str = result_x.decode('utf-8')
                if result_x_str == "数据包发送失败" or result_x_str == "数据包接收失败":
                    print("扫描铁x数据处理失败")
                else:
                    fields = result_x_str.split(',')
                    # 转换为键值对
                    data = {}
                    for field in fields:
                        key, value = field.split('：')  # 中文冒号
                        data[key.strip()] = value.strip()
                    # 类型转换
                    data['电源状态'] = int(data['电源状态'], 16)  # 十六进制
                    data['电流'] = float(data['电流'])  # 浮点数
                    data['电压'] = float(data['电压'])  # 浮点数
                    print(data)
                    if data['反馈状态'] != '正常':
                        return
                dll.Statusstrfree()
            else:
                print("获取扫描铁数据失败")
            # 连接y扫描铁
            if dll.GetConnection(0x0A001850, 30000, sock_pointer_y):
            # if dll.GetConnection(0x0A814941, 30000, sock_pointer_x) and \
            #         dll.GetConnection(0x0A814941, 30000, sock_pointer_y):
                self.PLLC_FLAG = True
                print("y连接成功")
            else:
                self.PLLC_FLAG = False
                print("y连接失败！！！")
                return
            float_array_y = (ctypes.c_float * len(position_datay))(*position_datay)
            if dll.WriteSpotDataToPower(float_array_y, len(position_datay), sock_y, 80):
                print("y发送成功")
            else:
                print("y发送失败！！！")
            result_y = dll.QueryStatus(sock_y, 80)
            if result_y is not None:
                result_y_str = result_y.decode('utf-8')
                if result_y_str == "数据包发送失败" or result_y_str == "数据包接收失败":
                    print("扫描铁y数据处理失败")
                else:
                    fields = result_y_str.split(',')
                    # 转换为键值对
                    data = {}
                    for field in fields:
                        key, value = field.split('：')  # 中文冒号
                        data[key.strip()] = value.strip()
                    # 类型转换
                    data['电源状态'] = int(data['电源状态'], 16)  # 十六进制
                    data['电流'] = float(data['电流'])  # 浮点数
                    data['电压'] = float(data['电压'])  # 浮点数
                    print(data)
            else:
                print("获取扫描铁数据失败")
            dll.Statusstrfree()
        except Exception as e:
            print(f"发送扫描铁数据异常：{e}")

    def stop(self):
        """ 停止线程的循环 """
        self._running = False
        # self.opcua_tool.client.disconnect()


class PowerThread(QThread):
    power_x_status = pyqtSignal(str)
    power_y_status = pyqtSignal(str)
    power_x_electric = pyqtSignal(float)
    power_y_electric = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        while self._running:
            time.sleep(0.5)
            path = r'lib\\Powerlib.dll'
            # 调用扫描铁协议库
            dll = ctypes.WinDLL(path)
            # 定义C函数的原型
            SOCKET = ctypes.c_int
            dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(SOCKET)]
            dll.GetConnection.restype = ctypes.c_bool
            dll.QueryStatus.argtypes = [SOCKET, ctypes.c_ulong]
            dll.QueryStatus.restype = ctypes.c_char_p  # 返回值为 const char* 类型
            dll.Statusstrfree.restype = ctypes.c_void_p
            sock_x = SOCKET()
            sock_y = SOCKET()
            sock_pointer_x = ctypes.byref(sock_x)
            sock_pointer_y = ctypes.byref(sock_y)
            # 连接x扫描铁
            if dll.GetConnection(0x0A00184F, 30000, sock_pointer_x):
                print("x连接成功")
            else:
                print("x连接失败！！！")
                return
            # 监控扫描铁数据
            result_x = dll.QueryStatus(sock_x, 79)
            if result_x is not None:
                print(result_x)
                result_x_str = result_x.decode('utf-8')
                if result_x_str == "数据包发送失败" or result_x_str == "数据包接收失败":
                    print("扫描铁x数据处理失败")
                else:
                    fields = result_x_str.split(',')
                    # 转换为键值对
                    data = {}
                    for field in fields:
                        key, value = field.split('：')  # 中文冒号
                        data[key.strip()] = value.strip()
                    # 类型转换
                    data['电源状态'] = int(data['电源状态'], 16)  # 十六进制
                    data['电流'] = float(data['电流'])  # 浮点数
                    data['电压'] = float(data['电压'])  # 浮点数
                    self.power_x_electric.emit(data['电流'])
                    self.power_x_status.emit(data['电源状态'])
                dll.Statusstrfree()
            else:
                print("获取扫描铁数据失败")
            # 连接y扫描铁
            if dll.GetConnection(0x0A001850, 30000, sock_pointer_y):
                print("y连接成功")
            else:
                print("y连接失败！！！")
                return
            result_y = dll.QueryStatus(sock_y, 80)
            if result_y is not None:
                result_y_str = result_y.decode('utf-8')
                if result_y_str == "数据包发送失败" or result_y_str == "数据包接收失败":
                    print("扫描铁y数据处理失败")
                else:
                    fields = result_y_str.split(',')
                    # 转换为键值对
                    data = {}
                    for field in fields:
                        key, value = field.split('：')  # 中文冒号
                        data[key.strip()] = value.strip()
                    # 类型转换
                    data['电源状态'] = int(data['电源状态'], 16)  # 十六进制
                    data['电流'] = float(data['电流'])  # 浮点数
                    data['电压'] = float(data['电压'])  # 浮点数
                    self.power_y_electric.emit(data['电流'])
                    self.power_y_status.emit(data['电源状态'])
            else:
                print("获取扫描铁数据失败")
            dll.Statusstrfree()

        def stop(self):
            """ 停止线程的循环 """
            self._running = False


class TreatInfo:
    # MAX_LAYER_N = 256
    # MAX_SPOT_K = 16000
    SPOT_EXCHANGE_MAXNUM = 2
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.nozzle = 0
            cls._instance.layers = 0  # 总层数
            cls._instance.layers_index = 0  # 治疗层数标识位，当前计划从第几层开始
            cls._instance.spot_index = 0  # 点标识
            cls._instance.current_layer = 0  # 当前层
            cls._instance.energy = []
            cls._instance.dose = []
            cls._instance.ic2_dose = []
            cls._instance.dose_count = []
            cls._instance.pos_x = []
            cls._instance.pos_y = []
            cls._instance.ic1_count = 0
            cls._instance.ic2_count = 0
            cls._instance.ic3_count = 0
        return cls._instance
