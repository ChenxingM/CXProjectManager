# -*- coding: utf-8 -*-
"""
CX Project Manager - 动画项目管理工具
=====================================
功能特性：
• 支持有/无 Episode 模式（单集/PV）
• Episode 和 Cut 的创建与批量创建
• 素材导入管理（BG/Cell/Timesheet/AEP）
• 项目配置持久化
• 软件配置记忆（默认路径、最近项目）
• 目录树可视化
• 深色主题 UI
"""

import json
import shutil
import sys
import os
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QBrush, QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMenuBar,
    QMessageBox, QPushButton, QSpinBox, QSplitter, QStatusBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem
)

# ================================ 样式表 ================================ #
QSS_THEME = """
/* 全局样式 */
* {
    color: #E0E0E0;
    font-family: "MiSans", "微软雅黑", "Segoe UI", Arial;
    font-size: 13px;
}

QMainWindow, QWidget {
    background-color: #1E1E1E;
}

/* 按钮样式 */
QPushButton {
    background-color: #2D2D2D;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #3A3A3A;
    border-color: #4A4A4A;
}

QPushButton:pressed {
    background-color: #252525;
}

QPushButton:disabled {
    color: #666666;
    background-color: #242424;
}

/* 输入框样式 */
QLineEdit, QSpinBox, QComboBox {
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    padding: 4px 6px;
    min-height: 24px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #0D7ACC;
}

/* 标签样式 */
QLabel {
    padding: 2px;
}

/* 分组框样式 */
QGroupBox {
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

/* 列表控件样式 */
QListWidget {
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    outline: none;
}

QListWidget::item {
    padding: 4px 8px;
}

QListWidget::item:hover {
    background-color: #2A2A2A;
}

QListWidget::item:selected {
    background-color: #0D7ACC;
}

/* 菜单样式 */
QMenuBar {
    background-color: #2D2D2D;
    border-bottom: 1px solid #3C3C3C;
}

QMenuBar::item:selected {
    background-color: #3A3A3A;
}

QMenu {
    background-color: #2D2D2D;
    border: 1px solid #3C3C3C;
}

QMenu::item:selected {
    background-color: #0D7ACC;
}

/* 状态栏样式 */
QStatusBar {
    background-color: #252525;
    border-top: 1px solid #3C3C3C;
}

/* 复选框样式 */
QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
    background-color: #262626;
}

QCheckBox::indicator:checked {
    background-color: #0D7ACC;
    border-color: #0D7ACC;
}

/* 分割器样式 */
QSplitter::handle {
    background-color: #2D2D2D;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}
"""


# ================================ 自定义控件 ================================ #

class SearchLineEdit(QLineEdit):
    """支持Esc键清除的搜索框"""

    def keyPressEvent(self, event):
        """处理按键事件"""
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)


# ================================ 工具函数 ================================ #

def zero_pad(number: int, width: int = 3) -> str:
    """数字补零"""
    return str(number).zfill(width)


def ensure_dir(path: Path) -> None:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)


def copy_file_safe(src: Path, dst: Path) -> bool:
    """安全复制文件"""
    try:
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"复制文件失败: {e}")
        return False


# ================================ 项目浏览器组件 ================================ #

