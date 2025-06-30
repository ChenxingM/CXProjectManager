# -*- coding: utf-8 -*-
"""
对话框组件模块 - 完整版本
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialogButtonBox, QGroupBox, QRadioButton, QButtonGroup, QCheckBox,
    QPlainTextEdit, QListWidget, QMessageBox
)

from cx_project_manager.utils.qss import QSS_THEME
from cx_project_manager.utils.constants import CUT_PATTERN
from cx_project_manager.core.registry import ProjectRegistry
from cx_project_manager.utils.utils import parse_cut_id, zero_pad, format_cut_id


class ProjectBrowserDialog(QDialog):
    """项目浏览器对话框"""

    project_selected = Signal(str)  # 项目路径信号

    def __init__(self, registry: ProjectRegistry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowTitle("项目浏览器")
        self.setModal(True)
        self.resize(800, 500)
        self.setStyleSheet(QSS_THEME)
        self._setup_ui()
        self._load_projects()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._load_projects)
        toolbar_layout.addWidget(self.btn_refresh)

        self.btn_open = QPushButton("打开项目")
        self.btn_open.clicked.connect(self._open_project)
        self.btn_open.setEnabled(False)
        toolbar_layout.addWidget(self.btn_open)

        self.btn_delete = QPushButton("删除记录")
        self.btn_delete.clicked.connect(self._delete_record)
        self.btn_delete.setEnabled(False)
        toolbar_layout.addWidget(self.btn_delete)

        toolbar_layout.addStretch()

        self.lbl_count = QLabel("项目数: 0")
        toolbar_layout.addWidget(self.lbl_count)

        layout.addLayout(toolbar_layout)

        # 项目表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "项目名称", "Episode数", "创建时间", "最后访问", "路径", "状态"
        ])

        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._open_project)

        layout.addWidget(self.table)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_projects(self):
        """加载项目列表"""
        self.registry.load_registry()  # 重新加载以获取最新数据
        projects = self.registry.get_all_projects()

        self.table.setRowCount(len(projects))

        for row, project in enumerate(projects):
            # 项目名称
            self.table.setItem(row, 0, QTableWidgetItem(project.project_name))

            # Episode数
            if project.no_episode:
                ep_text = f"单集模式 ({len(project.episode_list)} 特殊)"
            else:
                ep_text = str(project.episode_count)
            self.table.setItem(row, 1, QTableWidgetItem(ep_text))

            # 创建时间
            created = datetime.fromisoformat(project.created_time)
            self.table.setItem(row, 2, QTableWidgetItem(created.strftime("%Y-%m-%d")))

            # 最后访问
            accessed = datetime.fromisoformat(project.last_accessed)
            self.table.setItem(row, 3, QTableWidgetItem(accessed.strftime("%Y-%m-%d %H:%M")))

            # 路径
            path_item = QTableWidgetItem(project.project_path)
            path_item.setToolTip(project.project_path)
            self.table.setItem(row, 4, path_item)

            # 状态
            status = "正常" if Path(project.project_path).exists() else "路径不存在"
            status_item = QTableWidgetItem(status)
            if status == "路径不存在":
                status_item.setForeground(QBrush(QColor("#F44336")))
            else:
                status_item.setForeground(QBrush(QColor("#4CAF50")))
            self.table.setItem(row, 5, status_item)

        self.lbl_count.setText(f"项目数: {len(projects)}")

    def _on_selection_changed(self):
        """选择改变时的处理"""
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_open.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def _open_project(self):
        """打开选中的项目"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            project_path = self.table.item(current_row, 4).text()
            if Path(project_path).exists():
                self.project_selected.emit(project_path)
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "项目路径不存在")

    def _delete_record(self):
        """删除选中的记录"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            project_name = self.table.item(current_row, 0).text()

            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要从注册表中删除项目 '{project_name}' 的记录吗？\n"
                "注意：这只会删除注册信息，不会删除实际的项目文件。",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.registry.unregister_project(project_name)
                self._load_projects()


class ReuseCutDialog(QDialog):
    """兼用卡创建对话框"""

    def __init__(self, project_config: Dict, episode_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.episode_id = episode_id
        self.setWindowTitle("创建兼用卡")
        self.setModal(True)
        self.resize(500, 400)
        self.setStyleSheet(QSS_THEME)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        layout.addWidget(QLabel("请输入要合并为兼用卡的Cut编号，用逗号或换行分隔："))
        layout.addWidget(QLabel("示例：100, 102, 150, 151 或 100A, 100B, 100C"))

        # Cut输入框
        self.txt_cuts = QPlainTextEdit()
        self.txt_cuts.setPlaceholderText("输入Cut编号...")
        self.txt_cuts.setMaximumHeight(150)
        self.txt_cuts.textChanged.connect(self._update_preview)
        layout.addWidget(self.txt_cuts)

        # 可用Cut列表
        layout.addWidget(QLabel("可用的Cut列表："))
        self.list_available = QListWidget()
        self.list_available.setMaximumHeight(120)
        self.list_available.setSelectionMode(QAbstractItemView.MultiSelection)
        self._load_available_cuts()
        layout.addWidget(self.list_available)

        # 添加选中的Cut按钮
        btn_add_selected = QPushButton("添加选中的Cut")
        btn_add_selected.clicked.connect(self._add_selected_cuts)
        layout.addWidget(btn_add_selected)

        # 预览
        layout.addWidget(QLabel("预览："))
        self.lbl_preview = QLabel("(请输入Cut编号)")
        self.lbl_preview.setStyleSheet("""
            QLabel {
                background-color: #2A2A2A;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                padding: 10px;
                font-family: Consolas, Monaco, monospace;
            }
        """)
        self.lbl_preview.setWordWrap(True)
        layout.addWidget(self.lbl_preview)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("创建兼用卡")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_available_cuts(self):
        """加载可用的Cut列表"""
        self.list_available.clear()

        existing_reuse_cuts = set()
        for reuse_cut in self.project_config.get("reuse_cuts", []):
            existing_reuse_cuts.update(reuse_cut["cuts"])

        cuts = (self.project_config.get("episodes", {}).get(self.episode_id, [])
                if self.episode_id
                else self.project_config.get("cuts", []))

        for cut in sorted(cuts):
            if cut not in existing_reuse_cuts:
                self.list_available.addItem(cut)

    def _add_selected_cuts(self):
        """添加选中的Cut到输入框"""
        selected_cuts = [item.text() for item in self.list_available.selectedItems()]
        if selected_cuts:
            current_text = self.txt_cuts.toPlainText().strip()
            new_text = f"{current_text}, {', '.join(selected_cuts)}" if current_text else ", ".join(selected_cuts)
            self.txt_cuts.setPlainText(new_text)

    def _update_preview(self):
        """更新预览"""
        text = self.txt_cuts.toPlainText().strip()
        if not text:
            self.lbl_preview.setText("(请输入Cut编号)")
            return

        cuts = self._parse_cuts(text)
        if not cuts:
            self.lbl_preview.setText("(无效的Cut编号)")
            return

        sorted_cuts = self._sort_cuts(cuts)
        project_name = self.project_config.get("project_name", "项目名")

        preview_text = (f"主Cut: {sorted_cuts[0]}\n"
                        f"所有Cut: {', '.join(sorted_cuts)}\n"
                        f"文件夹名: {sorted_cuts[0]}\n"
                        f"文件名示例: {project_name}_{'_'.join(sorted_cuts)}_T1.psd")

        self.lbl_preview.setText(preview_text)

    def _parse_cuts(self, text: str) -> List[str]:
        """解析Cut编号"""
        cuts = []
        parts = re.split(r'[,，\s\n]+', text)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if CUT_PATTERN.match(part):
                num, letter = parse_cut_id(part)
                cuts.append(format_cut_id(num, letter))
            elif part.isdigit():
                cuts.append(zero_pad(int(part), 3))

        return list(set(cuts))

    def _sort_cuts(self, cuts: List[str]) -> List[str]:
        """排序Cut编号"""
        return sorted(cuts, key=lambda c: parse_cut_id(c))

    def _validate_and_accept(self):
        """验证并接受"""
        text = self.txt_cuts.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "错误", "请输入Cut编号")
            return

        cuts = self._parse_cuts(text)
        if len(cuts) < 2:
            QMessageBox.warning(self, "错误", "兼用卡至少需要2个Cut")
            return

        existing_cuts = (self.project_config.get("episodes", {}).get(self.episode_id, [])
                         if self.episode_id
                         else self.project_config.get("cuts", []))

        not_found = [cut for cut in cuts if cut not in existing_cuts]
        if not_found:
            QMessageBox.warning(self, "错误",
                                f"以下Cut不存在: {', '.join(not_found)}\n"
                                "请先创建这些Cut，或从输入中移除它们。")
            return

        # 检查是否已经是兼用卡
        existing_reuse = []
        for cut in cuts:
            for reuse_cut in self.project_config.get("reuse_cuts", []):
                if cut in reuse_cut["cuts"]:
                    existing_reuse.append(f"{cut} (已在兼用卡: {', '.join(reuse_cut['cuts'])})")

        if existing_reuse:
            QMessageBox.warning(self, "错误",
                                "以下Cut已经是兼用卡的一部分:\n" + "\n".join(existing_reuse))
            return

        self.accept()

    def get_cuts(self) -> List[str]:
        """获取Cut列表"""
        return self._sort_cuts(self._parse_cuts(self.txt_cuts.toPlainText().strip()))


class VersionConfirmDialog(QDialog):
    """版本确认对话框"""

    def __init__(self, material_type: str, current_version: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("确认版本号")
        self.setModal(True)
        self.setStyleSheet(QSS_THEME)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"检测到已存在的{material_type.upper()}文件，\n建议使用版本号: T{current_version}"))

        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("版本号:"))
        self.spin_version = QSpinBox()
        self.spin_version.setPrefix("T")
        self.spin_version.setRange(1, 999)
        self.spin_version.setValue(current_version)
        version_layout.addWidget(self.spin_version)
        layout.addLayout(version_layout)

        self.chk_skip = QCheckBox("不再询问，自动使用推荐的版本号")
        layout.addWidget(self.chk_skip)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_version(self) -> int:
        return self.spin_version.value()

    def should_skip_confirmation(self) -> bool:
        return self.chk_skip.isChecked()


class BatchAepDialog(QDialog):
    """批量复制AEP模板对话框"""

    def __init__(self, project_config: Dict, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.setWindowTitle(f"批量复制 AEP 模板 - {project_config.get('project_name', '未命名项目')}")
        self.setModal(True)
        self.resize(450, 350)
        self.setStyleSheet(QSS_THEME)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 模板信息
        template_count = self._get_template_count()
        info_text = (f"ℹ️ 找到 {template_count} 个 AEP 模板文件" if template_count > 0
                     else "⚠️ 未找到 AEP 模板文件")
        info_label = QLabel(info_text)
        info_label.setStyleSheet(f"color: {'#03A9F4' if template_count > 0 else '#FF9800'}; padding: 8px;")
        layout.addWidget(info_label)

        # 选择范围
        scope_group = QGroupBox("选择范围")
        scope_layout = QVBoxLayout(scope_group)

        self.radio_all = QRadioButton("所有 Episode 和 Cut")
        self.radio_episode = QRadioButton("指定 Episode 的所有 Cut")
        self.radio_selected = QRadioButton("指定 Episode 和 Cut 范围")

        self.radio_group = QButtonGroup()
        for i, radio in enumerate([self.radio_all, self.radio_episode, self.radio_selected]):
            self.radio_group.addButton(radio, i)
            scope_layout.addWidget(radio)

        self.radio_all.setChecked(True)

        # Episode 选择
        ep_layout = QHBoxLayout()
        self.cmb_episode = QComboBox()
        self.cmb_episode.setEnabled(False)
        self.cmb_episode.addItems(sorted(self.project_config.get("episodes", {}).keys()))
        ep_layout.addWidget(QLabel("Episode:"))
        ep_layout.addWidget(self.cmb_episode)
        scope_layout.addLayout(ep_layout)

        # Cut 范围
        cut_layout = QHBoxLayout()
        self.spin_cut_from = QSpinBox()
        self.spin_cut_from.setRange(1, 999)
        self.spin_cut_from.setValue(1)
        self.spin_cut_from.setEnabled(False)

        self.spin_cut_to = QSpinBox()
        self.spin_cut_to.setRange(1, 999)
        self.spin_cut_to.setValue(100)
        self.spin_cut_to.setEnabled(False)

        cut_layout.addWidget(QLabel("Cut 范围:"))
        cut_layout.addWidget(self.spin_cut_from)
        cut_layout.addWidget(QLabel("到"))
        cut_layout.addWidget(self.spin_cut_to)
        cut_layout.addStretch()
        scope_layout.addLayout(cut_layout)

        layout.addWidget(scope_group)

        # 选项
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout(options_group)

        self.chk_overwrite = QCheckBox("覆盖已存在的文件")
        self.chk_skip_existing = QCheckBox("跳过已有 AEP 文件的 Cut")
        self.chk_skip_existing.setChecked(True)
        self.chk_skip_reuse = QCheckBox("跳过兼用卡")
        self.chk_skip_reuse.setChecked(True)

        for chk in [self.chk_overwrite, self.chk_skip_existing, self.chk_skip_reuse]:
            options_layout.addWidget(chk)

        layout.addWidget(options_group)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("开始复制")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 连接信号
        self.radio_group.buttonClicked.connect(self._on_scope_changed)
        self.chk_overwrite.toggled.connect(lambda c: self.chk_skip_existing.setChecked(False) if c else None)

    def _get_template_count(self) -> int:
        if hasattr(self.parent(), 'project_base') and self.parent().project_base:
            template_dir = self.parent().project_base / "07_master_assets" / "aep_templates"
            return len(list(template_dir.glob("*.aep"))) if template_dir.exists() else 0
        return 0

    def _on_scope_changed(self, button):
        scope_id = self.radio_group.id(button)
        self.cmb_episode.setEnabled(scope_id >= 1)
        self.spin_cut_from.setEnabled(scope_id == 2)
        self.spin_cut_to.setEnabled(scope_id == 2)

    def get_settings(self) -> Dict:
        scope_id = self.radio_group.checkedId()
        return {
            "scope": scope_id,
            "episode": self.cmb_episode.currentText() if scope_id >= 1 else None,
            "cut_from": self.spin_cut_from.value() if scope_id == 2 else None,
            "cut_to": self.spin_cut_to.value() if scope_id == 2 else None,
            "overwrite": self.chk_overwrite.isChecked(),
            "skip_existing": self.chk_skip_existing.isChecked(),
            "skip_reuse": self.chk_skip_reuse.isChecked(),
        }