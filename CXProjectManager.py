# -*- coding: utf-8 -*-
"""
CX Project Manager - 动画项目管理工具（优化版）
=============================================
功能特性：
• 支持有/无 Episode 模式（单集/PV）
• 单集模式下支持创建特殊类型 Episode（op/ed/pv 等，但不支持 ep）
• Episode 和 Cut 的创建与批量创建
• 素材导入管理（BG/Cell/Timesheet/AEP）
• AEP 模板批量复制功能
• 项目配置持久化
• 软件配置记忆（默认路径、最近项目）
• 目录树可视化
• Cut 搜索功能
• 版本管理系统
• 文件预览和时间显示
• 深色主题 UI

Author: 千石まよひ
Version: 2.1
GitHub: https://github.com/ChenxingM/CXProjectManager
"""

import json
import shutil
import sys
import os
import subprocess
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import Qt, QSettings, Signal, QSize, QTimer, QRect, QDateTime, QPoint
from PySide6.QtGui import (
    QAction, QFont, QIcon, QBrush, QColor, QPixmap, QPainter,
    QPen, QFontMetrics, QPalette
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMenuBar,
    QMessageBox, QPushButton, QSpinBox, QSplitter, QStatusBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QRadioButton, QButtonGroup, QListView, QAbstractItemView,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem
)

# 导入样式表
from _utils._qss import QSS_THEME

# 导入版本信息
from _utils._version_info import version_info

# ================================ 常量定义 ================================ #

# 图片文件扩展名 - 添加了.tga支持
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.psd', '.tiff', '.bmp', '.gif', '.tga', '.exr', '.dpx'}

# 视频文件扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm'}

# 3D文件扩展名
THREED_EXTENSIONS = {
    '.ma', '.mb',  # Maya
    '.max', '.3ds',  # 3ds Max
    '.blend',  # Blender
    '.c4d',  # Cinema 4D
    '.fbx', '.obj', '.dae',  # 通用格式
    '.abc',  # Alembic
    '.usd', '.usda', '.usdc',  # USD
    '.pld'  # 特殊格式
}

# 版本号正则表达式
VERSION_PATTERN = re.compile(r'_[TVtv](\d+)(?:\.\w+)?$')


# ================================ 枚举和数据类 ================================ #

class EpisodeType(Enum):
    """Episode 类型枚举"""
    EP = "ep"  # 普通集数
    PV = "pv"  # Promotional Video
    OP = "op"  # Opening
    ED = "ed"  # Ending
    SP = "sp"  # Special
    OVA = "ova"  # Original Video Animation
    CM = "cm"  # Commercial
    SV = "sv"  # Special Version
    EX = "ex"  # Extra
    NC = "nc"  # Non-Credit

    @classmethod
    def get_all_types(cls) -> List[str]:
        """获取所有类型"""
        return [t.value for t in cls]

    @classmethod
    def get_special_types(cls) -> List[str]:
        """获取特殊类型（非 ep）"""
        return [t.value for t in cls if t != cls.EP]


@dataclass
class ProjectPaths:
    """项目路径配置"""
    reference: str = "00_reference_project"
    render: str = "06_render"
    assets: str = "07_master_assets"
    aep_templates: str = "07_master_assets/aep_templates"
    tools: str = "08_tools"
    vfx: str = "01_vfx"
    cg: str = "02_3dcg"
    tmp: str = "98_tmp"
    other: str = "99_other"


@dataclass
class MaterialType:
    """素材类型定义"""
    BG = "bg"
    CELL = "cell"
    CG_3D = "3dcg"
    TIMESHEET = "timesheet"
    AEP = "aep"


@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    name: str
    version: Optional[int] = None
    modified_time: datetime = field(default_factory=datetime.now)
    size: int = 0
    is_folder: bool = False
    is_aep: bool = False  # 添加AEP标识
    is_png_seq: bool = False  # PNG序列标识
    first_png: Optional[Path] = None  # PNG序列第一张
    is_no_render: bool = False  # 未渲染标识

    @property
    def version_str(self) -> str:
        """获取版本字符串"""
        if self.version is not None:
            # AEP文件的特殊版本显示
            if self.is_aep:
                if self.version == 0:
                    return "T摄"
                else:
                    return f"本摄V{self.version}"
            # 其他文件的正常版本显示
            else:
                if "V" in self.name or "v" in self.name:
                    return f"V{self.version}"
                elif "T" in self.name or "t" in self.name:
                    return f"T{self.version}"
        return ""  # 返回空字符串表示没有版本号


# ================================ 工具函数 ================================ #

def zero_pad(number: int, width: int = 3) -> str:
    """数字补零

    Args:
        number: 要补零的数字
        width: 目标宽度

    Returns:
        str: 补零后的字符串
    """
    return str(number).zfill(width)


def ensure_dir(path: Path) -> None:
    """确保目录存在

    Args:
        path: 要创建的目录路径
    """
    path.mkdir(parents=True, exist_ok=True)


def copy_file_safe(src: Path, dst: Path) -> bool:
    """安全复制文件

    Args:
        src: 源文件路径
        dst: 目标文件路径

    Returns:
        bool: 是否成功复制
    """
    try:
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"复制文件失败: {e}")
        return False


def open_in_file_manager(path: Path) -> None:
    """在文件管理器中打开路径

    Args:
        path: 要打开的路径
    """
    if not path or not path.exists():
        return

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
        print(f"打开文件管理器失败: {e}")


def extract_version_from_filename(filename: str) -> Optional[int]:
    """从文件名中提取版本号

    Args:
        filename: 文件名

    Returns:
        Optional[int]: 版本号，如果没有则返回None
    """
    # 特殊处理_v0的情况
    if "_v0" in filename.lower():
        return 0

    match = VERSION_PATTERN.search(filename)
    if match:
        return int(match.group(1))
    return None


def format_file_size(size: int) -> str:
    """格式化文件大小

    Args:
        size: 文件大小（字节）

    Returns:
        str: 格式化后的字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def get_file_info(path: Path) -> FileInfo:
    """获取文件信息

    Args:
        path: 文件路径

    Returns:
        FileInfo: 文件信息对象
    """
    stat = path.stat()
    is_aep = path.suffix.lower() == '.aep'

    return FileInfo(
        path=path,
        name=path.name,
        version=extract_version_from_filename(path.stem),
        modified_time=datetime.fromtimestamp(stat.st_mtime),
        size=stat.st_size if path.is_file() else 0,
        is_folder=path.is_dir(),
        is_aep=is_aep
    )


def get_png_seq_info(png_seq_path: Path) -> FileInfo:
    """获取PNG序列文件夹信息

    Args:
        png_seq_path: PNG序列文件夹路径

    Returns:
        FileInfo: 包含PNG序列信息的文件信息对象
    """
    stat = png_seq_path.stat()

    # 查找第一张PNG
    first_png = None
    png_files = sorted(png_seq_path.glob("*.png"))
    if png_files:
        first_png = png_files[0]

    return FileInfo(
        path=png_seq_path,
        name=f"{png_seq_path.name} ({len(png_files)} frames)" if png_files else png_seq_path.name,
        modified_time=datetime.fromtimestamp(stat.st_mtime),
        size=0,
        is_folder=True,
        is_png_seq=True,
        first_png=first_png
    )


# ================================ 自定义控件 ================================ #

class SearchLineEdit(QLineEdit):
    """支持Esc键清除的搜索框"""

    def keyPressEvent(self, event):
        """处理按键事件"""
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)


class VersionConfirmDialog(QDialog):
    """版本确认对话框"""

    def __init__(self, material_type: str, current_version: int, parent=None):
        super().__init__(parent)
        self.material_type = material_type
        self.version = current_version
        self.skip_confirmation = False

        self.setWindowTitle("确认版本号")
        self.setModal(True)
        self.setStyleSheet(QSS_THEME)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 信息提示
        info_text = f"检测到已存在的{self.material_type.upper()}文件，\n建议使用版本号: T{self.version}"
        info_label = QLabel(info_text)
        info_label.setStyleSheet("padding: 10px; font-size: 14px;")
        layout.addWidget(info_label)

        # 版本号输入
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("版本号:"))
        self.spin_version = QSpinBox()
        self.spin_version.setPrefix("T")
        self.spin_version.setRange(1, 999)
        self.spin_version.setValue(self.version)
        self.spin_version.setMinimumWidth(100)
        version_layout.addWidget(self.spin_version)
        version_layout.addStretch()
        layout.addLayout(version_layout)

        # 不再询问选项
        self.chk_skip = QCheckBox("不再询问，自动使用推荐的版本号")
        layout.addWidget(self.chk_skip)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_version(self) -> int:
        """获取用户选择的版本号"""
        return self.spin_version.value()

    def should_skip_confirmation(self) -> bool:
        """是否跳过后续确认"""
        return self.chk_skip.isChecked()


class FileItemDelegate(QStyledItemDelegate):
    """文件列表项委托，用于自定义绘制"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_size = 64
        self.padding = 8
        # 调整字体设置
        self.version_font = QFont("MiSans", 20, QFont.Bold)  # 版本号字体稍微小一点
        self.name_font = QFont("MiSans", 12, QFont.Bold)  # 文件名加大加粗
        self.time_font = QFont("MiSans", 9)  # 时间字体弱化
        self.size_font = QFont("MiSans", 9)  # 大小字体弱化

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """绘制列表项"""
        painter.save()

        # 获取数据
        file_info = index.data(Qt.UserRole + 1)
        if not file_info:
            super().paint(painter, option, index)
            painter.restore()
            return

        rect = option.rect

        # 绘制选中背景
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor("#0D7ACC"))  # 更深的蓝色
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(rect, QColor("#3A3A3A"))

        # 绘制图标
        icon = index.data(Qt.DecorationRole)
        if icon:
            icon_rect = QRect(
                rect.left() + self.padding,
                rect.top() + self.padding,
                self.icon_size,
                self.icon_size
            )
            icon.paint(painter, icon_rect)

        # 文本区域
        text_left = rect.left() + self.icon_size + self.padding * 2
        text_width = rect.width() - self.icon_size - self.padding * 3

        # 如果有版本号，留出空间
        if file_info.version is not None:
            text_width -= 80  # 为版本号留出更多空间

        # 绘制文件名 - 加粗且更大
        painter.setFont(self.name_font)
        if option.state & QStyle.State_Selected:
            painter.setPen(Qt.white)
        else:
            painter.setPen(QColor("#FFFFFF"))  # 更亮的白色

        name_rect = QRect(
            text_left,
            rect.top() + self.padding,
            text_width,
            25  # 增加高度
        )
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, file_info.name)

        # 绘制时间 - 弱化显示
        painter.setFont(self.time_font)
        if option.state & QStyle.State_Selected:
            painter.setPen(QColor("#E0E0E0"))
        else:
            painter.setPen(QColor("#808080"))  # 更暗的灰色

        time_text = file_info.modified_time.strftime("%Y-%m-%d %H:%M")
        time_rect = QRect(
            text_left,
            rect.top() + self.padding + 30,
            text_width,
            20
        )
        painter.drawText(time_rect, Qt.AlignLeft | Qt.AlignVCenter, time_text)

        # 绘制文件大小 - 弱化显示
        if not file_info.is_folder and file_info.size > 0:
            painter.setFont(self.size_font)
            size_text = format_file_size(file_info.size)
            size_rect = QRect(
                text_left,
                rect.top() + self.padding + 48,
                text_width,
                20
            )
            painter.drawText(size_rect, Qt.AlignLeft | Qt.AlignVCenter, size_text)

        # 绘制版本号
        if file_info.version is not None and file_info.version_str:
            painter.setFont(self.version_font)

            # 根据版本类型选择颜色
            if file_info.is_aep:
                if file_info.version == 0:
                    painter.setPen(QColor("#FF9800"))  # 橙色 for T摄
                else:
                    painter.setPen(QColor("#4CAF50"))  # 绿色 for 本摄Vx
            else:
                painter.setPen(QColor("#4CAF50"))  # 绿色 for 普通版本

            # 计算版本文字宽度来居中显示
            version_text = file_info.version_str
            fm = QFontMetrics(self.version_font)
            text_width = fm.horizontalAdvance(version_text)

            version_rect = QRect(
                rect.right() - text_width - 15,
                rect.top() + rect.height() // 2 - 20,
                text_width + 10,
                40
            )
            painter.drawText(version_rect, Qt.AlignCenter, version_text)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """返回项目大小"""
        return QSize(400, self.icon_size + self.padding * 2)


