from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QWidget, QFrame, QPushButton, QScrollArea, QGroupBox,
                               QGridLayout, QTabWidget, QTreeWidget, QTreeWidgetItem,
                               QHeaderView, QAbstractItemView, QProgressDialog, QApplication,
                               QCheckBox, QMessageBox)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QTimer, QPoint
from PySide6.QtGui import QPainter, QColor, QBrush, QPixmap, QIcon, QFont
import os
from pathlib import Path
import subprocess
import platform


# 主题颜色常量
THEME_COLORS = {
    # 背景色系
    'bg_dark': '#1a1a1a',
    'bg_medium': '#2a2a2a',
    'bg_light': '#3a3a3a',
    'bg_lighter': '#4a4a4a',
    'bg_lightest': '#5a5a5a',
    'bg_disabled': '#6a6a6a',

    # 主要颜色
    'primary_blue': '#4FC3F7',
    'primary_blue_light': '#29B6F6',
    'text_white': '#ffffff',
    'text_gray': '#999',
    'text_light_gray': '#ccc',

    # 状态颜色
    'success_green': '#66BB6A',
    'version_green': '#52F262',
    'warning_orange': '#FFB74D',
    'error_red': '#ff6b6b',
    'old_orange': '#FF7043',
    'critical_red': '#EF5350',
    'purple': '#AB47BC',

    # 透明背景
    'transparent': 'transparent',
    'semi_transparent_dark': 'rgba(26, 26, 26, 240)'
}

# UI 常量
UI_CONSTANTS = {
    'thumbnail_base_size': 120,
    'thumbnail_scale_factor': 1.1,
    'window_width_scale': 1.15,
    'window_height_margin': 150,
    'hover_delay_ms': 300,
    'thread_start_delay_ms': 100,
    'dialog_min_width': 1200,
    'dialog_min_height': 800,
    'progress_dialog_width': 400,
    'progress_dialog_height': 120,
    'close_button_width': 120,
    'close_button_height': 35,
    'size_warning_threshold_mb': 1000,
    'size_critical_threshold_mb': 5000,
    'bytes_per_kb': 1024,
    'bytes_per_mb': 1024 * 1024,
    'bytes_per_gb': 1024 * 1024 * 1024
}


# ======================== Utility Classes ========================

class FileUtils:
    """文件操作工具类 - 提取公共文件查找逻辑"""

    @staticmethod
    def find_latest_file(search_path: Path, file_patterns: list) -> dict:
        """查找最新的文件（通用方法）"""
        if not search_path.exists():
            return None

        files = []
        for pattern in file_patterns:
            files.extend(search_path.glob(pattern))

        if not files:
            return None

        # 按修改时间排序，取最新的
        latest_file = max(files, key=lambda f: f.stat().st_mtime)

        # 提取版本信息
        from cx_project_manager.utils.utils import extract_version_string_from_filename
        version_str = extract_version_string_from_filename(latest_file.stem)
        if not version_str:
            version_str = "v0"

        return {
            'path': latest_file,
            'version': version_str
        }

    @staticmethod
    def find_latest_aep(vfx_path: Path) -> dict:
        """查找最新的AEP文件"""
        return FileUtils.find_latest_file(vfx_path, ["*.aep"])

    @staticmethod
    def find_latest_mov(render_path: Path) -> dict:
        """查找最新的MOV文件"""
        video_patterns = ["*.mov", "*.mp4", "*.avi", "*.mkv"]
        return FileUtils.find_latest_file(render_path, video_patterns)

    @staticmethod
    def find_thumbnail(project_base: Path, cut_id: str, episode_id: str) -> Path:
        """查找缩略图（第一帧）"""
        if episode_id:
            still_path = project_base / "05_stills" / episode_id
        else:
            still_path = project_base / "05_stills"

        if not still_path.exists():
            return None

        # 查找第一帧缩略图 (格式: "014+still_F0001.jpg")
        first_frame_pattern = f"{cut_id}+still_F*.jpg"
        thumbnails = list(still_path.glob(first_frame_pattern))

        if thumbnails:
            return thumbnails[0]

        return None

    @staticmethod
    def format_file_info_html(file_path: Path, file_size_func) -> str:
        """格式化文件信息为HTML字符串，高亮版本号"""
        if not file_path:
            return f"<span style='color: {THEME_COLORS['error_red']};'>无</span>"

        filename = file_path.name
        # 提取版本信息
        from cx_project_manager.utils.utils import extract_version_string_from_filename
        version_str = extract_version_string_from_filename(file_path.stem)
        file_size = file_size_func(file_path)

        # 高亮版本号
        highlighted_filename = filename
        if version_str and version_str != "v0" and version_str != "未知版本":
            import re
            version_pattern = re.compile(f"_{version_str[1:]}", re.IGNORECASE)  # 去掉v前缀查找
            highlighted_filename = version_pattern.sub(
                f"_<span style='color: {THEME_COLORS['success_green']}; font-weight: bold;'>{version_str[1:]}</span>",
                filename
            )

        result = highlighted_filename
        if file_size:
            result += f"<br><span style='color: {THEME_COLORS['text_gray']}; font-size: 10px;'>{file_size}</span>"

        return result


# ======================== Tooltip Components ========================

