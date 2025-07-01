from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QWidget, QFrame, QPushButton, QScrollArea, QGroupBox,
                               QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QBrush
import os


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

    def __init__(self, label: str, value: str, value_color: str = "#ffffff", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("""
            color: #999; 
            font-size: 14px;
            background-color: transparent;
        """)

        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"""
            font-weight: bold; 
            font-size: 15px; 
            color: {value_color};
            background-color: transparent;
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
        self.setStyleSheet("background-color: transparent;")

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
        painter.fillRect(x_offset, 0, width, height, QColor("#1a1a1a"))

        # 最新版本部分（蓝色）
        latest_width = int(width * latest_percent)
        painter.fillRect(x_offset, 0, latest_width, height, QColor("#4FC3F7"))

        # 旧版本部分（橙色）
        old_width = int(width * old_percent)
        painter.fillRect(x_offset + latest_width, 0, old_width, height, QColor("#FF7043"))

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


class ProjectStatisticsDialog(QDialog):
    """项目综合统计对话框 - 横向布局"""

    def __init__(self, project_config: dict, version_stats: dict, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.version_stats = version_stats
        self.setWindowTitle("项目统计")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                font-family: "MiSans", "Microsoft YaHei", sans-serif;
                color: #ffffff;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a5a;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 主内容区域 - 横向布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # 左侧：项目统计
        left_widget = self.create_project_stats_panel()
        content_layout.addWidget(left_widget, 1)

        # 右侧：版本统计
        right_widget = self.create_version_stats_panel()
        content_layout.addWidget(right_widget, 1)

        main_layout.addLayout(content_layout)

        # 底部按钮区域
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)

        # 显示项目总体积
        total_size_gb = self.calculate_project_size() / 1024
        size_label = QLabel(f"项目总体积: {total_size_gb:.2f} GB")
        size_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #4FC3F7;
            background-color: transparent;
        """)

        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(120, 35)
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
                                      "#4FC3F7"))
        info_layout.addWidget(StatRow("创建时间",
                                      self.project_config.get('created_time', 'Unknown')[:10]))
        info_layout.addWidget(StatRow("最后修改",
                                      self.project_config.get('last_modified', 'Unknown')[:10]))

        mode = "单集/PV 模式" if self.project_config.get("no_episode", False) else "Episode 模式"
        info_layout.addWidget(StatRow("项目模式", mode, "#66BB6A"))

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
                episode_layout.addWidget(StatRow("特殊 Episode 数", str(len(episodes)), "#FFB74D"))
                episode_layout.addWidget(StatRow("特殊 Episode 内 Cut 数", str(special_count)))
        else:
            total_cuts = sum(len(cuts) for cuts in episodes.values())
            episode_layout.addWidget(StatRow("Episode 总数", str(len(episodes))))
            episode_layout.addWidget(StatRow("Cut 总数", str(total_cuts), "#66BB6A"))

        layout.addWidget(episode_group)

        # 文件类型分布（移到左边）
        type_group = StatGroupBox("📁 文件类型分布")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(5)

        type_layout.addWidget(StatRow("AEP文件",
                                      str(self.version_stats['aep_count']),
                                      "#4FC3F7"))
        type_layout.addWidget(StatRow("BG文件",
                                      str(self.version_stats['bg_count']),
                                      "#4FC3F7"))
        type_layout.addWidget(StatRow("Cell文件夹",
                                      str(self.version_stats['cell_count']),
                                      "#4FC3F7"))

        layout.addWidget(type_group)

        # 兼用卡统计
        reuse_cuts = self.project_config.get("reuse_cuts", [])
        if reuse_cuts:
            reuse_group = StatGroupBox("♻️ 兼用卡统计")
            reuse_layout = QVBoxLayout(reuse_group)
            reuse_layout.setSpacing(5)

            total_reuse_cuts = sum(len(cut["cuts"]) for cut in reuse_cuts)
            reuse_layout.addWidget(StatRow("兼用卡数量", str(len(reuse_cuts)), "#AB47BC"))
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
                                      "#4FC3F7"))
        file_layout.addWidget(StatRow("最新版本",
                                      str(self.version_stats['latest_versions']),
                                      "#66BB6A"))
        file_layout.addWidget(StatRow("历史版本",
                                      str(self.version_stats['old_versions']),
                                      "#FF7043"))

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
                                      "#66BB6A"))
        lock_layout.addWidget(StatRow("锁定的旧版本",
                                      str(self.version_stats['locked_old']),
                                      "#FF7043"))

        layout.addWidget(lock_group)

        # 存储空间
        storage_group = StatGroupBox("💾 存储空间")
        storage_layout = QVBoxLayout(storage_group)
        storage_layout.setSpacing(10)

        total_mb = self.version_stats['total_size_mb']
        color = "#66BB6A"
        if total_mb > 1000:
            color = "#FF7043"
        if total_mb > 5000:
            color = "#EF5350"

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
        legend_widget.setStyleSheet("background-color: transparent;")
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setContentsMargins(15, 5, 15, 5)

        # 最新版本图例
        latest_icon = QLabel()
        latest_icon.setFixedSize(12, 12)
        latest_icon.setStyleSheet("background-color: #4FC3F7; border-radius: 2px;")
        latest_label = QLabel("最新版本")
        latest_label.setStyleSheet("color: #999; font-size: 12px; background-color: transparent;")

        # 历史版本图例
        old_icon = QLabel()
        old_icon.setFixedSize(12, 12)
        old_icon.setStyleSheet("background-color: #FF7043; border-radius: 2px;")
        old_label = QLabel("历史版本")
        old_label.setStyleSheet("color: #999; font-size: 12px; background-color: transparent;")

        legend_layout.addWidget(latest_icon)
        legend_layout.addWidget(latest_label)
        legend_layout.addSpacing(20)
        legend_layout.addWidget(old_icon)
        legend_layout.addWidget(old_label)
        legend_layout.addStretch()

        storage_layout.addWidget(legend_widget)

        storage_layout.addWidget(StatRow("可释放空间",
                                         f"{self.version_stats['deletable_size_mb']:.1f} MB",
                                         "#EF5350"))

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

        return total_size / (1024 * 1024)  # 转换为MB