class DetailedFileListWidget(QListWidget):
    """详细文件列表控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(FileItemDelegate(self))
        self.setSpacing(4)
        self.setUniformItemSizes(False)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        # 加载所有图标
        self._load_icons()

    def _load_icons(self):
        """加载所有图标"""
        icon_base = Path("_imgs")

        # 文件类型图标
        self.icons = {
            'aep': self._load_icon(icon_base / "aep_icon.png"),
            'psd': self._load_icon(icon_base / "psd_icon.png"),
            'folder': self._load_icon(icon_base / "folder_icon.png"),
            'image': self._load_icon(icon_base / "image_icon.png"),
            'video': self._load_icon(icon_base / "video_icon.png"),
            'file': self._load_icon(icon_base / "file_icon.png"),
            'clip': self._load_icon(icon_base / "clip_icon.png"),
            'maya': self._load_icon(icon_base / "maya_icon.png"),
            '3dsmax': self._load_icon(icon_base / "3dsmax_icon.png"),
            'blender': self._load_icon(icon_base / "blender_icon.png"),
            'c4d': self._load_icon(icon_base / "c4d_icon.png"),
            'fbx': self._load_icon(icon_base / "fbx_icon.png"),
            'pld': self._load_icon(icon_base / "pld_icon.png"),
            '3d': self._load_icon(icon_base / "3d_icon.png"),  # 通用3D图标
            'png_seq': self._load_icon(icon_base / "png_seq_icon.png"),
            'no_render': self._load_icon(icon_base / "no_render_icon.png"),
        }

    def _load_icon(self, path: Path) -> Optional[QIcon]:
        """加载单个图标"""
        if path.exists():
            return QIcon(str(path))
        return None

    def add_file_item(self, file_info: FileInfo):
        """添加文件项"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, str(file_info.path))
        item.setData(Qt.UserRole + 1, file_info)

        # 设置图标
        icon = self._get_file_icon(file_info)
        if icon:
            item.setIcon(icon)

        self.addItem(item)

    def load_files(self, directory: Path, pattern: str = "*", expand_folders: bool = False):
        """加载目录中的文件

        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            expand_folders: 是否展开文件夹内容
        """
        self.clear()

        if not directory.exists():
            return

        # 收集文件信息
        files = []
        for file_path in directory.glob(pattern):
            if expand_folders and file_path.is_dir():
                # 展开文件夹内容
                for sub_file in file_path.rglob("*"):
                    if sub_file.is_file():
                        files.append(get_file_info(sub_file))
            else:
                files.append(get_file_info(file_path))

        # 按修改时间降序排序（最新的在前）
        files.sort(key=lambda f: f.modified_time, reverse=True)

        # 添加到列表
        for file_info in files:
            self.add_file_item(file_info)

    def _get_file_icon(self, file_info: FileInfo) -> Optional[QIcon]:
        """获取文件图标"""
        # 未渲染状态
        if file_info.is_no_render:
            return self.icons.get('no_render')

        if file_info.is_folder:
            # PNG序列文件夹特殊处理
            if file_info.is_png_seq and file_info.first_png:
                try:
                    # 尝试加载第一张PNG作为缩略图
                    pixmap = QPixmap(str(file_info.first_png))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        return QIcon(scaled)
                except:
                    pass
                return self.icons.get('png_seq', self.icons.get('folder'))
            return self.icons.get('folder')

        # 文件扩展名
        ext = file_info.path.suffix.lower()

        # AEP文件
        if ext == '.aep':
            return self.icons.get('aep')

        # PSD文件
        if ext == '.psd':
            return self.icons.get('psd')

        # Clip文件
        if ext == '.clip':
            return self.icons.get('clip')

        # 3D文件
        if ext in ['.ma', '.mb']:
            return self.icons.get('maya', self.icons.get('3d'))
        if ext in ['.max', '.3ds']:
            return self.icons.get('3dsmax', self.icons.get('3d'))
        if ext == '.blend':
            return self.icons.get('blender', self.icons.get('3d'))
        if ext == '.c4d':
            return self.icons.get('c4d', self.icons.get('3d'))
        if ext in ['.fbx', '.obj', '.dae', '.abc', '.usd', '.usda', '.usdc']:
            return self.icons.get('fbx', self.icons.get('3d'))
        if ext == '.pld':
            return self.icons.get('pld')
        if ext in THREED_EXTENSIONS:
            return self.icons.get('3d')

        # 图片文件
        if ext in IMAGE_EXTENSIONS:
            # 尝试加载缩略图
            try:
                pixmap = QPixmap(str(file_info.path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return QIcon(scaled)
            except:
                pass
            return self.icons.get('image')

        # 视频文件
        if ext in VIDEO_EXTENSIONS:
            return self.icons.get('video')

        # 默认文件图标
        return self.icons.get('file')


class BatchAepDialog(QDialog):
    """批量复制AEP模板对话框"""

    def __init__(self, project_config: Dict, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        project_name = project_config.get("project_name", "未命名项目")
        self.setWindowTitle(f"批量复制 AEP 模板 - {project_name}")
        self.setModal(True)
        self.resize(450, 350)
        self.setStyleSheet(QSS_THEME)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 模板信息提示
        info_label = QLabel()
        template_count = self._get_template_count()
        if template_count > 0:
            info_label.setText(f"ℹ️ 找到 {template_count} 个 AEP 模板文件")
            info_label.setStyleSheet("color: #03A9F4; padding: 8px;")
        else:
            info_label.setText("⚠️ 未找到 AEP 模板文件")
            info_label.setStyleSheet("color: #FF9800; padding: 8px;")
        layout.addWidget(info_label)

        # 选择范围
        scope_group = QGroupBox("选择范围")
        scope_layout = QVBoxLayout(scope_group)

        self.radio_all = QRadioButton("所有 Episode 和 Cut")
        self.radio_episode = QRadioButton("指定 Episode 的所有 Cut")
        self.radio_selected = QRadioButton("指定 Episode 和 Cut 范围")

        self.radio_group = QButtonGroup()
        self.radio_group.addButton(self.radio_all, 0)
        self.radio_group.addButton(self.radio_episode, 1)
        self.radio_group.addButton(self.radio_selected, 2)

        self.radio_all.setChecked(True)

        scope_layout.addWidget(self.radio_all)
        scope_layout.addWidget(self.radio_episode)
        scope_layout.addWidget(self.radio_selected)

        # Episode 选择
        ep_layout = QHBoxLayout()
        self.lbl_episode = QLabel("Episode:")
        self.cmb_episode = QComboBox()
        self.cmb_episode.setEnabled(False)

        # 填充Episode列表
        episodes = self.project_config.get("episodes", {})
        self.cmb_episode.addItems(sorted(episodes.keys()))

        ep_layout.addWidget(self.lbl_episode)
        ep_layout.addWidget(self.cmb_episode)
        scope_layout.addLayout(ep_layout)

        # Cut 范围选择
        cut_layout = QHBoxLayout()
        self.lbl_cut_range = QLabel("Cut 范围:")
        self.spin_cut_from = QSpinBox()
        self.spin_cut_from.setRange(1, 999)
        self.spin_cut_from.setValue(1)
        self.spin_cut_from.setEnabled(False)

        self.lbl_cut_to = QLabel("到")
        self.spin_cut_to = QSpinBox()
        self.spin_cut_to.setRange(1, 999)
        self.spin_cut_to.setValue(100)
        self.spin_cut_to.setEnabled(False)

        cut_layout.addWidget(self.lbl_cut_range)
        cut_layout.addWidget(self.spin_cut_from)
        cut_layout.addWidget(self.lbl_cut_to)
        cut_layout.addWidget(self.spin_cut_to)
        cut_layout.addStretch()
        scope_layout.addLayout(cut_layout)

        layout.addWidget(scope_group)

        # 选项
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout(options_group)

        self.chk_overwrite = QCheckBox("覆盖已存在的文件")
        self.chk_overwrite.setChecked(False)

        self.chk_skip_existing = QCheckBox("跳过已有 AEP 文件的 Cut")
        self.chk_skip_existing.setChecked(True)

        options_layout.addWidget(self.chk_overwrite)
        options_layout.addWidget(self.chk_skip_existing)

        layout.addWidget(options_group)

        # 按钮
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.buttons.button(QDialogButtonBox.Ok).setText("开始复制")
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout.addWidget(self.buttons)

        # 连接信号
        self.radio_group.buttonClicked.connect(self._on_scope_changed)
        self.chk_overwrite.toggled.connect(self._on_overwrite_changed)

    def _get_template_count(self) -> int:
        """获取模板文件数量"""
        if not hasattr(self.parent(), 'project_base') or not self.parent().project_base:
            return 0

        template_dir = self.parent().project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists():
            return 0

        return len(list(template_dir.glob("*.aep")))

    def _on_scope_changed(self, button):
        """范围选择改变时的处理"""
        scope_id = self.radio_group.id(button)
        self.cmb_episode.setEnabled(scope_id >= 1)
        self.spin_cut_from.setEnabled(scope_id == 2)
        self.spin_cut_to.setEnabled(scope_id == 2)

    def _on_overwrite_changed(self, checked):
        """覆盖选项改变时的处理"""
        if checked:
            self.chk_skip_existing.setChecked(False)

    def get_settings(self) -> Dict:
        """获取用户设置"""
        scope_id = self.radio_group.checkedId()

        settings = {
            "scope": scope_id,  # 0: all, 1: episode, 2: selected
            "episode": self.cmb_episode.currentText() if scope_id >= 1 else None,
            "cut_from": self.spin_cut_from.value() if scope_id == 2 else None,
            "cut_to": self.spin_cut_to.value() if scope_id == 2 else None,
            "overwrite": self.chk_overwrite.isChecked(),
            "skip_existing": self.chk_skip_existing.isChecked(),
        }

        return settings


# ================================ 项目管理器类 ================================ #

class ProjectManager:
    """项目管理核心类，负责项目的创建、加载、保存等操作"""

    def __init__(self, project_base: Path = None):
        self.project_base = project_base
        self.project_config = None
        self.paths = ProjectPaths()

    def create_project(self, project_name: str, base_folder: Path, no_episode: bool = False) -> bool:
        """创建新项目

        Args:
            project_name: 项目名称
            base_folder: 项目基础文件夹
            no_episode: 是否为无Episode模式

        Returns:
            bool: 是否创建成功
        """
        self.project_base = base_folder / project_name

        # 创建项目结构
        self._create_project_structure(no_episode)

        # 初始化项目配置
        self.project_config = {
            "project_name": project_name,
            "project_path": str(self.project_base),
            "no_episode": no_episode,
            "episodes": {},
            "cuts": [],  # 无 Episode 模式下的 cuts
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "paths": self.paths.__dict__
        }

        # 保存配置
        self.save_config()

        # 创建README
        self._create_readme()

        return True

    def load_project(self, project_path: Path) -> bool:
        """加载项目

        Args:
            project_path: 项目路径

        Returns:
            bool: 是否加载成功
        """
        config_file = project_path / "project_config.json"

        if not config_file.exists():
            return False

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self.project_config = json.load(f)
            self.project_base = project_path
            return True
        except Exception as e:
            print(f"加载项目配置失败：{e}")
            return False

    def save_config(self):
        """保存项目配置"""
        if not self.project_base or not self.project_config:
            return

        self.project_config["last_modified"] = datetime.now().isoformat()

        config_file = self.project_base / "project_config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self.project_config, f, indent=4, ensure_ascii=False)

    def _create_project_structure(self, no_episode: bool):
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
            "07_master_assets/aep_templates",
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

        # 创建所有目录
        all_dirs = ref_dirs + asset_dirs + tool_dirs + other_dirs
        for dir_path in all_dirs:
            ensure_dir(self.project_base / dir_path)

    def _create_readme(self):
        """创建项目README文件"""
        readme_content = f"""# {self.project_base.name}

创建时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 项目结构说明

### 项目根目录
- `00_reference_project/` - 全项目通用参考资料
- `01_vfx/` - VFX/AE 制作文件
- `02_3dcg/` - 3DCG 制作文件（按需创建）
- `06_render/` - 最终渲染输出
- `07_master_assets/` - 共用素材
  - `aep_templates/` - AE 项目模板
  - `fonts/` - 字体文件
  - `logo/` - Logo 素材
  - `fx_presets/` - 特效预设
- `08_tools/` - 自动化脚本与工具
- `98_tmp/` - 临时文件
- `99_other/` - 其他文件

## 项目模式

{'单集/PV 模式' if self.project_config.get('no_episode', False) else 'Episode 模式'}

## 使用说明

请使用 CX Project Manager 管理本项目。
"""
        (self.project_base / "README.md").write_text(readme_content, encoding="utf-8")

    def create_episode(self, ep_type: str, ep_identifier: str = "") -> Tuple[bool, str]:
        """创建Episode

        Args:
            ep_type: Episode类型
            ep_identifier: Episode标识（可选）

        Returns:
            Tuple[bool, str]: (是否成功, Episode ID或错误信息)
        """
        # 构建 Episode ID
        if ep_type == "ep" and ep_identifier and ep_identifier.isdigit():
            ep_id = f"ep{zero_pad(int(ep_identifier), 2)}"
        elif ep_identifier:
            safe_identifier = ep_identifier.replace(" ", "_").replace("/", "_").replace("\\", "_")
            if ep_type and ep_type != ep_identifier.lower():
                ep_id = f"{ep_type}_{safe_identifier}"
            else:
                ep_id = safe_identifier
        else:
            ep_id = ep_type

        # 检查是否已存在
        if ep_id in self.project_config.get("episodes", {}):
            return False, f"Episode '{ep_id}' 已存在"

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
        self.save_config()

        return True, ep_id

    def create_cut(self, cut_num: str, episode_id: str = None) -> Tuple[bool, str]:
        """创建Cut

        Args:
            cut_num: Cut编号
            episode_id: Episode ID（可选）

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        if not cut_num.isdigit():
            return False, "请输入有效的 Cut 编号"

        cut_id = zero_pad(int(cut_num), 3)

        if self.project_config.get("no_episode", False) and not episode_id:
            # 无 Episode 模式
            if cut_id in self.project_config.get("cuts", []):
                return False, f"Cut {cut_id} 已存在"

            cut_path = self.project_base / "01_vfx" / cut_id
            self._create_cut_structure(cut_path, episode_id=None)

            # 更新配置
            if "cuts" not in self.project_config:
                self.project_config["cuts"] = []
            self.project_config["cuts"].append(cut_id)

        else:
            # 有 Episode 模式或单集模式下的特殊Episode
            if not episode_id:
                return False, "请选择 Episode"

            if episode_id not in self.project_config.get("episodes", {}):
                return False, f"Episode '{episode_id}' 不存在"

            if cut_id in self.project_config["episodes"][episode_id]:
                return False, f"Cut {cut_id} 已存在于 {episode_id}"

            cut_path = self.project_base / episode_id / "01_vfx" / cut_id
            self._create_cut_structure(cut_path, episode_id=episode_id)

            # 更新配置
            self.project_config["episodes"][episode_id].append(cut_id)

        self.save_config()
        return True, cut_id

    def _create_cut_structure(self, cut_path: Path, episode_id: Optional[str] = None):
        """创建Cut目录结构"""
        # 创建Cut内部子目录
        subdirs = ["cell", "bg", "prerender"]
        for subdir in subdirs:
            ensure_dir(cut_path / subdir)

        # 获取cut_id
        cut_id = cut_path.name
        proj_name = self.project_base.name

        # 创建render目录结构
        if episode_id:
            render_path = self.project_base / "06_render" / episode_id / cut_id
        else:
            render_path = self.project_base / "06_render" / cut_id

        # 创建render子目录
        render_subdirs = ["png_seq", "prores", "mp4"]
        for subdir in render_subdirs:
            ensure_dir(render_path / subdir)

        # 复制AEP模板（如果存在）
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if template_dir.exists():
            for template in template_dir.glob("*.aep"):
                # 保留模板的原始文件名中的版本号或其他信息
                template_stem = template.stem

                # 构建新文件名
                if episode_id:
                    ep_part = episode_id.upper()
                    if '_v' in template_stem:
                        version_part = template_stem[template_stem.rfind('_v'):]
                        aep_name = f"{proj_name}_{ep_part}_{cut_id}{version_part}{template.suffix}"
                    else:
                        aep_name = f"{proj_name}_{ep_part}_{cut_id}_v0{template.suffix}"
                else:
                    if '_v' in template_stem:
                        version_part = template_stem[template_stem.rfind('_v'):]
                        aep_name = f"{proj_name}_{cut_id}{version_part}{template.suffix}"
                    else:
                        aep_name = f"{proj_name}_{cut_id}_v0{template.suffix}"

                dst = cut_path / aep_name
                copy_file_safe(template, dst)

    def get_next_version(self, target_dir: Path, pattern: str) -> int:
        """获取下一个版本号

        Args:
            target_dir: 目标目录
            pattern: 文件名模式（不含版本号部分）

        Returns:
            int: 下一个版本号
        """
        if not target_dir.exists():
            return 1

        # 查找所有匹配的文件
        max_version = 0
        for file in target_dir.iterdir():
            version = extract_version_from_filename(file.stem)
            if version is not None and file.stem.startswith(pattern):
                max_version = max(max_version, version)

        return max_version + 1


# ================================ 主窗口类 ================================ #

class CXProjectManager(QMainWindow):
    """动画项目管理器主窗口"""

    project_changed = Signal()  # 项目变更信号

    def __init__(self):
        super().__init__()
        # 使用版本信息
        version = version_info.get("version", "2.1")
        build = version_info.get("build-version", "")
        if build:
            version_str = f"{version} {build}"
        else:
            version_str = version

        self.setWindowTitle(f"CX Project Manager - 动画项目管理工具 v{version_str}")
        self.resize(1300, 750)

        # 初始化项目管理器
        self.project_manager = ProjectManager()

        # 初始化变量
        self.project_base: Optional[Path] = None
        self.project_config: Optional[Dict] = None
        self.app_settings = QSettings("CXStudio", "ProjectManager")

        # 版本确认跳过设置
        self.skip_version_confirmation = {
            "bg": False,
            "cell": False,
            "3dcg": False
        }

        # 初始化控件变量
        self._init_widget_variables()

        # 设置UI
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()

        # 应用样式
        self.setStyleSheet(QSS_THEME)

        # 初始状态设置
        self._set_initial_state()

        # 加载软件配置
        self._load_app_settings()

        # 连接信号
        self.project_changed.connect(self._on_project_changed)

    def _init_widget_variables(self):
        """初始化所有控件变量"""
        # 项目管理控件
        self.lbl_project_path = None
        self.txt_project_name = None
        self.btn_new_project = None
        self.btn_open_project = None
        self.chk_no_episode = None

        # Episode管理控件
        self.episode_group = None
        self.cmb_episode_type = None
        self.txt_episode = None
        self.btn_create_episode = None
        self.btn_batch_episode = None
        self.lbl_batch_ep = None
        self.spin_ep_from = None
        self.spin_ep_to = None

        # Cut管理控件
        self.cmb_cut_episode = None
        self.txt_cut = None
        self.btn_create_cut = None
        self.btn_batch_cut = None
        self.spin_cut_from = None
        self.spin_cut_to = None

        # 素材导入控件
        self.lbl_target_episode = None
        self.cmb_target_episode = None
        self.cmb_target_cut = None
        self.txt_bg_path = None
        self.txt_cell_path = None
        self.txt_3dcg_path = None
        self.txt_timesheet_path = None
        self.btn_browse_bg = None
        self.btn_browse_cell = None
        self.btn_browse_3dcg = None
        self.btn_browse_timesheet = None
        self.btn_import_single = None
        self.btn_import_all = None
        self.btn_copy_aep = None
        self.btn_batch_copy_aep = None

        # 树和Tab控件
        self.tree = None
        self.tabs = None

        # 浏览器相关控件
        self.txt_project_stats = None
        self.browser_tree = None
        self.file_tabs = None
        self.vfx_list: Optional[DetailedFileListWidget] = None
        self.cell_list: Optional[DetailedFileListWidget] = None
        self.bg_list: Optional[DetailedFileListWidget] = None
        self.render_list: Optional[DetailedFileListWidget] = None
        self.cg_list: Optional[DetailedFileListWidget] = None
        self.lbl_current_cut = None
        self.txt_cut_search = None
        self.btn_clear_search = None

        # 状态变量
        self.current_cut_id = None
        self.current_episode_id = None
        self.current_path = None

        # 菜单相关
        self.recent_menu = None
        self.statusbar = None

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
        management_tab = self._create_management_tab()

        # Tab 2: 项目浏览
        browser_tab = self._create_browser_tab()

        # 添加Tab
        self.tabs.addTab(management_tab, "📁 项目管理")
        self.tabs.addTab(browser_tab, "📊 项目浏览")

        # 设置默认Tab
        self.tabs.setCurrentIndex(0)

    def _create_management_tab(self) -> QWidget:
        """创建项目管理Tab"""
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

        return management_tab

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

        # 添加弹性空间
        layout.addStretch()

        return panel

    def _create_project_group(self) -> QGroupBox:
        """创建项目管理组"""
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
        self.txt_project_name.returnPressed.connect(self.new_project)
        self.btn_new_project = QPushButton("新建")
        self.btn_new_project.clicked.connect(self.new_project)

        new_project_layout.addWidget(self.txt_project_name)
        new_project_layout.addWidget(self.btn_new_project)
        project_layout.addLayout(new_project_layout)

        # 打开项目按钮
        self.btn_open_project = QPushButton("打开项目")
        self.btn_open_project.clicked.connect(self.open_project)
        project_layout.addWidget(self.btn_open_project)

        # Episode 模式选择
        self.chk_no_episode = QCheckBox("单集/PV 模式（支持特殊 Episode）")
        self.chk_no_episode.setToolTip("单集模式下可以创建 op/ed/pv 等特殊类型，但不能创建标准集数 ep")
        self.chk_no_episode.stateChanged.connect(self._toggle_episode_mode)
        project_layout.addWidget(self.chk_no_episode)

        return project_group

    def _create_episode_group(self) -> QGroupBox:
        """创建Episode管理组"""
        self.episode_group = QGroupBox("🎬 Episode 管理")
        episode_layout = QVBoxLayout(self.episode_group)

        # Episode 类型和编号输入
        single_ep_layout = QHBoxLayout()

        # Episode 类型下拉框
        self.cmb_episode_type = QComboBox()
        self.cmb_episode_type.setEditable(True)
        self.cmb_episode_type.addItems(EpisodeType.get_all_types())
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

        return self.episode_group

    def _create_cut_group(self) -> QGroupBox:
        """创建Cut管理组"""
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

        return cut_group

    def _create_import_group(self) -> QGroupBox:
        """创建素材导入组"""
        import_group = QGroupBox("📥 素材导入")
        import_layout = QVBoxLayout(import_group)

        # Episode 和 Cut 选择
        target_layout = QHBoxLayout()

        # Episode 选择（有 Episode 模式时显示）
        self.cmb_target_episode = QComboBox()
        self.cmb_target_episode.setPlaceholderText("选择 Episode")
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

        # 素材路径选择
        import_layout.addLayout(self._create_material_browse_layout("BG", "bg"))
        import_layout.addLayout(self._create_material_browse_layout("Cell", "cell"))
        import_layout.addLayout(self._create_material_browse_layout("3DCG", "3dcg"))
        import_layout.addLayout(self._create_material_browse_layout("TS", "timesheet"))

        # 导入操作按钮
        import_action_layout = QHBoxLayout()
        self.btn_import_single = QPushButton("导入选中")
        self.btn_import_all = QPushButton("批量导入")
        self.btn_copy_aep = QPushButton("复制 AEP 模板")
        self.btn_batch_copy_aep = QPushButton("批量复制 AEP")
        self.btn_batch_copy_aep.setToolTip("批量复制AEP模板到多个Cut并自动重命名")

        self.btn_import_single.clicked.connect(self.import_single)
        self.btn_import_all.clicked.connect(self.import_all)
        self.btn_copy_aep.clicked.connect(self.copy_aep_template)
        self.btn_batch_copy_aep.clicked.connect(self.batch_copy_aep_template)

        import_action_layout.addWidget(self.btn_import_single)
        import_action_layout.addWidget(self.btn_import_all)
        import_action_layout.addWidget(self.btn_copy_aep)
        import_action_layout.addWidget(self.btn_batch_copy_aep)
        import_layout.addLayout(import_action_layout)

        return import_group

    def _create_material_browse_layout(self, label_text: str, material_type: str) -> QHBoxLayout:
        """创建素材浏览布局"""
        layout = QHBoxLayout()

        # 创建对应的文本框
        txt_path = QLineEdit()
        txt_path.setPlaceholderText(f"{label_text} 文件路径")
        txt_path.setReadOnly(True)

        # 保存到实例变量
        setattr(self, f"txt_{material_type}_path", txt_path)

        # 创建浏览按钮
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(lambda: self.browse_material(material_type))
        setattr(self, f"btn_browse_{material_type}", btn_browse)

        layout.addWidget(QLabel(f"{label_text}:"))
        layout.addWidget(txt_path)
        layout.addWidget(btn_browse)

        return layout

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

        # 左侧面板
        left_panel = self._create_browser_left_panel()

        # 右侧面板
        right_panel = self._create_browser_right_panel()

        # 添加到主分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        layout.addWidget(main_splitter)

        return browser

    def _create_browser_left_panel(self) -> QWidget:
        """创建浏览器左侧面板"""
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
                font-family: "MiSans", "微软雅黑", "Segoe UI", Arial;
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
        self.txt_cut_search.setClearButtonEnabled(True)
        self.txt_cut_search.returnPressed.connect(self._select_first_match)
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

        left_layout.addWidget(tree_group, 1)

        return left_panel

    def _create_browser_right_panel(self) -> QWidget:
        """创建浏览器右侧面板"""
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
        self.lbl_current_cut.setWordWrap(True)
        self.lbl_current_cut.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_current_cut.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lbl_current_cut.customContextMenuRequested.connect(self._show_path_context_menu)
        files_layout.addWidget(self.lbl_current_cut)

        # 文件类型Tab
        self.file_tabs = QTabWidget()
        self.file_tabs.currentChanged.connect(self._on_file_tab_changed)

        # 创建各种文件列表
        self.vfx_list = self._create_file_list_widget()
        self.cell_list = self._create_file_list_widget()
        self.bg_list = self._create_file_list_widget()
        self.render_list = self._create_file_list_widget()
        self.cg_list = self._create_file_list_widget()

        self.file_tabs.addTab(self.vfx_list, "VFX")
        self.file_tabs.addTab(self.cell_list, "Cell")
        self.file_tabs.addTab(self.bg_list, "BG")
        self.file_tabs.addTab(self.render_list, "Render")
        self.file_tabs.addTab(self.cg_list, "3DCG")

        files_layout.addWidget(self.file_tabs)
        right_layout.addWidget(files_group)

        return right_panel

    def _create_file_list_widget(self) -> DetailedFileListWidget:
        """创建文件列表控件"""
        list_widget = DetailedFileListWidget()
        list_widget.itemDoubleClicked.connect(self._on_file_item_double_clicked)
        return list_widget

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

        tools_menu.addSeparator()

        act_batch_aep = QAction("批量复制AEP模板...", self)
        act_batch_aep.triggered.connect(self.batch_copy_aep_template)
        tools_menu.addAction(act_batch_aep)

        tools_menu.addSeparator()

        act_open_folder = QAction("在文件管理器中打开", self)
        act_open_folder.triggered.connect(self.open_in_explorer)
        tools_menu.addAction(act_open_folder)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        act_help = QAction("使用说明", self)
        act_help.triggered.connect(self.show_help)
        help_menu.addAction(act_help)

        act_about = QAction("关于", self)
        act_about.triggered.connect(self.show_about)
        help_menu.addAction(act_about)

    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("请打开或新建项目以开始使用")

    def _set_initial_state(self):
        """设置初始状态"""
        self._enable_controls(False)

        # 确保项目名称输入框始终启用
        self.txt_project_name.setEnabled(True)
        self.btn_new_project.setEnabled(True)
        self.btn_open_project.setEnabled(True)

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
            base_folder = Path(default_path)
        else:
            base_folder = QFileDialog.getExistingDirectory(
                self, "选择项目创建位置", ""
            )
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

            # 更新UI
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

    def _load_project(self, folder: str):
        """加载项目"""
        project_path = Path(folder)

        if self.project_manager.load_project(project_path):
            self.project_base = self.project_manager.project_base
            self.project_config = self.project_manager.project_config
            self.project_changed.emit()
            self._add_to_recent(str(project_path))
        else:
            QMessageBox.warning(
                self, "错误", "所选文件夹不是有效的项目（缺少 project_config.json）"
            )

    # ========================== Episode 和 Cut 管理 ========================== #

    def create_episode(self):
        """创建单个Episode"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取Episode类型和标识
        ep_type = self.cmb_episode_type.currentText().strip().lower()
        ep_identifier = self.txt_episode.text().strip()

        # 检查单集模式下的限制
        if self.chk_no_episode.isChecked() and ep_type == "ep":
            QMessageBox.information(
                self, "提示",
                "单集/PV 模式下不支持创建标准集数 (ep)，\n"
                "但可以创建其他类型如 op、ed、pv 等。"
            )
            return

        # 创建Episode
        success, result = self.project_manager.create_episode(ep_type, ep_identifier)

        if success:
            # 刷新UI
            self._refresh_tree()
            self._update_import_combos()
            self._update_cut_episode_combo()
            self._update_project_stats()
            self._update_browser_tree()

            self.statusbar.showMessage(f"已创建 Episode: {result}", 3000)
        else:
            QMessageBox.warning(self, "错误", result)

    def batch_create_episodes(self):
        """批量创建Episode（仅支持ep类型）"""
        # 确保是ep类型
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
            success, result = self.project_manager.create_episode("ep", str(i))
            if success:
                created_count += 1
            else:
                skipped_count += 1

        # 恢复原始类型
        self.cmb_episode_type.setCurrentText(original_type)

        # 显示结果
        message = f"成功创建 {created_count} 个 Episode"
        if skipped_count > 0:
            message += f"，跳过 {skipped_count} 个已存在的 Episode"

        if created_count > 0 or skipped_count > 0:
            QMessageBox.information(self, "完成", message)
            # 批量创建后刷新
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
            # 单集模式下，如果有选择Episode（特殊类型），则使用
            ep_text = self.cmb_cut_episode.currentText().strip()
            if ep_text and ep_text in self.project_config.get("episodes", {}):
                episode_id = ep_text
        else:
            # 标准模式下必须选择Episode
            episode_id = self.cmb_cut_episode.currentText().strip()

        # 创建Cut
        success, result = self.project_manager.create_cut(cut_num, episode_id)

        if success:
            if show_error:  # 单个创建时刷新
                self._refresh_all_views()
                self.statusbar.showMessage(
                    f"已创建 Cut: {result} (含 06_render 输出目录)", 3000
                )
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

        # 获取Episode ID
        episode_id = None
        if self.chk_no_episode.isChecked():
            # 单集模式下，检查是否选择了特殊Episode
            ep_text = self.cmb_cut_episode.currentText().strip()
            if ep_text and ep_text in self.project_config.get("episodes", {}):
                episode_id = ep_text
        else:
            # 标准模式下必须选择Episode
            episode_id = self.cmb_cut_episode.currentText().strip()
            if not episode_id:
                QMessageBox.warning(self, "错误", "批量创建需要先选择 Episode")
                return

        # 批量创建
        created_count = 0
        skipped_count = 0

        for i in range(start, end + 1):
            self.txt_cut.setText(str(i))
            success, _ = self.project_manager.create_cut(str(i), episode_id)
            if success:
                created_count += 1
            else:
                skipped_count += 1

        # 显示结果
        message = f"成功创建 {created_count} 个 Cut"
        if skipped_count > 0:
            message += f"，跳过 {skipped_count} 个已存在的 Cut"

        if created_count > 0 or skipped_count > 0:
            QMessageBox.information(self, "完成", message)
            self._refresh_all_views()

    # ========================== 素材导入 ========================== #

    def browse_material(self, material_type: str):
        """浏览选择素材"""
        if material_type in ["cell", "3dcg"]:
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(
                self, f"选择 {material_type.upper()} 文件夹", ""
            )
            if path:
                getattr(self, f"txt_{material_type}_path").setText(path)
        else:
            # 选择文件
            file_filter = {
                "bg": "图像文件 (*.psd *.png *.jpg *.jpeg *.tga *.tiff *.bmp *.exr *.dpx)",
                "timesheet": "CSV 文件 (*.csv)",
            }.get(material_type, "所有文件 (*.*)")

            file_path, _ = QFileDialog.getOpenFileName(
                self, f"选择 {material_type.upper()} 文件", "", file_filter
            )
            if file_path:
                getattr(self, f"txt_{material_type}_path").setText(file_path)

    def import_single(self):
        """导入单个选中的素材"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
            # 单集模式
            if self.cmb_target_episode.currentText():
                # 选择了特殊Episode
                target_ep = self.cmb_target_episode.currentText()
                target_cut = self.cmb_target_cut.currentText()
                if not target_cut:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                target = f"{target_ep}|{target_cut}"
            else:
                # 直接选择Cut
                target_cut = self.cmb_target_cut.currentText()
                if not target_cut:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                target = target_cut
        else:
            # 标准模式
            target_ep = self.cmb_target_episode.currentText()
            target_cut = self.cmb_target_cut.currentText()
            if not target_ep or not target_cut:
                QMessageBox.warning(self, "错误", "请选择目标 Episode 和 Cut")
                return
            target = f"{target_ep}|{target_cut}"

        # 收集要导入的素材
        imports = []
        material_types = ["bg", "cell", "3dcg", "timesheet"]
        for mt in material_types:
            path_widget = getattr(self, f"txt_{mt}_path")
            if path_widget.text():
                imports.append((mt, path_widget.text()))

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
            for mt, path in imports:
                getattr(self, f"txt_{mt}_path").clear()

            # 重置版本确认跳过设置（为下次导入准备）
            self.skip_version_confirmation = {
                "bg": False,
                "cell": False,
                "3dcg": False
            }

    def import_all(self):
        """批量导入所有已选择的素材"""
        self.import_single()

    def _import_material(self, material_type: str, source_path: str, target: str) -> bool:
        """执行素材导入（带版本管理）"""
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

            # 构建基础文件名（不含版本号）
            base_name = f"{proj_name}_{ep_part}{cut_id}"

            # 根据类型处理
            if material_type == "bg":
                bg_dir = vfx_base / cut_id / "bg"
                ensure_dir(bg_dir)

                # 获取版本号
                version = self.project_manager.get_next_version(bg_dir, base_name)

                # 确认版本号
                if not self.skip_version_confirmation["bg"] and bg_dir.exists() and any(bg_dir.iterdir()):
                    dialog = VersionConfirmDialog("BG", version, self)
                    if dialog.exec() == QDialog.Accepted:
                        version = dialog.get_version()
                        if dialog.should_skip_confirmation():
                            self.skip_version_confirmation["bg"] = True
                    else:
                        return False

                # 复制文件
                file_name = f"{base_name}_T{version}{src.suffix.lower()}"
                dst = bg_dir / file_name
                copy_file_safe(src, dst)

            elif material_type == "cell":
                cell_dir = vfx_base / cut_id / "cell"
                ensure_dir(cell_dir)

                # 获取版本号
                version = self.project_manager.get_next_version(cell_dir, base_name)

                # 确认版本号
                if not self.skip_version_confirmation["cell"] and cell_dir.exists() and any(cell_dir.iterdir()):
                    dialog = VersionConfirmDialog("Cell", version, self)
                    if dialog.exec() == QDialog.Accepted:
                        version = dialog.get_version()
                        if dialog.should_skip_confirmation():
                            self.skip_version_confirmation["cell"] = True
                    else:
                        return False

                # 复制文件夹
                folder_name = f"{base_name}_T{version}"
                dst_folder = cell_dir / folder_name
                if dst_folder.exists():
                    shutil.rmtree(dst_folder)
                shutil.copytree(src, dst_folder)

            elif material_type == "3dcg":
                ensure_dir(cg_base)
                cg_cut_dir = cg_base / cut_id
                ensure_dir(cg_cut_dir)

                # 3DCG直接复制，不需要版本管理
                for item in src.iterdir():
                    if item.is_file():
                        copy_file_safe(item, cg_cut_dir / item.name)
                    elif item.is_dir():
                        target_dir = cg_cut_dir / item.name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(item, target_dir)

            else:  # timesheet
                # Timesheet直接覆盖，不需要版本管理
                dst = vfx_base / "timesheets" / f"{cut_id}.csv"
                ensure_dir(dst.parent)
                copy_file_safe(src, dst)

            return True

        except Exception as e:
            print(f"导入失败 ({material_type}): {e}")
            return False

    def copy_aep_template(self):
        """复制AEP模板（带版本管理）"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
            # 单集模式
            if self.cmb_target_episode.currentText():
                # 选择了特殊Episode
                ep_id = self.cmb_target_episode.currentText()
                cut_id = self.cmb_target_cut.currentText()
                if not cut_id:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                cut_path = self.project_base / ep_id / "01_vfx" / cut_id
            else:
                # 直接选择Cut
                cut_id = self.cmb_target_cut.currentText()
                if not cut_id:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                cut_path = self.project_base / "01_vfx" / cut_id
                ep_id = None
        else:
            # 标准模式
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

        proj_name = self.project_base.name

        # 复制所有模板
        copied = 0
        for template in template_dir.glob("*.aep"):
            # 保留模板的原始文件名中的版本号或其他信息
            template_stem = template.stem

            # 构建新文件名
            if ep_id:
                ep_part = ep_id.upper()
                if '_v' in template_stem:
                    version_part = template_stem[template_stem.rfind('_v'):]
                    aep_name = f"{proj_name}_{ep_part}_{cut_id}{version_part}{template.suffix}"
                else:
                    aep_name = f"{proj_name}_{ep_part}_{cut_id}_v0{template.suffix}"
            else:
                if '_v' in template_stem:
                    version_part = template_stem[template_stem.rfind('_v'):]
                    aep_name = f"{proj_name}_{cut_id}{version_part}{template.suffix}"
                else:
                    aep_name = f"{proj_name}_{cut_id}_v0{template.suffix}"

            dst = cut_path / aep_name
            if copy_file_safe(template, dst):
                copied += 1

        QMessageBox.information(
            self, "成功", f"已复制 {copied} 个 AEP 模板到 Cut {cut_id}"
        )
        self._refresh_tree()

        # 如果在浏览器Tab，刷新文件列表
        if self.tabs.currentIndex() == 1 and self.current_cut_id == cut_id:
            self._load_cut_files(cut_id, ep_id)

    def batch_copy_aep_template(self):
        """批量复制AEP模板"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 检查模板目录
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists() or not list(template_dir.glob("*.aep")):
            QMessageBox.warning(
                self, "错误", "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件"
            )
            return

        # 显示批量复制对话框
        dialog = BatchAepDialog(self.project_config, self)
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            self._batch_copy_with_settings(settings)

    def _batch_copy_with_settings(self, settings: Dict):
        """根据设置批量复制"""
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        templates = list(template_dir.glob("*.aep"))
        proj_name = self.project_base.name

        # 收集要处理的Episode和Cut
        targets = []

        if settings["scope"] == 0:  # 所有
            # 处理无Episode模式的Cuts
            if self.project_config.get("no_episode", False):
                for cut_id in self.project_config.get("cuts", []):
                    targets.append((None, cut_id))

            # 处理所有Episodes
            for ep_id, cuts in self.project_config.get("episodes", {}).items():
                for cut_id in cuts:
                    targets.append((ep_id, cut_id))

        elif settings["scope"] >= 1:  # 指定Episode
            ep_id = settings["episode"]
            cuts = self.project_config["episodes"][ep_id]

            # 如果指定了Cut范围
            if settings["scope"] == 2:
                cut_from = settings["cut_from"]
                cut_to = settings["cut_to"]
                # 筛选在范围内的Cut
                filtered_cuts = []
                for cut in cuts:
                    try:
                        cut_num = int(cut)
                        if cut_from <= cut_num <= cut_to:
                            filtered_cuts.append(cut)
                    except:
                        continue
                cuts = filtered_cuts

            for cut_id in cuts:
                targets.append((ep_id, cut_id))

        # 执行复制
        success_count = 0
        skip_count = 0
        overwrite_count = 0

        for ep_id, cut_id in targets:
            # 确定Cut路径
            if ep_id:
                cut_path = self.project_base / ep_id / "01_vfx" / cut_id
            else:
                cut_path = self.project_base / "01_vfx" / cut_id

            if not cut_path.exists():
                continue

            # 检查是否要跳过已有AEP的Cut
            if settings["skip_existing"]:
                existing_aeps = list(cut_path.glob("*.aep"))
                if existing_aeps:
                    skip_count += len(existing_aeps)
                    continue

            cut_copied = 0
            for template in templates:
                # 保留模板的原始文件名中的版本号或其他信息
                template_stem = template.stem

                # 构建新文件名
                if ep_id:
                    ep_part = ep_id.upper()
                    if '_v' in template_stem:
                        version_part = template_stem[template_stem.rfind('_v'):]
                        aep_name = f"{proj_name}_{ep_part}_{cut_id}{version_part}{template.suffix}"
                    else:
                        aep_name = f"{proj_name}_{ep_part}_{cut_id}_v0{template.suffix}"
                else:
                    if '_v' in template_stem:
                        version_part = template_stem[template_stem.rfind('_v'):]
                        aep_name = f"{proj_name}_{cut_id}{version_part}{template.suffix}"
                    else:
                        aep_name = f"{proj_name}_{cut_id}_v0{template.suffix}"

                dst = cut_path / aep_name

                if dst.exists():
                    if settings["overwrite"]:
                        overwrite_count += 1
                    else:
                        skip_count += 1
                        continue

                if copy_file_safe(template, dst):
                    cut_copied += 1

            if cut_copied > 0:
                success_count += 1

        # 显示结果
        message_lines = [f"✅ 成功为 {success_count} 个 Cut 复制了模板"]
        if overwrite_count > 0:
            message_lines.append(f"🔄 覆盖了 {overwrite_count} 个文件")
        if skip_count > 0:
            message_lines.append(f"⏭️ 跳过了 {skip_count} 个文件")

        message = "\n".join(message_lines)

        QMessageBox.information(self, "批量复制完成", message)
        self._refresh_tree()

    # ========================== UI 更新 ========================== #

    def _on_project_changed(self):
        """项目变更时的处理"""
        if self.project_base and self.project_config:
            # 更新项目路径显示
            self.lbl_project_path.setText(str(self.project_base))
            self.lbl_project_path.setStyleSheet("color: #0D7ACC;")

            # 更新Episode模式
            no_episode = self.project_config.get("no_episode", False)
            self.chk_no_episode.setChecked(no_episode)

            # 刷新界面
            self._refresh_all_views()

            # 重置当前选择
            self.current_cut_id = None
            self.current_episode_id = None
            self.current_path = None

            # 清除搜索
            if self.txt_cut_search:
                self.txt_cut_search.clear()

            # 启用控件
            self._enable_controls(True)

            # 更新状态栏
            self.statusbar.showMessage(f"当前项目: {self.project_base.name}")
        else:
            # 清空项目状态
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
        # 检查单集模式下的限制
        if self.chk_no_episode.isChecked() and episode_type.lower() == "ep":
            self.btn_create_episode.setEnabled(False)
            self.btn_create_episode.setToolTip("单集模式下不能创建标准集数(ep)")
        else:
            self.btn_create_episode.setEnabled(True)
            self.btn_create_episode.setToolTip("")

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
        """Episode选择变化时更新Cut列表"""
        self.cmb_target_cut.clear()

        # 如果没有选择Episode或配置不存在，直接返回
        if not self.project_config or not episode or episode == "":
            # 如果是单集模式，加载所有cuts
            if self.project_config and self.project_config.get("no_episode", False):
                cuts = self.project_config.get("cuts", [])
                if cuts:
                    self.cmb_target_cut.addItems(sorted(cuts))
            return

        # 获取该Episode的所有Cuts
        cuts = self.project_config.get("episodes", {}).get(episode, [])
        if cuts:
            self.cmb_target_cut.addItems(sorted(cuts))

    def _toggle_episode_mode(self, state: int):
        """切换Episode模式"""
        no_episode = self.chk_no_episode.isChecked()

        # 更新Episode管理组的状态
        if no_episode:
            # 单集模式：只允许创建特殊类型的Episode
            self.episode_group.setEnabled(True)
            self.episode_group.setTitle("🎬 特殊 Episode 管理 (op/ed/pv等)")
            # 如果当前选择的是ep类型，切换到其他类型
            if self.cmb_episode_type.currentText().lower() == "ep":
                self.cmb_episode_type.setCurrentText("pv")
        else:
            # 标准模式：允许所有类型
            self.episode_group.setEnabled(True)
            self.episode_group.setTitle("🎬 Episode 管理")

        # 更新Cut Episode下拉框的显示
        self.cmb_cut_episode.setVisible(True)  # 始终显示
        if no_episode:
            self.cmb_cut_episode.setPlaceholderText("选择特殊 Episode (可选)")
        else:
            self.cmb_cut_episode.setPlaceholderText("选择 Episode")

        # 更新导入面板的Episode显示
        self.cmb_target_episode.setVisible(True)  # 始终显示
        self.lbl_target_episode.setVisible(True)
        if no_episode:
            self.lbl_target_episode.setText("特殊 Ep:")
        else:
            self.lbl_target_episode.setText("Episode:")

        # 更新配置
        if self.project_config:
            self.project_config["no_episode"] = no_episode
            self.project_manager.project_config = self.project_config
            self.project_manager.save_config()
            self._update_import_combos()
            self._update_cut_episode_combo()

    def _enable_controls(self, enabled: bool):
        """启用/禁用控件"""
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
            self.btn_batch_copy_aep,
            self.cmb_target_episode,
            self.cmb_target_cut,
            self.txt_bg_path,
            self.txt_cell_path,
            self.txt_3dcg_path,
            self.txt_timesheet_path,
        ]

        for control in operation_controls:
            control.setEnabled(enabled)

        # 如果启用，还需要根据当前状态调整某些控件
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
            # 单集模式
            # 添加特殊Episodes（如果有）
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                self.cmb_target_episode.setCurrentIndex(-1)

            # 添加所有Cuts（包括根目录下的）
            cuts = self.project_config.get("cuts", [])
            if cuts:
                self.cmb_target_cut.addItems(sorted(cuts))
        else:
            # 标准模式
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                self.cmb_target_episode.setCurrentIndex(-1)

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
            # 单集模式统计
            cuts = self.project_config.get("cuts", [])
            stats_lines.append(f"模式: 单集/PV 模式")
            stats_lines.append(f"根目录 Cut 数: {len(cuts)}")

            # 特殊Episode统计
            episodes = self.project_config.get("episodes", {})
            if episodes:
                special_count = sum(len(cuts) for cuts in episodes.values())
                stats_lines.append(f"特殊 Episode 数: {len(episodes)}")
                stats_lines.append(f"特殊 Episode 内 Cut 数: {special_count}")
                stats_lines.append("")
                stats_lines.append("特殊 Episode 详情:")
                for ep_id in sorted(episodes.keys()):
                    cut_count = len(episodes[ep_id])
                    if cut_count > 0:
                        stats_lines.append(f"  {ep_id}: {cut_count} cuts")
                    else:
                        stats_lines.append(f"  {ep_id}: (空)")
        else:
            # 标准模式统计
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

    def _update_browser_tree(self):
        """更新浏览器的Episode/Cut树"""
        self.browser_tree.clear()

        if not self.project_config:
            return

        # 单集模式
        if self.project_config.get("no_episode", False):
            # 添加根目录下的Cuts
            cuts = self.project_config.get("cuts", [])
            if cuts:
                root_item = QTreeWidgetItem(["根目录 Cuts"])
                root_item.setData(0, Qt.UserRole, {"type": "root"})
                self.browser_tree.addTopLevelItem(root_item)

                for cut_id in sorted(cuts):
                    item = QTreeWidgetItem([cut_id])
                    item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": None})
                    root_item.addChild(item)

                root_item.setExpanded(True)

            # 添加特殊Episodes
            episodes = self.project_config.get("episodes", {})
            if episodes:
                for ep_id in sorted(episodes.keys()):
                    ep_item = QTreeWidgetItem([f"📁 {ep_id}"])
                    ep_item.setData(0, Qt.UserRole, {"episode": ep_id})
                    self.browser_tree.addTopLevelItem(ep_item)

                    # 添加该Episode下的Cuts
                    for cut_id in sorted(episodes[ep_id]):
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

                # 添加该Episode下的Cuts
                for cut_id in sorted(episodes[ep_id]):
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

        # 添加所有Episodes（无论是否单集模式）
        episodes = self.project_config.get("episodes", {})
        if episodes:
            self.cmb_cut_episode.addItems(sorted(episodes.keys()))
            self.cmb_cut_episode.setCurrentIndex(-1)

    def _on_browser_tree_clicked(self, item: QTreeWidgetItem):
        """处理浏览器树的点击事件"""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        # 如果点击的是Cut节点
        if "cut" in data and data["cut"]:
            self.current_cut_id = data["cut"]
            self.current_episode_id = data.get("episode")

            # 加载文件列表
            self._load_cut_files(self.current_cut_id, self.current_episode_id)

            # 更新路径显示
            self._update_current_path_label()
        else:
            # 点击的是Episode节点或根节点，清空文件列表
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
        path_str = str(path).replace("\\", "/")

        # 如果路径太长，显示缩略版本
        if len(path_str) > 100:
            relative_path = path.relative_to(self.project_base.parent)
            display_path = f".../{relative_path}"
        else:
            display_path = path_str

        # 更新标签
        self.lbl_current_cut.setText(f"📁 {tab_name}: {display_path}")
        self.lbl_current_cut.setToolTip(path_str)

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
        act_open.triggered.connect(lambda: open_in_file_manager(self.current_path))
        menu.addAction(act_open)

        # 显示菜单
        menu.exec_(self.lbl_current_cut.mapToGlobal(position))

    def _load_cut_files(self, cut_id: str, episode_id: Optional[str] = None):
        """加载指定Cut的文件列表"""
        self._clear_file_lists()

        if not self.project_base:
            return

        # 确定各路径
        if episode_id:
            vfx_path = self.project_base / episode_id / "01_vfx" / cut_id
            render_path = self.project_base / "06_render" / episode_id / cut_id
            cg_path = self.project_base / episode_id / "02_3dcg" / cut_id
        else:
            vfx_path = self.project_base / "01_vfx" / cut_id
            render_path = self.project_base / "06_render" / cut_id
            cg_path = self.project_base / "02_3dcg" / cut_id

        # 加载各种文件类型
        self._load_vfx_files(vfx_path)
        self._load_cell_files(vfx_path / "cell")
        self._load_bg_files(vfx_path / "bg")
        self._load_render_files(render_path)
        self._load_cg_files(cg_path)

        # 更新Tab标题显示文件数量
        self._update_file_tab_titles()

    def _load_vfx_files(self, vfx_path: Path):
        """加载VFX文件"""
        if vfx_path.exists():
            self.vfx_list.load_files(vfx_path, "*.aep")

        if self.vfx_list.count() == 0:
            item = QListWidgetItem("(没有 AEP 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.vfx_list.addItem(item)

    def _load_cell_files(self, cell_path: Path):
        """加载Cell文件 - 仅显示带版本号的文件夹"""
        if not cell_path.exists():
            return

        # 收集所有Cell文件夹
        folders = []
        for folder in cell_path.iterdir():
            if folder.is_dir():
                file_info = get_file_info(folder)
                # 只添加带版本号的文件夹
                if file_info.version is not None:
                    folders.append(file_info)

        # 按修改时间排序（最新的在前）
        folders.sort(key=lambda f: f.modified_time, reverse=True)

        # 添加到列表
        for folder_info in folders:
            self.cell_list.add_file_item(folder_info)

        if self.cell_list.count() == 0:
            item = QListWidgetItem("(没有 Cell 文件夹)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.cell_list.addItem(item)

    def _load_bg_files(self, bg_path: Path):
        """加载BG文件"""
        if not bg_path.exists():
            return

        # 收集所有BG文件
        files = []
        for file in bg_path.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(get_file_info(file))

        # 按修改时间排序（最新的在前）
        files.sort(key=lambda f: f.modified_time, reverse=True)

        # 添加到列表
        for file_info in files:
            self.bg_list.add_file_item(file_info)

        if self.bg_list.count() == 0:
            item = QListWidgetItem("(没有 BG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.bg_list.addItem(item)

    def _load_render_files(self, render_path: Path):
        """加载渲染文件"""
        if not render_path.exists():
            # 如果render目录都不存在，显示未渲染
            no_render_info = FileInfo(
                path=render_path,
                name="未渲染",
                modified_time=datetime.now(),
                size=0,
                is_folder=False,
                is_no_render=True
            )
            self.render_list.add_file_item(no_render_info)
            return

        render_items = []
        has_any_render = False

        # PNG序列文件夹
        png_path = render_path / "png_seq"
        if png_path.exists() and any(png_path.glob("*.png")):
            # 有PNG序列
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

        # 添加到列表
        for item_info in render_items:
            self.render_list.add_file_item(item_info)

    def _load_cg_files(self, cg_path: Path):
        """加载3DCG文件 - 递归加载所有文件"""
        if not cg_path.exists():
            return

        # 递归加载所有文件
        files = []
        for item in cg_path.rglob("*"):
            if item.is_file():
                files.append(get_file_info(item))

        # 按修改时间排序（最新的在前）
        files.sort(key=lambda f: f.modified_time, reverse=True)

        # 添加到列表
        for file_info in files:
            self.cg_list.add_file_item(file_info)

        if self.cg_list.count() == 0:
            item = QListWidgetItem("(没有 3DCG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.cg_list.addItem(item)

    def _update_file_tab_titles(self):
        """更新文件Tab的标题，显示文件数量"""
        tab_info = [
            (0, "VFX", self.vfx_list),
            (1, "Cell", self.cell_list),
            (2, "BG", self.bg_list),
            (3, "Render", self.render_list),
            (4, "3DCG", self.cg_list),
        ]

        for index, name, list_widget in tab_info:
            count = list_widget.count()
            # 检查是否有实际文件（排除"没有文件"提示项）
            if count > 0 and list_widget.item(0).data(Qt.UserRole) is not None:
                self.file_tabs.setTabText(index, f"{name} ({count})")
            else:
                self.file_tabs.setTabText(index, name)

    def _clear_file_lists(self):
        """清空所有文件列表"""
        self.vfx_list.clear()
        self.cell_list.clear()
        self.bg_list.clear()
        self.render_list.clear()
        self.cg_list.clear()

        # 重置Tab标题
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

        # 检查是否是视频文件
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            # 使用默认播放器播放视频
            self._play_video(path)
        else:
            # 其他文件在文件管理器中打开
            open_in_file_manager(path)

    def _play_video(self, video_path: Path):
        """使用默认播放器播放视频"""
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(str(video_path))
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(video_path)])
            else:  # Linux
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

        # 递归搜索并显示匹配的项目
        def search_items(item: QTreeWidgetItem):
            nonlocal match_count, first_match
            item_text = item.text(0).lower()

            # 智能匹配
            has_match = False
            if search_text in item_text:
                has_match = True
            elif search_text.isdigit():
                # 数字智能匹配
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
                item.setForeground(0, QBrush(QColor("#4CAF50")))
                item.setFont(0, QFont("MiSans", -1, QFont.Bold))
                match_count += 1
                if first_match is None:
                    first_match = item
            else:
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
            self.btn_new_project.setToolTip(f"将创建到: {default_path}")
            self.statusbar.showMessage(f"默认项目路径: {default_path}")
        else:
            self.btn_new_project.setToolTip("点击后选择创建位置")
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

        for path in recent_projects[:10]:
            if Path(path).exists():
                action = self.recent_menu.addAction(Path(path).name)
                action.setShortcut("Ctrl+R")
                action.setToolTip(path)
                action.triggered.connect(
                    lambda checked, p=path: self.open_recent_project(p)
                )

    def open_recent_project(self, path: str):
        """打开最近项目"""
        if Path(path).exists():
            self._load_project(path)
        else:
            QMessageBox.warning(
                self, "错误", f"项目路径不存在：\n{path}"
            )
            self._remove_from_recent(path)

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
        """在文件管理器中打开项目根目录"""
        if self.project_base:
            open_in_file_manager(self.project_base)

    def show_help(self):
        """显示帮助信息"""
        help_text = f"""
CX Project Manager 使用说明
========================

版本: {version_info.get("version", "2.1")} {version_info.get("build-version", "")}

## 项目模式
- **标准模式**: 支持创建多个Episode（ep01, ep02等），每个Episode下可创建多个Cut
- **单集/PV模式**: 根目录下直接创建Cut，但支持创建特殊类型的Episode（op/ed/pv等）

## 单集模式特点
- 不能创建标准集数（ep类型）
- 可以创建特殊类型：op, ed, pv, sp, ova, cm, sv, ex, nc
- 特殊Episode下也可以包含Cut
- 适合制作单集动画、PV、广告等项目

## 版本管理
- BG和Cell导入时自动管理版本号（T1, T2, T3...）
- AEP文件版本显示：V0显示"T摄"，V1以后显示"本摄Vx"
- 可设置自动使用推荐版本号，跳过确认对话框
- 文件按修改时间排序，最新的显示在最前面

## 文件浏览
- 完整文件名加粗显示在图标右侧
- 显示文件修改时间和大小（弱化显示）
- 所有文件类型都有专门的图标
- Cell仅显示带版本号的文件夹
- 3DCG Tab会递归显示所有文件
- PNG序列显示第一张图片的缩略图
- 没有渲染时显示"未渲染"状态
- 支持TGA图片格式
- 双击视频文件直接播放
- 双击其他文件在资源管理器中打开

## 快捷键
- Ctrl+N: 新建项目
- Ctrl+O: 打开项目
- Ctrl+F: 搜索Cut
- F5: 刷新目录树
- Ctrl+Q: 退出

## 素材导入
- BG: 导入单个背景图像文件（支持psd, png, jpg, jpeg, tga, tiff, bmp, exr, dpx）
- Cell: 导入包含分层素材的文件夹
- 3DCG: 导入3D素材文件夹
- Timesheet: 导入时间表CSV文件

## 批量操作
- 批量创建Episode（仅ep类型支持）
- 批量创建Cut
- 批量复制AEP模板

## 项目结构
项目创建后会自动生成标准化的目录结构，包括：
- 00_reference_project: 参考资料
- 01_vfx: VFX制作文件
- 02_3dcg: 3D制作文件
- 06_render: 渲染输出
- 07_master_assets: 共用素材
- 08_tools: 工具脚本
- 98_tmp: 临时文件
- 99_other: 其他文件

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

版本: {version_info.get("version", "2.1")} {version_info.get("build-version", "")}
作者: {version_info.get("author", "千石まよひ")}
邮箱: {version_info.get("email", "tammcx@gmail.com")}
GitHub: https://github.com/ChenxingM/CXProjectManager

{version_info.get("description", "动画项目管理工具，专为动画制作流程优化设计。")}

如有问题或建议，欢迎在GitHub提交Issue。"""

        QMessageBox.about(self, "关于", about_text)

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._save_app_settings()
        event.accept()


# ================================ 项目浏览器组件 ================================ #

class ProjectBrowser(QWidget):
    """独立的项目浏览器组件，可以在其他程序中导入使用"""

    def __init__(self, project_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.project_manager = ProjectManager()
        self.project_base: Optional[Path] = None
        self.project_config: Optional[Dict] = None

        self._setup_ui()
        self.setStyleSheet(QSS_THEME)

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
        self.file_list = DetailedFileListWidget()

        splitter.addWidget(self.tree)
        splitter.addWidget(self.file_list)
        layout.addWidget(splitter)

    def load_project(self, project_path: str) -> bool:
        """加载项目"""
        path = Path(project_path)

        if self.project_manager.load_project(path):
            self.project_base = self.project_manager.project_base
            self.project_config = self.project_manager.project_config
            self._update_view()
            return True
        return False

    def _update_view(self):
        """更新视图"""
        if not self.project_config:
            return

        # 更新统计
        stats = f"项目: {self.project_config.get('project_name', 'Unknown')}\n"

        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            stats += f"模式: 单集/PV模式\n"
            stats += f"根目录 Cut 数: {len(cuts)}\n"

            # 特殊Episode统计
            episodes = self.project_config.get("episodes", {})
            if episodes:
                stats += f"特殊 Episode 数: {len(episodes)}"
        else:
            episodes = self.project_config.get("episodes", {})
            total_cuts = sum(len(cuts) for cuts in episodes.values())
            stats += f"Episodes: {len(episodes)}, Cuts: {total_cuts}"

        self.txt_stats.setText(stats)

        # 更新树
        self._update_tree()

    def _update_tree(self):
        """更新树视图"""
        self.tree.clear()

        if not self.project_config:
            return

        if self.project_config.get("no_episode", False):
            # 单集模式：显示根目录Cuts和特殊Episodes
            cuts = self.project_config.get("cuts", [])
            if cuts:
                root_item = QTreeWidgetItem(["根目录 Cuts"])
                self.tree.addTopLevelItem(root_item)
                for cut_id in sorted(cuts):
                    QTreeWidgetItem(root_item, [cut_id])
                root_item.setExpanded(True)

            # 特殊Episodes
            episodes = self.project_config.get("episodes", {})
            for ep_id in sorted(episodes.keys()):
                ep_item = QTreeWidgetItem([ep_id])
                self.tree.addTopLevelItem(ep_item)
                for cut_id in sorted(episodes[ep_id]):
                    QTreeWidgetItem(ep_item, [cut_id])
                ep_item.setExpanded(True)
        else:
            # 标准模式
            episodes = self.project_config.get("episodes", {})
            for ep_id in sorted(episodes.keys()):
                ep_item = QTreeWidgetItem([ep_id])
                self.tree.addTopLevelItem(ep_item)
                for cut_id in sorted(episodes[ep_id]):
                    QTreeWidgetItem(ep_item, [cut_id])
                ep_item.setExpanded(True)

    def _on_tree_clicked(self, item: QTreeWidgetItem):
        """树节点点击事件"""
        pass


# ================================ 导出的组件 ================================ #

__all__ = [
    'CXProjectManager',
    'ProjectBrowser',
    'SearchLineEdit',
    'BatchAepDialog',
    'VersionConfirmDialog',
    'DetailedFileListWidget',
    'FileItemDelegate',
    'ProjectManager',
    'EpisodeType',
    'ProjectPaths',
    'MaterialType',
    'FileInfo'
]


# ================================ 主程序入口 ================================ #

def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("CX Project Manager")
    app.setOrganizationName("CXStudio")

    # 设置应用图标（可选）
    icon_path = Path("_imgs/app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = CXProjectManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()