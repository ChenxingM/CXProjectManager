# -*- coding: utf-8 -*-
"""菜单和工具栏功能混入类"""

from typing import TYPE_CHECKING
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QMenu, QMenuBar, QStatusBar
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from cx_project_manager.utils.version_info import version_info
from cx_project_manager.utils.utils import open_in_file_manager

if TYPE_CHECKING:
    from cx_project_manager.ui.mixins.base import MixinBase
else:
    MixinBase = object


class MenuMixin(MixinBase):
    """菜单和工具栏功能混入类"""

    # 需要在主類中定義的属性
    project_base: Path
    recent_menu: QMenu
    statusbar: any  # QStatusBar instance

    if TYPE_CHECKING:
        # 这些方法将通过多重继承在运行时提供
        def menuBar(self) -> 'QMenuBar': ...

        def statusBar(self) -> 'QStatusBar': ...

        def setStatusBar(self, statusbar: 'QStatusBar') -> None: ...

        def close(self) -> None: ...

        # 来自其他 Mixin 的方法
        def new_project(self) -> None: ...

        def open_project(self) -> None: ...

        def browse_all_projects(self) -> None: ...

        def set_default_path(self) -> None: ...

        def _update_recent_menu(self) -> None: ...

        def _refresh_tree(self) -> None: ...

        def _focus_cut_search(self) -> None: ...

        def batch_copy_aep_template(self) -> None: ...

        def create_reuse_cut(self) -> None: ...

        def copy_mov_to_cut_folder(self) -> None: ...

        def lock_all_latest_versions(self) -> None: ...

        def unlock_all_versions(self) -> None: ...

        def delete_all_old_versions(self) -> None: ...

        def show_version_statistics(self) -> None: ...

    def _setup_menubar(self):
        """設置菜單欄"""
        menubar = self.menuBar()

        # 文件菜單
        file_menu = menubar.addMenu("文件")

        actions = [
            ("✨ 新建项目", "Ctrl+N", self.new_project),
            ("📂 打开项目", "Ctrl+O", self.open_project),
            None,  # 分隔符
            ("🌐 浏览所有项目...", None, self.browse_all_projects),
            None,
            ("⚙️ 设置默认路径...", None, self.set_default_path),
            None,
            ("❌ 退出", "Ctrl+Q", self.close)
        ]

        # 添加基本操作
        for i, action_data in enumerate(actions):
            if action_data is None:
                file_menu.addSeparator()
            else:
                action = QAction(action_data[0], self)  # type: ignore
                if action_data[1]:
                    action.setShortcut(action_data[1])
                action.triggered.connect(action_data[2])  # type: ignore
                file_menu.addAction(action)

                # 在"浏览所有项目"后插入最近项目菜單
                if i == 3:  # 在"浏览所有项目"之后
                    self.recent_menu = QMenu("🕓 最近项目", self)  # type: ignore
                    file_menu.insertMenu(action, self.recent_menu)
                    self._update_recent_menu()  # type: ignore

        # 工具菜單
        tools_menu = menubar.addMenu("工具")

        tool_actions = [
            ("🔄 刷新目录树", "F5", self._refresh_tree),
            ("🔍 搜索Cut", "Ctrl+F", self._focus_cut_search),
            None,
            ("📑 批量复制AEP模板...", None, self.batch_copy_aep_template),
            ("✨ 创建兼用卡...", None, self.create_reuse_cut),
            ("📑 复制MOV到剪辑文件夹", "Ctrl+M", self.copy_mov_to_cut_folder),
            None,
            ("📂 在文件管理器中打开", None, self.open_in_explorer)
        ]

        for action_data in tool_actions:
            if action_data is None:
                tools_menu.addSeparator()
            else:
                action = QAction(action_data[0], self)  # type: ignore
                if action_data[1]:
                    action.setShortcut(action_data[1])
                action.triggered.connect(action_data[2])
                tools_menu.addAction(action)

        # 操作菜单
        operations_menu = menubar.addMenu("操作")

        version_actions = [
            ("🔒 锁定项目所有最新版本", None, self.lock_all_latest_versions),
            ("🔓 解锁项目所有版本", None, self.unlock_all_versions),
            None,
            ("❌ 删除项目所有旧版本", None, self.delete_all_old_versions),
            None,
            ("📊 版本统计", "Ctrl+T", self.show_version_statistics)
        ]

        for action_data in version_actions:
            if action_data is None:
                operations_menu.addSeparator()
            else:
                action = QAction(action_data[0], self)  # type: ignore
                if action_data[1]:
                    action.setShortcut(action_data[1])
                action.triggered.connect(action_data[2])
                operations_menu.addAction(action)

        # 帮助菜單
        help_menu = menubar.addMenu("帮助")

        help_actions = [
            ("📚 使用说明", self.show_help),
            ("ℹ️ 关于", self.show_about)
        ]

        for text, handler in help_actions:
            action = QAction(text, self)  # type: ignore
            action.triggered.connect(handler)
            help_menu.addAction(action)

    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusbar = self.statusBar()  # 自动创建状态栏
        self.statusbar.showMessage("请打开或新建项目以开始使用")

    def open_in_explorer(self):
        """在文件管理器中打开项目根目录"""
        if self.project_base:
            open_in_file_manager(self.project_base)

    def show_help(self):
        """顯示帮助信息"""
        help_text = f"""
CX Project Manager 使用说明
========================

版本: {version_info.get("version", "2.2")} {version_info.get("build-version", "")}

## 新增功能
- **项目注册管理**: 自动记录所有创建的项目信息
- **项目浏览器**: 浏览和管理所有已注册的项目
- **目录树双击**: 双击目录树节点直接打开文件夹
- **右键菜单支持**: 
  - 项目结构树支持右键导入文件和AEP模板
  - 文件浏览器支持删除、锁定/解锁版本等操作
- **中文注释**: 项目结构显示中文说明
- **版本管理系统**:
  - 🔒 锁定文件前会显示锁定图标
  - 支持锁定/解锁单个版本或最新版本
  - 批量删除旧版本（保护锁定版本）
  - 项目级别批量操作（操作菜单）

## 项目模式
- **标准模式**: 支持创建多个Episode（ep01, ep02等）
- **单集/PV模式**: 根目录下直接创建Cut，支持特殊Episode

## 快捷键
- Ctrl+N: 新建项目
- Ctrl+O: 打开项目
- Ctrl+F: 搜索Cut
- F5: 刷新目录树
- Ctrl+Q: 退出

## 文件管理功能
- **版本锁定**: 右键点击文件可锁定版本，防止被自动删除
- **批量清理**: 可删除所有非最新版本的文件（保留锁定版本）
- **导入文件**: 右键项目结构中的文件夹可直接导入文件
- **项目级操作**: 
  - 锁定所有最新版本
  - 解锁所有版本
  - 删除所有旧版本
  - 查看版本统计

## 项目注册
- 创建项目时自动注册到项目管理系统
- 记录项目名称、Episode数、创建时间、路径等信息
- 通过"文件 > 浏览所有项目"查看所有已注册项目
- 支持删除不需要的项目记录（仅删除记录，不删除文件）

作者: {version_info.get("author", "千石まよひ")}
"""

        dialog = QMessageBox(self)  # type: ignore
        dialog.setWindowTitle("使用说明")
        dialog.setText(help_text)
        dialog.setTextFormat(Qt.PlainText)  # type: ignore
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
        """顯示关于对话框"""
        about_text = f"""CX Project Manager - 动画项目管理工具

版本: {version_info.get("version", "Unknow")} {version_info.get("build-version", "")}
作者: {version_info.get("author", "千石まよひ")}
邮箱: {version_info.get("email", "tammcx@gmail.com")}
GitHub: https://github.com/ChenxingM/CXProjectManager

{version_info.get("description", "动画项目管理工具，专为动画制作流程优化设计。")}

新增功能：
- 项目注册管理系统
- 文件版本管理（锁定、批量删除）
- 右键菜单支持（导入文件、管理版本）
- 项目结构中文注释
- 项目级版本批量操作

如有问题或建议，欢迎在GitHub提交Issue。"""

        QMessageBox.about(self, "关于", about_text)  # type: ignore
