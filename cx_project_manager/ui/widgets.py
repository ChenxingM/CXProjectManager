# -*- coding: utf-8 -*-
"""
自定义控件模块
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QFont, QIcon, QColor, QPainter, QPixmap, QFontMetrics
from PySide6.QtWidgets import (
    QLineEdit, QListWidget, QListWidgetItem, QStyledItemDelegate,
    QAbstractItemView, QStyle, QStyleOptionViewItem
)

from cx_project_manager.utils.constants import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, THREED_EXTENSIONS
from cx_project_manager.utils.models import FileInfo, ProjectPaths, ProjectInfo
from cx_project_manager.utils.utils import get_file_info, format_file_size


class SearchLineEdit(QLineEdit):
    """支持Esc键清除的搜索框"""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)


class FileItemDelegate(QStyledItemDelegate):
    """文件列表项委托，用于自定义绘制"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_size = 64
        self.padding = 8
        self.version_font = QFont("MiSans", 20, QFont.Bold)
        self.name_font = QFont("MiSans", 12, QFont.Bold)
        self.time_font = QFont("MiSans", 9)
        self.size_font = QFont("MiSans", 9)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

        file_info = index.data(Qt.UserRole + 1)
        if not file_info:
            super().paint(painter, option, index)
            painter.restore()
            return

        rect = option.rect

        # 背景
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor("#0D7ACC"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(rect, QColor("#3A3A3A"))

        # 图标
        icon = index.data(Qt.DecorationRole)
        if icon:
            icon_rect = QRect(rect.left() + self.padding, rect.top() + self.padding,
                              self.icon_size, self.icon_size)
            icon.paint(painter, icon_rect)

        # 文本区域
        text_left = rect.left() + self.icon_size + self.padding * 2
        text_width = rect.width() - self.icon_size - self.padding * 3

        if file_info.version is not None:
            text_width -= 80

        # 文件名
        painter.setFont(self.name_font)
        painter.setPen(QColor(
            "#FFFFFF") if file_info.is_reuse_cut else Qt.white if option.state & QStyle.State_Selected else QColor(
            "#FFFFFF"))
        name_rect = QRect(text_left, rect.top() + self.padding, text_width, 25)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, file_info.name)

        # 时间
        painter.setFont(self.time_font)
        painter.setPen(QColor("#E0E0E0") if option.state & QStyle.State_Selected else QColor("#808080"))
        time_text = file_info.modified_time.strftime("%Y-%m-%d %H:%M")
        time_rect = QRect(text_left, rect.top() + self.padding + 30, text_width, 20)
        painter.drawText(time_rect, Qt.AlignLeft | Qt.AlignVCenter, time_text)

        # 文件大小
        if not file_info.is_folder and file_info.size > 0:
            painter.setFont(self.size_font)
            size_text = format_file_size(file_info.size)
            size_rect = QRect(text_left, rect.top() + self.padding + 48, text_width, 20)
            painter.drawText(size_rect, Qt.AlignLeft | Qt.AlignVCenter, size_text)

        # 版本号
        if file_info.version is not None and file_info.version_str:
            painter.setFont(self.version_font)
            color = QColor("#FF9800") if file_info.is_aep and file_info.version == 0 else QColor("#4CAF50")
            painter.setPen(color)

            fm = QFontMetrics(self.version_font)
            text_width = fm.horizontalAdvance(file_info.version_str)
            version_rect = QRect(rect.right() - text_width - 15, rect.top() + rect.height() // 2 - 20,
                                 text_width + 10, 40)
            painter.drawText(version_rect, Qt.AlignCenter, file_info.version_str)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
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
        self._load_icons()

    def _load_icons(self):
        """加载图标"""
        icon_base = Path("cx_project_manager/ui/_icons")
        icon_types = [
            'aep', 'psd', 'folder', 'image', 'video', 'file', 'clip',
            'maya', '3dsmax', 'blender', 'c4d', 'fbx', 'pld', '3d',
            'png_seq', 'no_render'
        ]

        self.icons = {}
        for icon_type in icon_types:
            icon_path = icon_base / f"{icon_type}_icon.png"
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    self.icons[icon_type] = icon

    def add_file_item(self, file_info: FileInfo):
        """添加文件项"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, str(file_info.path))
        item.setData(Qt.UserRole + 1, file_info)

        icon = self._get_file_icon(file_info)
        if icon:
            item.setIcon(icon)
        else:
            item.setIcon(self.icons.get('file', QIcon()))

        self.addItem(item)

    def load_files(self, directory: Path, pattern: str = "*", expand_folders: bool = False):
        """加载目录中的文件"""
        self.clear()

        if not directory.exists():
            return

        files = []
        for file_path in directory.glob(pattern):
            if expand_folders and file_path.is_dir():
                for sub_file in file_path.rglob("*"):
                    if sub_file.is_file():
                        files.append(get_file_info(sub_file))
            else:
                files.append(get_file_info(file_path))

        files.sort(key=lambda f: f.modified_time, reverse=True)

        for file_info in files:
            self.add_file_item(file_info)

    def _get_file_icon(self, file_info: FileInfo) -> Optional[QIcon]:
        """获取文件图标（支持自定义缩略图）"""
        if file_info.is_no_render:
            return self.icons.get('no_render')

        # 优先使用自定义缩略图
        if hasattr(file_info, 'thumbnail_path') and file_info.thumbnail_path:
            try:
                pixmap = QPixmap(str(file_info.thumbnail_path))
                if not pixmap.isNull():
                    # 缩放到合适的尺寸，保持纵横比
                    scaled_pixmap = pixmap.scaled(
                        64, 64,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    return QIcon(scaled_pixmap)
            except Exception as e:
                print(f"加载缩略图失败: {e}")
                # 如果加载失败，继续使用默认图标

        if file_info.is_folder:
            if file_info.is_png_seq and file_info.first_png:
                try:
                    pixmap = QPixmap(str(file_info.first_png))
                    if not pixmap.isNull():
                        return QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                except:
                    pass
                return self.icons.get('png_seq', self.icons.get('folder'))
            return self.icons.get('folder')

        ext = file_info.path.suffix.lower()

        # 特定文件类型
        ext_to_icon = {
            '.aep': 'aep',
            '.psd': 'psd',
            '.clip': 'clip',
            '.ma': 'maya', '.mb': 'maya',
            '.max': '3dsmax', '.3ds': '3dsmax',
            '.blend': 'blender',
            '.c4d': 'c4d',
            '.pld': 'pld'
        }

        if ext in ext_to_icon:
            return self.icons.get(ext_to_icon[ext], self.icons.get('3d' if ext in THREED_EXTENSIONS else 'file'))

        if ext in ['.fbx', '.obj', '.dae', '.abc', '.usd', '.usda', '.usdc']:
            return self.icons.get('fbx', self.icons.get('3d'))

        if ext in THREED_EXTENSIONS:
            return self.icons.get('3d')

        if ext in IMAGE_EXTENSIONS:
            try:
                pixmap = QPixmap(str(file_info.path))
                if not pixmap.isNull():
                    return QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except:
                pass
            return self.icons.get('image')

        if ext in VIDEO_EXTENSIONS:
            # 对于视频文件，如果有缩略图，已经在上面处理了
            return self.icons.get('video')

        return self.icons.get('file')