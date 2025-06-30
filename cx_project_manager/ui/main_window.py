# -*- coding: utf-8 -*-
"""
主窗口类模块 - 完整版本
"""

import os
import platform
import shutil
import subprocess
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Dict, Optional, cast, List

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSpinBox, QSplitter, QStatusBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QTabWidget,
    QTextEdit, QListWidgetItem, QDialog, QInputDialog
)

from cx_project_manager.utils.qss import QSS_THEME
from cx_project_manager.utils.version_info import version_info
from cx_project_manager.utils.constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS, EpisodeType
from cx_project_manager.core import ProjectManager, ProjectRegistry
from cx_project_manager.utils.models import FileInfo, ReuseCut
from cx_project_manager.utils.utils import (
    ensure_dir, copy_file_safe, open_in_file_manager, get_file_info, get_png_seq_info, extract_version_from_filename
)
from .dialogs import (
    ProjectBrowserDialog, ReuseCutDialog, VersionConfirmDialog, BatchAepDialog
)
from .widgets import SearchLineEdit, DetailedFileListWidget


class CXProjectManager(QMainWindow):
    """动画项目管理器主窗口"""

    project_changed = Signal()

    def __init__(self):
        super().__init__()

        # 版本信息
        version = version_info.get("version", "Unknow Version")
        build = version_info.get("build-version", "")
        version_str = f"{version} {build}" if build else version

        self.setWindowTitle(f"CX Project Manager - 动画项目管理工具 v{version_str}")
        self.resize(1300, 750)

        # 初始化
        self.project_manager = ProjectManager()
        self.project_base: Optional[Path] = None
        self.project_config: Optional[Dict] = None
        self.app_settings = QSettings("CXStudio", "ProjectManager")
        self.project_registry = ProjectRegistry(self.app_settings)

        # 版本确认跳过设置
        self.skip_version_confirmation = {"bg": False, "cell": False, "3dcg": False}

        # 初始化控件变量
        self._init_widget_variables()

        # 设置UI
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()

        # 应用样式
        self.setStyleSheet(QSS_THEME)

        # 初始状态
        self._set_initial_state()
        self._load_app_settings()

        # 连接信号
        self.project_changed.connect(self._on_project_changed)

    def _init_widget_variables(self):
        """初始化控件变量"""
        # 项目管理
        self.lbl_project_path = None
        self.txt_project_name = None
        self.btn_new_project = None
        self.btn_open_project = None
        self.chk_no_episode = None

        # Episode管理
        self.episode_group = None
        self.cmb_episode_type = None
        self.txt_episode = None
        self.btn_create_episode = None
        self.btn_batch_episode = None
        self.spin_ep_from = None
        self.spin_ep_to = None

        # Cut管理
        self.cmb_cut_episode = None
        self.txt_cut = None
        self.btn_create_cut = None
        self.btn_batch_cut = None
        self.spin_cut_from = None
        self.spin_cut_to = None
        self.btn_create_reuse_cut = None

        # 素材导入
        self.cmb_target_episode = None
        self.cmb_target_cut = None
        self.material_paths = {}  # 存储素材路径输入框
        self.material_buttons = {}  # 存储浏览按钮

        # 其他控件
        self.tree = None
        self.tabs = None
        self.txt_project_stats = None
        self.browser_tree = None
        self.file_tabs = None
        self.file_lists = {}  # 存储文件列表
        self.lbl_current_cut = None
        self.txt_cut_search = None

        # 状态变量
        self.current_cut_id = None
        self.current_episode_id = None
        self.current_path = None

        # 菜单
        self.recent_menu = None
        self.statusbar = None

    def _setup_ui(self):
        """设置主界面"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 0)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: 项目管理
        management_tab = self._create_management_tab()
        self.tabs.addTab(management_tab, "📁 项目管理")

        # Tab 2: 项目浏览
        browser_tab = self._create_browser_tab()
        self.tabs.addTab(browser_tab, "📊 项目浏览")

        self.tabs.setCurrentIndex(0)

    def _create_management_tab(self) -> QWidget:
        """创建项目管理Tab"""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧控制面板
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # 右侧目录树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("项目结构")
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        splitter.addWidget(self.tree)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        return tab

    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 项目信息组
        layout.addWidget(self._create_project_group())

        # Episode 管理组
        layout.addWidget(self._create_episode_group())

        # Cut 管理组
        layout.addWidget(self._create_cut_group())

        # 素材导入组
        layout.addWidget(self._create_import_group())

        layout.addStretch()

        return panel

    def _create_project_group(self) -> QGroupBox:
        """创建项目管理组"""
        group = QGroupBox("📁 项目管理")
        layout = QVBoxLayout(group)

        # 当前项目路径
        self.lbl_project_path = QLabel("未打开项目")
        self.lbl_project_path.setStyleSheet("color: #999; font-style: italic;")
        layout.addWidget(self.lbl_project_path)

        # 新建项目
        new_layout = QHBoxLayout()
        self.txt_project_name = QLineEdit()
        self.txt_project_name.setPlaceholderText("输入项目名称")
        self.txt_project_name.returnPressed.connect(self.new_project)
        self.btn_new_project = QPushButton("新建")
        self.btn_new_project.clicked.connect(self.new_project)
        new_layout.addWidget(self.txt_project_name)
        new_layout.addWidget(self.btn_new_project)
        layout.addLayout(new_layout)

        # 打开项目
        self.btn_open_project = QPushButton("打开项目")
        self.btn_open_project.clicked.connect(self.open_project)
        layout.addWidget(self.btn_open_project)

        # Episode 模式选择
        self.chk_no_episode = QCheckBox("单集/PV 模式（支持特殊 Episode）")
        self.chk_no_episode.setToolTip("单集模式下可以创建 op/ed/pv 等特殊类型，但不能创建标准集数 ep")
        self.chk_no_episode.stateChanged.connect(self._toggle_episode_mode)
        layout.addWidget(self.chk_no_episode)

        return group

    def _create_episode_group(self) -> QGroupBox:
        """创建Episode管理组"""
        self.episode_group = QGroupBox("🎬 Episode 管理")
        layout = QVBoxLayout(self.episode_group)

        # Episode创建
        single_layout = QHBoxLayout()

        self.cmb_episode_type = QComboBox()
        self.cmb_episode_type.setEditable(True)
        self.cmb_episode_type.addItems(EpisodeType.get_all_types())
        self.cmb_episode_type.setCurrentText("ep")
        self.cmb_episode_type.currentTextChanged.connect(self._on_episode_type_changed)

        self.txt_episode = QLineEdit()
        self.txt_episode.setPlaceholderText("编号或名称 (可留空)")

        self.btn_create_episode = QPushButton("创建")
        self.btn_create_episode.clicked.connect(self.create_episode)

        single_layout.addWidget(QLabel("类型:"))
        single_layout.addWidget(self.cmb_episode_type)
        single_layout.addWidget(self.txt_episode)
        single_layout.addWidget(self.btn_create_episode)
        layout.addLayout(single_layout)

        # 批量创建
        layout.addWidget(QLabel("批量创建 (仅限数字编号):"))

        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("从:"))
        self.spin_ep_from = QSpinBox()
        self.spin_ep_from.setRange(1, 999)
        self.spin_ep_from.setValue(1)
        batch_layout.addWidget(self.spin_ep_from)

        batch_layout.addWidget(QLabel("到:"))
        self.spin_ep_to = QSpinBox()
        self.spin_ep_to.setRange(1, 999)
        self.spin_ep_to.setValue(12)
        batch_layout.addWidget(self.spin_ep_to)

        self.btn_batch_episode = QPushButton("批量创建")
        self.btn_batch_episode.clicked.connect(self.batch_create_episodes)
        batch_layout.addWidget(self.btn_batch_episode)

        layout.addLayout(batch_layout)

        return self.episode_group

    def _create_cut_group(self) -> QGroupBox:
        """创建Cut管理组"""
        group = QGroupBox("✂️ Cut 管理")
        layout = QVBoxLayout(group)

        # 单个Cut创建
        single_layout = QHBoxLayout()
        self.cmb_cut_episode = QComboBox()
        self.cmb_cut_episode.setPlaceholderText("选择 Episode")

        self.txt_cut = QLineEdit()
        self.txt_cut.setPlaceholderText("Cut编号(可带字母)")
        self.txt_cut.setToolTip("支持纯数字或数字+字母，如: 100, 100A")

        self.btn_create_cut = QPushButton("创建")
        self.btn_create_cut.clicked.connect(lambda: self.create_cut())

        single_layout.addWidget(self.cmb_cut_episode)
        single_layout.addWidget(self.txt_cut)
        single_layout.addWidget(self.btn_create_cut)
        layout.addLayout(single_layout)

        # 批量创建
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("批量:"))

        self.spin_cut_from = QSpinBox()
        self.spin_cut_from.setRange(1, 999)
        self.spin_cut_from.setValue(1)
        batch_layout.addWidget(self.spin_cut_from)

        batch_layout.addWidget(QLabel("到"))
        self.spin_cut_to = QSpinBox()
        self.spin_cut_to.setRange(1, 999)
        self.spin_cut_to.setValue(10)
        batch_layout.addWidget(self.spin_cut_to)

        self.btn_batch_cut = QPushButton("批量创建")
        self.btn_batch_cut.clicked.connect(self.batch_create_cuts)
        batch_layout.addWidget(self.btn_batch_cut)

        layout.addLayout(batch_layout)

        # 兼用卡
        self.btn_create_reuse_cut = QPushButton("🔗 创建兼用卡")
        self.btn_create_reuse_cut.setToolTip("将多个Cut合并为兼用卡（共用素材）")
        self.btn_create_reuse_cut.clicked.connect(self.create_reuse_cut)
        layout.addWidget(self.btn_create_reuse_cut)

        return group

    def _create_import_group(self) -> QGroupBox:
        """创建素材导入组"""
        group = QGroupBox("📥 素材导入")
        layout = QVBoxLayout(group)

        # Episode和Cut选择
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Episode:"))

        self.cmb_target_episode = QComboBox()
        self.cmb_target_episode.setPlaceholderText("选择 Episode")
        self.cmb_target_episode.currentTextChanged.connect(self._on_episode_changed)
        target_layout.addWidget(self.cmb_target_episode)

        target_layout.addWidget(QLabel("Cut:"))
        self.cmb_target_cut = QComboBox()
        self.cmb_target_cut.setPlaceholderText("选择 Cut")
        target_layout.addWidget(self.cmb_target_cut)

        layout.addLayout(target_layout)

        # 素材路径选择
        materials = [("BG", "bg"), ("Cell", "cell"), ("3DCG", "3dcg"), ("TS", "timesheet")]

        for label, key in materials:
            mat_layout = QHBoxLayout()
            mat_layout.addWidget(QLabel(f"{label}:"))

            txt_path = QLineEdit()
            txt_path.setPlaceholderText(f"{label} 文件路径")
            txt_path.setReadOnly(True)
            self.material_paths[key] = txt_path
            mat_layout.addWidget(txt_path)

            btn_browse = QPushButton("浏览")
            btn_browse.clicked.connect(partial(self.browse_material, key))
            self.material_buttons[key] = btn_browse
            mat_layout.addWidget(btn_browse)

            layout.addLayout(mat_layout)

        # 导入操作按钮
        action_layout = QHBoxLayout()

        buttons = [
            ("导入选中", self.import_single),
            ("批量导入", self.import_all),
            ("复制 AEP 模板", self.copy_aep_template),
            ("批量复制 AEP", self.batch_copy_aep_template)
        ]

        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            action_layout.addWidget(btn)

        layout.addLayout(action_layout)

        return group

    def _create_browser_tab(self) -> QWidget:
        """创建项目浏览Tab"""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧面板
        left_panel = self._create_browser_left_panel()
        splitter.addWidget(left_panel)

        # 右侧面板
        right_panel = self._create_browser_right_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        return tab

    def _create_browser_left_panel(self) -> QWidget:
        """创建浏览器左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # 项目统计
        stats_group = QGroupBox("📊 项目统计")
        stats_layout = QVBoxLayout(stats_group)

        self.txt_project_stats = QTextEdit()
        self.txt_project_stats.setReadOnly(True)
        self.txt_project_stats.setMaximumHeight(200)
        stats_layout.addWidget(self.txt_project_stats)

        layout.addWidget(stats_group)

        # Cut树
        tree_group = QGroupBox("📂 Cut")
        tree_layout = QVBoxLayout(tree_group)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍"))

        self.txt_cut_search = SearchLineEdit()
        self.txt_cut_search.setPlaceholderText("搜索 Cut (支持数字快速定位)...")
        self.txt_cut_search.textChanged.connect(self._on_cut_search_changed)
        self.txt_cut_search.setClearButtonEnabled(True)
        self.txt_cut_search.returnPressed.connect(self._select_first_match)
        search_layout.addWidget(self.txt_cut_search)

        tree_layout.addLayout(search_layout)

        self.browser_tree = QTreeWidget()
        self.browser_tree.setHeaderLabel("选择要浏览的 Cut")
        self.browser_tree.itemClicked.connect(self._on_browser_tree_clicked)
        self.browser_tree.setAlternatingRowColors(True)
        tree_layout.addWidget(self.browser_tree)

        layout.addWidget(tree_group, 1)

        return panel

    def _create_browser_right_panel(self) -> QWidget:
        """创建浏览器右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # 文件浏览器
        files_group = QGroupBox("📁 文件浏览器")
        files_layout = QVBoxLayout(files_group)

        self.lbl_current_cut = QLabel("当前位置：未选择")
        self.lbl_current_cut.setStyleSheet("""
            QLabel {
                background-color: #252525;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)
        self.lbl_current_cut.setWordWrap(True)
        self.lbl_current_cut.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_current_cut.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lbl_current_cut.customContextMenuRequested.connect(self._show_path_context_menu)
        files_layout.addWidget(self.lbl_current_cut)

        # 文件类型Tab
        self.file_tabs = QTabWidget()
        self.file_tabs.currentChanged.connect(self._on_file_tab_changed)

        # 创建文件列表
        tab_names = ["VFX", "Cell", "BG", "Render", "3DCG"]
        for name in tab_names:
            list_widget = DetailedFileListWidget()
            list_widget.itemDoubleClicked.connect(self._on_file_item_double_clicked)
            self.file_lists[name.lower()] = list_widget
            self.file_tabs.addTab(list_widget, name)

        files_layout.addWidget(self.file_tabs)
        layout.addWidget(files_group)

        return panel

    def _setup_menubar(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        actions = [
            ("新建项目", "Ctrl+N", self.new_project),
            ("打开项目", "Ctrl+O", self.open_project),
            None,  # 分隔符
            ("浏览所有项目...", None, self.browse_all_projects),
            None,
            ("设置默认路径...", None, self.set_default_path),
            None,
            ("退出", "Ctrl+Q", self.close)
        ]

        # 添加基本操作
        for i, action_data in enumerate(actions):
            if action_data is None:
                file_menu.addSeparator()
            else:
                action = QAction(action_data[0], self)
                if action_data[1]:
                    action.setShortcut(action_data[1])
                action.triggered.connect(action_data[2])
                file_menu.addAction(action)

                # 在"浏览所有项目"后插入最近项目菜单
                if i == 3:  # 在"浏览所有项目"之后
                    self.recent_menu = QMenu("最近项目", self)
                    file_menu.insertMenu(action, self.recent_menu)
                    self._update_recent_menu()

        # 工具菜单
        tools_menu = menubar.addMenu("工具")

        tool_actions = [
            ("刷新目录树", "F5", self._refresh_tree),
            ("搜索Cut", "Ctrl+F", self._focus_cut_search),
            None,
            ("批量复制AEP模板...", None, self.batch_copy_aep_template),
            ("创建兼用卡...", None, self.create_reuse_cut),
            ("复制MOV到剪辑文件夹", "Ctrl+M", self.copy_mov_to_cut_folder),
            None,
            ("在文件管理器中打开", None, self.open_in_explorer)
        ]

        for action_data in tool_actions:
            if action_data is None:
                tools_menu.addSeparator()
            else:
                action = QAction(action_data[0], self)
                if action_data[1]:
                    action.setShortcut(action_data[1])
                action.triggered.connect(action_data[2])
                tools_menu.addAction(action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        help_actions = [
            ("使用说明", self.show_help),
            ("关于", self.show_about)
        ]

        for text, handler in help_actions:
            action = QAction(text, self)
            action.triggered.connect(handler)
            help_menu.addAction(action)

    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("请打开或新建项目以开始使用")

    def _set_initial_state(self):
        """设置初始状态"""
        self._enable_controls(False)
        self.txt_project_name.setEnabled(True)
        self.btn_new_project.setEnabled(True)
        self.btn_open_project.setEnabled(True)

    # ========================== 项目操作 ========================== #

    def new_project(self):
        """新建项目"""
        project_name = self.txt_project_name.text().strip()
        if not project_name:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            self.txt_project_name.setFocus()
            return

        # 检查默认路径
        default_path = self.app_settings.value("default_project_path", "")

        if default_path and Path(default_path).exists():
            base_folder = Path(default_path)
        else:
            base_folder = QFileDialog.getExistingDirectory(self, "选择项目创建位置", "")
            if not base_folder:
                return
            base_folder = Path(base_folder)

        # 检查项目是否已存在
        project_path = base_folder / project_name
        if project_path.exists():
            reply = QMessageBox.question(
                self, "确认",
                f"项目 '{project_name}' 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # 创建项目
        no_episode = self.chk_no_episode.isChecked()
        if self.project_manager.create_project(project_name, base_folder, no_episode):
            self.project_base = self.project_manager.project_base
            self.project_config = self.project_manager.project_config

            # 注册项目
            self.project_registry.register_project(self.project_config, self.project_base)

            # 更新注册表，确保即使默认路径改变也能保留项目信息
            if hasattr(self, 'project_registry'):
                episodes = self.project_config.get("episodes", {})
                self.project_config["episode_count"] = len(episodes)
                self.project_config["episode_list"] = sorted(episodes.keys())

            self.project_changed.emit()
            self._add_to_recent(str(self.project_base))
            self.txt_project_name.clear()

            QMessageBox.information(self, "成功", f"项目 '{project_name}' 创建成功！")

    def open_project(self):
        """打开已有项目"""
        folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹", "")
        if folder:
            self._load_project(folder)

    def browse_all_projects(self):
        """浏览所有项目"""
        dialog = ProjectBrowserDialog(self.project_registry, self)
        dialog.project_selected.connect(self._load_project)
        dialog.exec_()

    def _load_project(self, folder: str):
        """加载项目"""
        project_path = Path(folder)

        if self.project_manager.load_project(project_path):
            self.project_base = self.project_manager.project_base
            self.project_config = self.project_manager.project_config

            # 更新访问时间
            project_name = self.project_config.get("project_name")
            if project_name:
                self.project_registry.update_access_time(project_name)

            self.project_changed.emit()
            self._add_to_recent(str(project_path))
        else:
            QMessageBox.warning(self, "错误", "所选文件夹不是有效的项目（缺少 project_config.json）")

    # ========================== Episode 和 Cut 管理 ========================== #

    def create_episode(self):
        """创建单个Episode"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        ep_type = self.cmb_episode_type.currentText().strip().lower()
        ep_identifier = self.txt_episode.text().strip()

        if self.chk_no_episode.isChecked() and ep_type == "ep":
            QMessageBox.information(
                self, "提示",
                "单集/PV 模式下不支持创建标准集数 (ep)，\n"
                "但可以创建其他类型如 op、ed、pv 等。"
            )
            return

        success, result = self.project_manager.create_episode(ep_type, ep_identifier)

        if success:
            self._refresh_all_views()
            self.statusbar.showMessage(f"已创建 Episode: {result}", 3000)
        else:
            QMessageBox.warning(self, "错误", result)

    def batch_create_episodes(self):
        """批量创建Episode"""
        if self.cmb_episode_type.currentText().lower() != "ep":
            QMessageBox.warning(self, "错误", "批量创建仅支持 'ep' 类型")
            return

        start = self.spin_ep_from.value()
        end = self.spin_ep_to.value()

        if start > end:
            QMessageBox.warning(self, "错误", "起始编号不能大于结束编号")
            return

        created_count = 0
        for i in range(start, end + 1):
            success, _ = self.project_manager.create_episode("ep", str(i))
            if success:
                created_count += 1

        if created_count > 0:
            QMessageBox.information(self, "完成", f"成功创建 {created_count} 个 Episode")
            self._refresh_all_views()

    def create_cut(self, show_error=True):
        """创建单个Cut"""
        if not self.project_base:
            if show_error:
                QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        cut_num = self.txt_cut.text().strip()

        # 获取Episode ID
        episode_id = None
        if self.chk_no_episode.isChecked():
            ep_text = self.cmb_cut_episode.currentText().strip()
            if ep_text and ep_text in self.project_config.get("episodes", {}):
                episode_id = ep_text
        else:
            episode_id = self.cmb_cut_episode.currentText().strip()

        success, result = self.project_manager.create_cut(cut_num, episode_id)

        if success:
            if show_error:
                self._refresh_all_views()
                self.statusbar.showMessage(f"已创建 Cut: {result} (含 06_render 输出目录)", 3000)
        else:
            if show_error:
                QMessageBox.warning(self, "错误", result)

    def batch_create_cuts(self):
        """批量创建Cut"""
        start = self.spin_cut_from.value()
        end = self.spin_cut_to.value()

        if start > end:
            QMessageBox.warning(self, "错误", "起始编号不能大于结束编号")
            return

        episode_id = None
        if self.chk_no_episode.isChecked():
            ep_text = self.cmb_cut_episode.currentText().strip()
            if ep_text and ep_text in self.project_config.get("episodes", {}):
                episode_id = ep_text
        else:
            episode_id = self.cmb_cut_episode.currentText().strip()
            if not episode_id:
                QMessageBox.warning(self, "错误", "批量创建需要先选择 Episode")
                return

        created_count = 0
        for i in range(start, end + 1):
            success, _ = self.project_manager.create_cut(str(i), episode_id)
            if success:
                created_count += 1

        if created_count > 0:
            QMessageBox.information(self, "完成", f"成功创建 {created_count} 个 Cut")
            self._refresh_all_views()

    def create_reuse_cut(self):
        """创建兼用卡"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取Episode ID
        episode_id = None
        if not self.chk_no_episode.isChecked():
            episode_id = self.cmb_cut_episode.currentText().strip()
            if not episode_id:
                episodes = list(self.project_config.get("episodes", {}).keys())
                if not episodes:
                    QMessageBox.warning(self, "错误", "请先创建Episode")
                    return

                episode_id, ok = QInputDialog.getItem(
                    self, "选择Episode",
                    "请选择要创建兼用卡的Episode:",
                    episodes, 0, False
                )
                if not ok:
                    return
        else:
            selected_ep = self.cmb_cut_episode.currentText().strip()
            if selected_ep and selected_ep in self.project_config.get("episodes", {}):
                episode_id = selected_ep

        # 显示对话框
        dialog = ReuseCutDialog(self.project_config, episode_id, self)
        if dialog.exec() == QDialog.Accepted:
            cuts = dialog.get_cuts()
            success, message = self.project_manager.create_reuse_cut(cuts, episode_id)

            if success:
                QMessageBox.information(self, "成功", message)
                self._refresh_all_views()
                self.statusbar.showMessage(message, 5000)
            else:
                QMessageBox.warning(self, "错误", message)

    def copy_mov_to_cut_folder(self):
        """复制所有MOV文件到剪辑文件夹"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        render_dir = self.project_base / "06_render"
        if not render_dir.exists():
            QMessageBox.warning(self, "错误", "06_render 文件夹不存在")
            return

        # 创建目标文件夹
        footage_dir = self.project_base / "09_edit" / "footage"
        ensure_dir(footage_dir)

        # 统计信息
        mov_files_by_episode = {}  # {episode_id: [(source_path, filename), ...]}
        total_count = 0
        total_size = 0

        # 判断项目模式
        no_episode = self.project_config.get("no_episode", False)

        # 收集所有MOV文件并筛选最新版本
        def get_latest_versions(mov_files):
            """从MOV文件列表中获取每个cut的最新版本"""
            # 按基础名称（不含版本号）分组
            files_by_base = {}

            for mov_file in mov_files:
                filename = mov_file.stem
                # 提取版本号
                version = extract_version_from_filename(filename)

                # 获取基础名称（去掉版本号部分）
                if version is not None:
                    # 查找 _v 的位置
                    version_index = filename.rfind('_v')
                    if version_index != -1:
                        base_name = filename[:version_index]
                    else:
                        base_name = filename
                else:
                    base_name = filename
                    version = 0  # 没有版本号的文件视为版本0

                # 分组存储
                if base_name not in files_by_base:
                    files_by_base[base_name] = []
                files_by_base[base_name].append((mov_file, version))

            # 选择每组中版本号最高的文件
            latest_files = []
            for base_name, file_versions in files_by_base.items():
                # 按版本号排序，取最高版本
                file_versions.sort(key=lambda x: x[1], reverse=True)
                latest_files.append(file_versions[0][0])  # 只取文件路径

            return latest_files

        if no_episode:
            # 单集模式：直接在06_render下查找cut文件夹
            cuts = self.project_config.get("cuts", [])

            # 处理根目录下的cuts
            root_mov_files = []
            for cut_id in cuts:
                cut_render_path = render_dir / cut_id / "prores"
                if cut_render_path.exists():
                    root_mov_files.extend(cut_render_path.glob("*.mov"))

            if root_mov_files:
                latest_files = get_latest_versions(root_mov_files)
                mov_files_by_episode["root"] = [(f, f.name) for f in latest_files]
                total_count += len(latest_files)
                total_size += sum(f.stat().st_size for f in latest_files)

            # 处理特殊episodes
            episodes = self.project_config.get("episodes", {})
            for ep_id, ep_cuts in episodes.items():
                ep_render_path = render_dir / ep_id
                if ep_render_path.exists():
                    ep_mov_files = []
                    for cut_id in ep_cuts:
                        cut_render_path = ep_render_path / cut_id / "prores"
                        if cut_render_path.exists():
                            ep_mov_files.extend(cut_render_path.glob("*.mov"))

                    if ep_mov_files:
                        latest_files = get_latest_versions(ep_mov_files)
                        mov_files_by_episode[ep_id] = [(f, f.name) for f in latest_files]
                        total_count += len(latest_files)
                        total_size += sum(f.stat().st_size for f in latest_files)
        else:
            # 标准Episode模式
            episodes = self.project_config.get("episodes", {})
            for ep_id, cuts in episodes.items():
                ep_render_path = render_dir / ep_id
                if ep_render_path.exists():
                    ep_mov_files = []
                    for cut_id in cuts:
                        cut_render_path = ep_render_path / cut_id / "prores"
                        if cut_render_path.exists():
                            ep_mov_files.extend(cut_render_path.glob("*.mov"))

                    if ep_mov_files:
                        latest_files = get_latest_versions(ep_mov_files)
                        mov_files_by_episode[ep_id] = [(f, f.name) for f in latest_files]
                        total_count += len(latest_files)
                        total_size += sum(f.stat().st_size for f in latest_files)

        if total_count == 0:
            QMessageBox.information(self, "提示", "没有找到任何 MOV 文件")
            return

        # 显示确认对话框
        size_mb = total_size / (1024 * 1024)
        episode_info = []

        for ep_id, files in sorted(mov_files_by_episode.items()):
            if ep_id == "root":
                episode_info.append(f"根目录: {len(files)} 个文件（最新版本）")
            else:
                episode_info.append(f"{ep_id}: {len(files)} 个文件（最新版本）")

        message = f"找到 {total_count} 个最新版本 MOV 文件（总大小: {size_mb:.1f} MB）\n\n"
        message += "分布情况:\n" + "\n".join(episode_info)
        message += "\n\n注意：只会复制每个Cut的最新版本（版本号最高的文件）"
        message += "\n是否继续复制？"

        reply = QMessageBox.question(
            self, "确认复制",
            message,
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 执行复制
        copied_count = 0
        skipped_count = 0
        error_count = 0

        # 创建进度对话框
        from PySide6.QtWidgets import QProgressDialog

        progress = QProgressDialog("正在复制最新版本 MOV 文件...", "取消", 0, total_count, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        file_index = 0

        try:
            for ep_id, files in mov_files_by_episode.items():
                # 创建episode子文件夹
                if ep_id == "root":
                    target_dir = footage_dir
                else:
                    target_dir = footage_dir / ep_id
                    ensure_dir(target_dir)

                for source_path, filename in files:
                    if progress.wasCanceled():
                        break

                    progress.setValue(file_index)
                    progress.setLabelText(f"正在复制: {filename}")
                    QApplication.processEvents()

                    target_path = target_dir / filename

                    # 处理重名文件
                    if target_path.exists():
                        # 比较文件大小和修改时间
                        source_stat = source_path.stat()
                        target_stat = target_path.stat()

                        if (source_stat.st_size == target_stat.st_size and
                                source_stat.st_mtime <= target_stat.st_mtime):
                            skipped_count += 1
                            file_index += 1
                            continue

                        # 如果文件不同，添加序号
                        base_name = target_path.stem
                        suffix = target_path.suffix
                        counter = 1

                        while target_path.exists():
                            new_name = f"{base_name}_{counter}{suffix}"
                            target_path = target_dir / new_name
                            counter += 1

                    # 复制文件
                    try:
                        if copy_file_safe(source_path, target_path):
                            copied_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        print(f"复制失败 {filename}: {e}")
                        error_count += 1

                    file_index += 1

                if progress.wasCanceled():
                    break

        finally:
            progress.close()

        # 显示结果
        result_lines = [f"✅ 成功复制: {copied_count} 个最新版本文件"]

        if skipped_count > 0:
            result_lines.append(f"⏭️ 跳过相同文件: {skipped_count} 个")

        if error_count > 0:
            result_lines.append(f"❌ 复制失败: {error_count} 个")

        result_lines.append(f"\n目标文件夹: 09_edit/footage/")
        result_lines.append("（只复制了每个Cut的最新版本）")

        QMessageBox.information(
            self, "复制完成",
            "\n".join(result_lines)
        )

        # 询问是否打开文件夹
        open_folder = QMessageBox.question(
            self, "打开文件夹",
            "是否打开 footage 文件夹查看？",
            QMessageBox.Yes | QMessageBox.No
        )

        if open_folder == QMessageBox.Yes:
            open_in_file_manager(footage_dir)

    # ========================== 素材导入 ========================== #

    def browse_material(self, material_type: str):
        """浏览选择素材"""
        if material_type in ["cell", "3dcg"]:
            path = QFileDialog.getExistingDirectory(
                self, f"选择 {material_type.upper()} 文件夹", ""
            )
            if path:
                self.material_paths[material_type].setText(path)
        else:
            file_filter = {
                "bg": "图像文件 (*.psd *.png *.jpg *.jpeg *.tga *.tiff *.bmp *.exr *.dpx)",
                "timesheet": "CSV 文件 (*.csv)",
            }.get(material_type, "所有文件 (*.*)")

            file_path, _ = QFileDialog.getOpenFileName(
                self, f"选择 {material_type.upper()} 文件", "", file_filter
            )
            if file_path:
                self.material_paths[material_type].setText(file_path)

    def import_single(self):
        """导入单个选中的素材"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
            if self.cmb_target_episode.currentText():
                target_ep = self.cmb_target_episode.currentText()
                target_cut = self.cmb_target_cut.currentText()
                if not target_cut:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                target = f"{target_ep}|{target_cut}"
            else:
                target_cut = self.cmb_target_cut.currentText()
                if not target_cut:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                target = target_cut
        else:
            target_ep = self.cmb_target_episode.currentText()
            target_cut = self.cmb_target_cut.currentText()
            if not target_ep or not target_cut:
                QMessageBox.warning(self, "错误", "请选择目标 Episode 和 Cut")
                return
            target = f"{target_ep}|{target_cut}"

        # 收集要导入的素材
        imports = []
        for mt in ["bg", "cell", "3dcg", "timesheet"]:
            if self.material_paths[mt].text():
                imports.append((mt, self.material_paths[mt].text()))

        if not imports:
            QMessageBox.warning(self, "错误", "请先选择要导入的素材")
            return

        # 执行导入
        success_count = 0
        for material_type, path in imports:
            if self._import_material(material_type, path, target):
                success_count += 1

        if success_count > 0:
            message = f"已导入 {success_count} 个素材"
            if any(mt == "3dcg" for mt, _ in imports):
                message += "（已创建 3DCG 目录）"

            QMessageBox.information(self, "成功", message)
            self._refresh_tree()

            # 清空已导入的路径
            for mt, _ in imports:
                self.material_paths[mt].clear()

            # 重置版本确认跳过设置
            self.skip_version_confirmation = {"bg": False, "cell": False, "3dcg": False}

    def import_all(self):
        """批量导入所有已选择的素材"""
        self.import_single()

    def _import_material(self, material_type: str, source_path: str, target: str) -> bool:
        """执行素材导入"""
        try:
            src = Path(source_path)
            if not src.exists():
                return False

            proj_name = self.project_base.name

            # 解析目标路径
            if "|" in target:
                ep_id, cut_id = target.split("|")
                vfx_base = self.project_base / ep_id / "01_vfx"
                cg_base = self.project_base / ep_id / "02_3dcg"
                ep_part = ep_id.upper() + "_"
            else:
                cut_id = target
                vfx_base = self.project_base / "01_vfx"
                cg_base = self.project_base / "02_3dcg"
                ep_part = ""

            # 检查是否是兼用卡
            reuse_cut = self.project_manager.get_reuse_cut_for_cut(cut_id)
            if reuse_cut:
                cut_id = reuse_cut.main_cut
                base_name = f"{proj_name}_{ep_part}{reuse_cut.get_display_name()}"
            else:
                base_name = f"{proj_name}_{ep_part}{cut_id}"

            # 根据类型处理
            if material_type == "bg":
                bg_dir = vfx_base / cut_id / "bg"
                ensure_dir(bg_dir)

                version = self.project_manager.get_next_version(bg_dir, base_name)

                if not self.skip_version_confirmation["bg"] and bg_dir.exists() and any(bg_dir.iterdir()):
                    dialog = VersionConfirmDialog("BG", version, self)
                    if dialog.exec() == QDialog.Accepted:
                        version = dialog.get_version()
                        if dialog.should_skip_confirmation():
                            self.skip_version_confirmation["bg"] = True
                    else:
                        return False

                file_name = f"{base_name}_T{version}{src.suffix.lower()}"
                dst = bg_dir / file_name
                copy_file_safe(src, dst)

            elif material_type == "cell":
                cell_dir = vfx_base / cut_id / "cell"
                ensure_dir(cell_dir)

                version = self.project_manager.get_next_version(cell_dir, base_name)

                if not self.skip_version_confirmation["cell"] and cell_dir.exists() and any(cell_dir.iterdir()):
                    dialog = VersionConfirmDialog("Cell", version, self)
                    if dialog.exec() == QDialog.Accepted:
                        version = dialog.get_version()
                        if dialog.should_skip_confirmation():
                            self.skip_version_confirmation["cell"] = True
                    else:
                        return False

                folder_name = f"{base_name}_T{version}"
                dst_folder = cell_dir / folder_name
                if dst_folder.exists():
                    shutil.rmtree(dst_folder)
                shutil.copytree(src, dst_folder)

            elif material_type == "3dcg":
                ensure_dir(cg_base)
                cg_cut_dir = cg_base / cut_id
                ensure_dir(cg_cut_dir)

                for item in src.iterdir():
                    if item.is_file():
                        copy_file_safe(item, cg_cut_dir / item.name)
                    elif item.is_dir():
                        target_dir = cg_cut_dir / item.name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(item, target_dir)

            else:  # timesheet
                if reuse_cut:
                    dst = vfx_base / "timesheets" / f"{reuse_cut.get_display_name()}.csv"
                else:
                    dst = vfx_base / "timesheets" / f"{cut_id}.csv"
                ensure_dir(dst.parent)
                copy_file_safe(src, dst)

            return True

        except Exception as e:
            print(f"导入失败 ({material_type}): {e}")
            return False

    def copy_aep_template(self):
        """复制AEP模板"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
            if self.cmb_target_episode.currentText():
                ep_id = self.cmb_target_episode.currentText()
                cut_id = self.cmb_target_cut.currentText()
                if not cut_id:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                cut_path = self.project_base / ep_id / "01_vfx" / cut_id
            else:
                cut_id = self.cmb_target_cut.currentText()
                if not cut_id:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                cut_path = self.project_base / "01_vfx" / cut_id
                ep_id = None
        else:
            ep_id = self.cmb_target_episode.currentText()
            cut_id = self.cmb_target_cut.currentText()
            if not ep_id or not cut_id:
                QMessageBox.warning(self, "错误", "请选择目标 Episode 和 Cut")
                return
            cut_path = self.project_base / ep_id / "01_vfx" / cut_id

        # 检查是否是兼用卡
        reuse_cut = self.project_manager.get_reuse_cut_for_cut(cut_id)
        if reuse_cut:
            if ep_id:
                cut_path = self.project_base / ep_id / "01_vfx" / reuse_cut.main_cut
            else:
                cut_path = self.project_base / "01_vfx" / reuse_cut.main_cut

        # 检查模板目录
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists() or not list(template_dir.glob("*.aep")):
            # QMessageBox.warning(
            #     self, "错误", "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件"
            # )
            open_tmp_aep = QMessageBox.question(self,"提示", "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件\n是否手动选择AEP模板？",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if open_tmp_aep == QMessageBox.Yes:
                default_aep_template = self.app_settings.value("default_aep_template", "")
                aep_path, _ = QFileDialog.getOpenFileName(
                    self, "选择 AEP 模板", default_aep_template, "AEP 文件 (*.aep)"
                )
                if aep_path:
                    self.app_settings.setValue("default_aep_template", aep_path)
                    cut_path.mkdir(parents=True, exist_ok=True)
                    if copy_file_safe(Path(aep_path), cut_path / Path(aep_path).name):
                        QMessageBox.information(self, "成功", "已复制 AEP 模板")
                        self._refresh_tree()
                    return
                else:
                    QMessageBox.warning(self, "错误", "未选择 AEP 模板文件")
                    return
            return

        # 复制模板
        proj_name = self.project_base.name
        copied = 0

        for template in template_dir.glob("*.aep"):
            template_stem = template.stem

            if reuse_cut:
                cuts_str = reuse_cut.get_display_name()
                base_name = f"{proj_name}_{ep_id.upper() + '_' if ep_id else ''}{cuts_str}"
            else:
                base_name = f"{proj_name}_{ep_id.upper() + '_' if ep_id else ''}{cut_id}"

            version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"
            aep_name = f"{base_name}{version_part}{template.suffix}"

            if copy_file_safe(template, cut_path / aep_name):
                copied += 1

        message = f"已复制 {copied} 个 AEP 模板到 {'兼用卡 ' + reuse_cut.get_display_name() if reuse_cut else 'Cut ' + cut_id}"
        QMessageBox.information(self, "成功", message)
        self._refresh_tree()

        if self.tabs.currentIndex() == 1 and self.current_cut_id == cut_id:
            self._load_cut_files(cut_id, ep_id)

    def batch_copy_aep_template(self):
        """批量复制AEP模板"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists() or not list(template_dir.glob("*.aep")):
            # QMessageBox.warning(
            #     self, "错误", "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件"
            # )
            open_tmp_aep = QMessageBox.question(self, "提示",
                                                "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件\n是否手动选择AEP模板？",
                                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if open_tmp_aep == QMessageBox.Yes:
                aep_path, _ = QFileDialog.getOpenFileName(
                    self, "选择 AEP 模板", "", "AEP 文件 (*.aep)"
                )
                if template_dir:
                    copy_file_safe(Path(aep_path), template_dir / Path(aep_path).name)
                else:
                    QMessageBox.warning(self, "错误", "未选择 AEP 模板文件")
                    return

        dialog = BatchAepDialog(self.project_config, self)
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            self._batch_copy_with_settings(settings)

    def _batch_copy_with_settings(self, settings: Dict):
        """根据设置批量复制"""
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        templates = list(template_dir.glob("*.aep"))
        proj_name = self.project_base.name

        # 收集目标
        targets = []

        # 获取兼用卡信息
        reuse_cuts_map = {}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            for cut_id in cut.cuts:
                reuse_cuts_map[cut_id] = cut

        if settings["scope"] == 0:  # 所有
            if self.project_config.get("no_episode", False):
                for cut_id in self.project_config.get("cuts", []):
                    if cut_id in reuse_cuts_map and reuse_cuts_map[cut_id].main_cut != cut_id:
                        continue
                    targets.append((None, cut_id))

            for ep_id, cuts in self.project_config.get("episodes", {}).items():
                for cut_id in cuts:
                    if cut_id in reuse_cuts_map and reuse_cuts_map[cut_id].main_cut != cut_id:
                        continue
                    targets.append((ep_id, cut_id))

        elif settings["scope"] >= 1:  # 指定Episode
            ep_id = settings["episode"]
            cuts = self.project_config["episodes"][ep_id]

            if settings["scope"] == 2:
                cut_from = settings["cut_from"]
                cut_to = settings["cut_to"]
                cuts = [cut for cut in cuts if cut.isdigit() and cut_from <= int(cut) <= cut_to]

            for cut_id in cuts:
                if cut_id in reuse_cuts_map and reuse_cuts_map[cut_id].main_cut != cut_id:
                    continue
                targets.append((ep_id, cut_id))

        # 执行复制
        counts = {"success": 0, "skip": 0, "overwrite": 0, "reuse_skip": 0}

        for ep_id, cut_id in targets:
            is_reuse = cut_id in reuse_cuts_map
            reuse_cut = reuse_cuts_map.get(cut_id)

            if settings["skip_reuse"] and is_reuse:
                counts["reuse_skip"] += 1
                continue

            actual_cut_id = reuse_cut.main_cut if is_reuse else cut_id
            cut_path = (self.project_base / ep_id / "01_vfx" / actual_cut_id if ep_id
                        else self.project_base / "01_vfx" / actual_cut_id)

            if not cut_path.exists():
                continue

            if settings["skip_existing"] and list(cut_path.glob("*.aep")):
                counts["skip"] += len(list(cut_path.glob("*.aep")))
                continue

            cut_copied = 0
            for template in templates:
                template_stem = template.stem

                if is_reuse:
                    cuts_str = reuse_cut.get_display_name()
                    base_name = f"{proj_name}_{ep_id.upper() + '_' if ep_id else ''}{cuts_str}"
                else:
                    base_name = f"{proj_name}_{ep_id.upper() + '_' if ep_id else ''}{cut_id}"

                version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"
                aep_name = f"{base_name}{version_part}{template.suffix}"
                dst = cut_path / aep_name

                if dst.exists():
                    if settings["overwrite"]:
                        counts["overwrite"] += 1
                    else:
                        counts["skip"] += 1
                        continue

                if copy_file_safe(template, dst):
                    cut_copied += 1

            if cut_copied > 0:
                counts["success"] += 1

        # 显示结果
        message_lines = [f"✅ 成功为 {counts['success']} 个 Cut 复制了模板"]
        if counts["overwrite"] > 0:
            message_lines.append(f"🔄 覆盖了 {counts['overwrite']} 个文件")
        if counts["skip"] > 0:
            message_lines.append(f"⏭️ 跳过了 {counts['skip']} 个文件")
        if counts["reuse_skip"] > 0:
            message_lines.append(f"🔗 跳过了 {counts['reuse_skip']} 个兼用卡")

        QMessageBox.information(self, "批量复制完成", "\n".join(message_lines))
        self._refresh_tree()

    # ========================== UI 更新方法 ========================== #

    def _on_project_changed(self):
        """项目变更时的处理"""
        if self.project_base and self.project_config:
            self.lbl_project_path.setText(str(self.project_base))
            self.lbl_project_path.setStyleSheet("color: #0D7ACC;")

            no_episode = self.project_config.get("no_episode", False)
            self.chk_no_episode.setChecked(no_episode)

            self._refresh_all_views()

            self.current_cut_id = None
            self.current_episode_id = None
            self.current_path = None

            if self.txt_cut_search:
                self.txt_cut_search.clear()

            self._enable_controls(True)
            self.statusbar.showMessage(f"当前项目: {self.project_base.name}")
        else:
            self.lbl_project_path.setText("未打开项目")
            self.lbl_project_path.setStyleSheet("color: #999; font-style: italic;")
            self._clear_all_views()
            self._enable_controls(False)
            self.statusbar.showMessage("请打开或新建项目以开始使用")

    def _refresh_all_views(self):
        """刷新所有视图"""
        self._refresh_tree()
        self._update_import_combos()
        self._update_cut_episode_combo()
        self._update_project_stats()
        self._update_browser_tree()
        self._toggle_episode_mode(self.chk_no_episode.checkState())

    def _clear_all_views(self):
        """清空所有视图"""
        self.tree.clear()
        self.cmb_target_episode.clear()
        self.cmb_cut_episode.clear()
        self.cmb_target_cut.clear()
        self._clear_file_lists()
        self.txt_project_stats.clear()
        self.browser_tree.clear()
        self.current_cut_id = None
        self.current_episode_id = None
        self.current_path = None
        if self.txt_cut_search:
            self.txt_cut_search.clear()

    def _on_episode_type_changed(self, episode_type: str):
        """Episode类型变化时的处理"""
        if self.chk_no_episode.isChecked() and episode_type.lower() == "ep":
            self.btn_create_episode.setEnabled(False)
            self.btn_batch_episode.setEnabled(False)
            self.spin_ep_from.setEnabled(False)
            self.spin_ep_to.setEnabled(False)
            self.btn_create_episode.setToolTip("单集模式下不能创建标准集数(ep)")
        else:
            self.btn_create_episode.setEnabled(True)
            self.btn_create_episode.setToolTip("")

        if episode_type.lower() == "ep" and not self.chk_no_episode.isChecked():
            self.txt_episode.setPlaceholderText("编号 (如: 01, 02) - 可留空")
            self.btn_batch_episode.setEnabled(True)
            self.spin_ep_from.setEnabled(True)
            self.spin_ep_to.setEnabled(True)
        else:
            self.txt_episode.setPlaceholderText("名称或编号 (可选) - 可留空")
            self.btn_batch_episode.setEnabled(False)
            self.spin_ep_from.setEnabled(False)
            self.spin_ep_to.setEnabled(False)

    def _on_episode_changed(self, episode: str):
        """Episode选择变化时更新Cut列表"""
        self.cmb_target_cut.clear()

        if not self.project_config or not episode:
            if self.project_config and self.project_config.get("no_episode", False):
                cuts = self.project_config.get("cuts", [])
                if cuts:
                    self.cmb_target_cut.addItems(sorted(cuts))
            return

        cuts = self.project_config.get("episodes", {}).get(episode, [])
        if cuts:
            self.cmb_target_cut.addItems(sorted(cuts))

    def _toggle_episode_mode(self, state: int):
        """切换Episode模式"""
        no_episode = self.chk_no_episode.isChecked()

        if no_episode:
            self.episode_group.setEnabled(True)
            self.episode_group.setTitle("🎬 特殊 Episode 管理 (op/ed/pv等)")
            if self.cmb_episode_type.currentText().lower() == "ep":
                self.cmb_episode_type.setCurrentText("pv")
        else:
            self.episode_group.setEnabled(True)
            self.episode_group.setTitle("🎬 Episode 管理")

        self.cmb_cut_episode.setVisible(True)
        if no_episode:
            self.cmb_cut_episode.setPlaceholderText("选择特殊 Episode (可选)")
        else:
            self.cmb_cut_episode.setPlaceholderText("选择 Episode")

        self.cmb_target_episode.setVisible(True)

        if self.project_config:
            self.project_config["no_episode"] = no_episode
            self.project_manager.project_config = self.project_config
            self.project_manager.save_config()
            self._update_import_combos()
            self._update_cut_episode_combo()

    def _enable_controls(self, enabled: bool):
        """启用/禁用控件"""
        controls = [
            self.chk_no_episode, self.episode_group, self.cmb_episode_type,
            self.txt_episode, self.btn_create_episode, self.btn_batch_episode,
            self.spin_ep_from, self.spin_ep_to, self.cmb_cut_episode,
            self.txt_cut, self.btn_create_cut, self.btn_batch_cut,
            self.spin_cut_from, self.spin_cut_to, self.btn_create_reuse_cut,
            self.cmb_target_episode, self.cmb_target_cut
        ]

        controls.extend(self.material_paths.values())
        controls.extend(self.material_buttons.values())

        for control in controls:
            if control:
                control.setEnabled(enabled)

        if enabled and hasattr(self, 'cmb_episode_type'):
            self._on_episode_type_changed(self.cmb_episode_type.currentText())

    def _refresh_tree(self):
        """刷新目录树"""
        self.tree.clear()

        if not self.project_base or not self.project_base.exists():
            return

        def add_items(parent_item: QTreeWidgetItem, path: Path, depth: int = 0):
            if depth > 5:
                return

            try:
                for item_path in sorted(path.iterdir()):
                    if item_path.name.startswith('.'):
                        continue

                    item = QTreeWidgetItem([item_path.name])
                    parent_item.addChild(item)

                    if item_path.is_dir():
                        item.setToolTip(0, str(item_path))
                        add_items(item, item_path, depth + 1)
                    else:
                        item.setToolTip(0, f"{item_path.name} ({item_path.stat().st_size:,} bytes)")
            except PermissionError:
                pass

        root_item = QTreeWidgetItem([self.project_base.name])
        self.tree.addTopLevelItem(root_item)
        add_items(root_item, self.project_base)
        self.tree.expandToDepth(2)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """树节点双击事件"""
        # 获取完整路径
        path_parts = []
        current = item
        while current:
            path_parts.insert(0, current.text(0))
            current = current.parent()

        # 构建完整路径
        if path_parts:
            # 第一个部分是项目名，需要使用项目基础路径
            full_path = self.project_base
            for part in path_parts[1:]:  # 跳过项目名
                full_path = full_path / part

            if full_path.exists():
                open_in_file_manager(full_path)

    def _update_import_combos(self):
        """更新导入面板的下拉列表"""
        self.cmb_target_episode.clear()
        self.cmb_target_cut.clear()

        if not self.project_config:
            return

        if self.project_config.get("no_episode", False):
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                self.cmb_target_episode.setCurrentIndex(-1)

            cuts = self.project_config.get("cuts", [])
            if cuts:
                self.cmb_target_cut.addItems(sorted(cuts))
        else:
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                self.cmb_target_episode.setCurrentIndex(-1)

    def _update_project_stats(self):
        """更新项目统计信息"""
        if not self.project_config:
            return

        stats_lines = []
        stats_lines.append(f"项目名称: {self.project_config.get('project_name', 'Unknown')}")
        stats_lines.append(f"创建时间: {self.project_config.get('created_time', 'Unknown')[:10]}")
        stats_lines.append(f"最后修改: {self.project_config.get('last_modified', 'Unknown')[:10]}")
        stats_lines.append("")

        reuse_cuts = self.project_config.get("reuse_cuts", [])
        if reuse_cuts:
            stats_lines.append(f"兼用卡数量: {len(reuse_cuts)}")
            total_reuse_cuts = sum(len(cut["cuts"]) for cut in reuse_cuts)
            stats_lines.append(f"兼用Cut总数: {total_reuse_cuts}")
            stats_lines.append("")

        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            stats_lines.append(f"模式: 单集/PV 模式")
            stats_lines.append(f"根目录 Cut 数: {len(cuts)}")

            episodes = self.project_config.get("episodes", {})
            if episodes:
                special_count = sum(len(cuts) for cuts in episodes.values())
                stats_lines.append(f"特殊 Episode 数: {len(episodes)}")
                stats_lines.append(f"特殊 Episode 内 Cut 数: {special_count}")
                stats_lines.append("")
                stats_lines.append("特殊 Episode 详情:")
                for ep_id in sorted(episodes.keys()):
                    cut_count = len(episodes[ep_id])
                    stats_lines.append(f"  {ep_id}: {cut_count} cuts" if cut_count > 0 else f"  {ep_id}: (空)")
        else:
            episodes = self.project_config.get("episodes", {})
            total_cuts = sum(len(cuts) for cuts in episodes.values())

            stats_lines.append(f"模式: Episode 模式")
            stats_lines.append(f"Episode 总数: {len(episodes)}")
            stats_lines.append(f"Cut 总数: {total_cuts}")

            if episodes:
                stats_lines.append("")
                stats_lines.append("Episode 详情:")
                for ep_id in sorted(episodes.keys()):
                    cut_count = len(episodes[ep_id])
                    stats_lines.append(f"  {ep_id}: {cut_count} cuts" if cut_count > 0 else f"  {ep_id}: (空)")

        if reuse_cuts:
            stats_lines.append("")
            stats_lines.append("兼用卡详情:")
            for cut_data in reuse_cuts:
                cut = ReuseCut.from_dict(cut_data)
                ep_info = f" ({cut.episode_id})" if cut.episode_id else ""
                stats_lines.append(f"  {cut.get_display_name()}{ep_info}")

        self.txt_project_stats.setText("\n".join(stats_lines))

    def _update_browser_tree(self):
        """更新浏览器的Episode/Cut树"""
        self.browser_tree.clear()

        if not self.project_config:
            return

        # 获取兼用卡信息
        reuse_cuts_map = {}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.episode_id:
                for cut_id in cut.cuts:
                    reuse_cuts_map[f"{cut.episode_id}:{cut_id}"] = cut
            else:
                for cut_id in cut.cuts:
                    reuse_cuts_map[f"root:{cut_id}"] = cut

        # 单集模式
        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            if cuts:
                root_item = QTreeWidgetItem(["根目录 Cuts"])
                root_item.setData(0, Qt.UserRole, {"type": "root"})
                self.browser_tree.addTopLevelItem(root_item)

                for cut_id in sorted(cuts):
                    key = f"root:{cut_id}"
                    if key in reuse_cuts_map:
                        cut = reuse_cuts_map[key]
                        display_name = f"{cut_id} [兼用卡: {cut.get_display_name()}]"
                        item = QTreeWidgetItem([display_name])
                        item.setForeground(0, QBrush(QColor("#FF9800")))
                    else:
                        item = QTreeWidgetItem([cut_id])

                    item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": None})
                    root_item.addChild(item)

                root_item.setExpanded(True)

            # 特殊Episodes
            episodes = self.project_config.get("episodes", {})
            if episodes:
                for ep_id in sorted(episodes.keys()):
                    ep_item = QTreeWidgetItem([f"📁 {ep_id}"])
                    ep_item.setData(0, Qt.UserRole, {"episode": ep_id})
                    self.browser_tree.addTopLevelItem(ep_item)

                    for cut_id in sorted(episodes[ep_id]):
                        key = f"{ep_id}:{cut_id}"
                        if key in reuse_cuts_map:
                            cut = reuse_cuts_map[key]
                            display_name = f"{cut_id} [兼用卡: {cut.get_display_name()}]"
                            cut_item = QTreeWidgetItem([display_name])
                            cut_item.setForeground(0, QBrush(QColor("#FF9800")))
                        else:
                            cut_item = QTreeWidgetItem([cut_id])

                        cut_item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": ep_id})
                        ep_item.addChild(cut_item)

                    ep_item.setExpanded(True)
        else:
            # 标准模式
            episodes = self.project_config.get("episodes", {})
            for ep_id in sorted(episodes.keys()):
                ep_item = QTreeWidgetItem([ep_id])
                ep_item.setData(0, Qt.UserRole, {"episode": ep_id})
                self.browser_tree.addTopLevelItem(ep_item)

                for cut_id in sorted(episodes[ep_id]):
                    key = f"{ep_id}:{cut_id}"
                    if key in reuse_cuts_map:
                        cut = reuse_cuts_map[key]
                        display_name = f"{cut_id} [兼用卡: {cut.get_display_name()}]"
                        cut_item = QTreeWidgetItem([display_name])
                        cut_item.setForeground(0, QBrush(QColor("#FF9800")))
                    else:
                        cut_item = QTreeWidgetItem([cut_id])

                    cut_item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": ep_id})
                    ep_item.addChild(cut_item)

                ep_item.setExpanded(True)

        # 如果搜索框有内容，重新应用搜索
        if self.txt_cut_search and self.txt_cut_search.text().strip():
            self._on_cut_search_changed(self.txt_cut_search.text())

    def _update_cut_episode_combo(self):
        """更新Cut管理中的Episode下拉列表"""
        self.cmb_cut_episode.clear()

        if not self.project_config:
            return

        episodes = self.project_config.get("episodes", {})
        if episodes:
            self.cmb_cut_episode.addItems(sorted(episodes.keys()))
            self.cmb_cut_episode.setCurrentIndex(-1)

    def _on_browser_tree_clicked(self, item: QTreeWidgetItem):
        """处理浏览器树的点击事件"""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if "cut" in data and data["cut"]:
            self.current_cut_id = data["cut"]
            self.current_episode_id = data.get("episode")
            self._load_cut_files(self.current_cut_id, self.current_episode_id)
            self._update_current_path_label()
        else:
            self._clear_file_lists()
            self.current_cut_id = None
            self.current_episode_id = data.get("episode")
            if self.current_episode_id:
                self.lbl_current_cut.setText(f"当前位置：{self.current_episode_id} (请选择具体的 Cut)")
            elif data.get("type") == "root":
                self.lbl_current_cut.setText("当前位置：根目录 (请选择具体的 Cut)")

    def _on_file_tab_changed(self, index: int):
        """处理文件Tab切换"""
        self._update_current_path_label()

    def _update_current_path_label(self):
        """更新当前路径标签"""
        if not self.project_base or not self.current_cut_id:
            self.lbl_current_cut.setText("当前位置：未选择")
            self.current_path = None
            return

        current_index = self.file_tabs.currentIndex()
        tab_names = ["VFX", "Cell", "BG", "Render", "3DCG"]

        if current_index < 0 or current_index >= len(tab_names):
            return

        tab_name = tab_names[current_index]

        # 检查是否是兼用卡
        reuse_cut = self.project_manager.get_reuse_cut_for_cut(self.current_cut_id)
        if reuse_cut:
            actual_cut_id = reuse_cut.main_cut
            display_cut_id = reuse_cut.get_display_name()
        else:
            actual_cut_id = self.current_cut_id
            display_cut_id = self.current_cut_id

        # 构建路径
        if self.current_episode_id:
            if tab_name in ["VFX", "Cell", "BG"]:
                path = self.project_base / self.current_episode_id / "01_vfx" / actual_cut_id
                if tab_name == "Cell":
                    path = path / "cell"
                elif tab_name == "BG":
                    path = path / "bg"
            elif tab_name == "Render":
                path = self.project_base / "06_render" / self.current_episode_id / actual_cut_id
            elif tab_name == "3DCG":
                path = self.project_base / self.current_episode_id / "02_3dcg" / actual_cut_id
        else:
            if tab_name in ["VFX", "Cell", "BG"]:
                path = self.project_base / "01_vfx" / actual_cut_id
                if tab_name == "Cell":
                    path = path / "cell"
                elif tab_name == "BG":
                    path = path / "bg"
            elif tab_name == "Render":
                path = self.project_base / "06_render" / actual_cut_id
            elif tab_name == "3DCG":
                path = self.project_base / "02_3dcg" / actual_cut_id

        self.current_path = path
        path_str = str(path).replace("\\", "/")

        # 如果路径太长，显示缩略版本
        if len(path_str) > 100:
            relative_path = path.relative_to(self.project_base.parent)
            display_path = f".../{relative_path}"
        else:
            display_path = path_str

        if reuse_cut:
            self.lbl_current_cut.setText(f"📁 {tab_name} [兼用卡 {display_cut_id}]: {display_path}")
        else:
            self.lbl_current_cut.setText(f"📁 {tab_name}: {display_path}")
        self.lbl_current_cut.setToolTip(path_str)

    def _show_path_context_menu(self, position):
        """显示路径标签的右键菜单"""
        if not self.current_path:
            return

        menu = QMenu(self)

        act_copy = QAction("复制路径", self)
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(str(self.current_path)))
        menu.addAction(act_copy)

        act_open = QAction("在文件管理器中打开", self)
        act_open.triggered.connect(lambda: open_in_file_manager(self.current_path))
        menu.addAction(act_open)

        menu.exec_(self.lbl_current_cut.mapToGlobal(position))

    def _load_cut_files(self, cut_id: str, episode_id: Optional[str] = None):
        """加载指定Cut的文件列表"""
        self._clear_file_lists()

        if not self.project_base:
            return

        # 检查是否是兼用卡
        reuse_cut = self.project_manager.get_reuse_cut_for_cut(cut_id)
        actual_cut_id = reuse_cut.main_cut if reuse_cut else cut_id

        # 确定路径
        if episode_id:
            vfx_path = self.project_base / episode_id / "01_vfx" / actual_cut_id
            render_path = self.project_base / "06_render" / episode_id / actual_cut_id
            cg_path = self.project_base / episode_id / "02_3dcg" / actual_cut_id
        else:
            vfx_path = self.project_base / "01_vfx" / actual_cut_id
            render_path = self.project_base / "06_render" / actual_cut_id
            cg_path = self.project_base / "02_3dcg" / actual_cut_id

        # 加载文件
        self._load_vfx_files(vfx_path)
        self._load_cell_files(vfx_path / "cell")
        self._load_bg_files(vfx_path / "bg")
        self._load_render_files(render_path)
        self._load_cg_files(cg_path)

        self._update_file_tab_titles()

    def _load_vfx_files(self, vfx_path: Path):
        """加载VFX文件"""
        list_widget = self.file_lists["vfx"]
        if vfx_path.exists():
            list_widget.load_files(vfx_path, "*.aep")

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 AEP 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _load_cell_files(self, cell_path: Path):
        """加载Cell文件"""
        list_widget = self.file_lists["cell"]
        if not cell_path.exists():
            return

        folders = []
        for folder in cell_path.iterdir():
            if folder.is_dir():
                file_info = get_file_info(folder)
                if file_info.version is not None:
                    folders.append(file_info)

        folders.sort(key=lambda f: f.modified_time, reverse=True)

        for folder_info in folders:
            list_widget.add_file_item(folder_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 Cell 文件夹)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _load_bg_files(self, bg_path: Path):
        """加载BG文件"""
        list_widget = self.file_lists["bg"]
        if not bg_path.exists():
            return

        files = []
        for file in bg_path.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(get_file_info(file))

        files.sort(key=lambda f: f.modified_time, reverse=True)

        for file_info in files:
            list_widget.add_file_item(file_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 BG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _load_render_files(self, render_path: Path):
        """加载渲染文件"""
        list_widget = self.file_lists["render"]

        if not render_path.exists():
            no_render_info = FileInfo(
                path=render_path,
                name="未渲染",
                modified_time=datetime.now(),
                size=0,
                is_folder=False,
                is_no_render=True
            )
            list_widget.add_file_item(no_render_info)
            return

        render_items = []
        has_any_render = False

        # PNG序列
        png_path = render_path / "png_seq"
        if png_path.exists() and any(png_path.glob("*.png")):
            render_items.append(get_png_seq_info(png_path))
            has_any_render = True

        # ProRes视频
        prores_path = render_path / "prores"
        if prores_path.exists():
            for file in prores_path.glob("*.mov"):
                render_items.append(get_file_info(file))
                has_any_render = True

        # MP4视频
        mp4_path = render_path / "mp4"
        if mp4_path.exists():
            for file in mp4_path.glob("*.mp4"):
                render_items.append(get_file_info(file))
                has_any_render = True

        if has_any_render:
            render_items.sort(key=lambda f: f.modified_time, reverse=True)

        for item_info in render_items:
            list_widget.add_file_item(item_info)

    def _load_cg_files(self, cg_path: Path):
        """加载3DCG文件"""
        list_widget = self.file_lists["3dcg"]
        if not cg_path.exists():
            return

        files = []
        for item in cg_path.rglob("*"):
            if item.is_file():
                files.append(get_file_info(item))

        files.sort(key=lambda f: f.modified_time, reverse=True)

        for file_info in files:
            list_widget.add_file_item(file_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 3DCG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _update_file_tab_titles(self):
        """更新文件Tab的标题"""
        tab_info = [
            (0, "VFX", self.file_lists["vfx"]),
            (1, "Cell", self.file_lists["cell"]),
            (2, "BG", self.file_lists["bg"]),
            (3, "Render", self.file_lists["render"]),
            (4, "3DCG", self.file_lists["3dcg"]),
        ]

        for index, name, list_widget in tab_info:
            count = list_widget.count()
            if count > 0 and list_widget.item(0).data(Qt.UserRole) is not None:
                self.file_tabs.setTabText(index, f"{name} ({count})")
            else:
                self.file_tabs.setTabText(index, name)

    def _clear_file_lists(self):
        """清空所有文件列表"""
        for list_widget in self.file_lists.values():
            list_widget.clear()

        for i, name in enumerate(["VFX", "Cell", "BG", "Render", "3DCG"]):
            self.file_tabs.setTabText(i, name)

    def _on_file_item_double_clicked(self, item: QListWidgetItem):
        """处理文件项目双击"""
        file_path = item.data(Qt.UserRole)
        if not file_path:
            return

        path = Path(file_path)
        if not path.exists():
            return

        if path.suffix.lower() in VIDEO_EXTENSIONS:
            self._play_video(path)
        else:
            open_in_file_manager(path)

    def _play_video(self, video_path: Path):
        """使用默认播放器播放视频"""
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(str(video_path))
            elif system == "Darwin":
                subprocess.run(["open", str(video_path)])
            else:
                subprocess.run(["xdg-open", str(video_path)])
        except Exception as e:
            print(f"播放视频失败: {e}")

    def _on_cut_search_changed(self, text: str):
        """处理Cut搜索框内容变化"""
        search_text = text.strip().lower()

        if not search_text:
            self._show_all_tree_items()
            self.browser_tree.setHeaderLabel("选择要浏览的 Cut")
            return

        match_count = 0
        first_match = None

        # 获取兼用卡信息
        reuse_cuts_by_location = {"root": [], "episodes": {}}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.episode_id:
                if cut.episode_id not in reuse_cuts_by_location["episodes"]:
                    reuse_cuts_by_location["episodes"][cut.episode_id] = []
                reuse_cuts_by_location["episodes"][cut.episode_id].append(cut)
            else:
                reuse_cuts_by_location["root"].append(cut)

        def search_items(item: QTreeWidgetItem):
            nonlocal match_count, first_match
            item_text = item.text(0).lower()

            data = item.data(0, Qt.UserRole)
            cut_id = data.get("cut") if data else None
            episode_id = data.get("episode") if data else None

            has_match = False
            if search_text in item_text:
                has_match = True
            elif search_text.isdigit() and cut_id:
                if search_text in cut_id:
                    has_match = True

                # 检查兼用卡
                if episode_id:
                    for cut in reuse_cuts_by_location["episodes"].get(episode_id, []):
                        if cut.contains_cut(cut_id):
                            for reuse_cut in cut.cuts:
                                if search_text in reuse_cut:
                                    has_match = True
                                    break
                else:
                    for cut in reuse_cuts_by_location["root"]:
                        if cut.contains_cut(cut_id):
                            for reuse_cut in cut.cuts:
                                if search_text in reuse_cut:
                                    has_match = True
                                    break

            has_child_match = False

            for i in range(item.childCount()):
                child = item.child(i)
                if search_items(child):
                    has_child_match = True

            should_show = has_match or has_child_match
            item.setHidden(not should_show)

            if has_match and item.childCount() == 0:
                item.setForeground(0, QBrush(QColor("#4CAF50")))
                item.setFont(0, QFont("MiSans", -1, QFont.Bold))
                match_count += 1
                if first_match is None:
                    first_match = item
            else:
                # 恢复原始样式
                if cut_id:
                    is_reuse = False
                    if episode_id:
                        for cut in reuse_cuts_by_location["episodes"].get(episode_id, []):
                            if cut.contains_cut(cut_id):
                                is_reuse = True
                                break
                    else:
                        for cut in reuse_cuts_by_location["root"]:
                            if cut.contains_cut(cut_id):
                                is_reuse = True
                                break

                    if is_reuse:
                        item.setForeground(0, QBrush(QColor("#FF9800")))
                    else:
                        item.setForeground(0, QBrush())
                else:
                    item.setForeground(0, QBrush())
                item.setFont(0, QFont())

            if has_child_match:
                item.setExpanded(True)

            return should_show

        for i in range(self.browser_tree.topLevelItemCount()):
            search_items(self.browser_tree.topLevelItem(i))

        if match_count > 0:
            self.browser_tree.setHeaderLabel(f"搜索结果: {match_count} 个Cut")
        else:
            self.browser_tree.setHeaderLabel("没有找到匹配的Cut")

    def _select_first_match(self):
        """选择第一个匹配的Cut"""

        def find_first_visible_leaf(item: QTreeWidgetItem):
            if not item.isHidden():
                if item.childCount() == 0:
                    return item
                for i in range(item.childCount()):
                    result = find_first_visible_leaf(item.child(i))
                    if result:
                        return result
            return None

        for i in range(self.browser_tree.topLevelItemCount()):
            result = find_first_visible_leaf(self.browser_tree.topLevelItem(i))
            if result:
                self.browser_tree.setCurrentItem(result)
                self._on_browser_tree_clicked(result)
                break

    def _show_all_tree_items(self):
        """显示所有树项目"""
        reuse_cuts_by_location = {"root": [], "episodes": {}}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.episode_id:
                if cut.episode_id not in reuse_cuts_by_location["episodes"]:
                    reuse_cuts_by_location["episodes"][cut.episode_id] = []
                reuse_cuts_by_location["episodes"][cut.episode_id].append(cut)
            else:
                reuse_cuts_by_location["root"].append(cut)

        def show_items(item: QTreeWidgetItem):
            item.setHidden(False)

            data = item.data(0, Qt.UserRole)
            cut_id = data.get("cut") if data else None
            episode_id = data.get("episode") if data else None

            if cut_id:
                is_reuse = False
                if episode_id:
                    for cut in reuse_cuts_by_location["episodes"].get(episode_id, []):
                        if cut.contains_cut(cut_id):
                            is_reuse = True
                            break
                else:
                    for cut in reuse_cuts_by_location["root"]:
                        if cut.contains_cut(cut_id):
                            is_reuse = True
                            break

                if is_reuse:
                    item.setForeground(0, QBrush(QColor("#FF9800")))
                else:
                    item.setForeground(0, QBrush())
            else:
                item.setForeground(0, QBrush())

            item.setFont(0, QFont())

            for i in range(item.childCount()):
                show_items(item.child(i))

        for i in range(self.browser_tree.topLevelItemCount()):
            show_items(self.browser_tree.topLevelItem(i))

        self.browser_tree.setHeaderLabel("选择要浏览的 Cut")

    def _focus_cut_search(self):
        """聚焦到Cut搜索框"""
        if self.txt_cut_search:
            self.tabs.setCurrentIndex(1)
            self.txt_cut_search.setFocus()
            self.txt_cut_search.selectAll()

    # ========================== 软件设置 ========================== #

    def _load_app_settings(self):
        """加载软件设置"""
        geometry = self.app_settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

        default_path = self.app_settings.value("default_project_path", "")
        if default_path and Path(default_path).exists():
            self.btn_new_project.setToolTip(f"将创建到: {default_path}")
            self.statusbar.showMessage(f"默认项目路径: {default_path}")
        else:
            self.btn_new_project.setToolTip("点击后选择创建位置")
            self.statusbar.showMessage("未设置默认项目路径，新建项目时需要选择位置")

        # last_project = self.app_settings.value("last_project")
        # if last_project and Path(last_project).exists():
        #     self._load_project(last_project)

    def _save_app_settings(self):
        """保存软件设置"""
        self.app_settings.setValue("window_geometry", self.saveGeometry())
        if self.project_base:
            self.app_settings.setValue("last_project", str(self.project_base))

    def set_default_path(self):
        """设置默认项目路径"""
        current = self.app_settings.value("default_project_path", "")
        folder = QFileDialog.getExistingDirectory(self, "设置默认项目路径", current)

        if folder:
            self.app_settings.setValue("default_project_path", folder)
            self.btn_new_project.setToolTip(f"将创建到: {folder}")

            # 更新项目注册管理器的路径
            self.project_registry.registry_path = self.project_registry._get_registry_path()
            self.project_registry.load_registry()

            QMessageBox.information(self, "成功", f"默认项目路径已设置为:\n{folder}")

    def _update_recent_menu(self):
        """刷新『最近项目』菜单"""
        self.recent_menu.clear()

        # 取出最近项目并过滤掉已失效的路径
        recent_paths = cast(list[str], self.app_settings.value("recent_projects", []))
        recent_list = [p for p in recent_paths if Path(p).exists()]

        if not recent_list:
            action = self.recent_menu.addAction("(无最近项目)")
            action.setEnabled(False)
            return

        for idx, path in enumerate(recent_list[:10]):
            act = QAction(Path(path).name, self)
            if idx == 0:  # 只有第 1 个加快捷键
                act.setShortcut("Ctrl+R")
            act.setToolTip(path)
            act.triggered.connect(lambda _=False, p=path: self.open_recent_project(p))
            self.recent_menu.addAction(act)

    def open_recent_project(self, path: str):
        """打开最近项目"""
        if Path(path).exists():
            self._load_project(path)
        else:
            QMessageBox.warning(self, "错误", f"项目路径不存在：\n{path}")
            self._remove_from_recent(path)

    def _add_to_recent(self, path: str):
        """添加到最近项目"""
        recent = self.app_settings.value("recent_projects", [])

        if path in recent:
            recent.remove(path)

        recent.insert(0, path)
        recent = recent[:20]

        self.app_settings.setValue("recent_projects", recent)
        self._update_recent_menu()

    def _remove_from_recent(self, path: str):
        """从最近项目中移除"""
        recent = self.app_settings.value("recent_projects", [])
        if path in recent:
            recent.remove(path)
            self.app_settings.setValue("recent_projects", recent)
            self._update_recent_menu()

    # ========================== 其他功能 ========================== #

    def open_in_explorer(self):
        """在文件管理器中打开项目根目录"""
        if self.project_base:
            open_in_file_manager(self.project_base)

    def show_help(self):
        """显示帮助信息"""
        help_text = f"""
CX Project Manager 使用说明
========================

版本: {version_info.get("version", "2.2")} {version_info.get("build-version", "")}

## 新增功能
- **项目注册管理**: 自动记录所有创建的项目信息
- **项目浏览器**: 浏览和管理所有已注册的项目
- **目录树双击**: 双击目录树节点直接打开文件夹

## 项目模式
- **标准模式**: 支持创建多个Episode（ep01, ep02等）
- **单集/PV模式**: 根目录下直接创建Cut，支持特殊Episode

## 快捷键
- Ctrl+N: 新建项目
- Ctrl+O: 打开项目
- Ctrl+F: 搜索Cut
- F5: 刷新目录树
- Ctrl+Q: 退出

## 项目注册
- 创建项目时自动注册到项目管理系统
- 记录项目名称、Episode数、创建时间、路径等信息
- 通过"文件 > 浏览所有项目"查看所有已注册项目
- 支持删除不需要的项目记录（仅删除记录，不删除文件）

作者: {version_info.get("author", "千石まよひ")}
"""

        dialog = QMessageBox(self)
        dialog.setWindowTitle("使用说明")
        dialog.setText(help_text)
        dialog.setTextFormat(Qt.PlainText)
        dialog.setStyleSheet("""
            QMessageBox {
                min-width: 700px;
            }
            QLabel {
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)
        dialog.exec_()

    def show_about(self):
        """显示关于对话框"""
        about_text = f"""CX Project Manager - 动画项目管理工具

版本: {version_info.get("version", "Unknow")} {version_info.get("build-version", "")}
作者: {version_info.get("author", "千石まよひ")}
邮箱: {version_info.get("email", "tammcx@gmail.com")}
GitHub: https://github.com/ChenxingM/CXProjectManager

{version_info.get("description", "动画项目管理工具，专为动画制作流程优化设计。")}

新增项目注册管理系统，支持浏览和管理所有创建的项目。

如有问题或建议，欢迎在GitHub提交Issue。"""

        QMessageBox.about(self, "关于", about_text)

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._save_app_settings()
        event.accept()