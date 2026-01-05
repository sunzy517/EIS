import sys
import random
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, \
    QSizePolicy, QSpinBox, QPushButton, QSpacerItem
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt, QRectF


class SingleBarWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.setMinimumHeight(400)  # 设置最小高度
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 确保占据可用空间
        self.rect_data_x = [None] * 34
        self.rect_data_y = [None] * 34
        self.default_color = QColor(100, 150, 200)  # 初始颜色
        self.selected_color = QColor(200, 100, 150)  # 被选中后的颜色
        self.is_bar_selected = [True] * 68  # 是否被选中
        # self.data_x = [random.randint(10, 50) for _ in range(34)]
        # self.data_y = [random.randint(10, 50) for _ in range(34)]
        self.mlcinfo = MlcInfo()
        self.data_x = self.mlcinfo.temp_x
        self.data_y = self.mlcinfo.temp_y

    def draw_bars(self, painter, start_index, data, reverse=False):
        window_width = self.width()
        window_height = self.height()
        max_width = window_width
        bar_height = window_height / len(data)

        for i, value in enumerate(data):
            bar_x = 0 if not reverse else window_width - (value / 100) * max_width
            bar_y = i * bar_height
            bar_width = (value / 100) * max_width
            rect = QRectF(bar_x, bar_y, bar_width, bar_height)
            painter.setBrush(self.default_color if self.is_bar_selected[start_index + i]
                             else self.selected_color)
            painter.drawRect(rect)
            if start_index + i < 34:
                self.rect_data_x[i] = rect
            else:
                self.rect_data_y[i] = rect

    def paintEvent(self, event):
        # 创建 QPainter 对象
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_bars(painter, 0, self.data_x, reverse=False)
        self.draw_bars(painter, 34, self.data_y, reverse=True)
        # 确保绘图完成后释放资源
        painter.end()

    # 鼠标点击方法，可以得到鼠标点击坐标
    def mousePressEvent(self, event):
        # 检查鼠标点击是否在矩形内
        for i in range(68):
            if i < 34:
                if self.rect_data_x[i].contains(event.pos()):
                    self.is_bar_selected[i] = False
                else:
                    self.is_bar_selected[i] = True
            else:
                if self.rect_data_y[i - 34].contains(event.pos()):
                    self.is_bar_selected[i] = False
                else:
                    self.is_bar_selected[i] = True
        self.update()


class CustomSpinBox(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        # 创建 QSpinBox 控件
        self.spin_box = QSpinBox(self)
        self.spin_box.setMinimum(1)  # 设置最小值
        self.spin_box.setMaximum(100)  # 设置最大值
        self.spin_box.setValue(0)  # 设置默认值
        self.spin_box.setFont(QFont("Arial", 14, QFont.Bold))
        # 设置 QSS样式表，给 spin_box设置圆角
        self.spin_box.setStyleSheet("""border-radius: 4px;""")
        self.spin_box.setButtonSymbols(QSpinBox.NoButtons)
        layout.addWidget(self.spin_box)

        # 创建按钮
        self.button = QPushButton("加载值", self)
        layout.addWidget(self.button)

        # 创建左右按钮控制矩形长度
        self.button1 = QPushButton("←", self)
        layout.addWidget(self.button1)
        self.button2 = QPushButton("→", self)
        layout.addWidget(self.button2)
        # 水平方向伸展，垂直方向不会伸展
        spacer = QSpacerItem(20, 40, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer)
        self.button_load_current = QPushButton("加载当前光栅", self)
        layout.addWidget(self.button_load_current)
        self.setLayout(layout)


class MlcInfo:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.x_coordinate = []
            cls._instance.y_coordinate = []
            cls._instance.temp_x = [0] * 34
            cls._instance.temp_y = [0] * 34
        return cls._instance