# -*- coding: utf-8 -*-
"""项目管理功能混入类"""

from pathlib import Path
from typing import Optional, cast

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import Signal

from cx_project_manager.core import ProjectManager, ProjectRegistry
from cx_project_manager.ui.dialogs import ProjectBrowserDialog


class ProjectMixin:
    """项目管理相关功能"""

    # 需要在主类中定义的信号
    project_changed: Signal

    # 需要在主类中定义的属性
    project_manager: ProjectManager
    project_registry: ProjectRegistry
    project_base: Optional[Path]
    project_config: Optional[dict]
    app_settings: any
    project_prefix: str
    txt_project_name: str
    chk_no_episode: any
    statusbar: any
    recent_menu: any

    def new_project(self):
        """新建项目"""
        project_name = self.txt_project_name.text().strip()
        project_display_name = None
        if not project_name:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            self.txt_project_name.setFocus()
            return

        # 检查默认路径
        default_path = self.app_settings.value("default_project_path", "")

        if default_path and Path(default_path).exists():
            base_folder = Path(default_path)
        else:
            base_folder = QFileDialog.getExistingDirectory(self, "选择项目创建位置", "")
            if not base_folder:
                return
            base_folder = Path(base_folder)

        # 检查前缀 (前缀_项目名 作为路径，但项目名不变)
        if self.project_prefix:
            project_name = f"{self.project_prefix}_{project_name}"
            project_display_name = project_name

        # 检查项目是否已存在
        project_path = base_folder / project_name
        if project_path.exists():
            reply = QMessageBox.question(
                self, "确认",
                f"项目 '{project_display_name}' 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # 创建项目
        no_episode = self.chk_no_episode.isChecked()
        if self.project_manager.create_project(project_name, base_folder, no_episode):
            self.project_base = self.project_manager.project_base
            self.project_config = self.project_manager.project_config

            # 注册项目
            self.project_registry.register_project(self.project_config, self.project_base)

            # 更新注册表
            if hasattr(self, 'project_registry'):
                episodes = self.project_config.get("episodes", {})
                self.project_config["episode_count"] = len(episodes)
                self.project_config["episode_list"] = sorted(episodes.keys())
                from ...utils.convert_registry_to_csv import convert_registry_to_csv
                convert_registry_to_csv(self.project_base)

            self.project_changed.emit()
            self._add_to_recent(str(self.project_base))
            self.txt_project_name.clear()

            QMessageBox.information(self, "成功", f"项目 '{project_name}' 创建成功！")

    def open_project(self):
        """打开已有项目"""
        folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹", "")
        if folder:
            self._load_project(folder)

    def browse_all_projects(self):
        """浏览所有项目"""
        dialog = ProjectBrowserDialog(self.project_registry, self)
        dialog.project_selected.connect(self._load_project)
        dialog.exec_()

    def _load_project(self, folder: str):
        """加载项目"""
        project_path = Path(folder)

        if self.project_manager.load_project(project_path):
            self.project_base = self.project_manager.project_base
            self.project_config = self.project_manager.project_config

            # 更新访问时间
            project_name = self.project_config.get("project_name")
            if project_name:
                self.project_registry.update_access_time(project_name)

            self.project_changed.emit()
            self._add_to_recent(str(project_path))
        else:
            QMessageBox.warning(self, "错误", "所选文件夹不是有效的项目（缺少 project_config.json）")

    def set_default_path(self):
        """设置默认项目路径"""
        current = self.app_settings.value("default_project_path", "")
        folder = QFileDialog.getExistingDirectory(self, "设置默认项目路径", current)

        if folder:
            self.app_settings.setValue("default_project_path", folder)
            self.btn_new_project.setToolTip(f"将创建到: {folder}")

            # 更新项目注册管理器的路径
            self.project_registry.registry_path = self.project_registry._get_registry_path()
            self.project_registry.load_registry()

            QMessageBox.information(self, "成功", f"默认项目路径已设置为:\n{folder}")

    # 最近项目相关方法
    def _update_recent_menu(self):
        """刷新『最近项目』菜单"""
        self.recent_menu.clear()

        recent_paths = cast(list[str], self.app_settings.value("recent_projects", []))
        recent_list = [p for p in recent_paths if Path(p).exists()]

        if not recent_list:
            action = self.recent_menu.addAction("(无最近项目)")
            action.setEnabled(False)
            return

        for idx, path in enumerate(recent_list[:10]):
            act = QAction(Path(path).name, self)
            if idx == 0:
                act.setShortcut("Ctrl+R")
            act.setToolTip(path)
            act.triggered.connect(lambda _=False, p=path: self.open_recent_project(p))
            self.recent_menu.addAction(act)

    def open_recent_project(self, path: str):
        """打开最近项目"""
        if Path(path).exists():
            self._load_project(path)
        else:
            QMessageBox.warning(self, "错误", f"项目路径不存在：\n{path}")
            self._remove_from_recent(path)

    def _add_to_recent(self, path: str):
        """添加到最近项目"""
        recent = self.app_settings.value("recent_projects", [])

        if path in recent:
            recent.remove(path)

        recent.insert(0, path)
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
