import sys
import random
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, \
    QSizePolicy, QGroupBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QRectF
from beam.beam_widget_1 import Ui_Form as BeamUI
from beam.beam import BeamData
from mlc.mlc import MLC
from scatter.scatter import ScatterControl


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("调试软件")
        self.setGeometry(100, 100, 650, 800)  # 设置窗口初始大小
        # 整体布局
        layout = QHBoxLayout(self)
        # 散射体和束流控件布局
        vlayout = QVBoxLayout()
        # 束流相关控件
        group_beam = QGroupBox("束流", self)
        # beam_ui = BeamUI()
        # beam_ui.setupUi(group_beam)
        # vlayout.addWidget(group_beam)
        beam = BeamData(group_beam)
        vlayout.addWidget(group_beam)
        # 散射体相关控件
        group_scatter = QGroupBox("散射体", self)
        scatter_widget = ScatterControl(group_scatter)
        # scatter_widget.setupUi(group_scatter)
        vlayout.addWidget(group_scatter)
        layout.addLayout(vlayout)
        # 光栅
        groupbox_mlc = QGroupBox("光栅", self)
        mlc_layout = QVBoxLayout(groupbox_mlc)
        # mwidget = QWidget()
        # button_ui = MlcButtonUI(mwidget)
        # button_ui.setupUi(mwidget)
        # button_widget = CustomSpinBox()
        # bar_widget = SingleBarWidget()

        # 不用self，mlc中加载的数据被回收了
        self.mlc = MLC()
        mlc_layout.addWidget(self.mlc.mwidget)
        mlc_layout.addWidget(self.mlc.button_widget)
        mlc_layout.addWidget(self.mlc.bar_widget)
        layout.addWidget(groupbox_mlc)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())