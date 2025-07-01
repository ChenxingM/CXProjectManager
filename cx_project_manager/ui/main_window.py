# -*- coding: utf-8 -*-
"""
主窗口类模块

通过 Mixin 模式将功能分散到不同模块，提高可维护性。
"""

from pathlib import Path
from typing import Dict, Optional
from functools import partial

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QPushButton,
    QSpinBox, QSplitter, QStatusBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QTabWidget, QTextEdit, QMessageBox
)

from cx_project_manager.utils.qss import QSS_THEME
from cx_project_manager.utils.version_info import version_info
from cx_project_manager.utils.constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS, EpisodeType
from cx_project_manager.core import ProjectManager, ProjectRegistry
from cx_project_manager.utils.models import FileInfo, ReuseCut
from cx_project_manager.utils.utils import (
    ensure_dir, copy_file_safe, open_in_file_manager, get_file_info,
    get_png_seq_info, extract_version_from_filename
)
from cx_project_manager.ui.widgets import SearchLineEdit, DetailedFileListWidget
from cx_project_manager.ui.mixins import (
    ProjectMixin, EpisodeCutMixin, ImportMixin,
    BrowserMixin, VersionMixin, MenuMixin
)

# 项目结构中文注释映射
PROJECT_STRUCTURE_NAMES = {
    "00_reference_project": "00_项目参考",
    "00_reference": "00_参考",
    "art_design": "美术",
    "character_design": "角色设定",
    "concept_art": "氛围图",
    "docs": "文档",
    "other_design": "其他设计",
    "storyboard": "分镜",
    "director_notes": "导演笔记",
    "script": "脚本",
    "01_vfx": "01_摄影",
    "02_3dcg": "02_3DCG",
    "03_preview": "03_预览",
    "04_log": "04_日志",
    "05_output_mixdown": "05_输出混音",
    "05_stills": "05_缩略图",
    "06_render": "06_渲染输出",
    "07_master_assets": "07_主资产",
    "08_tools": "08_工具",
    "09_edit": "09_剪辑",
    "98_tmp": "98_临时文件",
    "99_other": "99_其他",
    "aep_templates": "AEP模板",
    "timesheets": "摄影表",
    "bg": "背景",
    "cell": "Cell动画",
    "prerender": "预渲染",
    "png_seq": "PNG序列",
    "prores": "ProRes视频",
    "mp4": "MP4视频",
    "footage": "素材片段",
    "project_config.json": "项目配置文件",
    "README.md": "项目文档",
    "project": "剪辑工程",
    "output": "剪辑输出",
    "fonts": "字体资源",
    "fx_presets": "特效预设",
    "logo": "Logo资源",
    "ae_scripts": "AE脚本",
    "config": "配置文件",
    "python": "Python脚本",
}


class CXProjectManager(QMainWindow, ProjectMixin, EpisodeCutMixin,
                       ImportMixin, BrowserMixin, VersionMixin, MenuMixin):
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
        # 添加右键菜单支持
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
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

        # layout.addWidget(stats_group)

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
            # 添加右键菜单支持
            list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(
                lambda pos, n=name.lower(): self._show_file_context_menu(pos, n))
            self.file_lists[name.lower()] = list_widget
            self.file_tabs.addTab(list_widget, name)

        files_layout.addWidget(self.file_tabs)
        layout.addWidget(files_group)

        return panel

    def _set_initial_state(self):
        """设置初始状态"""
        self._enable_controls(False)
        self.txt_project_name.setEnabled(True)
        self.btn_new_project.setEnabled(True)
        self.btn_open_project.setEnabled(True)

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

                    # 获取显示名称（添加中文注释）
                    display_name = item_path.name
                    if item_path.name in PROJECT_STRUCTURE_NAMES:
                        display_name = PROJECT_STRUCTURE_NAMES[item_path.name]

                    item = QTreeWidgetItem([display_name])
                    parent_item.addChild(item)

                    if item_path.is_dir():
                        item.setToolTip(0, str(item_path))
                        # 存储实际路径以供右键菜单使用
                        item.setData(0, Qt.UserRole, str(item_path))
                        add_items(item, item_path, depth + 1)
                    else:
                        item.setToolTip(0, f"{item_path.name} ({item_path.stat().st_size:,} bytes)")
                        item.setData(0, Qt.UserRole, str(item_path))
            except PermissionError:
                pass

        root_item = QTreeWidgetItem([self.project_base.name])
        root_item.setData(0, Qt.UserRole, str(self.project_base))
        self.tree.addTopLevelItem(root_item)
        add_items(root_item, self.project_base)
        self.tree.expandToDepth(2)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """树节点双击事件"""
        # 从UserRole获取实际路径
        path_str = item.data(0, Qt.UserRole)
        if path_str:
            full_path = Path(path_str)
            if full_path.exists():
                open_in_file_manager(full_path)

    def _show_tree_context_menu(self, position):
        """显示树形结构的右键菜单"""
        from PySide6.QtGui import QAction

        item = self.tree.itemAt(position)
        if not item:
            return

        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            return

        path = Path(path_str)
        if not path.is_dir():
            return

        menu = QMenu(self)

        # 打开文件夹
        act_open = QAction("在文件管理器中打开", self)
        act_open.triggered.connect(lambda: open_in_file_manager(path))
        menu.addAction(act_open)

        menu.addSeparator()

        # 导入文件
        act_import = QAction("导入文件到此文件夹...", self)
        act_import.triggered.connect(lambda: self._import_to_folder(path))
        menu.addAction(act_import)

        # 如果是aep_templates文件夹，添加导入AEP模板选项
        if path.name == "aep_templates" or path.parent.name == "aep_templates":
            act_import_aep = QAction("导入AEP模板...", self)
            act_import_aep.triggered.connect(lambda: self._import_aep_template(path))
            menu.addAction(act_import_aep)

        menu.exec_(self.tree.mapToGlobal(position))

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

    def _save_app_settings(self):
        """保存软件设置"""
        self.app_settings.setValue("window_geometry", self.saveGeometry())
        if self.project_base:
            self.app_settings.setValue("last_project", str(self.project_base))

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._save_app_settings()
        event.accept()