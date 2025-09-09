# -*- coding: utf-8 -*-
"""
项目注册管理器模块 - 完整版本
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import QSettings

from ..utils.constants import PROJECT_REGISTRY_FILE, PROJECT_SETTINGS_DIR
from ..utils.models import ProjectInfo
from ..utils.utils import ensure_dir


class ProjectRegistry:
    """项目注册管理器"""

    def __init__(self, app_settings: QSettings):
        self.app_settings = app_settings
        self.registry_path = self._get_registry_path()
        self.projects: Dict[str, ProjectInfo] = {}
        self.load_registry()

    def _get_registry_path(self) -> Path:
        """获取注册文件路径"""
        default_path = self.app_settings.value("default_project_path", "")
        if default_path and Path(default_path).exists():
            settings_dir = Path(default_path) / PROJECT_SETTINGS_DIR
            ensure_dir(settings_dir)
            return settings_dir / PROJECT_REGISTRY_FILE
        else:
            # 使用应用数据目录
            app_dir = Path.home() / ".cx_project_manager"
            ensure_dir(app_dir)
            return app_dir / PROJECT_REGISTRY_FILE

    def load_registry(self):
        """加载注册信息"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.projects = {
                        name: ProjectInfo.from_dict(info)
                        for name, info in data.items()
                    }
            except Exception as e:
                print(f"加载项目注册信息失败: {e}")
                self.projects = {}

    def save_registry(self):
        """保存注册信息"""
        try:
            data = {name: info.to_dict() for name, info in self.projects.items()}
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            from ..utils.convert_registry_to_csv import convert_registry_to_csv
            convert_registry_to_csv(self.registry_path.parent)
        except Exception as e:
            print(f"保存项目注册信息失败: {e}")

    def register_project(self, project_config: Dict, project_path: Path):
        """注册项目"""
        project_name = project_config.get("project_name", "Unknown")
        project_display_name = project_config.get("project_display_name", "Unknown")

        # 计算Episode信息
        episodes = project_config.get("episodes", {})
        episode_count = len(episodes)
        episode_list = sorted(episodes.keys())

        info = ProjectInfo(
            project_name=project_name,
            project_display_name=project_display_name,
            project_path=str(project_path),
            config_path=str(project_path / "project_config.json"),
            created_time=project_config.get("created_time", datetime.now().isoformat()),
            episode_count=episode_count,
            episode_list=episode_list,
            no_episode=project_config.get("no_episode", False)
        )

        self.projects[project_name] = info
        self.save_registry()

    def unregister_project(self, project_name: str):
        """注销项目"""
        if project_name in self.projects:
            del self.projects[project_name]
            self.save_registry()

    def update_access_time(self, project_name: str):
        """更新访问时间"""
        if project_name in self.projects:
            self.projects[project_name].last_accessed = datetime.now().isoformat()
            self.save_registry()

    def get_all_projects(self) -> List[ProjectInfo]:
        """获取所有项目"""
        return sorted(self.projects.values(),
                      key=lambda p: p.last_accessed,
                      reverse=True)

    def project_exists(self, project_name: str) -> bool:
        """检查项目是否存在"""
        return project_name in self.projects