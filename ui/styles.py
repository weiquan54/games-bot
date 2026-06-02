"""PyQt5 stylesheets for the floating window."""

FLOATING_WINDOW_STYLE = """
QWidget#floatingWindow {
    background-color: #2d2d3a;
    border: 1px solid #505060;
    border-radius: 8px;
}

QPushButton {
    background-color: #3c3c50;
    color: #e0e0e0;
    border: 1px solid #555568;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #505068;
    border: 1px solid #707088;
}
QPushButton:pressed {
    background-color: #323246;
}
QPushButton#btnStart {
    background-color: #3ca050;
}
QPushButton#btnStart:hover {
    background-color: #46be5a;
}
QPushButton#btnStop {
    background-color: #b43c3c;
}
QPushButton#btnStop:hover {
    background-color: #d24646;
}
QPushButton#btnExit {
    background-color: #6b3030;
    font-size: 14px;
    padding: 2px 6px;
    border-radius: 3px;
}
QPushButton#btnExit:hover {
    background-color: #904040;
}

QLabel {
    color: #d0d0d0;
    font-size: 12px;
}

QLineEdit {
    background-color: #282837;
    color: #e0e0e0;
    border: 1px solid #555568;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 12px;
}

QComboBox {
    background-color: #282837;
    color: #e0e0e0;
    border: 1px solid #555568;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 12px;
}
QComboBox:hover {
    border: 1px solid #707088;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #282837;
    color: #e0e0e0;
    selection-background-color: #464664;
}

QLabel#statusLabel {
    font-size: 12px;
    font-weight: bold;
}
"""
