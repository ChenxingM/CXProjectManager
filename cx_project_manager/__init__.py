# -*- coding: utf-8 -*-
"""
CX Project Manager - 动画项目管理工具

专为动画制作流程优化设计的项目管理工具。

功能特性：
• 支持有/无 Episode 模式（单集/PV）
• 单集模式下支持创建特殊类型 Episode（op/ed/pv 等，但不支持 ep）
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

__version__ = "2.2"
__author__ = "千石まよひ"
__email__ = "tammcx@gmail.com"

from .ui.main_window import CXProjectManager

__all__ = ['CXProjectManager']