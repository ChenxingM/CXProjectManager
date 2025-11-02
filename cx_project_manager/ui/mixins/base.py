# -*- coding: utf-8 -*-
"""Mixin 基类"""

from abc import ABC
from typing import Optional, Any
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QMenu, QStatusBar


class MixinBase(ABC):
    """
    Mixin 基类，定义所有 Mixin 需要的接口。
    这个类仅用于类型检查，实际功能由主窗口类提供。
    """

    # 从 QMainWindow 继承的方法
    def menuBar(self) -> Any:
        """获取菜单栏"""
        raise NotImplementedError

    def statusBar(self) -> QStatusBar:
        """获取状态栏"""
        raise NotImplementedError

    def close(self) -> None:
        """关闭窗口"""
        raise NotImplementedError

    # 需要在主类中定义的属性
    project_base: Optional[Path]
    project_config: Optional[dict]
    project_manager: Any
    app_settings: Any
    recent_menu: QMenu
    statusbar: QStatusBar

    # 来自各个 Mixin 的方法
    def new_project(self) -> None:
        """新建项目"""
        raise NotImplementedError

    def open_project(self) -> None:
        """打开项目"""
        raise NotImplementedError

    def browse_all_projects(self) -> None:
        """浏览所有项目"""
        raise NotImplementedError

    def set_default_path(self) -> None:
        """设置默认路径"""
        raise NotImplementedError

    def _update_recent_menu(self) -> None:
        """更新最近项目菜单"""
        raise NotImplementedError

    def _refresh_tree(self) -> None:
        """刷新目录树"""
        raise NotImplementedError

    def _focus_cut_search(self) -> None:
        """聚焦搜索框"""
        raise NotImplementedError

    def batch_copy_aep_template(self) -> None:
        """批量复制AEP模板"""
        raise NotImplementedError

    def create_reuse_cut(self) -> None:
        """创建兼用卡"""
        raise NotImplementedError

    def copy_mov_to_cut_folder(self) -> None:
        """复制MOV到剪辑文件夹"""
        raise NotImplementedError

    def lock_all_latest_versions(self) -> None:
        """锁定所有最新版本"""
        raise NotImplementedError

    def unlock_all_versions(self) -> None:
        """解锁所有版本"""
        raise NotImplementedError

    def delete_all_old_versions(self) -> None:
        """删除所有旧版本"""
        raise NotImplementedError

    def show_version_statistics(self) -> None:
        """显示版本统计"""
        raise NotImplementedError

    def open_in_explorer(self) -> None:
        """在文件管理器中打开"""
        raise NotImplementedError

    def show_help(self) -> None:
        """显示帮助"""
        raise NotImplementedError

    def show_about(self) -> None:
        """显示关于"""
        raise NotImplementedError