class CutTooltipWidget(QWidget):
    """Cut详情悬浮提示框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 缩略图尺寸
        self.thumbnail_size = int(UI_CONSTANTS['thumbnail_base_size'] * UI_CONSTANTS['thumbnail_scale_factor'])
        window_width = int(self.thumbnail_size * UI_CONSTANTS['window_width_scale'])
        # 高度根据内容调整
        window_height = self.thumbnail_size + UI_CONSTANTS['window_height_margin']
        self.setFixedSize(window_width, window_height)

        # 使用全局版本映射器
        from cx_project_manager.utils.version_mapper import get_version_label_global
        self.get_version_label = get_version_label_global

        # 设置布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 缩略图标签
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        self.thumbnail_label.setStyleSheet(f"""
            QLabel {{
                background-color: {THEME_COLORS['bg_light']};
                border: 2px solid {THEME_COLORS['bg_lighter']};
                border-radius: 8px;
                color: {THEME_COLORS['text_gray']};
            }}
        """)
        layout.addWidget(self.thumbnail_label)

        # 信息标签
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"""
            QLabel {{
                background-color: {THEME_COLORS['bg_medium']};
                border: 1px solid {THEME_COLORS['bg_lighter']};
                border-radius: 6px;
                padding: 6px;
                color: {THEME_COLORS['text_white']};
                font-family: "MiSans", "Microsoft YaHei", sans-serif;
                font-size: 11px;
                line-height: 1.2;
            }}
        """)
        layout.addWidget(self.info_label)

        # 设置整体样式
        self.setStyleSheet(f"""
            CutTooltipWidget {{
                background-color: {THEME_COLORS['semi_transparent_dark']};
                border: 2px solid {THEME_COLORS['primary_blue']};
                border-radius: 10px;
            }}
        """)

    def show_cut_info(self, cut_data: dict, thumbnail_path: Path = None):
        """显示Cut信息"""
        cut_id = cut_data.get('cut_id', 'Unknown')
        episode_id = cut_data.get('episode_id', '')
        aep_path = cut_data.get('aep_path')
        mov_path = cut_data.get('mov_path')

        # 清除之前的缩略图
        self.thumbnail_label.clear()

        # 设置缩略图
        if thumbnail_path and Path(thumbnail_path).exists():
            # 强制重新加载图片，避免缓存问题
            pixmap = QPixmap()
            if pixmap.load(str(thumbnail_path)):
                # 缩放到新尺寸，保持宽高比
                scaled_pixmap = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbnail_label.setPixmap(scaled_pixmap)
                self.thumbnail_label.setText("")
            else:
                self.thumbnail_label.setText("加载失败")
        else:
            self.thumbnail_label.setText("无缩略图")

        # 获取最新版本标签
        latest_version = ""
        version_label = ""

        # 优先使用AEP版本，如果没有则使用MOV版本
        if aep_path:
            latest_version = self._extract_version_from_path(aep_path)
        elif mov_path:
            latest_version = self._extract_version_from_path(mov_path)

        if latest_version:
            version_label = self._get_version_label(latest_version)

        # 构建信息文本
        if version_label:
            info_text = f"<b style='color: {THEME_COLORS['primary_blue']};'>{cut_id}</b> <span style='color: {THEME_COLORS['version_green']}; font-size: 11px; background-color: {THEME_COLORS['bg_medium']}; padding: 2px 4px; border-radius: 3px;'>    {version_label}</span>"
        else:
            info_text = f"<b style='color: {THEME_COLORS['primary_blue']};'>{cut_id}</b>"

        if episode_id:
            info_text += f"<br><span style='color: {THEME_COLORS['text_gray']};'>Episode: {episode_id}</span>"

        # AEP信息
        aep_info_html = FileUtils.format_file_info_html(aep_path, self._get_file_size)
        info_text += f"<br><br>{aep_info_html}"

        # MOV信息
        mov_info_html = FileUtils.format_file_info_html(mov_path, self._get_file_size)
        info_text += f"<br>{mov_info_html}"

        self.info_label.setText(info_text)

        # 强制刷新widget
        self.update()
        QApplication.processEvents()

    def _extract_version_from_path(self, file_path):
        """从文件路径提取版本信息"""
        if not file_path:
            return "未知版本"

        from cx_project_manager.utils.utils import extract_version_string_from_filename
        stem = Path(file_path).stem
        version_str = extract_version_string_from_filename(stem)
        return version_str if version_str else "v0"

    def _get_file_size(self, file_path):
        """获取文件大小"""
        if not file_path or not Path(file_path).exists():
            return ""

        try:
            size_bytes = Path(file_path).stat().st_size
            if size_bytes < UI_CONSTANTS['bytes_per_kb']:
                return f"{size_bytes} B"
            elif size_bytes < UI_CONSTANTS['bytes_per_mb']:
                return f"{size_bytes / UI_CONSTANTS['bytes_per_kb']:.1f} KB"
            elif size_bytes < UI_CONSTANTS['bytes_per_gb']:
                return f"{size_bytes / UI_CONSTANTS['bytes_per_mb']:.1f} MB"
            else:
                return f"{size_bytes / UI_CONSTANTS['bytes_per_gb']:.1f} GB"
        except:
            return ""

    def _get_version_label(self, version_str: str) -> str:
        """根据版本号生成显示标签"""
        return self.get_version_label(version_str)


class CutTreeWidget(QTreeWidget):
    """自定义的Cut树形控件，支持悬浮提示"""

    item_hovered = Signal(QTreeWidgetItem, QPoint)
    mouse_left = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._on_hover_timeout)
        self.current_hover_item = None
        self.current_hover_pos = QPoint()
        self.hover_enabled = True  # 悬浮功能启用状态

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        super().mouseMoveEvent(event)

        # 如果悬浮功能被禁用，直接返回
        if not self.hover_enabled:
            return

        item = self.itemAt(event.pos())
        if item != self.current_hover_item:
            # 先清除之前的悬浮状态
            self._clear_hover()

            if item:
                # 检查是否是Cut项（有UserRole数据）
                cut_data = item.data(0, Qt.UserRole)
                if cut_data:
                    self.current_hover_item = item
                    self.current_hover_pos = event.globalPos()
                    self.hover_timer.start(UI_CONSTANTS['hover_delay_ms'])
                else:
                    # 如果是Episode项，发送信号隐藏tooltip
                    self.mouse_left.emit()
            else:
                # 鼠标移动到空白区域
                self.mouse_left.emit()

    def leaveEvent(self, event):
        """鼠标离开事件"""
        super().leaveEvent(event)
        self._clear_hover()
        self.mouse_left.emit()

    def _on_hover_timeout(self):
        """悬浮超时处理"""
        if self.current_hover_item:
            self.item_hovered.emit(self.current_hover_item, self.current_hover_pos)

    def _clear_hover(self):
        """清除悬浮状态"""
        self.hover_timer.stop()
        self.current_hover_item = None

    def set_hover_enabled(self, enabled: bool):
        """设置悬浮功能启用状态"""
        self.hover_enabled = enabled

        if not enabled:
            # 如果禁用悬浮，清除当前状态并发送隐藏信号
            self._clear_hover()
            self.mouse_left.emit()
        else:
            # 如果启用悬浮，确保状态正确重置
            self._clear_hover()


# ======================== Statistics Components ========================

class StatGroupBox(QGroupBox):
    """深色主题统计分组框"""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #4FC3F7;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
            }
        """)


