from PyQt5.QtWidgets import QWidget, QMessageBox, QProgressBar
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIntValidator
from opcua_connect.OPCUAConnection import OPCUAConnectionManager
import configparser
import os
import json
from datetime import datetime
import pydicom
import ctypes
from beam.beam_widget_1 import Ui_Form as Beam_ui
from beam.beam_threads import TreatInfo, BeamThread, PowerThread


class BeamData(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        pydicom.datadict.add_dict_entries({0x300a0397: ('FL', '1-n', "Num Shoot", '', 'NumShoot')})
        self.beam_thread = None
        self.Flag = None
        self.layer_info_dict = None
        self.filename_choose = None
        self.pssc_dict = {}
        self.dose_spot = []
        self.pos_x_spot = []
        self.pos_y_spot = []
        self.position_x1 = []
        self.position_x2 = []
        self.position_y1 = []
        self.position_y2 = []
        self.pos_num = []

        self.ui = Beam_ui()
        self.ui.setupUi(parent)

        # self.ui.groupBox_3.move(20, 20)
        self.power_status_signal = PowerThread()
        # 选择计划文件
        self.cwd = os.getcwd()  # 获取当前程序文件位置
        self.ui.import_plan.clicked.connect(self.slot_btn_choose_file)
        # 加载计划
        self.ui.pushButton_load_plan.clicked.connect(self.load_plan)
        # 申请束流
        self.ui.pushButton_beam.clicked.connect(self.apply_beam)
        # 设置QIntValidator以仅允许整数输入
        self.set_validator()
        # 获取参数
        self.ui.pushButton_get_argu.clicked.connect(self.get_argument)
        # 代入参数
        self.ui.pushButton_set_argu.clicked.connect(self.set_argument)
        # 保存参数
        self.ui.pushButton_save_argu.clicked.connect(self.save_argument)
        # 扫描铁开机
        self.ui.pushButton_on.clicked.connect(self.pssc_on)
        # 扫描铁关机
        self.ui.pushButton_off.clicked.connect(self.pssc_off)
        # 扫描铁复位
        self.ui.pushButton_reset.clicked.connect(self.pssc_reset)
        # 扫描铁归零
        self.ui.pushButton_zero.clicked.connect(self.pssc_zero)
        # 扫描铁x电流值
        self.power_status_signal.power_x_electric.connect(self.set_x_electric)
        # 扫描铁y电流值
        self.power_status_signal.power_y_electric.connect(self.set_y_electric)
        # 扫描铁x状态
        self.power_status_signal.power_x_status.connect(self.set_x_status)
        # 扫描铁y状态
        self.power_status_signal.power_y_status.connect(self.set_y_status)
        # 两个复选框绑定信号到槽函数
        self.ui.checkBox_test.stateChanged.connect(self.checkbox_test_changed)
        self.ui.checkBox_tcs.stateChanged.connect(self.checkbox_tcs_changed)

        # 读取配置文件 TODO暂时放在这里，后续再改变位置
        path = r'config\opcua_node.ini'
        self.config = configparser.ConfigParser()
        self.config.read(path, encoding='utf-8')
        # self.power_status_signal.start()

    def slot_btn_choose_file(self):
        self.filename_choose, _ = \
            QtWidgets.QFileDialog.getOpenFileName(self,
                                                  "选取文件",
                                                  self.cwd,
                                                  "Text Files(*.dcm);;All Files(*)")  # 设置文件扩展名过滤,用双分号间隔
        if self.filename_choose == "":
            print("取消选择\n")
            return
        print(f"你选择的文件为：{self.filename_choose}")
        self.ui.textEdit_output.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 计划导入成功！")

    def load_plan(self):
        try:
            treat_info = TreatInfo()
            if self.ui.checkBox_test.isChecked():
                # 打开dcm文件并存入字典
                if self.filename_choose:
                    ds = pydicom.dcmread(self.filename_choose)
                    # TODO 读取当前射野所有层信息，先默认为1，看了pydicom的API，没找到如何取
                    # 获取当前射野的所有层信息，将数据存入字典
                    self.layer_info_dict = ds[(0x300a, 0x03a2)][0][(0x300a, 0x03a8)].to_json_dict(None, None)
                    # self.layer_info_dict = ds[(0x300a, 0x03a2)][0][(0x300a, 0x03a8)][0][(0x300a, 0x0394)].to_json_dict(None, None)
                    # print(self.layer_info_dict["Value"][0]["00080005"]["Value"]) # Value列表中77个元素 字典->列表->字典->字典

                    # 扫描点位置图
                    # print(self.layer_info_dict["Value"][0]["300A0394"]["Value"])
                    # 扫描点剂量
                    # print(self.layer_info_dict["Value"][3]["300A0396"]["Value"])
                    # 当前层能量
                    # print(self.layer_info_dict["Value"][2]['300A0114']['Value'][0])  # 最后一个[0]表示取出列表中的唯一元素

                    # 北大计划的光栅数据，我现在先处理这个了^_^
                    # print(self.layer_info_dict["Value"][0]["300A011A"]["Value"][0]["300A011C"]["Value"])
                    # print(f"{sys.getsizeof(self.layer_info_dict) / 1024}KB")

                    '''给数据类赋值'''
                    treat_info.layers = len(self.layer_info_dict["Value"])  # 目前自己计算总层数
                    ic2dose = 0  # 中间变量，记录IC2的数据
                    # 每一层能量energy
                    for i in range(treat_info.layers):
                        if i % 2 == 0:
                            # treat_info.energy[i] = self.layer_info_dict["Value"][i]['300A0114']['Value'][0]
                            treat_info.energy.append(self.layer_info_dict["Value"][i]['300A0114']['Value'][0])
                            # 每一层的每一个点的剂量
                            for index, value in enumerate(self.layer_info_dict["Value"][i]["300A0396"]["Value"]):
                                self.dose_spot.append(f"{value:.3f}")  # 保留3位小数赋值给数组
                                # treat_info.dose[i][index] = f"{value:.3f}"  # 保留3位小数赋值给数组
                                ic2dose = ic2dose + value
                            # treat_info.dose_count[i] = index  # 每一层点个数
                            treat_info.dose_count.append(index + 1)  # 每一层点个数
                            # treat_info.ic2_dose[i] = f"{ic2dose:.3f}"  # 每一层IC2
                            treat_info.ic2_dose.append(f"{ic2dose:.3f}")  # 每一层IC2
                            ic2dose = 0
                            # 计算电源数据
                            for index, value in enumerate(self.layer_info_dict["Value"][i]["300A0394"]["Value"]):
                                # Map中的数据X、Y交替
                                if index % 2 == 0:  # X
                                    self.pos_x_spot.append(float(f"{value:.3f}"))
                                    # treat_info.pos_x[i][index // 2] = float(f"{value:.3f}")
                                else:
                                    self.pos_y_spot.append(float(f"{value:.3f}"))
                                    # treat_info.pos_y[i][index // 2 + 1] = float(f"{value:.3f}")
                            treat_info.dose.append(self.dose_spot.copy())
                            treat_info.pos_x.append(self.pos_x_spot.copy())
                            treat_info.pos_y.append(self.pos_y_spot.copy())
                            self.pos_num.append((index + 1) // 2)
                    # print(self.pos_num)
                    # print(treat_info.dose[2])
                    print(treat_info.dose[0])
                    print(self.layer_info_dict["Value"][0]["300A0394"]["Value"])
                else:
                    QMessageBox.information(self, "提示", "计划文件不存在，请先导入！", QMessageBox.Ok)
                    return
                self.ui.textEdit_output.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 计划加载成功！")
            else:
                # pass
                url_beam = self.config.get('Room1', 'OPCUA_SERVER_BEAM')
                conn_beam = OPCUAConnectionManager.get_connection(url_beam)
                client_beam = conn_beam.get_client()
                dds_data_node = f"ns = 2; s = {self.config.get('Room1Cmd', 'WR_STRING_DDSDATA')}"
                dds_data = client_beam.get_node(dds_data_node).get_value()
                list_data = json.loads(dds_data)
                # 解析数据
                for energy_data in list_data:
                    # 每层能量
                    treat_info.energy.append(energy_data[0])
                    # 每层电源数据
                    for i, position in enumerate(energy_data[1]):
                        if i % 2 == 0:
                            treat_info.pos_x.append(position)
                        else:
                            treat_info.pos_y.append(position)
                    # TODO 暂时没计算KB值
                    self.position_x2.append(treat_info.pos_x.copy())
                    self.position_y2.append(treat_info.pos_y.copy())
                    # 每层点个数
                    treat_info.dose_count.append(len(energy_data[2]))
                    treat_info.dose.append(energy_data[2])
                    treat_info.ic2_dose.append(sum(energy_data[2]))
                    # 总层数
                    treat_info.layers = len(list_data) * 2
        except Exception as e:
            print(f"导入计划发生错误：{e}")

    def apply_beam(self):
        # 更新总层数和总点数
        treat_info = TreatInfo()
        self.ui.label_total_spot.setText(str(treat_info.dose_count[0]))
        self.ui.label_total_layer.setText(str(treat_info.layers // 2))
        self.ui.label_total_spot_2.setText(str(treat_info.dose_count[0]))
        self.ui.label_total_layer_2.setText(str(treat_info.layers // 2))
        self.ui.staticPercentProgressBarSpot.MaxValue = treat_info.dose_count[0]
        self.ui.staticPercentProgressBarLayer.MaxValue = treat_info.layers // 2
        try:
            self.beam_thread = beam_thread = BeamThread(self.position_x2, self.position_y2)
            # 更新剂量
            beam_thread.spot_signal.connect(self.update_current_spot)
            beam_thread.layel_signal.connect(self.update_current_layer)
            beam_thread.total_spot_signal.connect(self.update_total_spot)
            beam_thread.ic1_signal.connect(self.update_ic1)
            beam_thread.ic2_signal.connect(self.update_ic2)
            beam_thread.request_beam_signal.connect(self.set_enable)
            # beam_thread.ic3_signal.connect(self.update_ic3)
            beam_thread.start()
        except Exception as e:
            print(e)
        # TODO 需要线程停止方法
        # TODO self.ui.pushButton_beam.setEnabled(False)  # 放束过程中申请束流按钮置为无效

    def set_validator(self):
        self.ui.lineEdit_kx.setValidator(QIntValidator(self.ui.lineEdit_kx))
        self.ui.lineEdit_kx_2.setValidator(QIntValidator(self.ui.lineEdit_kx_2))
        self.ui.lineEdit_bx.setValidator(QIntValidator(self.ui.lineEdit_bx))
        self.ui.lineEdit_bx_2.setValidator(QIntValidator(self.ui.lineEdit_bx_2))
        self.ui.lineEdit_ky.setValidator(QIntValidator(self.ui.lineEdit_ky))
        self.ui.lineEdit_ky_2.setValidator(QIntValidator(self.ui.lineEdit_ky_2))
        self.ui.lineEdit_by.setValidator(QIntValidator(self.ui.lineEdit_by))
        self.ui.lineEdit_by_2.setValidator(QIntValidator(self.ui.lineEdit_by_2))
        self.ui.lineEdit_current_engry.setValidator(QIntValidator(self.ui.lineEdit_current_engry))

    # 获取lineedit输入数据
    def get_argument(self):
        try:
            self.current_engry = self.ui.lineEdit_current_engry.text()
            if self.current_engry == "":
                QMessageBox.information(self, "提示", "请输入当前能量", QMessageBox.Ok)
                return
            temp = self.ui.lineEdit_kx.text()
            if temp == '':
                data_kx = 0
            else:
                data_kx = int(temp)
            temp = self.ui.lineEdit_kx_2.text()
            if temp == '':
                data_kx_2 = 0
            else:
                data_kx_2 = int(temp)
            temp = self.ui.lineEdit_bx.text()
            if temp == '':
                data_bx = 0
            else:
                data_bx = int(temp)
            temp = self.ui.lineEdit_bx_2.text()
            if temp == '':
                data_bx_2 = 0
            else:
                data_bx_2 = int(temp)
            temp = self.ui.lineEdit_ky.text()
            if temp == '':
                data_ky = 0
            else:
                data_ky = int(temp)
            temp = self.ui.lineEdit_ky_2.text()
            if temp == '':
                data_ky_2 = 0
            else:
                data_ky_2 = int(temp)
            temp = self.ui.lineEdit_by.text()
            if temp == '':
                data_by = 0
            else:
                data_by = int(temp)
            temp = self.ui.lineEdit_by_2.text()
            if temp == '':
                data_by_2 = 0
            else:
                data_by_2 = int(temp)
            self.pssc_dict[self.current_engry] = [data_kx, data_kx_2, data_bx, data_bx_2, data_ky, data_ky_2, data_by,
                                                  data_by_2]

            # print(self.pssc_dict)
        except Exception as e:
            print(e)

    # 将K、B参数代入，计算电源需要的数据
    def set_argument(self):
        try:
            path = r'config\pssc_data.txt'
            treat_info = TreatInfo()
            with open(path, encoding='utf-8') as file:
                content = {}
                # 校验文件是否为空
                if os.stat(path).st_size > 0:
                    content = json.load(file)
                # lineedit中没有输入K、B值故用当前能量保存在文件中的K、B
                for i in range(treat_info.layers // 2):
                    current_engry = content.get(f'"{treat_info.energy[i]}"', None)
                    if current_engry is None:
                        continue
                    self.position_x1.clear()
                    self.position_y1.clear()
                    for index in range(self.pos_num[i]):
                        value = treat_info.pos_x[i][index]
                        if value > 0:
                            self.position_x1.append(content[current_engry][0] * value + content[current_engry][2])
                        elif value < 0:
                            self.position_x1.append(content[current_engry][1] * value + content[current_engry][3])
                        else:
                            self.position_x1.append((content[current_engry][2] + content[current_engry][3]) / 2)
                    for index in range(self.pos_num[i]):
                        value = treat_info.pos_y[i][index]
                        if value > 0:
                            self.position_y1.append(content[current_engry][4] * value + content[current_engry][6])
                        elif value < 0:
                            self.position_y1.append(content[current_engry][5] * value + content[current_engry][7])
                        else:
                            self.position_y1.append((content[current_engry][6] + content[current_engry][7]) / 2)
                self.position_x2.append(self.position_x1.copy())
                self.position_y2.append(self.position_y1.copy())
        except Exception as e:
            print(f"代入参数异常：{e}")

    # 保存K、B
    def save_argument(self):
        # self.get_argument()
        path = r'config\pssc_data.txt'
        try:
            if not os.path.isfile(path):
                # 文件不存在直接保存
                with open(path, "w", encoding='utf-8') as file:
                    json.dump(self.pssc_dict, file, ensure_ascii=False, indent=4)
            else:
                # 文件存在，需要在当前文件追加或修改数据
                with open(path, "r", encoding="utf-8") as file:
                    content = {}
                    # 校验文件是否为空
                    if os.stat(path).st_size > 0:
                        content = json.load(file)
                # 更新内容
                content[self.ui.lineEdit_current_engry.text()] = self.pssc_dict[self.current_engry]

                # 重新写入文件
                with open(path, "w", encoding="utf-8") as file:
                    json.dump(content, file, ensure_ascii=False, indent=4)
        except Exception as e:
            print(e)

    def update_current_spot(self, current_spot):
        self.ui.label_current_spot.setText(str(current_spot))
        self.ui.staticPercentProgressBarSpot.setValue(current_spot)

    def update_current_layer(self, current_layer):
        self.ui.label_current_layer.setText(str(current_layer))
        self.ui.staticPercentProgressBarLayer.setValue(current_layer)

    def update_total_spot(self, total_spot):
        self.ui.label_total_spot.setText(str(total_spot))
        self.ui.label_total_spot_2.setText(str(total_spot))
        self.ui.staticPercentProgressBarSpot.MaxValue = total_spot

    def update_ic1(self, ic1):
        # self.ui.progressBar_ic1.setValue(ic1)
        ...

    def update_ic2(self, ic2):
        # self.ui.progressBar_ic2.setValue(ic2)
        ...

    def set_enable(self, status):
        self.ui.pushButton_beam.setEnabled(status)

    def pssc_on(self):
        path = r'lib\Powerlib.dll'
        # 调用扫描铁协议库
        dll = ctypes.WinDLL(path)
        # 定义C函数的原型
        SOCKET = ctypes.c_int
        dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(SOCKET)]
        dll.GetConnection.restype = ctypes.c_bool
        dll.OpenPower.argtypes = [SOCKET, ctypes.c_ulong]
        dll.OpenPower.restype = ctypes.c_bool

        sock_x = SOCKET()
        sock_y = SOCKET()
        sock_pointer_x = ctypes.byref(sock_x)
        sock_pointer_y = ctypes.byref(sock_y)
        # 连接x扫描铁
        if dll.GetConnection(0x0A00184F, 30000, sock_pointer_x):
            print("扫描铁开机x连接成功")
        else:
            print("扫描铁开机x连接失败！！！")
            return
        if dll.OpenPower(sock_x, 79):
            print("扫描铁x开机成功")
        else:
            print("扫描铁x开机失败")
        # 连接y扫描铁
        if dll.GetConnection(0x0A001850, 30000, sock_pointer_y):
            print("扫描铁开机y连接成功")
        else:
            print("扫描铁开机y连接失败！！！")
            return
        if dll.OpenPower(sock_y, 80):
            print("扫描铁y开机成功")
        else:
            print("扫描铁y开机失败")

    def pssc_off(self):
        path = r'lib\Powerlib.dll'
        # 调用扫描铁协议库
        dll = ctypes.WinDLL(path)
        # 定义C函数的原型
        SOCKET = ctypes.c_int
        dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(SOCKET)]
        dll.GetConnection.restype = ctypes.c_bool
        dll.ClosePower.argtypes = [SOCKET, ctypes.c_ulong]
        dll.ClosePower.restype = ctypes.c_bool

        sock_x = SOCKET()
        sock_y = SOCKET()
        sock_pointer_x = ctypes.byref(sock_x)
        sock_pointer_y = ctypes.byref(sock_y)
        # 连接x扫描铁
        if dll.GetConnection(0x0A00184F, 30000, sock_pointer_x):
            print("扫描铁关机x连接成功")
        else:
            print("扫描铁关机x连接失败！！！")
            return
        if dll.ClosePower(sock_x, 79):
            print("扫描铁x关机成功")
        else:
            print("扫描铁x关机失败")
        # 连接y扫描铁
        if dll.GetConnection(0x0A001850, 30000, sock_pointer_y):
            print("扫描铁关机y连接成功")
        else:
            print("扫描铁关机y连接失败！！！")
            return
        if dll.ClosePower(sock_y, 80):
            print("扫描铁y关机成功")
        else:
            print("扫描铁y关机失败")

    def pssc_reset(self):
        path = r'lib\Powerlib.dll'
        # 调用扫描铁协议库
        dll = ctypes.WinDLL(path)
        # 定义C函数的原型
        SOCKET = ctypes.c_int
        dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(SOCKET)]
        dll.GetConnection.restype = ctypes.c_bool
        dll.ResetPower.argtypes = [SOCKET, ctypes.c_ulong]
        dll.ResetPower.restype = ctypes.c_bool

        sock_x = SOCKET()
        sock_y = SOCKET()
        sock_pointer_x = ctypes.byref(sock_x)
        sock_pointer_y = ctypes.byref(sock_y)
        # 连接x扫描铁
        if dll.GetConnection(0x0A00184F, 30000, sock_pointer_x):
            print("扫描铁复位x连接成功")
        else:
            print("扫描铁复位x连接失败！！！")
            return
        if dll.ResetPower(sock_x, 79):
            print("扫描铁x复位成功")
        else:
            print("扫描铁x复位失败")
        # 连接y扫描铁
        if dll.GetConnection(0x0A001850, 30000, sock_pointer_y):
            print("扫描铁复位y连接成功")
        else:
            print("扫描铁复位y连接失败！！！")
            return
        if dll.ResetPower(sock_y, 80):
            print("扫描铁y复位成功")
        else:
            print("扫描铁y复位失败")

    def pssc_zero(self):
        path = r'lib\Powerlib.dll'
        # 调用扫描铁协议库
        dll = ctypes.WinDLL(path)
        # 定义C函数的原型
        SOCKET = ctypes.c_int
        dll.GetConnection.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(SOCKET)]
        dll.GetConnection.restype = ctypes.c_bool
        dll.SetDC.argtypes = [ctypes.c_float, SOCKET, ctypes.c_ulong]
        dll.SetDC.restype = ctypes.c_bool

        sock_x = SOCKET()
        sock_y = SOCKET()
        sock_pointer_x = ctypes.byref(sock_x)
        sock_pointer_y = ctypes.byref(sock_y)
        # 连接x扫描铁
        if dll.GetConnection(0x0A00184F, 30000, sock_pointer_x):
            print("扫描铁归零x连接成功")
        else:
            print("扫描铁归零x连接失败！！！")
            return
        if dll.SetDC(0.0, sock_x, 79):
            print("扫描铁x归零成功")
        else:
            print("扫描铁x归零失败")
        # 连接y扫描铁
        if dll.GetConnection(0x0A001850, 30000, sock_pointer_y):
            print("扫描铁归零y连接成功")
        else:
            print("扫描铁归零y连接失败！！！")
            return
        if dll.SetDC(0.0, sock_y, 80):
            print("扫描铁y归零成功")
        else:
            print("扫描铁y归零失败")

    def set_x_electric(self, value):
        # self.ui.label_x_value.setText(str(value))
        pass

    def set_y_electric(self, value):
        # self.ui.label_y_value.setText(str(value))
        pass

    def set_x_status(self, status):
        # self.ui.label_x_status.setText(status)
        pass

    def set_y_status(self, status):
        # self.ui.label_y_status.setText(status)
        pass

    def checkbox_test_changed(self, state):
        if state == 2:
            self.ui.checkBox_tcs.setChecked(False)
            self.ui.import_plan.setEnabled(True)

    def checkbox_tcs_changed(self, state):
        if state == 2:
            self.ui.checkBox_test.setChecked(False)
            self.ui.import_plan.setEnabled(False)

    def close_beam_thread(self):
        print("关闭窗口")
        # 在关闭窗口时停止线程，断开连接
        if self.beam_thread and self.beam_thread.isRunning():
            print("停止线程")
            self.beam_thread.stop()  # 停止线程
            self.beam_thread.wait()  # 等待线程退出
        # OPCUAConnectionManager.close_all()