class ProjectBrowser(QWidget):
    """独立的项目浏览器组件，可以在其他程序中导入使用"""

    def __init__(self, project_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.project_base: Optional[Path] = None
        self.project_config: Optional[Dict] = None

        self._setup_ui()
        self.setStyleSheet(QSS_THEME)  # 应用样式

        if project_path:
            self.load_project(project_path)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 项目统计
        stats_group = QGroupBox("📊 项目统计")
        stats_layout = QVBoxLayout(stats_group)

        self.txt_stats = QTextEdit()
        self.txt_stats.setReadOnly(True)
        self.txt_stats.setMaximumHeight(150)
        stats_layout.addWidget(self.txt_stats)
        layout.addWidget(stats_group)

        # 浏览器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Episode / Cut")
        self.tree.itemClicked.connect(self._on_tree_clicked)

        # 右侧文件列表
        self.file_list = QListWidget()

        splitter.addWidget(self.tree)
        splitter.addWidget(self.file_list)
        layout.addWidget(splitter)

    def load_project(self, project_path: str):
        """加载项目"""
        path = Path(project_path)
        config_file = path / "project_config.json"

        if not config_file.exists():
            return False

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self.project_config = json.load(f)
            self.project_base = path
            self._update_view()
            return True
        except:
            return False

    def _update_view(self):
        """更新视图"""
        # 更新统计和树（简化版）
        if not self.project_config:
            return

        stats = f"项目: {self.project_config.get('project_name', 'Unknown')}\n"

        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            stats += f"Cut 总数: {len(cuts)}"
        else:
            episodes = self.project_config.get("episodes", {})
            total_cuts = sum(len(cuts) for cuts in episodes.values())
            stats += f"Episodes: {len(episodes)}, Cuts: {total_cuts}"

        self.txt_stats.setText(stats)

    def _on_tree_clicked(self, item: QTreeWidgetItem):
        """树节点点击事件"""
        # 简化实现
        pass


# ================================ 主窗口类 ================================ #

class CXProjectManager(QMainWindow):
    """动画项目管理器主窗口"""

    project_changed = Signal()  # 项目变更信号

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CX Project Manager - 动画项目管理工具")
        self.resize(1200, 700)

        # 初始化变量
        self.project_base: Optional[Path] = None
        self.project_config: Optional[Dict] = None
        self.app_settings = QSettings("CXStudio", "ProjectManager")

        # 初始化控件变量
        self.cmb_cut_episode = None

        # 初始化浏览器相关变量
        self.txt_project_stats = None
        self.browser_tree = None
        self.file_tabs = None
        self.vfx_list = None
        self.cell_list = None
        self.bg_list = None
        self.render_list = None
        self.cg_list = None
        self.lbl_current_cut = None
        self.current_cut_id = None  # 当前选中的Cut ID
        self.current_episode_id = None  # 当前选中的Episode ID
        self.current_path = None  # 当前显示的路径
        self.txt_cut_search = None  # Cut搜索框
        self.btn_clear_search = None  # 清除搜索按钮

        # 设置 UI
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()

        # 应用样式
        self.setStyleSheet(QSS_THEME)

        # 初始禁用所有操作控件（在UI创建后）
        self._enable_controls(False)

        # 确保项目名称输入框始终启用
        self.txt_project_name.setEnabled(True)
        self.btn_new_project.setEnabled(True)
        self.btn_open_project.setEnabled(True)

        # 加载软件配置
        self._load_app_settings()

        # 连接信号
        self.project_changed.connect(self._on_project_changed)

    # ========================== UI 设置 ========================== #

    def _setup_ui(self):
        """设置主界面"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 0)

        # 创建Tab控件
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: 项目管理
        management_tab = QWidget()
        management_layout = QHBoxLayout(management_tab)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        management_layout.addWidget(splitter)

        # 左侧控制面板
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # 右侧目录树
        self.tree = self._create_tree_widget()
        splitter.addWidget(self.tree)

        # 设置分割比例
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        # Tab 2: 项目浏览
        browser_tab = self._create_browser_tab()

        # 添加Tab
        self.tabs.addTab(management_tab, "📁 项目管理")
        self.tabs.addTab(browser_tab, "📊 项目浏览")

        # 设置默认Tab
        self.tabs.setCurrentIndex(0)

    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 项目信息组
        project_group = QGroupBox("📁 项目管理")
        project_layout = QVBoxLayout(project_group)

        # 当前项目路径
        self.lbl_project_path = QLabel("未打开项目")
        self.lbl_project_path.setStyleSheet("color: #999; font-style: italic;")
        project_layout.addWidget(self.lbl_project_path)

        # 新建项目输入框和按钮
        new_project_layout = QHBoxLayout()
        self.txt_project_name = QLineEdit()
        self.txt_project_name.setPlaceholderText("输入项目名称")
        self.txt_project_name.returnPressed.connect(self.new_project)  # 支持回车键
        self.btn_new_project = QPushButton("新建")
        self.btn_new_project.clicked.connect(self.new_project)

        # 设置工具提示
        default_path = self.app_settings.value("default_project_path", "")
        if default_path and Path(default_path).exists():
            self.btn_new_project.setToolTip(f"将创建到: {default_path}")
        else:
            self.btn_new_project.setToolTip("点击后选择创建位置")

        new_project_layout.addWidget(self.txt_project_name)
        new_project_layout.addWidget(self.btn_new_project)
        project_layout.addLayout(new_project_layout)

        # 打开项目按钮
        self.btn_open_project = QPushButton("打开项目")
        self.btn_open_project.clicked.connect(self.open_project)
        project_layout.addWidget(self.btn_open_project)

        # Episode 模式选择
        self.chk_no_episode = QCheckBox("单集/PV 模式（无 Episode）")
        self.chk_no_episode.stateChanged.connect(self._toggle_episode_mode)
        project_layout.addWidget(self.chk_no_episode)

        layout.addWidget(project_group)

        # Episode 管理组
        self.episode_group = QGroupBox("🎬 Episode 管理")
        episode_layout = QVBoxLayout(self.episode_group)

        # Episode 类型和编号输入
        single_ep_layout = QHBoxLayout()

        # Episode 类型下拉框
        self.cmb_episode_type = QComboBox()
        self.cmb_episode_type.setEditable(True)  # 允许自定义输入
        self.cmb_episode_type.addItems([
            "ep",  # 普通集数
            "pv",  # Promotional Video
            "op",  # Opening
            "ed",  # Ending
            "sp",  # Special
            "ova",  # Original Video Animation
            "cm",  # Commercial
            "sv",  # Special Version
            "ex",  # Extra
            "nc",  # Non-Credit
        ])
        self.cmb_episode_type.setCurrentText("ep")
        self.cmb_episode_type.currentTextChanged.connect(self._on_episode_type_changed)

        # Episode 编号输入
        self.txt_episode = QLineEdit()
        self.txt_episode.setPlaceholderText("编号或名称 (可留空)")

        self.btn_create_episode = QPushButton("创建")
        self.btn_create_episode.clicked.connect(self.create_episode)

        single_ep_layout.addWidget(QLabel("类型:"))
        single_ep_layout.addWidget(self.cmb_episode_type)
        single_ep_layout.addWidget(self.txt_episode)
        single_ep_layout.addWidget(self.btn_create_episode)
        episode_layout.addLayout(single_ep_layout)

        # 批量创建 Episode（仅对数字编号有效）
        self.lbl_batch_ep = QLabel("批量创建 (仅限数字编号):")
        episode_layout.addWidget(self.lbl_batch_ep)

        batch_ep_layout = QHBoxLayout()
        batch_ep_layout.addWidget(QLabel("从:"))
        self.spin_ep_from = QSpinBox()
        self.spin_ep_from.setRange(1, 999)
        self.spin_ep_from.setValue(1)
        batch_ep_layout.addWidget(self.spin_ep_from)
        batch_ep_layout.addWidget(QLabel("到:"))
        self.spin_ep_to = QSpinBox()
        self.spin_ep_to.setRange(1, 999)
        self.spin_ep_to.setValue(12)
        batch_ep_layout.addWidget(self.spin_ep_to)
        self.btn_batch_episode = QPushButton("批量创建")
        self.btn_batch_episode.clicked.connect(self.batch_create_episodes)
        batch_ep_layout.addWidget(self.btn_batch_episode)
        episode_layout.addLayout(batch_ep_layout)

        layout.addWidget(self.episode_group)

        # Cut 管理组
        cut_group = QGroupBox("✂️ Cut 管理")
        cut_layout = QVBoxLayout(cut_group)

        # 创建单个 Cut
        single_cut_layout = QHBoxLayout()
        self.cmb_cut_episode = QComboBox()
        self.cmb_cut_episode.setPlaceholderText("选择 Episode")
        self.cmb_cut_episode.setToolTip("选择要创建Cut的Episode")
        self.txt_cut = QLineEdit()
        self.txt_cut.setPlaceholderText("Cut 编号")
        self.btn_create_cut = QPushButton("创建")
        self.btn_create_cut.clicked.connect(lambda: self.create_cut())
        single_cut_layout.addWidget(self.cmb_cut_episode)
        single_cut_layout.addWidget(self.txt_cut)
        single_cut_layout.addWidget(self.btn_create_cut)
        cut_layout.addLayout(single_cut_layout)

        # 批量创建 Cut
        batch_cut_layout = QHBoxLayout()
        batch_cut_layout.addWidget(QLabel("批量:"))
        self.spin_cut_from = QSpinBox()
        self.spin_cut_from.setRange(1, 999)
        self.spin_cut_from.setValue(1)
        batch_cut_layout.addWidget(self.spin_cut_from)
        batch_cut_layout.addWidget(QLabel("到"))
        self.spin_cut_to = QSpinBox()
        self.spin_cut_to.setRange(1, 999)
        self.spin_cut_to.setValue(10)
        batch_cut_layout.addWidget(self.spin_cut_to)
        self.btn_batch_cut = QPushButton("批量创建")
        self.btn_batch_cut.clicked.connect(self.batch_create_cuts)
        batch_cut_layout.addWidget(self.btn_batch_cut)
        cut_layout.addLayout(batch_cut_layout)

        layout.addWidget(cut_group)

        # 素材导入组
        import_group = QGroupBox("📥 素材导入")
        import_layout = QVBoxLayout(import_group)

        # Episode 和 Cut 选择
        target_layout = QHBoxLayout()

        # Episode 选择（有 Episode 模式时显示）
        self.cmb_target_episode = QComboBox()
        self.cmb_target_episode.setPlaceholderText("选择 Episode")
        # 确保初始状态为未选择
        self.cmb_target_episode.setCurrentIndex(-1)
        self.cmb_target_episode.currentTextChanged.connect(self._on_episode_changed)
        self.lbl_target_episode = QLabel("Episode:")
        target_layout.addWidget(self.lbl_target_episode)
        target_layout.addWidget(self.cmb_target_episode)

        # Cut 选择
        self.cmb_target_cut = QComboBox()
        self.cmb_target_cut.setPlaceholderText("选择 Cut")
        target_layout.addWidget(QLabel("Cut:"))
        target_layout.addWidget(self.cmb_target_cut)

        import_layout.addLayout(target_layout)

        # BG 导入
        bg_layout = QHBoxLayout()
        self.txt_bg_path = QLineEdit()
        self.txt_bg_path.setPlaceholderText("BG 文件路径")
        self.txt_bg_path.setReadOnly(True)
        self.btn_browse_bg = QPushButton("浏览")
        self.btn_browse_bg.clicked.connect(lambda: self.browse_material("bg"))
        bg_layout.addWidget(QLabel("BG:"))
        bg_layout.addWidget(self.txt_bg_path)
        bg_layout.addWidget(self.btn_browse_bg)
        import_layout.addLayout(bg_layout)

        # Cell 导入
        cell_layout = QHBoxLayout()
        self.txt_cell_path = QLineEdit()
        self.txt_cell_path.setPlaceholderText("Cell 文件夹路径")
        self.txt_cell_path.setReadOnly(True)
        self.btn_browse_cell = QPushButton("浏览")
        self.btn_browse_cell.clicked.connect(lambda: self.browse_material("cell"))
        cell_layout.addWidget(QLabel("Cell:"))
        cell_layout.addWidget(self.txt_cell_path)
        cell_layout.addWidget(self.btn_browse_cell)
        import_layout.addLayout(cell_layout)

        # 3DCG 导入
        cg_layout = QHBoxLayout()
        self.txt_3dcg_path = QLineEdit()
        self.txt_3dcg_path.setPlaceholderText("3DCG 文件夹路径")
        self.txt_3dcg_path.setReadOnly(True)
        self.btn_browse_3dcg = QPushButton("浏览")
        self.btn_browse_3dcg.clicked.connect(lambda: self.browse_material("3dcg"))
        cg_layout.addWidget(QLabel("3DCG:"))
        cg_layout.addWidget(self.txt_3dcg_path)
        cg_layout.addWidget(self.btn_browse_3dcg)
        import_layout.addLayout(cg_layout)

        # Timesheet 导入
        ts_layout = QHBoxLayout()
        self.txt_timesheet_path = QLineEdit()
        self.txt_timesheet_path.setPlaceholderText("Timesheet CSV 路径")
        self.txt_timesheet_path.setReadOnly(True)
        self.btn_browse_timesheet = QPushButton("浏览")
        self.btn_browse_timesheet.clicked.connect(lambda: self.browse_material("timesheet"))
        ts_layout.addWidget(QLabel("TS:"))
        ts_layout.addWidget(self.txt_timesheet_path)
        ts_layout.addWidget(self.btn_browse_timesheet)
        import_layout.addLayout(ts_layout)

        # 导入操作按钮
        import_action_layout = QHBoxLayout()
        self.btn_import_single = QPushButton("导入选中")
        self.btn_import_all = QPushButton("批量导入")
        self.btn_copy_aep = QPushButton("复制 AEP 模板")

        self.btn_import_single.clicked.connect(self.import_single)
        self.btn_import_all.clicked.connect(self.import_all)
        self.btn_copy_aep.clicked.connect(self.copy_aep_template)

        import_action_layout.addWidget(self.btn_import_single)
        import_action_layout.addWidget(self.btn_import_all)
        import_action_layout.addWidget(self.btn_copy_aep)
        import_layout.addLayout(import_action_layout)

        layout.addWidget(import_group)

        # 添加弹性空间
        layout.addStretch()

        return panel

    def _create_tree_widget(self) -> QTreeWidget:
        """创建目录树控件"""
        tree = QTreeWidget()
        tree.setHeaderLabel("项目结构")
        tree.setAlternatingRowColors(True)
        return tree

    def _create_browser_tab(self) -> QWidget:
        """创建项目浏览Tab"""
        browser = QWidget()
        layout = QHBoxLayout(browser)

        # 主分割器
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板：项目统计 + Episode/Cut 树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 项目统计组
        stats_group = QGroupBox("📊 项目统计")
        stats_layout = QVBoxLayout(stats_group)

        self.txt_project_stats = QTextEdit()
        self.txt_project_stats.setReadOnly(True)
        self.txt_project_stats.setMaximumHeight(180)
        self.txt_project_stats.setStyleSheet("""
            QTextEdit {
                background-color: #2A2A2A;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                padding: 8px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)
        stats_layout.addWidget(self.txt_project_stats)
        left_layout.addWidget(stats_group)

        # Cut 树组
        tree_group = QGroupBox("📂 Cut")
        tree_group.setToolTip("按 Ctrl+F 快速搜索Cut")
        tree_layout = QVBoxLayout(tree_group)

        # Cut 搜索框
        search_layout = QHBoxLayout()
        self.txt_cut_search = SearchLineEdit()
        self.txt_cut_search.setPlaceholderText("搜索 Cut (支持数字快速定位)...")
        self.txt_cut_search.textChanged.connect(self._on_cut_search_changed)
        self.txt_cut_search.setClearButtonEnabled(True)  # 添加内置清除按钮
        self.txt_cut_search.returnPressed.connect(self._select_first_match)  # 回车选择第一个匹配
        self.txt_cut_search.setToolTip(
            "输入Cut名称或数字进行搜索\n• 按回车选择第一个匹配项\n• 按Esc或点击清除按钮清空搜索\n• 快捷键: Ctrl+F")
        self.btn_clear_search = QPushButton("清除")
        self.btn_clear_search.clicked.connect(self._clear_cut_search)
        self.btn_clear_search.setMaximumWidth(60)
        search_layout.addWidget(QLabel("🔍"))
        search_layout.addWidget(self.txt_cut_search)
        search_layout.addWidget(self.btn_clear_search)
        tree_layout.addLayout(search_layout)

        self.browser_tree = QTreeWidget()
        self.browser_tree.setHeaderLabel("选择要浏览的 Cut")
        self.browser_tree.itemClicked.connect(self._on_browser_tree_clicked)
        self.browser_tree.setAlternatingRowColors(True)
        tree_layout.addWidget(self.browser_tree)

        left_layout.addWidget(tree_group, 1)  # 给树分配更多空间

        # 右侧面板：文件浏览器
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 文件浏览器组
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
        self.lbl_current_cut.setWordWrap(True)  # 允许自动换行
        self.lbl_current_cut.setTextInteractionFlags(Qt.TextSelectableByMouse)  # 允许选择复制
        self.lbl_current_cut.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lbl_current_cut.customContextMenuRequested.connect(self._show_path_context_menu)
        files_layout.addWidget(self.lbl_current_cut)

        # 文件类型Tab
        self.file_tabs = QTabWidget()
        self.file_tabs.currentChanged.connect(self._on_file_tab_changed)

        # VFX 文件列表
        self.vfx_list = QListWidget()
        self.vfx_list.itemDoubleClicked.connect(lambda item: self._open_file_location(item))

        # Cell 文件列表
        self.cell_list = QListWidget()
        self.cell_list.itemDoubleClicked.connect(lambda item: self._open_file_location(item))

        # BG 文件列表
        self.bg_list = QListWidget()
        self.bg_list.itemDoubleClicked.connect(lambda item: self._open_file_location(item))

        # Render 文件列表
        self.render_list = QListWidget()
        self.render_list.itemDoubleClicked.connect(lambda item: self._open_file_location(item))

        # 3DCG 文件列表
        self.cg_list = QListWidget()
        self.cg_list.itemDoubleClicked.connect(lambda item: self._open_file_location(item))

        self.file_tabs.addTab(self.vfx_list, "VFX")
        self.file_tabs.addTab(self.cell_list, "Cell")
        self.file_tabs.addTab(self.bg_list, "BG")
        self.file_tabs.addTab(self.render_list, "Render")
        self.file_tabs.addTab(self.cg_list, "3DCG")

        files_layout.addWidget(self.file_tabs)
        right_layout.addWidget(files_group)

        # 添加到主分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 1)  # 左侧占1份
        main_splitter.setStretchFactor(1, 3)  # 右侧占2份

        layout.addWidget(main_splitter)

        return browser

    def _setup_menubar(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        act_new = QAction("新建项目", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.new_project)
        file_menu.addAction(act_new)

        act_open = QAction("打开项目", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.open_project)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        # 最近项目子菜单
        self.recent_menu = file_menu.addMenu("最近项目")
        self._update_recent_menu()

        file_menu.addSeparator()

        act_settings = QAction("设置默认路径...", self)
        act_settings.triggered.connect(self.set_default_path)
        file_menu.addAction(act_settings)

        file_menu.addSeparator()

        act_exit = QAction("退出", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")

        act_refresh = QAction("刷新目录树", self)
        act_refresh.setShortcut("F5")
        act_refresh.triggered.connect(self._refresh_tree)
        tools_menu.addAction(act_refresh)

        act_search_cut = QAction("搜索Cut", self)
        act_search_cut.setShortcut("Ctrl+F")
        act_search_cut.triggered.connect(self._focus_cut_search)
        tools_menu.addAction(act_search_cut)

        act_open_folder = QAction("在文件管理器中打开", self)
        act_open_folder.triggered.connect(self.open_in_explorer)
        tools_menu.addAction(act_open_folder)

    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("请打开或新建项目以开始使用")

    # ========================== 项目操作 ========================== #

    def new_project(self):
        """新建项目"""
        # 获取项目名称
        project_name = self.txt_project_name.text().strip()
        if not project_name:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            self.txt_project_name.setFocus()
            return

        # 检查是否有默认路径
        default_path = self.app_settings.value("default_project_path", "")

        if default_path and Path(default_path).exists():
            # 有默认路径，直接创建
            base_folder = default_path
        else:
            # 没有默认路径，让用户选择
            base_folder = QFileDialog.getExistingDirectory(
                self, "选择项目创建位置", ""
            )
            if not base_folder:
                return

        # 创建项目
        self.project_base = Path(base_folder) / project_name

        # 检查项目是否已存在
        if self.project_base.exists():
            reply = QMessageBox.question(
                self, "确认",
                f"项目 '{project_name}' 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self._create_project_structure()

        # 初始化项目配置
        self.project_config = {
            "project_name": self.project_base.name,
            "project_path": str(self.project_base),
            "no_episode": self.chk_no_episode.isChecked(),
            "episodes": {},
            "cuts": [],  # 无 Episode 模式下的 cuts
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "paths": {
                "reference": "00_reference_project",
                "render": "06_render",
                "assets": "07_master_assets",
                "aep_templates": "07_master_assets/aep_templates",
                "tools": "08_tools",
                "vfx": "01_vfx",
                "3dcg": "02_3dcg",
                "tmp": "98_tmp",
                "other": "99_other",
            }
        }

        # 保存配置
        self._save_project_config()

        # 初始化统计信息
        self._update_project_stats()

        # 更新 UI
        self.project_changed.emit()
        self._add_to_recent(str(self.project_base))

        # 清空项目名输入框
        self.txt_project_name.clear()

        QMessageBox.information(
            self, "成功", f"项目 '{project_name}' 创建成功！"
        )

    def open_project(self):
        """打开已有项目"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择项目文件夹", ""
        )
        if not folder:
            return

        self._load_project(folder)

    def open_recent_project(self, path: str):
        """打开最近项目"""
        if Path(path).exists():
            self._load_project(path)
        else:
            QMessageBox.warning(
                self, "错误", f"项目路径不存在：\n{path}"
            )
            self._remove_from_recent(path)

    def _load_project(self, folder: str):
        """加载项目"""
        project_path = Path(folder)
        config_file = project_path / "project_config.json"

        if not config_file.exists():
            QMessageBox.warning(
                self, "错误", "所选文件夹不是有效的项目（缺少 project_config.json）"
            )
            return

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self.project_config = json.load(f)

            self.project_base = project_path
            self.project_changed.emit()
            self._add_to_recent(str(project_path))

        except Exception as e:
            QMessageBox.critical(
                self, "错误", f"加载项目配置失败：\n{str(e)}"
            )

    def _create_project_structure(self):
        """创建项目目录结构"""
        # 基础参考目录
        ref_dirs = [
            "00_reference_project/character_design",
            "00_reference_project/art_design",
            "00_reference_project/concept_art",
            "00_reference_project/storyboard",
            "00_reference_project/docs",
            "00_reference_project/other_design",
        ]

        # 渲染和资源目录
        asset_dirs = [
            "06_render",
            "07_master_assets/fonts",
            "07_master_assets/logo",
            "07_master_assets/fx_presets",
            "07_master_assets/aep_templates",  # AEP 模板移到这里
        ]

        # 工具目录
        tool_dirs = [
            "08_tools/ae_scripts",
            "08_tools/python",
            "08_tools/config",
        ]

        # 临时和其他目录
        other_dirs = [
            "98_tmp",
            "99_other",
        ]

        # 无 Episode 模式需要的目录
        if self.chk_no_episode.isChecked():
            no_ep_dirs = [
                "01_vfx/timesheets",
            ]
            all_dirs = ref_dirs + asset_dirs + tool_dirs + other_dirs + no_ep_dirs
        else:
            all_dirs = ref_dirs + asset_dirs + tool_dirs + other_dirs

        # 创建所有目录
        for dir_path in all_dirs:
            ensure_dir(self.project_base / dir_path)

        # 创建 README
        readme_content = f"""# {self.project_base.name}

创建时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 项目结构说明

### 项目根目录
- `00_reference_project/` - 全项目通用参考资料
- `01_vfx/` - VFX/AE 制作文件（无 Episode 模式）
- `02_3dcg/` - 3DCG 制作文件（按需创建）
- `06_render/` - 最终渲染输出
- `07_master_assets/` - 共用素材
  - `aep_templates/` - AE 项目模板
  - `fonts/` - 字体文件
  - `logo/` - Logo 素材
  - `fx_presets/` - 特效预设
- `08_tools/` - 自动化脚本与工具
  - `ae_scripts/` - AE 脚本
  - `python/` - Python 工具
  - `config/` - 配置文件
- `98_tmp/` - 临时文件
- `99_other/` - 其他文件

### Episode 目录结构
支持多种 Episode 类型：
- `ep01/`, `ep02/` - 标准集数
- `pv_teaser/`, `pv_main/` - 宣传片
- `op_v1/`, `ed_v1/` - 片头片尾
- `sp_bonus/` - 特别篇
- 其他自定义名称

每个 Episode 包含：
- `00_reference/` - 本集参考资料
- `01_vfx/` - VFX/AE 制作文件
- `02_3dcg/` - 3DCG 制作文件（按需创建）
- `03_preview/` - 预览文件
- `04_log/` - 日志和记录
- `05_output_mixdown/` - 混合输出

### Cut 渲染输出（06_render/）
- `epXX/XXX/` 或 `XXX/` - 每个 Cut 的渲染输出
  - `png_seq/` - PNG 序列
  - `prores/` - ProRes 视频
  - `mp4/` - MP4 预览

## 项目统计

_统计信息将在创建 Episode 和 Cut 后自动更新_

## 使用说明

请使用 CX Project Manager 管理本项目。
- 创建 Cut 时会自动在 06_render 目录下创建对应的输出文件夹结构
- 3DCG 目录在导入 3DCG 素材时按需创建

### 素材导入说明
- BG: 导入单个图像文件 → `title_EPXX_XXX_t1.psd`
- Cell: 导入整个文件夹 → `title_EPXX_XXX_t1/`
- 3DCG: 导入文件夹到对应 Cut（自动创建目录）
- Timesheet: 导入 CSV 文件 → `XXX.csv`
- AEP: 从模板复制 → `title_EPXX_XXX_v0.aep`

注：无 Episode 模式下，文件名中不包含 EP 部分
"""
        (self.project_base / "README.md").write_text(readme_content, encoding="utf-8")

    def _save_project_config(self):
        """保存项目配置"""
        if not self.project_base:
            return

        if not self.project_config:
            self.project_config = {
                "project_name": self.project_base.name,
                "project_path": str(self.project_base),
                "no_episode": self.chk_no_episode.isChecked(),
                "episodes": {},
                "cuts": [],  # 无 Episode 模式下的 cuts
                "created_time": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "paths": {
                    "reference": "00_reference_project",
                    "render": "06_render",
                    "assets": "07_master_assets",
                    "aep_templates": "07_master_assets/aep_templates",
                    "tools": "08_tools",
                    "vfx": "01_vfx",
                    "3dcg": "02_3dcg",
                    "tmp": "98_tmp",
                    "other": "99_other",
                }
            }
        else:
            self.project_config["last_modified"] = datetime.now().isoformat()

        config_file = self.project_base / "project_config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self.project_config, f, indent=4, ensure_ascii=False)

    # ========================== Episode 和 Cut 管理 ========================== #

    def create_episode(self):
        """创建单个 Episode"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        if self.chk_no_episode.isChecked():
            QMessageBox.information(self, "提示", "当前为单集/PV 模式，无需创建 Episode")
            return

        # 获取 Episode 类型和标识
        ep_type = self.cmb_episode_type.currentText().strip().lower()
        ep_identifier = self.txt_episode.text().strip()

        # 构建 Episode ID
        if ep_type == "ep" and ep_identifier and ep_identifier.isdigit():
            # 标准集数，自动补零
            ep_id = f"ep{zero_pad(int(ep_identifier), 2)}"
        elif ep_identifier:
            # 特殊类型或自定义名称，有标识
            safe_identifier = ep_identifier.replace(" ", "_").replace("/", "_").replace("\\", "_")
            if ep_type and ep_type != ep_identifier.lower():
                ep_id = f"{ep_type}_{safe_identifier}"
            else:
                ep_id = safe_identifier
        else:
            # 只有类型，没有标识（允许留空）
            ep_id = ep_type

        # 检查是否已存在
        if ep_id in self.project_config.get("episodes", {}):
            QMessageBox.warning(self, "错误", f"Episode '{ep_id}' 已存在")
            return

        # 创建目录结构
        ep_path = self.project_base / ep_id
        ep_dirs = [
            "00_reference/storyboard",
            "00_reference/script",
            "00_reference/director_notes",
            "01_vfx/timesheets",
            "03_preview",
            "04_log",
            "05_output_mixdown",
        ]

        for dir_path in ep_dirs:
            ensure_dir(ep_path / dir_path)

        # 在06_render目录下创建对应的Episode文件夹
        render_ep_path = self.project_base / "06_render" / ep_id
        ensure_dir(render_ep_path)

        # 更新配置
        if "episodes" not in self.project_config:
            self.project_config["episodes"] = {}
        self.project_config["episodes"][ep_id] = []
        self._save_project_config()

        # 刷新 UI
        self._refresh_tree()
        self._update_import_combos()
        self._update_cut_episode_combo()  # 更新Cut管理的Episode下拉框
        self._update_project_stats()  # 更新统计

        self.statusbar.showMessage(f"已创建 Episode: {ep_id}", 3000)

    def batch_create_episodes(self):
        """批量创建 Episode（仅支持 ep 类型）"""
        # 确保是 ep 类型
        if self.cmb_episode_type.currentText().lower() != "ep":
            QMessageBox.warning(self, "错误", "批量创建仅支持 'ep' 类型")
            return

        start = self.spin_ep_from.value()
        end = self.spin_ep_to.value()

        if start > end:
            QMessageBox.warning(self, "错误", "起始编号不能大于结束编号")
            return

        created_count = 0
        skipped_count = 0

        # 临时保存当前类型
        original_type = self.cmb_episode_type.currentText()
        self.cmb_episode_type.setCurrentText("ep")

        for i in range(start, end + 1):
            ep_id = f"ep{zero_pad(i, 2)}"
            if ep_id in self.project_config.get("episodes", {}):
                skipped_count += 1
                continue

            self.txt_episode.setText(str(i))
            # 暂时禁用状态栏消息
            original_showMessage = self.statusbar.showMessage
            self.statusbar.showMessage = lambda msg, timeout=0: None

            self.create_episode()

            # 恢复状态栏
            self.statusbar.showMessage = original_showMessage
            created_count += 1

        # 恢复原始类型
        self.cmb_episode_type.setCurrentText(original_type)

        # 显示最终结果
        message = f"成功创建 {created_count} 个 Episode"
        if skipped_count > 0:
            message += f"，跳过 {skipped_count} 个已存在的 Episode"

        if created_count > 0 or skipped_count > 0:
            QMessageBox.information(self, "完成", message)
            # 批量创建后刷新
            self._refresh_tree()
            self._update_import_combos()
            self._update_cut_episode_combo()  # 更新Cut管理的Episode下拉框
            self._update_project_stats()  # 更新统计

    def create_cut(self, show_error=True):
        """创建单个 Cut

        Args:
            show_error: 是否显示错误消息
        """
        if not self.project_base:
            if show_error:
                QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        cut_num = self.txt_cut.text().strip()
        if not cut_num.isdigit():
            if show_error:
                QMessageBox.warning(self, "错误", "请输入有效的 Cut 编号")
            return

        cut_id = zero_pad(int(cut_num), 3)

        if self.chk_no_episode.isChecked():
            # 无 Episode 模式
            if cut_id in self.project_config.get("cuts", []):
                if show_error:
                    QMessageBox.warning(self, "错误", f"Cut {cut_id} 已存在")
                return

            cut_path = self.project_base / "01_vfx" / cut_id
            self._create_cut_structure(cut_path, episode_id=None)

            # 更新配置
            if "cuts" not in self.project_config:
                self.project_config["cuts"] = []
            self.project_config["cuts"].append(cut_id)

        else:
            # 有 Episode 模式
            ep_input = self.cmb_cut_episode.currentText().strip()
            if not ep_input:
                if show_error:
                    QMessageBox.warning(self, "错误", "请选择 Episode")
                return

            # 直接使用下拉框中选择的Episode
            ep_id = ep_input

            if ep_id not in self.project_config.get("episodes", {}):
                if show_error:
                    QMessageBox.warning(self, "错误", f"Episode '{ep_id}' 不存在")
                return

            if cut_id in self.project_config["episodes"][ep_id]:
                if show_error:
                    QMessageBox.warning(self, "错误", f"Cut {cut_id} 已存在于 {ep_id}")
                return

            cut_path = self.project_base / ep_id / "01_vfx" / cut_id
            self._create_cut_structure(cut_path, episode_id=ep_id)

            # 更新配置
            self.project_config["episodes"][ep_id].append(cut_id)

        self._save_project_config()

        # 刷新 UI（批量创建时只在最后刷新一次）
        if show_error:  # 单个创建时刷新
            self._refresh_tree()
            self._update_import_combos()
            self._update_cut_episode_combo()  # 更新Cut管理的Episode下拉框
            self._update_project_stats()  # 更新统计
            self.statusbar.showMessage(f"已创建 Cut: {cut_id} (含 06_render 输出目录)", 3000)

    def batch_create_cuts(self):
        """批量创建 Cut"""
        start = self.spin_cut_from.value()
        end = self.spin_cut_to.value()

        if start > end:
            QMessageBox.warning(self, "错误", "起始编号不能大于结束编号")
            return

        ep_id = None  # 初始化 ep_id

        # 如果是有 Episode 模式，先验证 Episode
        if not self.chk_no_episode.isChecked():
            ep_id = self.cmb_cut_episode.currentText().strip()
            if not ep_id:
                QMessageBox.warning(self, "错误", "批量创建需要先选择 Episode")
                return

            if ep_id not in self.project_config.get("episodes", {}):
                QMessageBox.warning(self, "错误", f"Episode '{ep_id}' 不存在")
                return

        # 批量创建
        created_count = 0
        skipped_count = 0

        for i in range(start, end + 1):
            self.txt_cut.setText(str(i))
            cut_id = zero_pad(i, 3)

            # 检查是否已存在
            if self.chk_no_episode.isChecked():
                if cut_id in self.project_config.get("cuts", []):
                    skipped_count += 1
                    continue
            else:
                if cut_id in self.project_config["episodes"][ep_id]:
                    skipped_count += 1
                    continue

            # 创建 Cut（不显示单个错误消息）
            self.create_cut(show_error=False)
            created_count += 1

        # 显示结果
        message = f"成功创建 {created_count} 个 Cut"
        if skipped_count > 0:
            message += f"，跳过 {skipped_count} 个已存在的 Cut"

        if created_count > 0 or skipped_count > 0:
            QMessageBox.information(self, "完成", message)
            # 批量创建后刷新一次
            self._refresh_tree()
            self._update_import_combos()
            self._update_cut_episode_combo()  # 更新Cut管理的Episode下拉框
            self._update_project_stats()  # 更新统计

    def _create_cut_structure(self, cut_path: Path, episode_id: Optional[str] = None):
        """创建 Cut 目录结构

        Args:
            cut_path: Cut 的路径
            episode_id: Episode ID (如 'ep01')，无 Episode 模式时为 None
        """
        # 创建 Cut 内部子目录
        subdirs = ["cell", "bg", "prerender"]
        for subdir in subdirs:
            ensure_dir(cut_path / subdir)

        # 获取 cut_id
        cut_id = cut_path.name

        # 创建 render 目录结构
        if episode_id:
            # 有 Episode 模式: 06_render/ep01/001/
            render_path = self.project_base / "06_render" / episode_id / cut_id
        else:
            # 无 Episode 模式: 06_render/001/
            render_path = self.project_base / "06_render" / cut_id

        # 创建 render 子目录
        render_subdirs = ["png_seq", "prores", "mp4"]
        for subdir in render_subdirs:
            ensure_dir(render_path / subdir)

        # 复制 AEP 模板（如果存在）
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if template_dir.exists():
            for template in template_dir.glob("*.aep"):
                # 新的命名格式：title_EPXX_XXX_v0.aep（全大写）
                if episode_id:
                    # 提取 Episode 编号部分（如 ep01 -> EP01）
                    ep_part = episode_id.upper()
                    aep_name = f"title_{ep_part}_{cut_id}_v0{template.suffix}"
                else:
                    # 无 Episode 模式
                    aep_name = f"title_{cut_id}_v0{template.suffix}"

                dst = cut_path / aep_name
                copy_file_safe(template, dst)

    # ========================== 素材导入 ========================== #

    def browse_material(self, material_type: str):
        """浏览选择素材"""
        if material_type in ["cell", "3dcg"]:
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(
                self, f"选择 {material_type.upper()} 文件夹", ""
            )
            if path:
                if material_type == "cell":
                    self.txt_cell_path.setText(path)
                else:
                    self.txt_3dcg_path.setText(path)
        else:
            # 选择文件
            file_filter = {
                "bg": "图像文件 (*.psd *.png *.jpg *.jpeg)",
                "timesheet": "CSV 文件 (*.csv)",
            }.get(material_type, "所有文件 (*.*)")

            file_path, _ = QFileDialog.getOpenFileName(
                self, f"选择 {material_type.upper()} 文件", "", file_filter
            )
            if file_path:
                if material_type == "bg":
                    self.txt_bg_path.setText(file_path)
                else:
                    self.txt_timesheet_path.setText(file_path)

    def import_single(self):
        """导入单个选中的素材"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
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

        # 检查哪些有路径
        imports = []
        if self.txt_bg_path.text():
            imports.append(("bg", self.txt_bg_path.text()))
        if self.txt_cell_path.text():
            imports.append(("cell", self.txt_cell_path.text()))
        if self.txt_3dcg_path.text():
            imports.append(("3dcg", self.txt_3dcg_path.text()))
        if self.txt_timesheet_path.text():
            imports.append(("timesheet", self.txt_timesheet_path.text()))

        if not imports:
            QMessageBox.warning(self, "错误", "请先选择要导入的素材")
            return

        # 执行导入
        success_count = 0
        for material_type, path in imports:
            if self._import_material(material_type, path, target):
                success_count += 1

        if success_count > 0:
            # 检查是否导入了 3DCG
            imported_3dcg = any(mt == "3dcg" for mt, _ in imports)

            message = f"已导入 {success_count} 个素材"
            if imported_3dcg:
                message += "（已创建 3DCG 目录）"

            QMessageBox.information(self, "成功", message)
            self._refresh_tree()
            # 清空已导入的路径
            if self.txt_bg_path.text() and ("bg", self.txt_bg_path.text()) in imports:
                self.txt_bg_path.clear()
            if self.txt_cell_path.text() and ("cell", self.txt_cell_path.text()) in imports:
                self.txt_cell_path.clear()
            if self.txt_3dcg_path.text() and ("3dcg", self.txt_3dcg_path.text()) in imports:
                self.txt_3dcg_path.clear()
            if self.txt_timesheet_path.text() and ("timesheet", self.txt_timesheet_path.text()) in imports:
                self.txt_timesheet_path.clear()

    def import_all(self):
        """批量导入所有已选择的素材"""
        # 与 import_single 相同，因为已经支持批量
        self.import_single()

    def _import_material(self, material_type: str, source_path: str, target: str) -> bool:
        """执行素材导入

        Returns:
            bool: 是否成功导入
        """
        try:
            src = Path(source_path)
            if not src.exists():
                return False

            # 解析目标路径
            if "|" in target:
                ep_id, cut_id = target.split("|")
                vfx_base = self.project_base / ep_id / "01_vfx"
                cg_base = self.project_base / ep_id / "02_3dcg"
            else:
                cut_id = target
                vfx_base = self.project_base / "01_vfx"
                cg_base = self.project_base / "02_3dcg"

            # 根据类型处理
            if material_type == "bg":
                # BG 命名格式也改为包含 Episode 信息（全大写）
                if "|" in target:
                    ep_part = ep_id.upper()
                    file_name = f"title_{ep_part}_{cut_id}_t1{src.suffix.lower()}"
                else:
                    file_name = f"title_{cut_id}_t1{src.suffix.lower()}"

                dst = vfx_base / cut_id / "bg" / file_name
                ensure_dir(dst.parent)
                copy_file_safe(src, dst)

            elif material_type == "cell":
                # Cell 文件夹命名也包含 Episode 信息（全大写）
                if "|" in target:
                    ep_part = ep_id.upper()
                    folder_name = f"title_{ep_part}_{cut_id}_t1"
                else:
                    folder_name = f"title_{cut_id}_t1"

                cell_dir = vfx_base / cut_id / "cell" / folder_name
                if cell_dir.exists():
                    shutil.rmtree(cell_dir)
                shutil.copytree(src, cell_dir)

            elif material_type == "3dcg":
                # 确保 3DCG 基础目录存在
                ensure_dir(cg_base)
                # 创建3DCG目录并复制文件夹
                cg_cut_dir = cg_base / cut_id
                ensure_dir(cg_cut_dir)
                # 复制文件夹内容
                for item in src.iterdir():
                    if item.is_file():
                        copy_file_safe(item, cg_cut_dir / item.name)
                    elif item.is_dir():
                        target_dir = cg_cut_dir / item.name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(item, target_dir)

            else:  # timesheet
                dst = vfx_base / "timesheets" / f"{cut_id}.csv"
                ensure_dir(dst.parent)
                copy_file_safe(src, dst)

            return True

        except Exception as e:
            print(f"导入失败 ({material_type}): {e}")
            return False

    def copy_aep_template(self):
        """复制 AEP 模板"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
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

        # 检查模板目录
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists() or not list(template_dir.glob("*.aep")):
            QMessageBox.warning(
                self, "错误", "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件"
            )
            return

        # 复制所有模板
        copied = 0
        for template in template_dir.glob("*.aep"):
            # 使用与 _create_cut_structure 相同的命名格式
            if ep_id:
                # 提取 Episode 编号部分（如 ep01 -> EP01）
                ep_part = ep_id.upper()
                aep_name = f"title_{ep_part}_{cut_id}_v0{template.suffix}"
            else:
                # 无 Episode 模式
                aep_name = f"title_{cut_id}_v0{template.suffix}"

            dst = cut_path / aep_name
            if copy_file_safe(template, dst):
                copied += 1

        if copied > 0:
            QMessageBox.information(
                self, "成功", f"已复制 {copied} 个 AEP 模板到 Cut {cut_id}"
            )
            self._refresh_tree()

    # ========================== UI 更新 ========================== #

    def _on_project_changed(self):
        """项目变更时的处理"""
        if self.project_base and self.project_config:
            # 更新项目路径显示
            self.lbl_project_path.setText(str(self.project_base))
            self.lbl_project_path.setStyleSheet("color: #0D7ACC;")

            # 更新 Episode 模式
            no_episode = self.project_config.get("no_episode", False)
            self.chk_no_episode.setChecked(no_episode)

            # 显示/隐藏 Episode 下拉框
            self.cmb_cut_episode.setVisible(not no_episode)
            self.cmb_target_episode.setVisible(not no_episode)
            self.lbl_target_episode.setVisible(not no_episode)

            # 刷新界面
            self._refresh_tree()
            self._update_import_combos()
            self._update_cut_episode_combo()  # 更新Cut管理的Episode下拉框
            self._update_project_stats()  # 更新统计
            self._update_browser_tree()  # 更新浏览器树

            # 重置当前选择
            self.current_cut_id = None
            self.current_episode_id = None
            self.current_path = None

            # 清除搜索
            if self.txt_cut_search:
                self.txt_cut_search.clear()

            # 启用控件
            self._enable_controls(True)

            # 初始化 Episode 类型选择器的状态
            if hasattr(self, 'cmb_episode_type'):
                self._on_episode_type_changed(self.cmb_episode_type.currentText())

            # 更新状态栏
            self.statusbar.showMessage(f"当前项目: {self.project_base.name}")
        else:
            self.lbl_project_path.setText("未打开项目")
            self.lbl_project_path.setStyleSheet("color: #999; font-style: italic;")
            self.tree.clear()
            self.cmb_target_episode.clear()
            self.cmb_cut_episode.clear()
            self.cmb_target_cut.clear()
            self._clear_file_lists()
            self.txt_project_stats.clear()
            self.browser_tree.clear()
            self._enable_controls(False)
            self.current_cut_id = None
            self.current_episode_id = None
            self.current_path = None
            if self.txt_cut_search:
                self.txt_cut_search.clear()

            # 确保基本控件始终启用
            self.txt_project_name.setEnabled(True)
            self.btn_new_project.setEnabled(True)
            self.btn_open_project.setEnabled(True)

    def _on_episode_type_changed(self, episode_type: str):
        """Episode 类型变化时的处理"""
        # 根据类型调整输入提示和批量创建的可用性
        if episode_type.lower() == "ep":
            self.txt_episode.setPlaceholderText("编号 (如: 01, 02) - 可留空")
            self.btn_batch_episode.setEnabled(True)
            self.lbl_batch_ep.setEnabled(True)
            self.spin_ep_from.setEnabled(True)
            self.spin_ep_to.setEnabled(True)
        else:
            self.txt_episode.setPlaceholderText("名称或编号 (可选) - 可留空")
            # 非 ep 类型禁用批量创建
            self.btn_batch_episode.setEnabled(False)
            self.lbl_batch_ep.setEnabled(False)
            self.spin_ep_from.setEnabled(False)
            self.spin_ep_to.setEnabled(False)

    def _on_episode_changed(self, episode: str):
        """Episode 选择变化时更新 Cut 列表"""
        self.cmb_target_cut.clear()

        # 如果没有选择Episode或配置不存在，直接返回
        if not self.project_config or not episode or episode == "":
            return

        # 获取该 Episode 的所有 Cuts
        cuts = self.project_config.get("episodes", {}).get(episode, [])
        if cuts:
            self.cmb_target_cut.addItems(sorted(cuts))

    def _toggle_episode_mode(self, state: int):
        """切换 Episode 模式"""
        no_episode = self.chk_no_episode.isChecked()

        # 更新 UI
        self.episode_group.setEnabled(not no_episode)
        self.cmb_cut_episode.setEnabled(not no_episode)
        self.cmb_cut_episode.setVisible(not no_episode)

        # 显示/隐藏 Episode 下拉框
        self.cmb_target_episode.setVisible(not no_episode)
        self.lbl_target_episode.setVisible(not no_episode)

        # 更新配置
        if self.project_config:
            self.project_config["no_episode"] = no_episode
            self._save_project_config()
            self._update_import_combos()
            self._update_cut_episode_combo()

    def _enable_controls(self, enabled: bool):
        """启用/禁用控件"""
        # 新建和打开项目按钮以及项目名称输入框始终启用
        # 其他控件根据项目状态启用/禁用

        operation_controls = [
            self.chk_no_episode,
            self.episode_group,
            self.cmb_episode_type,
            self.txt_episode,
            self.btn_create_episode,
            self.btn_batch_episode,
            self.lbl_batch_ep,
            self.spin_ep_from,
            self.spin_ep_to,
            self.cmb_cut_episode,
            self.txt_cut,
            self.btn_create_cut,
            self.btn_batch_cut,
            self.spin_cut_from,
            self.spin_cut_to,
            self.btn_browse_bg,
            self.btn_browse_cell,
            self.btn_browse_3dcg,
            self.btn_browse_timesheet,
            self.btn_import_single,
            self.btn_import_all,
            self.btn_copy_aep,
            self.cmb_target_episode,
            self.cmb_target_cut,
            self.txt_bg_path,
            self.txt_cell_path,
            self.txt_3dcg_path,
            self.txt_timesheet_path,
        ]

        for control in operation_controls:
            control.setEnabled(enabled)

        # 如果启用且不是标准 ep 类型，调整批量创建的可用性
        if enabled and hasattr(self, 'cmb_episode_type'):
            self._on_episode_type_changed(self.cmb_episode_type.currentText())

    def _refresh_tree(self):
        """刷新目录树"""
        self.tree.clear()

        if not self.project_base or not self.project_base.exists():
            return

        def add_items(parent_item: QTreeWidgetItem, path: Path, depth: int = 0):
            """递归添加目录项"""
            if depth > 5:  # 限制深度
                return

            try:
                for item_path in sorted(path.iterdir()):
                    if item_path.name.startswith('.'):
                        continue

                    item = QTreeWidgetItem([item_path.name])
                    parent_item.addChild(item)

                    # 设置图标（可选）
                    if item_path.is_dir():
                        item.setToolTip(0, str(item_path))
                        add_items(item, item_path, depth + 1)
                    else:
                        item.setToolTip(0, f"{item_path.name} ({item_path.stat().st_size:,} bytes)")
            except PermissionError:
                pass

        # 添加根节点
        root_item = QTreeWidgetItem([self.project_base.name])
        self.tree.addTopLevelItem(root_item)
        add_items(root_item, self.project_base)

        # 展开到适当深度
        self.tree.expandToDepth(2)

    def _update_import_combos(self):
        """更新导入面板的下拉列表"""
        self.cmb_target_episode.clear()
        self.cmb_target_cut.clear()

        if not self.project_config:
            return

        if self.project_config.get("no_episode", False):
            # 无 Episode 模式
            cuts = self.project_config.get("cuts", [])
            self.cmb_target_cut.addItems(sorted(cuts))
        else:
            # 有 Episode 模式
            episodes = self.project_config.get("episodes", {})
            if episodes:
                # 添加 Episode 列表
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                # 重要：设置为未选择状态（-1表示没有选中任何项）
                self.cmb_target_episode.setCurrentIndex(-1)
                # Cut 列表保持空白，等待用户选择 Episode

    def _update_project_stats(self):
        """更新项目统计信息"""
        if not self.project_config:
            return

        # 收集统计数据
        stats_lines = []
        stats_lines.append(f"项目名称: {self.project_config.get('project_name', 'Unknown')}")
        stats_lines.append(f"创建时间: {self.project_config.get('created_time', 'Unknown')[:10]}")
        stats_lines.append(f"最后修改: {self.project_config.get('last_modified', 'Unknown')[:10]}")
        stats_lines.append("")

        if self.project_config.get("no_episode", False):
            # 无 Episode 模式统计
            cuts = self.project_config.get("cuts", [])
            stats_lines.append(f"模式: 单集/PV 模式")
            stats_lines.append(f"Cut 总数: {len(cuts)}")

            if cuts:
                stats_lines.append(f"Cut 范围: {min(cuts)} - {max(cuts)}")
        else:
            # 有 Episode 模式统计
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
                    if cut_count > 0:
                        stats_lines.append(f"  {ep_id}: {cut_count} cuts")
                    else:
                        stats_lines.append(f"  {ep_id}: (空)")

        # 更新统计显示
        self.txt_project_stats.setText("\n".join(stats_lines))

        # 同时更新 README
        self._update_readme_stats()

    def _update_browser_tree(self):
        """更新浏览器的Episode/Cut树"""
        self.browser_tree.clear()

        if not self.project_config:
            return

        if self.project_config.get("no_episode", False):
            # 无 Episode 模式
            cuts = self.project_config.get("cuts", [])
            for cut_id in sorted(cuts):
                item = QTreeWidgetItem([cut_id])
                item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": None})
                self.browser_tree.addTopLevelItem(item)
        else:
            # 有 Episode 模式
            episodes = self.project_config.get("episodes", {})
            for ep_id in sorted(episodes.keys()):
                ep_item = QTreeWidgetItem([ep_id])
                ep_item.setData(0, Qt.UserRole, {"episode": ep_id})
                self.browser_tree.addTopLevelItem(ep_item)

                # 添加该 Episode 下的 Cuts
                for cut_id in sorted(episodes[ep_id]):
                    cut_item = QTreeWidgetItem([cut_id])
                    cut_item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": ep_id})
                    ep_item.addChild(cut_item)

                # 展开 Episode 节点
                ep_item.setExpanded(True)

        # 如果搜索框有内容，重新应用搜索
        if self.txt_cut_search and self.txt_cut_search.text().strip():
            self._on_cut_search_changed(self.txt_cut_search.text())

    def _on_browser_tree_clicked(self, item: QTreeWidgetItem):
        """处理浏览器树的点击事件"""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        # 如果点击的是 Cut 节点
        if "cut" in data and data["cut"]:
            self.current_cut_id = data["cut"]
            self.current_episode_id = data.get("episode")

            # 加载文件列表
            self._load_cut_files(self.current_cut_id, self.current_episode_id)

            # 更新路径显示
            self._update_current_path_label()
        else:
            # 点击的是 Episode 节点，清空文件列表
            self._clear_file_lists()
            self.current_cut_id = None
            self.current_episode_id = data.get("episode")
            if self.current_episode_id:
                self.lbl_current_cut.setText(f"当前位置：{self.current_episode_id} (请选择具体的 Cut)")

    def _on_file_tab_changed(self, index: int):
        """处理文件Tab切换"""
        self._update_current_path_label()

    def _update_current_path_label(self):
        """更新当前路径标签"""
        if not self.project_base or not self.current_cut_id:
            self.lbl_current_cut.setText("当前位置：未选择")
            self.current_path = None
            return

        # 获取当前Tab索引和名称
        current_index = self.file_tabs.currentIndex()
        tab_names = ["VFX", "Cell", "BG", "Render", "3DCG"]

        if current_index < 0 or current_index >= len(tab_names):
            return

        tab_name = tab_names[current_index]

        # 构建路径
        if self.current_episode_id:
            if tab_name in ["VFX", "Cell", "BG"]:
                path = self.project_base / self.current_episode_id / "01_vfx" / self.current_cut_id
                if tab_name == "Cell":
                    path = path / "cell"
                elif tab_name == "BG":
                    path = path / "bg"
            elif tab_name == "Render":
                path = self.project_base / "06_render" / self.current_episode_id / self.current_cut_id
            elif tab_name == "3DCG":
                path = self.project_base / self.current_episode_id / "02_3dcg" / self.current_cut_id
        else:
            # 无Episode模式
            if tab_name in ["VFX", "Cell", "BG"]:
                path = self.project_base / "01_vfx" / self.current_cut_id
                if tab_name == "Cell":
                    path = path / "cell"
                elif tab_name == "BG":
                    path = path / "bg"
            elif tab_name == "Render":
                path = self.project_base / "06_render" / self.current_cut_id
            elif tab_name == "3DCG":
                path = self.project_base / "02_3dcg" / self.current_cut_id

        # 保存当前路径
        self.current_path = path

        # 格式化路径显示
        path_str = str(path).replace("\\", "/")  # 统一使用正斜杠

        # 如果路径太长，显示缩略版本
        if len(path_str) > 100:
            # 显示项目名和相对路径
            relative_path = path.relative_to(self.project_base.parent)
            display_path = f".../{relative_path}"
        else:
            display_path = path_str

        # 更新标签
        self.lbl_current_cut.setText(f"📁 {tab_name}: {display_path}")
        self.lbl_current_cut.setToolTip(path_str)  # 完整路径作为工具提示

    def _show_path_context_menu(self, position):
        """显示路径标签的右键菜单"""
        if not self.current_path:
            return

        menu = QMenu(self)

        # 复制路径
        act_copy = QAction("复制路径", self)
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(str(self.current_path)))
        menu.addAction(act_copy)

        # 在文件管理器中打开
        act_open = QAction("在文件管理器中打开", self)
        act_open.triggered.connect(lambda: self._open_path_in_explorer(self.current_path))
        menu.addAction(act_open)

        # 显示菜单
        menu.exec_(self.lbl_current_cut.mapToGlobal(position))

    def _open_path_in_explorer(self, path: Path):
        """在文件管理器中打开路径"""
        if not path or not path.exists():
            return

        system = platform.system()
        try:
            if system == "Windows":
                subprocess.run(["explorer", str(path)])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            print(f"打开文件管理器失败: {e}")

    def _load_cut_files(self, cut_id: str, episode_id: Optional[str] = None):
        """加载指定Cut的文件列表"""
        self._clear_file_lists()

        if not self.project_base:
            return

        # VFX 路径
        if episode_id:
            vfx_path = self.project_base / episode_id / "01_vfx" / cut_id
            render_path = self.project_base / "06_render" / episode_id / cut_id
            cg_path = self.project_base / episode_id / "02_3dcg" / cut_id
        else:
            vfx_path = self.project_base / "01_vfx" / cut_id
            render_path = self.project_base / "06_render" / cut_id
            cg_path = self.project_base / "02_3dcg" / cut_id

        # 加载 VFX 文件（AEP）
        aep_count = 0
        if vfx_path.exists():
            for file in vfx_path.glob("*.aep"):
                item = QListWidgetItem(file.name)
                item.setData(Qt.UserRole, str(file))
                self.vfx_list.addItem(item)
                aep_count += 1

        if aep_count == 0:
            item = QListWidgetItem("(没有 AEP 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.vfx_list.addItem(item)

        # 加载 Cell 文件夹
        cell_count = 0
        cell_path = vfx_path / "cell"
        if cell_path.exists():
            for folder in cell_path.iterdir():
                if folder.is_dir():
                    item = QListWidgetItem(f"📁 {folder.name}")
                    item.setData(Qt.UserRole, str(folder))
                    self.cell_list.addItem(item)
                    cell_count += 1

        if cell_count == 0:
            item = QListWidgetItem("(没有 Cell 文件夹)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.cell_list.addItem(item)

        # 加载 BG 文件
        bg_count = 0
        bg_path = vfx_path / "bg"
        if bg_path.exists():
            for file in bg_path.iterdir():
                if file.is_file() and file.suffix.lower() in ['.psd', '.png', '.jpg', '.jpeg']:
                    item = QListWidgetItem(file.name)
                    item.setData(Qt.UserRole, str(file))
                    self.bg_list.addItem(item)
                    bg_count += 1

        if bg_count == 0:
            item = QListWidgetItem("(没有 BG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.bg_list.addItem(item)

        # 加载 Render 文件
        render_count = 0
        if render_path.exists():
            # PNG 序列
            png_path = render_path / "png_seq"
            if png_path.exists():
                png_files = list(png_path.glob("*.png"))
                if png_files:
                    item = QListWidgetItem(f"📁 PNG序列 ({len(png_files)}张)")
                    item.setData(Qt.UserRole, str(png_path))
                    self.render_list.addItem(item)
                    render_count += 1

            # ProRes 视频
            prores_path = render_path / "prores"
            if prores_path.exists():
                for file in prores_path.glob("*.mov"):
                    item = QListWidgetItem(f"🎬 {file.name}")
                    item.setData(Qt.UserRole, str(file))
                    self.render_list.addItem(item)
                    render_count += 1

            # MP4 视频
            mp4_path = render_path / "mp4"
            if mp4_path.exists():
                for file in mp4_path.glob("*.mp4"):
                    item = QListWidgetItem(f"🎥 {file.name}")
                    item.setData(Qt.UserRole, str(file))
                    self.render_list.addItem(item)
                    render_count += 1

        if render_count == 0:
            item = QListWidgetItem("(没有渲染输出)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.render_list.addItem(item)

        # 加载 3DCG 文件
        cg_count = 0
        if cg_path.exists():
            for item_path in cg_path.iterdir():
                if item_path.is_file():
                    item = QListWidgetItem(item_path.name)
                    item.setData(Qt.UserRole, str(item_path))
                    self.cg_list.addItem(item)
                    cg_count += 1
                elif item_path.is_dir():
                    item = QListWidgetItem(f"📁 {item_path.name}")
                    item.setData(Qt.UserRole, str(item_path))
                    self.cg_list.addItem(item)
                    cg_count += 1

        # 更新Tab标题，显示文件数量
        vfx_count = self.vfx_list.count()
        if vfx_count > 0 and self.vfx_list.item(0).data(Qt.UserRole) is not None:
            self.file_tabs.setTabText(0, f"VFX ({vfx_count})")
        else:
            self.file_tabs.setTabText(0, "VFX")

        cell_count = self.cell_list.count()
        if cell_count > 0 and self.cell_list.item(0).data(Qt.UserRole) is not None:
            self.file_tabs.setTabText(1, f"Cell ({cell_count})")
        else:
            self.file_tabs.setTabText(1, "Cell")

        bg_count = self.bg_list.count()
        if bg_count > 0 and self.bg_list.item(0).data(Qt.UserRole) is not None:
            self.file_tabs.setTabText(2, f"BG ({bg_count})")
        else:
            self.file_tabs.setTabText(2, "BG")

        render_count = self.render_list.count()
        if render_count > 0 and self.render_list.item(0).data(Qt.UserRole) is not None:
            self.file_tabs.setTabText(3, f"Render ({render_count})")
        else:
            self.file_tabs.setTabText(3, "Render")

        cg_count = self.cg_list.count()
        if cg_count > 0 and self.cg_list.item(0).data(Qt.UserRole) is not None:
            self.file_tabs.setTabText(4, f"3DCG ({cg_count})")
        else:
            self.file_tabs.setTabText(4, "3DCG")

    def _clear_file_lists(self):
        """清空所有文件列表"""
        self.vfx_list.clear()
        self.cell_list.clear()
        self.bg_list.clear()
        self.render_list.clear()
        self.cg_list.clear()

        # 重置Tab标题
        self.file_tabs.setTabText(0, "VFX")
        self.file_tabs.setTabText(1, "Cell")
        self.file_tabs.setTabText(2, "BG")
        self.file_tabs.setTabText(3, "Render")
        self.file_tabs.setTabText(4, "3DCG")

    def _open_file_location(self, item: QListWidgetItem):
        """在文件管理器中打开文件位置"""
        file_path = item.data(Qt.UserRole)
        if not file_path:
            return

        path = Path(file_path)
        if not path.exists():
            return

        # 如果是文件，打开其父目录并选中文件
        # 如果是目录，直接打开
        system = platform.system()

        try:
            if system == "Windows":
                if path.is_file():
                    subprocess.run(["explorer", "/select,", str(path)])
                else:
                    subprocess.run(["explorer", str(path)])
            elif system == "Darwin":  # macOS
                if path.is_file():
                    subprocess.run(["open", "-R", str(path)])
                else:
                    subprocess.run(["open", str(path)])
            else:  # Linux
                if path.is_file():
                    subprocess.run(["xdg-open", str(path.parent)])
                else:
                    subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            print(f"打开文件位置失败: {e}")

    def _update_readme_stats(self):
        """更新README中的统计信息"""
        if not self.project_base:
            return

        readme_path = self.project_base / "README.md"
        if not readme_path.exists():
            return

        try:
            # 读取现有内容
            content = readme_path.read_text(encoding="utf-8")

            # 查找统计部分
            stats_start = content.find("## 项目统计")
            if stats_start == -1:
                return

            stats_end = content.find("\n## ", stats_start + 1)
            if stats_end == -1:
                stats_end = len(content)

            # 生成新的统计内容
            new_stats = ["## 项目统计", ""]

            if self.project_config.get("no_episode", False):
                cuts = self.project_config.get("cuts", [])
                new_stats.append(f"- 模式: 单集/PV 模式")
                new_stats.append(f"- Cut 总数: {len(cuts)}")
                if cuts:
                    new_stats.append(f"- Cut 范围: {min(cuts)} - {max(cuts)}")
            else:
                episodes = self.project_config.get("episodes", {})
                total_cuts = sum(len(cuts) for cuts in episodes.values())
                new_stats.append(f"- 模式: Episode 模式")
                new_stats.append(f"- Episode 总数: {len(episodes)}")
                new_stats.append(f"- Cut 总数: {total_cuts}")

                if episodes:
                    new_stats.append("")
                    new_stats.append("### Episode 详情")
                    for ep_id in sorted(episodes.keys()):
                        cut_count = len(episodes[ep_id])
                        if cut_count > 0:
                            cuts = episodes[ep_id]
                            new_stats.append(
                                f"- **{ep_id}**: {cut_count} cuts ({', '.join(sorted(cuts)[:5])}{'...' if len(cuts) > 5 else ''})")
                        else:
                            new_stats.append(f"- **{ep_id}**: (空)")

            new_stats.append("")
            new_stats.append(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 替换统计部分
            new_content = content[:stats_start] + "\n".join(new_stats) + "\n" + content[stats_end:]

            # 写回文件
            readme_path.write_text(new_content, encoding="utf-8")

        except Exception as e:
            print(f"更新README统计失败: {e}")

    def _update_cut_episode_combo(self):
        """更新Cut管理中的Episode下拉列表"""
        self.cmb_cut_episode.clear()

        if not self.project_config:
            return

        if not self.project_config.get("no_episode", False):
            # 有 Episode 模式，添加所有Episode
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_cut_episode.addItems(sorted(episodes.keys()))
                # 如果之前没有选中项，设置为未选择状态
                if self.cmb_cut_episode.count() > 0:
                    self.cmb_cut_episode.setCurrentIndex(-1)

    # ========================== 软件设置 ========================== #

    def _load_app_settings(self):
        """加载软件设置"""
        # 窗口几何
        geometry = self.app_settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # 更新默认路径提示
        default_path = self.app_settings.value("default_project_path", "")
        if default_path and Path(default_path).exists():
            self.statusbar.showMessage(f"默认项目路径: {default_path}")
        else:
            self.statusbar.showMessage("未设置默认项目路径，新建项目时需要选择位置")

        # 最后打开的项目
        last_project = self.app_settings.value("last_project")
        if last_project and Path(last_project).exists():
            self._load_project(last_project)

    def _save_app_settings(self):
        """保存软件设置"""
        self.app_settings.setValue("window_geometry", self.saveGeometry())
        if self.project_base:
            self.app_settings.setValue("last_project", str(self.project_base))

    def set_default_path(self):
        """设置默认项目路径"""
        current = self.app_settings.value("default_project_path", "")
        folder = QFileDialog.getExistingDirectory(
            self, "设置默认项目路径", current
        )

        if folder:
            self.app_settings.setValue("default_project_path", folder)

            # 更新新建按钮的工具提示
            self.btn_new_project.setToolTip(f"将创建到: {folder}")

            QMessageBox.information(
                self, "成功", f"默认项目路径已设置为:\n{folder}"
            )

    def _update_recent_menu(self):
        """更新最近项目菜单"""
        self.recent_menu.clear()

        recent_projects = self.app_settings.value("recent_projects", [])
        if not recent_projects:
            action = self.recent_menu.addAction("(无最近项目)")
            action.setEnabled(False)
            return

        for path in recent_projects[:10]:  # 最多显示 10 个
            if Path(path).exists():
                action = self.recent_menu.addAction(Path(path).name)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda checked, p=path: self.open_recent_project(p)
                )

    def _add_to_recent(self, path: str):
        """添加到最近项目"""
        recent = self.app_settings.value("recent_projects", [])

        # 移除已存在的
        if path in recent:
            recent.remove(path)

        # 添加到开头
        recent.insert(0, path)

        # 限制数量
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
        """在文件管理器中打开"""
        if not self.project_base:
            return

        system = platform.system()
        try:
            if system == "Windows":
                subprocess.run(["explorer", str(self.project_base)])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(self.project_base)])
            else:  # Linux
                subprocess.run(["xdg-open", str(self.project_base)])
        except Exception as e:
            print(f"打开文件管理器失败: {e}")

    def _on_cut_search_changed(self, text: str):
        """处理Cut搜索框内容变化"""
        search_text = text.strip().lower()

        if not search_text:
            # 如果搜索框为空，显示所有项目并重置颜色
            self._show_all_tree_items()
            self.browser_tree.setHeaderLabel("选择要浏览的 Cut")
            return

        match_count = 0
        first_match = None

        # 递归搜索并显示匹配的项目
        def search_items(item: QTreeWidgetItem):
            """递归搜索树项目"""
            nonlocal match_count, first_match
            item_text = item.text(0).lower()

            # 智能匹配
            has_match = False
            if search_text in item_text:
                has_match = True
            elif search_text.isdigit():
                # 如果搜索的是数字，进行智能匹配
                # 例如搜索"1"可以匹配"001", "010", "100"等
                if search_text in item.text(0):
                    has_match = True

            has_child_match = False

            # 检查子项
            for i in range(item.childCount()):
                child = item.child(i)
                if search_items(child):
                    has_child_match = True

            # 如果自身匹配或有子项匹配，则显示
            should_show = has_match or has_child_match
            item.setHidden(not should_show)

            # 高亮显示匹配的项目
            if has_match and item.childCount() == 0:
                # 设置匹配项的前景色为高亮色
                item.setForeground(0, QBrush(QColor("#4CAF50")))  # 绿色高亮
                item.setFont(0, QFont("", -1, QFont.Bold))  # 加粗
                match_count += 1
                if first_match is None:
                    first_match = item
            else:
                # 重置非匹配项的样式
                item.setForeground(0, QBrush())
                item.setFont(0, QFont())

            # 如果有子项匹配，展开该项
            if has_child_match:
                item.setExpanded(True)

            return should_show

        # 对所有顶级项目进行搜索
        for i in range(self.browser_tree.topLevelItemCount()):
            search_items(self.browser_tree.topLevelItem(i))

        # 更新标题显示搜索结果数
        if match_count > 0:
            self.browser_tree.setHeaderLabel(f"搜索结果: {match_count} 个Cut")
        else:
            self.browser_tree.setHeaderLabel("没有找到匹配的Cut")

    def _select_first_match(self):
        """选择第一个匹配的Cut"""

        # 查找第一个可见的叶子节点
        def find_first_visible_leaf(item: QTreeWidgetItem):
            if not item.isHidden():
                if item.childCount() == 0:
                    return item
                for i in range(item.childCount()):
                    result = find_first_visible_leaf(item.child(i))
                    if result:
                        return result
            return None

        # 搜索所有顶级项目
        for i in range(self.browser_tree.topLevelItemCount()):
            result = find_first_visible_leaf(self.browser_tree.topLevelItem(i))
            if result:
                self.browser_tree.setCurrentItem(result)
                self._on_browser_tree_clicked(result)
                break

    def _clear_cut_search(self):
        """清除Cut搜索"""
        self.txt_cut_search.clear()
        self._show_all_tree_items()

    def _show_all_tree_items(self):
        """显示所有树项目"""

        def show_items(item: QTreeWidgetItem):
            """递归显示所有项目"""
            item.setHidden(False)
            # 重置样式
            item.setForeground(0, QBrush())
            item.setFont(0, QFont())
            for i in range(item.childCount()):
                show_items(item.child(i))

        # 显示所有顶级项目
        for i in range(self.browser_tree.topLevelItemCount()):
            show_items(self.browser_tree.topLevelItem(i))

        # 恢复原始标题
        self.browser_tree.setHeaderLabel("选择要浏览的 Cut")

    def _focus_cut_search(self):
        """聚焦到Cut搜索框"""
        if self.txt_cut_search:
            # 切换到项目浏览Tab
            self.tabs.setCurrentIndex(1)
            # 聚焦到搜索框
            self.txt_cut_search.setFocus()
            self.txt_cut_search.selectAll()

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._save_app_settings()
        event.accept()


# ================================ 导出的组件 ================================ #
# 这些组件可以在其他程序中导入使用

__all__ = ['ProjectBrowser', 'CXProjectManager', 'SearchLineEdit']


# ================================ 主程序入口 ================================ #

def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("CX Project Manager")
    app.setOrganizationName("CXStudio")

    # 设置应用图标（可选）
    # app.setWindowIcon(QIcon("icon.png"))

    window = CXProjectManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()