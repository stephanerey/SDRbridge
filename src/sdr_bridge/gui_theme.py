"""Dark native-Qt theme for the SDRbridge v0.7 interface."""

from PyQt5 import QtCore, QtGui, QtWidgets


class SDRBridgeProxyStyle(QtWidgets.QProxyStyle):
    """Fusion style with high-contrast cyan arrows for dark controls."""

    def __init__(self) -> None:
        super().__init__(QtWidgets.QStyleFactory.create("Fusion"))

    def drawPrimitive(self, element, option, painter, widget=None):  # noqa: N802
        arrows = {
            QtWidgets.QStyle.PE_IndicatorArrowDown: False,
            QtWidgets.QStyle.PE_IndicatorArrowUp: True,
        }
        if element not in arrows:
            return super().drawPrimitive(element, option, painter, widget)
        rect = option.rect
        center = rect.center()
        half_width = max(3, min(5, rect.width() // 4))
        half_height = max(2, min(4, rect.height() // 5))
        if arrows[element]:
            points = (
                QtCore.QPoint(center.x() - half_width, center.y() + half_height),
                QtCore.QPoint(center.x() + half_width, center.y() + half_height),
                QtCore.QPoint(center.x(), center.y() - half_height),
            )
        else:
            points = (
                QtCore.QPoint(center.x() - half_width, center.y() - half_height),
                QtCore.QPoint(center.x() + half_width, center.y() - half_height),
                QtCore.QPoint(center.x(), center.y() + half_height),
            )
        color = QtGui.QColor("#39d5e4") if option.state & QtWidgets.QStyle.State_Enabled else QtGui.QColor("#61798b")
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QtGui.QPolygon(points))
        painter.restore()

DARK_STYLESHEET = r"""
QWidget {
    color: #dceaf4;
    background-color: #071522;
    font-family: "Segoe UI";
    font-size: 9pt;
}
QMainWindow, QDialog { background-color: #071522; }
QFrame[card="true"], QGroupBox {
    background-color: #102236;
    border: 1px solid #29465d;
    border-radius: 10px;
}
QFrame[scalePanel="true"] {
    background-color: #0b1c2c;
    border: 1px solid #29465d;
    border-radius: 7px;
}
QGroupBox {
    margin-top: 12px;
    padding: 14px 12px 10px 12px;
    font-weight: 650;
    color: #a9c0d3;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #a9c0d3;
}
QLabel[role="muted"] { color: #819db3; }
QLabel[role="metricTitle"] { color: #809db4; font-size: 8pt; font-weight: 650; }
QLabel[role="metricValue"] { color: #eef9ff; font-size: 12pt; font-weight: 700; }
QLabel[role="sectionTitle"] { color: #a9c0d3; font-size: 9pt; font-weight: 700; }
QLabel[role="success"] { color: #74e5b9; }
QLabel[role="warning"] { color: #ffcc78; }
QLabel[role="danger"] { color: #ff9dad; }
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #182e43;
    color: #e4f0f8;
    border: 1px solid #3a5267;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 22px;
    selection-background-color: #287fc9;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #39d5e4;
}
QComboBox::drop-down { border: 0; border-left: 1px solid #3a5267; width: 24px; }
QComboBox QAbstractItemView { background: #132a3e; border: 1px solid #35566e; selection-background-color: #246ca8; }
QPushButton, QToolButton {
    background: #17334c;
    color: #dceaf4;
    border: 1px solid #31546e;
    border-radius: 7px;
    padding: 6px 11px;
    font-weight: 600;
}
QPushButton:hover, QToolButton:hover { background: #1d405e; border-color: #4481a7; }
QPushButton:pressed, QToolButton:pressed, QPushButton:checked, QToolButton:checked { background: #246fae; border-color: #42bcec; }
QPushButton:disabled, QToolButton:disabled { color: #61798b; background: #102438; border-color: #243f53; }
QPushButton[accent="true"], QToolButton[accent="true"] { background: #2477d4; border-color: #429bef; color: white; }
QPushButton[success="true"], QToolButton[success="true"] { background: #116947; border-color: #168a60; color: white; }
QPushButton[pending="true"], QToolButton[pending="true"] { background: #815b12; border-color: #d69b25; color: white; }
QPushButton[danger="true"] { background: #542b39; border-color: #8b4759; color: #ffb4c0; }
QTabWidget::pane { border: 0; background: #071522; }
QTabBar::tab {
    color: #98aec0;
    background: transparent;
    padding: 10px 18px;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    min-width: 105px;
    font-weight: 600;
}
QTabBar::tab:selected { color: #eef9ff; background: #122940; border-color: #2b506e; border-bottom-color: #38cffa; }
QTabBar::tab:hover:!selected { color: #c6d9e8; background: #0e2235; }
QTableWidget {
    background: #102236;
    alternate-background-color: #0d1d2d;
    color: #d5e5f1;
    border: 1px solid #29465d;
    border-radius: 8px;
    gridline-color: #274257;
    selection-background-color: #1e5278;
}
QHeaderView::section {
    background: #173047;
    color: #91adc2;
    border: 0;
    border-bottom: 1px solid #38566c;
    padding: 7px;
    font-size: 8pt;
    font-weight: 700;
}
QScrollBar:vertical { background: #0d1d2d; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #31536a; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSlider::groove:horizontal { height: 4px; background: #52606a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #3ad3e2; border-radius: 2px; }
QSlider::handle:horizontal { background: #39d5e4; width: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::groove:vertical { width: 4px; background: #52606a; border-radius: 2px; }
QSlider::sub-page:vertical { background: #3ad3e2; border-radius: 2px; }
QSlider::handle:vertical { background: #39d5e4; height: 14px; margin: 0 -5px; border-radius: 7px; }
QCheckBox { color: #bad0e0; spacing: 7px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; }
QCheckBox::indicator:unchecked { background: #0b1c2c; border: 1px solid #6f91a8; }
QCheckBox::indicator:unchecked:hover { background: #132f45; border-color: #39d5e4; }
QCheckBox::indicator:checked { background: #28cdbf; border: 1px solid #61f2df; border-radius: 3px; }
QCheckBox::indicator:disabled { background: #102438; border-color: #385166; }
QMenu { background: #102236; border: 1px solid #31536a; padding: 5px; }
QMenu::item { padding: 7px 24px; border-radius: 4px; }
QMenu::item:selected { background: #1e5278; }
QStatusBar { color: #87a3b8; background: #081827; }
QToolTip { color: #edf8ff; background: #18334a; border: 1px solid #3d637e; }
"""