class StatRow(QWidget):
    """统计行组件"""

    def __init__(self, label: str, value: str, value_color: str = None, parent=None):
        if value_color is None:
            value_color = THEME_COLORS['text_white']
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME_COLORS['transparent']};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            color: {THEME_COLORS['text_gray']};
            font-size: 14px;
            background-color: {THEME_COLORS['transparent']};
        """)

        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"""
            font-weight: bold;
            font-size: 15px;
            color: {value_color};
            background-color: {THEME_COLORS['transparent']};
        """)

        layout.addWidget(label_widget)
        layout.addStretch()
        layout.addWidget(value_widget)


class StorageBarWidget(QWidget):
    """深色主题存储空间可视化条形图"""

    def __init__(self, latest_mb: float, old_mb: float, total_mb: float, parent=None):
        super().__init__(parent)
        self.latest_mb = latest_mb
        self.old_mb = old_mb
        self.total_mb = max(total_mb, 0.1)
        self.setFixedHeight(25)
        self.setStyleSheet(f"background-color: {THEME_COLORS['transparent']};")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width() - 30  # 留出边距
        height = self.height()
        x_offset = 15

        # 计算比例
        latest_percent = (self.latest_mb / self.total_mb)
        old_percent = (self.old_mb / self.total_mb)

        # 背景
        painter.fillRect(x_offset, 0, width, height, QColor(THEME_COLORS['bg_dark']))

        # 最新版本部分（蓝色）
        latest_width = int(width * latest_percent)
        painter.fillRect(x_offset, 0, latest_width, height, QColor(THEME_COLORS['primary_blue']))

        # 旧版本部分（橙色）
        old_width = int(width * old_percent)
        painter.fillRect(x_offset + latest_width, 0, old_width, height, QColor(THEME_COLORS['old_orange']))

        # 绘制文字（如果空间足够）
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)

        if latest_width > 40:
            painter.drawText(x_offset, 0, latest_width, height,
                             Qt.AlignCenter, f"{self.latest_mb:.0f}MB")

        if old_width > 40:
            painter.drawText(x_offset + latest_width, 0, old_width, height,
                             Qt.AlignCenter, f"{self.old_mb:.0f}MB")


# ======================== Main Dialog ========================

class ProjectStatisticsDialog(QDialog):
    """项目综合统计对话框 - Tab布局"""

    def __init__(self, project_config: dict, version_stats: dict, project_base: Path, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.version_stats = version_stats
        self.project_base = project_base
        self.setWindowTitle("项目统计")
        self.setMinimumSize(UI_CONSTANTS['dialog_min_width'], UI_CONSTANTS['dialog_min_height'])
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME_COLORS['bg_dark']};
            }}
            QLabel {{
                font-family: "MiSans", "Microsoft YaHei", sans-serif;
                color: {THEME_COLORS['text_white']};
            }}
            QScrollArea {{
                background-color: {THEME_COLORS['transparent']};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {THEME_COLORS['bg_medium']};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {THEME_COLORS['bg_lighter']};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {THEME_COLORS['bg_lightest']};
            }}
        """)

        self.setup_ui()

        # 设置默认版本映射
        self._setup_default_version_mapping()

    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 创建Tab控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {THEME_COLORS['bg_light']};
                background-color: {THEME_COLORS['bg_dark']};
            }}
            QTabBar::tab {{
                background-color: {THEME_COLORS['bg_medium']};
                color: {THEME_COLORS['text_white']};
                padding: 10px 20px;
                margin-right: 2px;
                border: 1px solid {THEME_COLORS['bg_light']};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {THEME_COLORS['primary_blue']};
                color: {THEME_COLORS['bg_dark']};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                background-color: {THEME_COLORS['bg_light']};
            }}
        """)

        # Tab 1: 项目概览
        overview_widget = self.create_overview_tab()
        self.tab_widget.addTab(overview_widget, "📊 项目概览")

        # Tab 2: Cut详情
        cut_details_widget = self.create_cut_details_tab()
        self.tab_widget.addTab(cut_details_widget, "🎬 Cut详情")

        # 默认显示Cut详情Tab
        self.tab_widget.setCurrentIndex(1)

        main_layout.addWidget(self.tab_widget)

        # 底部按钮区域
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)

        # 显示项目总体积
        total_size_gb = self.calculate_project_size() / UI_CONSTANTS['bytes_per_kb']
        size_label = QLabel(f"项目总体积: {total_size_gb:.2f} GB")
        size_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #4FC3F7;
            background-color: transparent;
        """)

        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(UI_CONSTANTS['close_button_width'], UI_CONSTANTS['close_button_height'])
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4FC3F7;
                color: #1a1a1a;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #29B6F6;
            }
        """)
        close_btn.clicked.connect(self.accept)

        button_layout.addWidget(size_label)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

    def closeEvent(self, event):
        """对话框关闭事件"""
        # 清理加载线程
        if hasattr(self, 'loader_thread') and self.loader_thread.isRunning():
            self.loader_thread.terminate()
            self.loader_thread.wait()
            self.loader_thread.deleteLater()

        # 关闭进度对话框
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        # 隐藏tooltip
        if hasattr(self, 'tooltip_widget') and self.tooltip_widget:
            self.tooltip_widget.hide()
            self.tooltip_widget.deleteLater()
            self.tooltip_widget = None

        super().closeEvent(event)

    def create_overview_tab(self) -> QWidget:
        """创建项目概览Tab"""
        tab = QWidget()
        tab.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(tab)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)

        # 左侧：项目统计
        left_widget = self.create_project_stats_panel()
        layout.addWidget(left_widget, 1)

        # 右侧：版本统计
        right_widget = self.create_version_stats_panel()
        layout.addWidget(right_widget, 1)

        return tab

    def create_project_stats_panel(self) -> QWidget:
        """创建项目统计面板"""
        panel = QWidget()
        panel.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)

        # 项目信息
        info_group = StatGroupBox("📋 项目信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(5)

        info_layout.addWidget(StatRow("项目名称",
                                      self.project_config.get('project_name', 'Unknown'),
                                      THEME_COLORS['primary_blue']))
        info_layout.addWidget(StatRow("创建时间",
                                      self.project_config.get('created_time', 'Unknown')[:10]))
        info_layout.addWidget(StatRow("最后修改",
                                      self.project_config.get('last_modified', 'Unknown')[:10]))

        mode = "单集/PV 模式" if self.project_config.get("no_episode", False) else "Episode 模式"
        info_layout.addWidget(StatRow("项目模式", mode, THEME_COLORS['success_green']))

        layout.addWidget(info_group)

        # Episode统计
        episode_group = StatGroupBox("📺 Episode 统计")
        episode_layout = QVBoxLayout(episode_group)
        episode_layout.setSpacing(5)

        episodes = self.project_config.get("episodes", {})

        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            episode_layout.addWidget(StatRow("根目录 Cut 数", str(len(cuts))))

            if episodes:
                special_count = sum(len(cuts) for cuts in episodes.values())
                episode_layout.addWidget(StatRow("特殊 Episode 数", str(len(episodes)), THEME_COLORS['warning_orange']))
                episode_layout.addWidget(StatRow("特殊 Episode 内 Cut 数", str(special_count)))
        else:
            total_cuts = sum(len(cuts) for cuts in episodes.values())
            episode_layout.addWidget(StatRow("Episode 总数", str(len(episodes))))
            episode_layout.addWidget(StatRow("Cut 总数", str(total_cuts), THEME_COLORS['success_green']))

        layout.addWidget(episode_group)

        # 文件类型分布（移到左边）
        type_group = StatGroupBox("📁 文件类型分布")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(5)

        type_layout.addWidget(StatRow("AEP文件",
                                      str(self.version_stats['aep_count']),
                                      THEME_COLORS['primary_blue']))
        type_layout.addWidget(StatRow("BG文件",
                                      str(self.version_stats['bg_count']),
                                      THEME_COLORS['primary_blue']))
        type_layout.addWidget(StatRow("Cell文件夹",
                                      str(self.version_stats['cell_count']),
                                      THEME_COLORS['primary_blue']))

        layout.addWidget(type_group)

        # 兼用卡统计
        reuse_cuts = self.project_config.get("reuse_cuts", [])
        if reuse_cuts:
            reuse_group = StatGroupBox("♻️ 兼用卡统计")
            reuse_layout = QVBoxLayout(reuse_group)
            reuse_layout.setSpacing(5)

            total_reuse_cuts = sum(len(cut["cuts"]) for cut in reuse_cuts)
            reuse_layout.addWidget(StatRow("兼用卡数量", str(len(reuse_cuts)), THEME_COLORS['purple']))
            reuse_layout.addWidget(StatRow("兼用 Cut 总数", str(total_reuse_cuts)))

            layout.addWidget(reuse_group)

        # Episode详情（小于18集时显示，分3栏）
        if episodes and len(episodes) <= 18:
            detail_group = StatGroupBox("📄 Episode 详情")
            detail_widget = QWidget()
            detail_widget.setStyleSheet("background-color: transparent;")
            detail_grid = QGridLayout(detail_widget)
            detail_grid.setContentsMargins(15, 10, 15, 10)
            detail_grid.setSpacing(10)

            sorted_episodes = sorted(episodes.keys())
            items_per_column = 6  # 每栏6个，3栏共18个

            for idx, ep_id in enumerate(sorted_episodes):
                row = idx % items_per_column
                col = idx // items_per_column

                cut_count = len(episodes[ep_id])
                text = f"{ep_id}: {cut_count} cuts" if cut_count > 0 else f"{ep_id}: (空)"

                detail_label = QLabel(text)
                detail_label.setStyleSheet("""
                    color: #ccc; 
                    font-size: 13px;
                    background-color: transparent;
                """)

                detail_grid.addWidget(detail_label, row, col)

            detail_group_layout = QVBoxLayout(detail_group)
            detail_group_layout.addWidget(detail_widget)

            layout.addWidget(detail_group)

        layout.addStretch()

        return panel

    def create_version_stats_panel(self) -> QWidget:
        """创建版本统计面板"""
        panel = QWidget()
        panel.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)

        # 文件统计
        file_group = StatGroupBox("📊 文件版本统计")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(5)

        version_rate = int((self.version_stats['versioned_files'] /
                            max(self.version_stats['total_files'], 1)) * 100)

        file_layout.addWidget(StatRow("总文件数", str(self.version_stats['total_files'])))
        file_layout.addWidget(StatRow("版本化管理",
                                      f"{self.version_stats['versioned_files']} ({version_rate}%)",
                                      THEME_COLORS['primary_blue']))
        file_layout.addWidget(StatRow("最新版本",
                                      str(self.version_stats['latest_versions']),
                                      THEME_COLORS['success_green']))
        file_layout.addWidget(StatRow("历史版本",
                                      str(self.version_stats['old_versions']),
                                      THEME_COLORS['old_orange']))

        layout.addWidget(file_group)

        # 锁定状态
        lock_group = StatGroupBox("🔒 锁定状态")
        lock_layout = QVBoxLayout(lock_group)
        lock_layout.setSpacing(5)

        lock_rate = int((self.version_stats['locked_files'] /
                         max(self.version_stats['total_files'], 1)) * 100)

        lock_layout.addWidget(StatRow("锁定文件总数",
                                      f"{self.version_stats['locked_files']} ({lock_rate}%)"))
        lock_layout.addWidget(StatRow("锁定的最新版",
                                      str(self.version_stats['locked_latest']),
                                      THEME_COLORS['success_green']))
        lock_layout.addWidget(StatRow("锁定的旧版本",
                                      str(self.version_stats['locked_old']),
                                      THEME_COLORS['old_orange']))

        layout.addWidget(lock_group)

        # 存储空间
        storage_group = StatGroupBox("💾 存储空间")
        storage_layout = QVBoxLayout(storage_group)
        storage_layout.setSpacing(10)

        total_mb = self.version_stats['total_size_mb']
        color = THEME_COLORS['success_green']
        if total_mb > UI_CONSTANTS['size_warning_threshold_mb']:
            color = THEME_COLORS['old_orange']
        if total_mb > UI_CONSTANTS['size_critical_threshold_mb']:
            color = THEME_COLORS['critical_red']

        storage_layout.addWidget(StatRow("总占用", f"{total_mb:.1f} MB", color))

        # 存储条形图
        storage_bar = StorageBarWidget(
            self.version_stats['latest_size_mb'],
            self.version_stats['old_size_mb'],
            total_mb
        )
        storage_layout.addWidget(storage_bar)

        # 图例
        legend_widget = QWidget()
        legend_widget.setStyleSheet(f"background-color: {THEME_COLORS['transparent']};")
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setContentsMargins(15, 5, 15, 5)

        # 最新版本图例
        latest_icon = QLabel()
        latest_icon.setFixedSize(12, 12)
        latest_icon.setStyleSheet(f"background-color: {THEME_COLORS['primary_blue']}; border-radius: 2px;")
        latest_label = QLabel("最新版本")
        latest_label.setStyleSheet(f"color: {THEME_COLORS['text_gray']}; font-size: 12px; background-color: {THEME_COLORS['transparent']};")

        # 历史版本图例
        old_icon = QLabel()
        old_icon.setFixedSize(12, 12)
        old_icon.setStyleSheet(f"background-color: {THEME_COLORS['old_orange']}; border-radius: 2px;")
        old_label = QLabel("历史版本")
        old_label.setStyleSheet(f"color: {THEME_COLORS['text_gray']}; font-size: 12px; background-color: {THEME_COLORS['transparent']};")

        legend_layout.addWidget(latest_icon)
        legend_layout.addWidget(latest_label)
        legend_layout.addSpacing(20)
        legend_layout.addWidget(old_icon)
        legend_layout.addWidget(old_label)
        legend_layout.addStretch()

        storage_layout.addWidget(legend_widget)

        storage_layout.addWidget(StatRow("可释放空间",
                                         f"{self.version_stats['deletable_size_mb']:.1f} MB",
                                         THEME_COLORS['critical_red']))

        layout.addWidget(storage_group)

        layout.addStretch()

        return panel

    def calculate_project_size(self) -> float:
        """计算项目总大小（MB）"""
        if not hasattr(self.parent(), 'project_base') or not self.parent().project_base:
            return 0.0

        total_size = 0
        for root, dirs, files in os.walk(self.parent().project_base):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                except:
                    continue

        return total_size / UI_CONSTANTS['bytes_per_mb']  # 转换为MB

    def create_cut_details_tab(self) -> QWidget:
        """创建Cut详情Tab"""
        tab = QWidget()
        tab.setStyleSheet(f"background-color: {THEME_COLORS['transparent']};")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部控制栏
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(10, 10, 10, 5)

        # 悬浮预览开关
        self.hover_preview_checkbox = QCheckBox("启用悬浮预览")
        self.hover_preview_checkbox.setChecked(True)  # 默认启用
        self.hover_preview_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {THEME_COLORS['text_white']};
                font-size: 14px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {THEME_COLORS['bg_lighter']};
                border-radius: 3px;
                background-color: {THEME_COLORS['bg_medium']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME_COLORS['primary_blue']};
                border: 2px solid {THEME_COLORS['primary_blue']};
            }}
            QCheckBox::indicator:checked::after {{
                content: "✓";
                color: {THEME_COLORS['bg_dark']};
                font-weight: bold;
                font-size: 12px;
            }}
        """)
        self.hover_preview_checkbox.stateChanged.connect(self._on_hover_preview_toggled)

        control_layout.addWidget(self.hover_preview_checkbox)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 创建树形控件
        self.cut_tree = CutTreeWidget()
        self.cut_tree.setHeaderLabels(['Cut', 'AEP版本', 'MOV版本', 'AEP路径', 'MOV路径'])
        self.cut_tree.setAlternatingRowColors(True)
        self.cut_tree.setRootIsDecorated(True)
        self.cut_tree.setIndentation(20)
        self.cut_tree.itemDoubleClicked.connect(self._on_cut_item_double_clicked)

        # tooltip widget将根据需要动态创建
        self.tooltip_widget = None

        # 连接鼠标事件
        self.cut_tree.item_hovered.connect(self._on_item_hovered)
        self.cut_tree.mouse_left.connect(self._hide_tooltip)

        # 设置悬浮预览开关，与checkbox状态保持一致
        initial_hover_enabled = self.hover_preview_checkbox.isChecked()
        self.cut_tree.set_hover_enabled(initial_hover_enabled)

        # 设置列宽
        header = self.cut_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Cut列自适应
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # AEP版本列自适应
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # MOV版本列自适应
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # AEP路径列拉伸
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # MOV路径列拉伸

        # 设置样式
        self.cut_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {THEME_COLORS['bg_medium']};
                color: {THEME_COLORS['text_white']};
                border: 1px solid {THEME_COLORS['bg_light']};
                font-family: "MiSans", "Microsoft YaHei", sans-serif;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                height: 32px;
                padding: 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {THEME_COLORS['primary_blue']};
                color: {THEME_COLORS['bg_dark']};
            }}
            QTreeWidget::item:hover {{
                background-color: {THEME_COLORS['bg_disabled']};
            }}
            QHeaderView::section {{
                background-color: {THEME_COLORS['bg_light']};
                color: {THEME_COLORS['text_white']};
                padding: 8px;
                border: 1px solid {THEME_COLORS['bg_lighter']};
                font-weight: bold;
            }}
        """)

        layout.addWidget(self.cut_tree)

        # 填充cut数据
        self._populate_cut_data()

        return tab

    def _populate_cut_data(self):
        """填充Cut数据"""
        # 计算总数以决定是否显示进度条
        episodes = self.project_config.get("episodes", {})
        total_cuts = 0

        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            total_cuts += len(cuts)
            for ep_cuts in episodes.values():
                total_cuts += len(ep_cuts)
        else:
            for ep_cuts in episodes.values():
                total_cuts += len(ep_cuts)

        # 如果Cut数量较少，直接同步加载
        if total_cuts < 20:
            self._populate_cut_data_sync()
        else:
            self._populate_cut_data_async()

    def _populate_cut_data_sync(self):
        """同步填充Cut数据（适用于小项目）"""
        episodes = self.project_config.get("episodes", {})

        if self.project_config.get("no_episode", False):
            # 单集模式
            cuts = self.project_config.get("cuts", [])
            if cuts:
                root_item = QTreeWidgetItem(self.cut_tree, ["根目录", "", "", "", ""])
                root_item.setExpanded(True)
                for cut_id in cuts:
                    self._add_cut_item(root_item, cut_id, None)

            # 处理特殊episode
            for ep_id in episodes:
                ep_cuts = episodes[ep_id]
                if ep_cuts:
                    ep_item = QTreeWidgetItem(self.cut_tree, [ep_id, "", "", "", ""])
                    ep_item.setExpanded(True)
                    for cut_id in ep_cuts:
                        self._add_cut_item(ep_item, cut_id, ep_id)
        else:
            # Episode模式
            for ep_id in sorted(episodes.keys()):
                ep_cuts = episodes[ep_id]
                ep_item = QTreeWidgetItem(self.cut_tree, [ep_id, "", "", "", ""])
                ep_item.setExpanded(True)
                for cut_id in ep_cuts:
                    self._add_cut_item(ep_item, cut_id, ep_id)

    def _populate_cut_data_async(self):
        """异步填充Cut数据（适用于大项目）"""
        # 创建进度对话框
        self.progress_dialog = QProgressDialog("正在加载Cut数据...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("加载中...")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setFixedSize(UI_CONSTANTS['progress_dialog_width'], UI_CONSTANTS['progress_dialog_height'])

        # 强制立即显示
        self.progress_dialog.show()
        self.progress_dialog.raise_()
        self.progress_dialog.activateWindow()

        # 设置初始进度值
        self.progress_dialog.setValue(0)
        QApplication.processEvents()

        self.progress_dialog.setStyleSheet(f"""
            QProgressDialog {{
                background-color: {THEME_COLORS['bg_medium']};
                color: {THEME_COLORS['text_white']};
                border: 2px solid {THEME_COLORS['primary_blue']};
                border-radius: 8px;
            }}
            QLabel {{
                color: {THEME_COLORS['text_white']};
                font-size: 14px;
                font-weight: bold;
                background-color: {THEME_COLORS['transparent']};
                padding: 10px;
            }}
            QProgressBar {{
                background-color: {THEME_COLORS['bg_light']};
                border: 2px solid {THEME_COLORS['bg_lighter']};
                border-radius: 6px;
                text-align: center;
                color: {THEME_COLORS['text_white']};
                font-weight: bold;
                height: 25px;
            }}
            QProgressBar::chunk {{
                background-color: {THEME_COLORS['primary_blue']};
                border-radius: 4px;
                margin: 1px;
            }}
            QPushButton {{
                background-color: {THEME_COLORS['bg_light']};
                color: {THEME_COLORS['text_white']};
                border: 2px solid {THEME_COLORS['bg_lighter']};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {THEME_COLORS['bg_lighter']};
                border-color: {THEME_COLORS['primary_blue']};
            }}
            QPushButton:pressed {{
                background-color: {THEME_COLORS['primary_blue']};
                color: {THEME_COLORS['bg_dark']};
            }}
        """)

        # 创建episode根节点
        self.episode_items = {}
        episodes = self.project_config.get("episodes", {})

        if self.project_config.get("no_episode", False):
            # 单集模式
            cuts = self.project_config.get("cuts", [])
            if cuts:
                root_item = QTreeWidgetItem(self.cut_tree, ["根目录", "", "", "", ""])
                root_item.setExpanded(True)
                self.episode_items["root"] = root_item

            # 处理特殊episode
            for ep_id in episodes:
                ep_cuts = episodes[ep_id]
                if ep_cuts:
                    ep_item = QTreeWidgetItem(self.cut_tree, [ep_id, "", "", "", ""])
                    ep_item.setExpanded(True)
                    self.episode_items[ep_id] = ep_item
        else:
            # Episode模式
            for ep_id in sorted(episodes.keys()):
                ep_cuts = episodes[ep_id]
                ep_item = QTreeWidgetItem(self.cut_tree, [ep_id, "", "", "", ""])
                ep_item.setExpanded(True)
                self.episode_items[ep_id] = ep_item

        # 创建并启动加载线程
        self.loader_thread = CutDataLoader(self.project_config, self.project_base)
        self.loader_thread.progress_updated.connect(self.progress_dialog.setValue)
        self.loader_thread.status_updated.connect(self.progress_dialog.setLabelText)
        self.loader_thread.cut_item_ready.connect(self._add_cut_item_async)
        self.loader_thread.finished.connect(self._on_loading_finished)

        # 连接取消按钮
        self.progress_dialog.canceled.connect(self._cancel_loading)

        # 启动加载线程
        QTimer.singleShot(UI_CONSTANTS['thread_start_delay_ms'], self.loader_thread.start)

    def _add_cut_item_async(self, parent_key: str, cut_id: str, episode_id: str, aep_info: dict, mov_info: dict, thumbnail: Path):
        """异步添加Cut项"""
        parent_item = self.episode_items.get(parent_key)
        if not parent_item:
            return

        # 创建Cut项
        cut_item = QTreeWidgetItem(parent_item, [
            cut_id,
            aep_info['version'] if aep_info else "无",
            mov_info['version'] if mov_info else "无",
            str(aep_info['path']) if aep_info else "",
            str(mov_info['path']) if mov_info else ""
        ])

        # 不在列表中显示缩略图，缩略图仅用于悬浮提示

        # 存储文件路径信息供双击使用和悬浮提示
        cut_item.setData(0, Qt.UserRole, {
            'aep_path': aep_info['path'] if aep_info else None,
            'mov_path': mov_info['path'] if mov_info else None,
            'cut_id': cut_id,
            'episode_id': episode_id,
            'thumbnail_path': thumbnail
        })

    def _on_loading_finished(self):
        """加载完成"""
        self.progress_dialog.close()
        if hasattr(self, 'loader_thread'):
            self.loader_thread.deleteLater()

    def _cancel_loading(self):
        """取消加载"""
        if hasattr(self, 'loader_thread') and self.loader_thread.isRunning():
            self.loader_thread.terminate()
            self.loader_thread.wait()
            self.loader_thread.deleteLater()
        self.progress_dialog.close()

    def _add_cut_item(self, parent_item: QTreeWidgetItem, cut_id: str, episode_id: str):
        """添加Cut项"""
        # 构建路径
        if episode_id:
            vfx_path = self.project_base / "01_vfx" / episode_id / cut_id
            render_path = self.project_base / "06_render" / episode_id / cut_id / "prores"
        else:
            vfx_path = self.project_base / "01_vfx" / cut_id
            render_path = self.project_base / "06_render" / cut_id / "prores"

        # 查找AEP文件
        aep_info = FileUtils.find_latest_aep(vfx_path)

        # 查找MOV文件
        mov_info = FileUtils.find_latest_mov(render_path)

        # 查找缩略图
        thumbnail = FileUtils.find_thumbnail(self.project_base, cut_id, episode_id)

        # 创建Cut项
        cut_item = QTreeWidgetItem(parent_item, [
            cut_id,
            aep_info['version'] if aep_info else "无",
            mov_info['version'] if mov_info else "无",
            str(aep_info['path']) if aep_info else "",
            str(mov_info['path']) if mov_info else ""
        ])

        # 不在列表中显示缩略图，缩略图仅用于悬浮提示

        # 存储文件路径信息供双击使用和悬浮提示
        cut_item.setData(0, Qt.UserRole, {
            'aep_path': aep_info['path'] if aep_info else None,
            'mov_path': mov_info['path'] if mov_info else None,
            'cut_id': cut_id,
            'episode_id': episode_id,
            'thumbnail_path': thumbnail
        })


    def _on_cut_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Cut项双击事件"""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if column == 1 or column == 3:  # AEP版本列或AEP路径列
            aep_path = data.get('aep_path')
            if aep_path and aep_path.exists():
                self._open_file(aep_path)
        elif column == 2 or column == 4:  # MOV版本列或MOV路径列
            mov_path = data.get('mov_path')
            if mov_path and mov_path.exists():
                self._open_file(mov_path)

    def _open_file(self, file_path: Path):
        """使用系统默认程序打开文件"""
        try:
            if platform.system() == "Windows":
                os.startfile(str(file_path))
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(file_path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(file_path)])
        except Exception as e:
            QMessageBox.warning(self, "打开文件失败", f"无法打开文件: {file_path}\n错误: {str(e)}")

    def _on_item_hovered(self, item: QTreeWidgetItem, global_pos: QPoint):
        """处理项目悬浮事件"""
        cut_data = item.data(0, Qt.UserRole)
        if not cut_data:
            return

        # 从存储的数据中获取缩略图路径
        thumbnail_path = cut_data.get('thumbnail_path')
        cut_id = cut_data.get('cut_id')


        # 销毁之前的tooltip
        if self.tooltip_widget:
            self.tooltip_widget.hide()
            self.tooltip_widget.deleteLater()
            self.tooltip_widget = None

        # 重新创建tooltip widget
        self.tooltip_widget = CutTooltipWidget()

        # tooltip会自动使用全局版本映射器，无需手动设置

        # 显示新的tooltip内容
        self.tooltip_widget.show_cut_info(cut_data, thumbnail_path)

        # 使用定时器延迟显示，确保内容更新完成
        QTimer.singleShot(50, lambda: self._show_tooltip_delayed(global_pos))

    def _show_tooltip_delayed(self, global_pos: QPoint):
        """延迟显示tooltip"""
        if not self.tooltip_widget:
            return

        # 调整tooltip位置，避免超出屏幕
        tooltip_size = self.tooltip_widget.size()
        screen_geometry = QApplication.primaryScreen().geometry()

        x = global_pos.x() + 10
        y = global_pos.y() - tooltip_size.height() // 2

        # 确保不超出屏幕右边界
        if x + tooltip_size.width() > screen_geometry.right():
            x = global_pos.x() - tooltip_size.width() - 10

        # 确保不超出屏幕上下边界
        if y < screen_geometry.top():
            y = screen_geometry.top()
        elif y + tooltip_size.height() > screen_geometry.bottom():
            y = screen_geometry.bottom() - tooltip_size.height()

        self.tooltip_widget.move(x, y)
        self.tooltip_widget.show()
        self.tooltip_widget.raise_()

    def _hide_tooltip(self):
        """隐藏tooltip"""
        if hasattr(self, 'tooltip_widget') and self.tooltip_widget:
            self.tooltip_widget.hide()
            self.tooltip_widget.deleteLater()
            self.tooltip_widget = None

    def _on_hover_preview_toggled(self, state):
        """悬浮预览开关状态变化"""
        enabled = self.hover_preview_checkbox.isChecked()

        if hasattr(self, 'cut_tree'):
            # 确保状态正确同步
            self.cut_tree.set_hover_enabled(enabled)

        # 如果禁用，立即隐藏tooltip
        if not enabled:
            self._hide_tooltip()
        else:
            # 如果启用，确保没有残留的tooltip
            self._hide_tooltip()

    def _setup_default_version_mapping(self):
        """设置默认版本映射（已改为使用全局版本映射器）"""
        pass


