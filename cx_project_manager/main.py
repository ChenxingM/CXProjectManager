# -*- coding: utf-8 -*-
"""
CX Project Manager - 动画项目管理工具
主程序入口

功能特性：
• 支持有/无 Episode 模式（单集/PV）
• Episode 和 Cut 的创建与批量创建
• 兼用卡功能 - 多个Cut共用同一套素材
• 素材导入管理（BG/Cell/Timesheet/AEP）
• AEP 模板批量复制功能
• 项目配置持久化
• 软件配置记忆（默认路径、最近项目）
• 目录树可视化
• Cut 搜索功能（支持兼用卡搜索）
• 版本管理系统
• 文件预览和时间显示
• 深色主题 UI
• 项目注册管理系统
• 项目浏览器和删除功能

Author: 千石まよひ
GitHub: https://github.com/ChenxingM/CXProjectManager
"""

import sys
import os
from pathlib import Path

# 添加当前目录到 Python 路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from ui.main_window import CXProjectManager


def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("CX Project Manager")
    app.setOrganizationName("CXStudio")

    # 设置应用图标
    icon_path = Path("../_imgs/app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = CXProjectManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()