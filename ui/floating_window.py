"""Main floating window UI — collapsible, multi-action sequential click control."""

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QApplication, QListWidget, QListWidgetItem,
    QAbstractItemView, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

logger = logging.getLogger("ui")

from ui.styles import FLOATING_WINDOW_STYLE
from ui.calibrator import CalibratorOverlay
from engine.clicker import ClickEngine
from config.manager import ConfigManager


class FloatingWindow(QWidget):
    def __init__(self, config: ConfigManager, click_engine: ClickEngine):
        super().__init__()
        self.config = config
        self.engine = click_engine
        self._collapsed = config.collapsed
        self._status_colors = {
            "idle": "#a0a0a0",
            "running": "#60d060",
            "clicked": "#80e0ff",
            "notfound": "#ffa040",
            "stopped": "#ff6060",
        }

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("floatingWindow")

        self._build_ui()
        self._apply_styles()
        self._connect_signals()
        self._restore_geometry()
        self._populate_action_list()

        # Status poll timer
        self._poll = QTimer()
        self._poll.timeout.connect(self._update_status)
        self._poll.start(200)

    # ---- Build UI ----

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

        # -- Top row: controls --
        top = QHBoxLayout()
        top.setSpacing(6)

        self.btn_capture = QPushButton("📷")
        self.btn_capture.setFixedWidth(36)
        self.btn_capture.setToolTip("截取新模板并添加到列表")

        self.btn_start = QPushButton("▶ 运行")
        self.btn_start.setObjectName("btnStart")
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)

        self.status_label = QLabel("● 空闲")
        self.status_label.setObjectName("statusLabel")

        self.btn_exit = QPushButton("✕")
        self.btn_exit.setObjectName("btnExit")
        self.btn_exit.setFixedWidth(28)
        self.btn_exit.setToolTip("退出程序")

        top.addWidget(self.btn_capture)
        top.addWidget(self.btn_start)
        top.addWidget(self.btn_stop)
        top.addStretch()
        top.addWidget(self.btn_exit)
        self.main_layout.addLayout(top)

        # -- Status panel (2-column grid) --
        self.status_frame = QWidget()
        self.status_frame.setObjectName("statusFrame")
        sf = QHBoxLayout(self.status_frame)
        sf.setContentsMargins(4, 2, 4, 2)
        sf.setSpacing(0)

        # Left: icon + text stacked
        iv = QVBoxLayout()
        iv.setSpacing(0)
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("font-size: 20px; color: #66bb6a;")
        self.status_text = QLabel("空闲")
        self.status_text.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.status_text.setObjectName("statusText")
        iv.addWidget(self.status_icon)
        iv.addWidget(self.status_text)
        sf.addLayout(iv)
        sf.addSpacing(10)

        # Right: action name (top) + progress (bottom)
        rv = QVBoxLayout()
        rv.setSpacing(0)
        self.status_action_name = QLabel("")
        self.status_action_name.setStyleSheet("font-size: 13px; font-weight: bold; color: #60d060;")
        self.status_action_name.setObjectName("statusActionName")
        self.status_action_name.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.status_progress = QLabel("")
        self.status_progress.setStyleSheet("font-size: 11px; color: #cccccc;")
        self.status_progress.setObjectName("statusProgress")
        self.status_progress.setAlignment(Qt.AlignRight | Qt.AlignTop)
        rv.addWidget(self.status_action_name)
        rv.addWidget(self.status_progress)
        sf.addStretch()
        sf.addLayout(rv)

        self.main_layout.addWidget(self.status_frame)

        # -- Config panel --
        self.config_panel = QWidget()
        cfg = QVBoxLayout(self.config_panel)
        cfg.setContentsMargins(0, 0, 0, 0)
        cfg.setSpacing(4)

        # Threshold row
        row_thresh = QHBoxLayout()
        row_thresh.addWidget(QLabel("阈值:"))
        self.threshold_edit = QLineEdit(f"{self.config.threshold:.2f}")
        self.threshold_edit.setFixedWidth(50)
        row_thresh.addWidget(self.threshold_edit)
        row_thresh.addStretch()
        cfg.addLayout(row_thresh)

        # Round interval row
        row_rint = QHBoxLayout()
        row_rint.addWidget(QLabel("轮次间隔:"))
        self.round_interval_edit = QLineEdit(str(self.config.round_interval))
        self.round_interval_edit.setFixedWidth(50)
        row_rint.addWidget(self.round_interval_edit)
        row_rint.addWidget(QLabel("秒"))
        row_rint.addStretch()
        cfg.addLayout(row_rint)

        # ---- Action list header ----
        header = QHBoxLayout()
        header.addWidget(QLabel("点击顺序列表:"))
        cfg.addLayout(header)

        # Action list widget
        self.action_list = QListWidget()
        self.action_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.action_list.setDefaultDropAction(Qt.MoveAction)
        self.action_list.setMinimumHeight(120)
        self.action_list.setMaximumHeight(200)
        cfg.addWidget(self.action_list)

        # Template capture buttons
        btn_row = QHBoxLayout()
        self.btn_add_template = QPushButton("+ 截取模板添加")
        self.btn_add_template.setObjectName("btnAddAction")
        btn_row.addWidget(self.btn_add_template)
        btn_row.addStretch()
        cfg.addLayout(btn_row)

        self.main_layout.addWidget(self.config_panel)

        # -- Collapse / expand toggle --
        self.toggle_btn = QPushButton("▲ 收起")
        self.toggle_btn.setFixedHeight(20)
        self.toggle_btn.setStyleSheet("font-size: 10px; padding: 0px;")
        self.main_layout.addWidget(self.toggle_btn)

        self.setFixedWidth(380)
        self._update_collapsed()

    def _apply_styles(self):
        self.setStyleSheet(FLOATING_WINDOW_STYLE)

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_capture.clicked.connect(self._open_calibrator)
        self.btn_add_template.clicked.connect(self._open_calibrator)
        self.btn_exit.clicked.connect(self._on_exit)
        self.toggle_btn.clicked.connect(self._toggle_collapse)

        self.threshold_edit.editingFinished.connect(self._on_threshold_changed)
        self.round_interval_edit.editingFinished.connect(self._on_round_interval_changed)
        self.action_list.model().rowsMoved.connect(self._on_list_reordered)

    def _restore_geometry(self):
        x, y = self.config.window_pos
        self.move(x, y)

    # ---- Collapse / Expand ----

    def _update_collapsed(self):
        self.config_panel.setVisible(not self._collapsed)
        self.toggle_btn.setText("▼ 展开" if self._collapsed else "▲ 收起")
        self.adjustSize()
        if self._collapsed:
            self.setFixedHeight(90)  # taller to fit 2-row status
        else:
            self.setFixedHeight(350)
        self.config.collapsed = self._collapsed

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._update_collapsed()

    # ---- Action list management ----

    def _populate_action_list(self):
        """Rebuild the action list widget from config."""
        self.action_list.clear()
        for i, action in enumerate(self.config.actions):
            item = QListWidgetItem()
            widget = self._make_action_row(i, action)
            item.setSizeHint(widget.sizeHint())
            # Store the full action data so reorder can read it back
            item.setData(Qt.UserRole, {
                "name": action["name"],
                "template": action["template"],
                "post_delay": action.get("post_delay", 2.0),
                "timeout": action.get("timeout", 10),
            })
            self.action_list.addItem(item)
            self.action_list.setItemWidget(item, widget)

    def _make_action_row(self, index: int, action: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)

        idx_label = QLabel(f"{index+1}.")
        idx_label.setFixedWidth(16)
        layout.addWidget(idx_label)

        name_label = QLabel(action["template"].rsplit("\\", 1)[-1].replace(".png", ""))
        name_label.setMinimumWidth(70)
        layout.addWidget(name_label)

        layout.addWidget(QLabel("延迟:"))
        delay_edit = QLineEdit(f"{action.get('post_delay', 2.0):.1f}")
        delay_edit.setFixedWidth(36)
        delay_edit.editingFinished.connect(
            lambda e=delay_edit, i=index: self._on_delay_changed(i, e)
        )
        layout.addWidget(delay_edit)

        layout.addWidget(QLabel("超时:"))
        timeout_edit = QLineEdit(f"{action.get('timeout', 10)}")
        timeout_edit.setFixedWidth(30)
        timeout_edit.editingFinished.connect(
            lambda e=timeout_edit, i=index: self._on_timeout_changed(i, e)
        )
        layout.addWidget(timeout_edit)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("btnMiniDel")
        btn_del.setFixedWidth(22)
        btn_del.clicked.connect(lambda checked, i=index: self._remove_action(i))
        layout.addWidget(btn_del)

        return row

    def _refresh_action_list(self):
        self._populate_action_list()

    def _on_delay_changed(self, index: int, edit: QLineEdit):
        try:
            val = float(edit.text())
            self.config.update_action(index, post_delay=max(0.5, val))
        except ValueError:
            edit.setText(f"{self.config.actions[index].get('post_delay', 2.0):.1f}")

    def _on_timeout_changed(self, index: int, edit: QLineEdit):
        try:
            val = int(edit.text())
            self.config.update_action(index, timeout=max(1, val))
        except ValueError:
            edit.setText(str(self.config.actions[index].get('timeout', 10)))

    def _remove_action(self, index: int):
        self.config.remove_action(index)
        self._refresh_action_list()

    def _on_list_reordered(self):
        """Save new order after drag-drop reorder."""
        actions = []
        for i in range(self.action_list.count()):
            item = self.action_list.item(i)
            w = self.action_list.itemWidget(item)
            delay = 2.0
            for child in w.findChildren(QLineEdit):
                try:
                    delay = float(child.text())
                except ValueError:
                    pass
                break
            data = item.data(Qt.UserRole)
            if data:
                data["post_delay"] = delay
                actions.append(data)
        if actions:
            self.config.set_actions(actions)
        self._refresh_action_list()

    # ---- Actions ----

    def _on_start(self):
        actions = self.config.actions
        if not actions:
            self._open_calibrator()
            return

        # Save delay edits from list widgets
        for i in range(self.action_list.count()):
            item = self.action_list.item(i)
            w = self.action_list.itemWidget(item)
            edits = w.findChildren(QLineEdit)
            if edits:
                try:
                    val = float(edits[0].text())
                    self.config.update_action(i, post_delay=max(0.5, val))
                except ValueError:
                    pass

        self.engine.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _on_stop(self):
        self.engine.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setStyleSheet("color: #a0a0a0;")

    def _on_exit(self):
        self.engine.stop()
        QApplication.quit()

    def _open_calibrator(self):
        template_dir = str(Path(self.config.base_dir) / "templates")
        self.calibrator = CalibratorOverlay(template_dir)
        self.calibrator.template_captured.connect(self._on_template_captured)
        self.calibrator.show()

    def _on_template_captured(self, path: str, bw: int, bh: int):
        self.config.baseline_resolution = (bw, bh)
        name = Path(path).stem
        self.config.add_action(name, path, post_delay=2.0)
        self._refresh_action_list()
        logger.info(f"Template captured: {path} (baseline {bw}x{bh})")

    def _on_threshold_changed(self):
        try:
            val = float(self.threshold_edit.text())
            self.config.threshold = val
        except ValueError:
            self.threshold_edit.setText(f"{self.config.threshold:.2f}")

    def _on_round_interval_changed(self):
        try:
            val = int(self.round_interval_edit.text())
            self.config.round_interval = val
        except ValueError:
            self.round_interval_edit.setText(str(self.config.round_interval))

    # ---- Status update ----

    def _update_status(self):
        status = self.engine.status
        color = self._status_colors.get(status, "#a0a0a0")

        labels = {
            "idle": ("●", "空闲"),
            "running": ("▶", "运行中"),
            "clicked": ("✓", "已点击"),
            "notfound": ("✗", "未找到"),
            "stopped": ("⏹", "已停止"),
        }
        # Show round info if running
        if status == "running":
            d = self.engine.details
            self.status_icon.setText("▶")
            self.status_icon.setStyleSheet(f"font-size: 20px; color: {color};")
            self.status_text.setText(f"第{d['current_round']}轮")
            btn_name = d.get("current_action_name", "")
            self.status_action_name.setText(f"[{btn_name}]" if btn_name else "")
            self.status_progress.setText(f"{d['current_action']}/{d['total_actions']}")
        elif status in ("clicked", "notfound") and self.engine.running:
            # Still in click loop — show running details, not the transient sub-status
            d = self.engine.details
            self.status_icon.setText("▶")
            self.status_icon.setStyleSheet(f"font-size: 20px; color: #60d060;")
            self.status_text.setText(f"第{d['current_round']}轮")
            btn_name = d.get("current_action_name", "")
            self.status_action_name.setText(f"[{btn_name}]" if btn_name else "")
            self.status_progress.setText(f"{d['current_action']}/{d['total_actions']}")
        elif status.startswith("countdown"):
            sec = status.split(":", 1)[1] if ":" in status else "?"
            self.status_icon.setText("⏳")
            self.status_icon.setStyleSheet(f"font-size: 18px; color: #ffd060;")
            self.status_text.setText(f"下轮 {sec}秒")
            self.status_action_name.setText("")
            self.status_progress.setText("")
            color = "#ffd060"
        elif status == "locked":
            self.status_icon.setText("🔒")
            self.status_icon.setStyleSheet("font-size: 16px; color: #ff7040;")
            self.status_text.setText("屏幕已锁定")
            self.status_action_name.setText("等待解锁...")
            self.status_progress.setText("")
            color = "#ff7040"
        else:
            icon, text = labels.get(status, ("●", "空闲"))
            self.status_icon.setText(icon)
            self.status_icon.setStyleSheet(f"font-size: 20px; color: {color};")
            self.status_text.setText(text)
            self.status_action_name.setText("")
            self.status_progress.setText("")

        # Auto re-enable start when stopped
        if status in ("idle", "stopped") and not self.engine.running:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    # ---- Window move / save position ----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.config.window_pos = (self.x(), self.y())
            del self._drag_pos

    def closeEvent(self, event):
        self.config.window_pos = (self.x(), self.y())
        self.config.collapsed = self._collapsed
        self.engine.stop()
        event.accept()