# ======================== Background Loader ========================

class CutDataLoader(QThread):
    """Cut数据加载线程"""
    progress_updated = Signal(int)
    status_updated = Signal(str)
    cut_item_ready = Signal(object, str, str, dict, dict, object)  # parent_item, cut_id, episode_id, aep_info, mov_info, thumbnail
    finished = Signal()

    def __init__(self, project_config, project_base, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.project_base = project_base

    def run(self):
        """运行数据加载"""
        episodes = self.project_config.get("episodes", {})
        total_cuts = 0

        # 计算总数
        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            total_cuts += len(cuts)
            for ep_cuts in episodes.values():
                total_cuts += len(ep_cuts)
        else:
            for ep_cuts in episodes.values():
                total_cuts += len(ep_cuts)

        current_cut = 0

        if self.project_config.get("no_episode", False):
            # 单集模式
            cuts = self.project_config.get("cuts", [])
            if cuts:
                for cut_id in cuts:
                    self.status_updated.emit(f"正在处理根目录 Cut: {cut_id}")
                    aep_info, mov_info, thumbnail = self._process_cut(cut_id, None)
                    self.cut_item_ready.emit("root", cut_id, None, aep_info, mov_info, thumbnail)
                    current_cut += 1
                    self.progress_updated.emit(int((current_cut / total_cuts) * 100))

            # 处理特殊episode
            for ep_id in episodes:
                ep_cuts = episodes[ep_id]
                for cut_id in ep_cuts:
                    self.status_updated.emit(f"正在处理 {ep_id} Cut: {cut_id}")
                    aep_info, mov_info, thumbnail = self._process_cut(cut_id, ep_id)
                    self.cut_item_ready.emit(ep_id, cut_id, ep_id, aep_info, mov_info, thumbnail)
                    current_cut += 1
                    self.progress_updated.emit(int((current_cut / total_cuts) * 100))
        else:
            # Episode模式
            for ep_id in sorted(episodes.keys()):
                ep_cuts = episodes[ep_id]
                for cut_id in ep_cuts:
                    self.status_updated.emit(f"正在处理 {ep_id} Cut: {cut_id}")
                    aep_info, mov_info, thumbnail = self._process_cut(cut_id, ep_id)
                    self.cut_item_ready.emit(ep_id, cut_id, ep_id, aep_info, mov_info, thumbnail)
                    current_cut += 1
                    self.progress_updated.emit(int((current_cut / total_cuts) * 100))

        self.finished.emit()

    def _process_cut(self, cut_id: str, episode_id: str):
        """处理单个Cut"""
        # 构建路径
        if episode_id:
            vfx_path = self.project_base / "01_vfx" / episode_id / cut_id
            render_path = self.project_base / "06_render" / episode_id / cut_id / "prores"
        else:
            vfx_path = self.project_base / "01_vfx" / cut_id
            render_path = self.project_base / "06_render" / cut_id / "prores"

        # 查找AEP文件
        aep_info = FileUtils.find_latest_aep(vfx_path)

        # 查找MOV文件
        mov_info = FileUtils.find_latest_mov(render_path)

        # 查找缩略图
        thumbnail = FileUtils.find_thumbnail(self.project_base, cut_id, episode_id)

        return aep_info, mov_info, thumbnail

