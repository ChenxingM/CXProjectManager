# -*- coding: utf-8 -*-
"""
项目管理核心类模块
包含项目创建、加载、保存、注册表同步等所有功能
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re

from ..utils.models import ProjectPaths, ReuseCut
from ..utils.utils import (
    ensure_dir, copy_file_safe, zero_pad, parse_cut_id, format_cut_id,
    extract_version_from_filename
)


class ProjectManager:
    """
    项目管理核心类
    负责项目的创建、加载、保存、注册表同步等操作
    """

    def __init__(self, project_base: Path = None, registry_path: Path = None):
        """
        初始化项目管理器

        Args:
            project_base: 项目基础路径
            registry_path: 注册表路径（可选）
        """
        self.project_base = project_base
        self.project_config = None
        self.paths = ProjectPaths()
        self.registry_path = registry_path

        # 默认配置
        self.default_registry_path = Path("E:/3_Projects/_proj_settings/project_registry.json")

    # ==================== 注册表管理 ====================

    def set_registry_path(self, registry_path: Path):
        """设置注册表路径"""
        self.registry_path = registry_path

    def _get_registry_path(self) -> Path:
        """
        获取注册表路径
        优先级：实例设置 > 项目父目录 > 默认路径
        """
        if self.registry_path:
            return self.registry_path

        if self.project_base:
            parent_registry = self.project_base.parent / "_proj_settings" / "project_registry.json"
            if parent_registry.exists() or parent_registry.parent.exists():
                return parent_registry

        return self.default_registry_path

    def _load_registry(self) -> Dict[str, Any]:
        """加载注册表数据"""
        registry_path = self._get_registry_path()

        if not registry_path.exists():
            return {}

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"读取注册表失败: {e}")
            return {}

    def _save_registry(self, registry_data: Dict[str, Any]) -> bool:
        """
        保存注册表数据

        Args:
            registry_data: 注册表数据

        Returns:
            bool: 是否保存成功
        """
        registry_path = self._get_registry_path()

        # 确保目录存在
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 创建备份
            if registry_path.exists():
                backup_path = registry_path.with_suffix('.backup.json')
                shutil.copy2(registry_path, backup_path)

            # 保存注册表
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存注册表失败: {e}")
            return False

    def _update_registry(self, force_update: bool = False) -> bool:
        """
        更新当前项目到注册表（修复版）
        只更新当前项目的条目，不影响其他项目

        Args:
            force_update: 是否强制更新所有字段

        Returns:
            bool: 是否更新成功
        """
        if not self.project_config or not self.project_base:
            return False

        # 获取当前项目名称
        project_name = self.project_config.get("project_name")
        if not project_name:
            return False

        # 验证项目路径匹配
        # 确保 project_base 的名称与 project_name 一致
        if self.project_base.name != project_name:
            print(f"警告：项目名称不匹配 - 配置: {project_name}, 路径: {self.project_base.name}")
            # 使用实际路径的名称
            project_name = self.project_base.name

        # 加载现有注册表
        registry_data = self._load_registry()

        # 准备当前项目的注册表条目
        episodes = self.project_config.get("episodes", {})
        registry_entry = {
            "project_name": project_name,
            "project_display_name": self.project_config.get("project_display_name", project_name),
            "project_path": str(self.project_base),
            "config_path": str(self.project_base / "project_config.json"),
            "created_time": self.project_config.get("created_time", datetime.now().isoformat()),
            "episode_count": len(episodes),
            "episode_list": sorted(episodes.keys()),
            "no_episode": self.project_config.get("no_episode", False),
            "last_accessed": datetime.now().isoformat()
        }

        # 只更新当前项目的条目
        if project_name not in registry_data:
            registry_data[project_name] = registry_entry
            print(f"注册新项目: {project_name}")
        else:
            # 现有项目，保留其他项目不变，只更新当前项目
            if force_update:
                # 强制更新：完全替换
                registry_data[project_name] = registry_entry
            else:
                # 正常更新：只更新必要字段
                registry_data[project_name].update({
                    "project_display_name": registry_entry["project_display_name"],
                    "episode_count": registry_entry["episode_count"],
                    "episode_list": registry_entry["episode_list"],
                    "no_episode": registry_entry["no_episode"],
                    "last_accessed": registry_entry["last_accessed"]
                })

        # 保存更新后的注册表
        return self._save_registry(registry_data)

    def _update_registry_access_time_only(self):
        """
        仅更新注册表中当前项目的访问时间
        不修改其他任何字段
        """
        if not self.project_config or not self.project_base:
            return

        project_name = self.project_config.get("project_name")
        if not project_name:
            return

        registry_data = self._load_registry()

        # 只更新当前项目的访问时间
        if project_name in registry_data:
            registry_data[project_name]["last_accessed"] = datetime.now().isoformat()
            self._save_registry(registry_data)
        # 如果项目不在注册表中，不创建新条目

    def batch_sync_registry(self, registry_path: Path = None) -> Tuple[int, int, str]:
        """
        批量同步所有项目配置到注册表

        Args:
            registry_path: 注册表路径（可选）

        Returns:
            tuple: (成功数, 失败数, 详细信息)
        """
        if registry_path:
            self.set_registry_path(registry_path)

        registry_data = self._load_registry()

        if not registry_data:
            return 0, 0, "注册表为空或不存在"

        success_count = 0
        fail_count = 0
        skip_count = 0
        details = []

        for project_name, entry in registry_data.items():
            config_path = Path(entry.get('config_path', ''))

            if not config_path or not config_path.exists():
                fail_count += 1
                details.append(f"❌ {project_name}: 配置文件不存在")
                continue

            try:
                # 读取项目配置
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 检查是否需要更新
                episodes = config.get('episodes', {})
                needs_update = False
                changes = []

                # 检查各字段
                if entry.get('project_display_name') != config.get('project_display_name', project_name):
                    needs_update = True
                    changes.append(
                        f"显示名: {entry.get('project_display_name')} → {config.get('project_display_name')}")

                if entry.get('no_episode') != config.get('no_episode', False):
                    needs_update = True
                    changes.append(f"Episode模式: {not entry.get('no_episode')} → {not config.get('no_episode')}")

                if entry.get('episode_count') != len(episodes):
                    needs_update = True
                    changes.append(f"Episode数: {entry.get('episode_count')} → {len(episodes)}")

                episode_list = sorted(episodes.keys())
                if entry.get('episode_list', []) != episode_list:
                    needs_update = True
                    changes.append(f"Episode列表更新")

                if needs_update:
                    # 更新注册表条目
                    entry.update({
                        'project_display_name': config.get('project_display_name', project_name),
                        'no_episode': config.get('no_episode', False),
                        'episode_count': len(episodes),
                        'episode_list': episode_list,
                        'last_accessed': datetime.now().isoformat()
                    })
                    success_count += 1
                    details.append(f"✅ {project_name}: 已更新")
                    for change in changes:
                        details.append(f"    - {change}")
                else:
                    skip_count += 1
                    details.append(f"✓ {project_name}: 无需更新")

            except Exception as e:
                fail_count += 1
                details.append(f"❌ {project_name}: 处理失败 - {e}")

        # 保存更新
        if success_count > 0:
            if self._save_registry(registry_data):
                details.append(f"\n💾 已保存 {success_count} 个项目的更新")
            else:
                return 0, len(registry_data), "保存注册表失败"

        # 生成摘要
        summary = f"\n📊 批量同步完成："
        summary += f"\n   总项目数: {len(registry_data)}"
        summary += f"\n   已更新: {success_count}"
        summary += f"\n   失败: {fail_count}"
        summary += f"\n   无需更新: {skip_count}"

        details.append(summary)
        return success_count, fail_count, "\n".join(details)

    def validate_registry_integrity(self) -> Tuple[bool, List[str]]:
        """
        验证注册表的完整性
        检查所有项目条目是否正确

        Returns:
            tuple: (是否有效, 问题列表)
        """
        registry_data = self._load_registry()
        issues = []

        for project_name, entry in registry_data.items():
            # 检查必要字段
            required_fields = ["project_name", "project_path", "config_path"]
            for field in required_fields:
                if field not in entry:
                    issues.append(f"{project_name}: 缺少字段 {field}")

            # 检查路径是否存在
            if "project_path" in entry:
                project_path = Path(entry["project_path"])
                if not project_path.exists():
                    issues.append(f"{project_name}: 项目路径不存在 {project_path}")
                elif project_path.name != project_name:
                    issues.append(f"{project_name}: 路径名称不匹配 {project_path.name}")

            # 检查配置文件
            if "config_path" in entry:
                config_path = Path(entry["config_path"])
                if not config_path.exists():
                    issues.append(f"{project_name}: 配置文件不存在 {config_path}")

        return len(issues) == 0, issues

    def repair_registry(self) -> Tuple[int, int, str]:
        """
        修复注册表中的问题

        Returns:
            tuple: (修复数, 失败数, 详细信息)
        """
        registry_data = self._load_registry()
        fixed = 0
        failed = 0
        details = []

        for project_name in list(registry_data.keys()):
            entry = registry_data[project_name]
            config_path = Path(entry.get("config_path", ""))

            if not config_path.exists():
                # 配置文件不存在，尝试从项目路径查找
                project_path = Path(entry.get("project_path", ""))
                if project_path.exists():
                    new_config_path = project_path / "project_config.json"
                    if new_config_path.exists():
                        entry["config_path"] = str(new_config_path)
                        fixed += 1
                        details.append(f"✅ 修复 {project_name} 的配置路径")
                    else:
                        failed += 1
                        details.append(f"❌ {project_name}: 找不到配置文件")
                else:
                    # 项目完全不存在，标记为删除
                    del registry_data[project_name]
                    details.append(f"🗑️ 删除不存在的项目 {project_name}")
                    fixed += 1
            else:
                # 配置文件存在，验证内容
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)

                    # 确保注册表数据是最新的
                    episodes = config.get("episodes", {})
                    updates = {}

                    if entry.get("no_episode") != config.get("no_episode", False):
                        updates["no_episode"] = config.get("no_episode", False)

                    if entry.get("episode_count") != len(episodes):
                        updates["episode_count"] = len(episodes)

                    episode_list = sorted(episodes.keys())
                    if entry.get("episode_list", []) != episode_list:
                        updates["episode_list"] = episode_list

                    if updates:
                        entry.update(updates)
                        fixed += 1
                        details.append(f"✅ 更新 {project_name} 的信息")

                except Exception as e:
                    failed += 1
                    details.append(f"❌ {project_name}: 读取配置失败 - {e}")

        # 保存修复后的注册表
        if fixed > 0:
            self._save_registry(registry_data)
            details.append(f"\n💾 已保存修复后的注册表")

        summary = f"\n📊 修复结果：修复 {fixed} 个，失败 {failed} 个"
        details.append(summary)

        return fixed, failed, "\n".join(details)

    # ==================== 项目管理 ====================

    def create_project(
            self,
            project_name: str,
            project_display_name: str,
            base_folder: Path,
            no_episode: bool = False
    ) -> bool:
        """
        创建新项目

        Args:
            project_name: 实际项目名（用于文件系统路径）
            project_display_name: 显示名称（用于UI显示）
            base_folder: 项目基础文件夹
            no_episode: 是否为无Episode模式

        Returns:
            bool: 创建是否成功
        """
        # 创建项目路径
        self.project_base = base_folder / project_name

        # 创建目录结构
        if not self._create_project_structure(no_episode):
            return False

        # 初始化项目配置
        self.project_config = {
            "project_name": project_name,
            "project_display_name": project_display_name,
            "project_path": str(self.project_base),
            "no_episode": no_episode,
            "episodes": {},
            "cuts": [],
            "reuse_cuts": [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "paths": self.paths.__dict__
        }

        # 保存配置和创建README
        if not self.save_config():
            return False

        self._create_readme()
        return True

    def load_project(self, project_path: Path) -> bool:
        """
        加载项目（修复版）
        确保完全切换到新项目，不影响其他项目

        Args:
            project_path: 项目路径

        Returns:
            bool: 是否加载成功
        """
        config_file = project_path / "project_config.json"

        if not config_file.exists():
            print(f"项目配置文件不存在: {config_file}")
            return False

        try:
            # 清理之前的项目状态
            self.project_config = None
            self.project_base = None

            # 加载新项目配置
            with open(config_file, "r", encoding="utf-8") as f:
                new_config = json.load(f)

            # 验证配置的完整性
            project_name = new_config.get("project_name")
            if not project_name:
                print("项目配置缺少 project_name")
                return False

            # 验证路径名称匹配
            if project_path.name != project_name:
                print(f"警告：路径名称 {project_path.name} 与配置中的 {project_name} 不匹配")
                # 优先使用实际路径名称
                new_config["project_name"] = project_path.name

            # 设置新项目
            self.project_config = new_config
            self.project_base = project_path

            # 兼容性处理
            self._ensure_compatibility()

            # 只更新当前项目的访问时间，不触发完整更新
            self._update_registry_access_time_only()

            print(f"成功加载项目: {project_name}")
            return True

        except Exception as e:
            print(f"加载项目配置失败: {e}")
            # 恢复到无项目状态
            self.project_config = None
            self.project_base = None
            return False

    def save_config(self, update_registry: bool = True) -> bool:
        """
        保存项目配置

        Args: update_registry: 是否同时更新注册表（默认True）

        Returns:
            bool: 是否保存成功
        """
        if not self.project_base or not self.project_config:
            return False

        # 验证项目名称一致性
        if self.project_config.get("project_name") != self.project_base.name:
            print(f"修正项目名称: {self.project_config.get('project_name')} -> {self.project_base.name}")
            self.project_config["project_name"] = self.project_base.name

        # 更新修改时间
        self.project_config["last_modified"] = datetime.now().isoformat()

        # 保存项目配置文件
        config_file = self.project_base / "project_config.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.project_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存项目配置失败: {e}")
            return False

        # 根据参数决定是否更新注册表
        if update_registry:
            self._update_registry()

        return True

    def switch_project(self, new_project_path: Path) -> bool:
        """
        切换项目

        Args:
            new_project_path: 新项目路径

        Returns:
            bool: 是否切换成功
        """
        # 保存当前项目（如果有）
        if self.project_config and self.project_base:
            print(f"保存当前项目: {self.project_base.name}")
            self.save_config(update_registry=True)

        # 清理当前状态
        self.project_config = None
        self.project_base = None

        # 加载新项目
        return self.load_project(new_project_path)

    def _ensure_compatibility(self):
        """确保配置的兼容性"""
        if not self.project_config:
            return

        # 确保有 display_name
        if "project_display_name" not in self.project_config:
            self.project_config["project_display_name"] = self.project_config.get("project_name", "")

        # 确保有 reuse_cuts
        if "reuse_cuts" not in self.project_config:
            self.project_config["reuse_cuts"] = []

        # 确保有 paths
        if "paths" not in self.project_config:
            self.project_config["paths"] = self.paths.__dict__

    # ==================== 目录结构管理 ====================

    def _create_project_structure(self, no_episode: bool) -> bool:
        """
        创建项目目录结构

        Args:
            no_episode: 是否为无Episode模式

        Returns:
            bool: 是否创建成功
        """
        try:
            dirs = [
                "00_reference_project/character_design",
                "00_reference_project/art_design",
                "00_reference_project/concept_art",
                "00_reference_project/storyboard",
                "00_reference_project/docs",
                "00_reference_project/other_design",
                "05_stills",
                "06_render",
                "07_master_assets/fonts",
                "07_master_assets/logo",
                "07_master_assets/fx_presets",
                "07_master_assets/aep_templates",
                "08_tools/ae_scripts",
                "08_tools/python",
                "08_tools/config",
                "09_edit",
                "09_edit/projects",
                "09_edit/output",
                "09_edit/footage",
                "98_tmp",
                "99_other",
            ]

            # 无Episode模式需要额外的目录
            if no_episode:
                dirs.extend([
                    "01_vfx",
                    "02_comp",
                    "03_render"
                ])

            for dir_path in dirs:
                ensure_dir(self.project_base / dir_path)

            return True

        except Exception as e:
            print(f"创建项目结构失败: {e}")
            return False

    def _create_readme(self):
        """创建项目README文件"""
        if not self.project_config or not self.project_base:
            return

        config = self.project_config
        readme_content = f"""# {config.get('project_display_name', config.get('project_name'))}

## 项目信息
- **项目名称**: {config.get('project_display_name', '')}
- **项目路径名**: {config.get('project_name', '')}
- **创建时间**: {config.get('created_time', '')}
- **Episode模式**: {'无Episode模式' if config.get('no_episode') else '有Episode模式'}

## 目录结构
```
{config.get('project_name', 'project')}/
├── 00_reference_project/  # 项目参考资料
├── 01_vfx/               # VFX制作文件
├── 05_stills/            # 静帧预览
├── 06_render/            # 渲染输出
├── 07_master_assets/     # 共用素材
├── 08_tools/             # 工具脚本
├── 09_edit/              # 剪辑文件
├── 98_tmp/               # 临时文件
├── 99_other/             # 其他文件
└── project_config.json   # 项目配置
```

## 使用说明
1. 使用 CX Project Manager 管理本项目
2. AEP文件存放在 01_vfx/ 对应的Cut文件夹中
3. 渲染输出保存到 06_render/ 对应的Cut文件夹中
4. 共用素材统一管理在 07_master_assets/ 目录下

---
*此文件由 CX Project Manager 自动生成*
"""

        readme_path = self.project_base / "README.md"
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
        except Exception as e:
            print(f"创建README失败: {e}")

    # ==================== Episode管理 ====================

    def create_episode(self, ep_type: str, ep_identifier: str = "") -> Tuple[bool, str]:
        """
        创建Episode

        Args::
            ep_type: Episode类型（ep, ova, pv等）
            ep_identifier: Episode标识符

        Returns:
            tuple: (是否成功, Episode ID或错误信息)
        """
        if not self.project_config:
            return False, "项目未加载"

        # 构建 Episode ID
        if ep_type == "ep" and ep_identifier and ep_identifier.isdigit():
            ep_id = f"ep{zero_pad(int(ep_identifier), 2)}"
        elif ep_identifier:
            safe_identifier = re.sub(r'[/\\]', '_', ep_identifier.replace(" ", "_"))
            ep_id = f"{ep_type}_{safe_identifier}" if ep_type and ep_type != ep_identifier.lower() else safe_identifier
        else:
            ep_id = ep_type

        # 检查是否已存在
        if ep_id in self.project_config.get("episodes", {}):
            return False, f"Episode '{ep_id}' 已存在"

        # 创建目录结构
        if not self._create_episode_structure(ep_id):
            return False, f"创建Episode目录失败"

        # 更新配置
        if "episodes" not in self.project_config:
            self.project_config["episodes"] = {}
        self.project_config["episodes"][ep_id] = []

        # 保存配置（自动更新注册表）
        if not self.save_config():
            return False, "保存配置失败"

        return True, ep_id

    def _create_episode_structure(self, ep_id: str) -> bool:
        """创建Episode目录结构"""
        try:
            ep_path = self.project_base / ep_id
            dirs = [
                "00_reference/storyboard",
                "00_reference/script",
                "00_reference/director_notes",
                "01_vfx/timesheets",
                "03_preview",
                "04_log",
                "05_stills",
                "06_output_mixdown",
            ]

            for dir_path in dirs:
                ensure_dir(ep_path / dir_path)

            # 创建render目录
            ensure_dir(self.project_base / "06_render" / ep_id)

            return True

        except Exception as e:
            print(f"创建Episode结构失败: {e}")
            return False

    # ==================== Cut管理 ====================

    def create_cut(self, cut_num: str, episode_id: str = None) -> Tuple[bool, str]:
        """
        创建Cut

        Args:
            cut_num: Cut编号
            episode_id: Episode ID（可选）

        Returns:
            tuple: (是否成功, Cut ID或错误信息)
        """
        if not self.project_config:
            return False, "项目未加载"

        # 解析和格式化Cut ID
        try:
            num_part, letter_part = parse_cut_id(cut_num)
            cut_id = format_cut_id(num_part, letter_part)
        except ValueError:
            return False, "请输入有效的Cut编号（数字或数字+字母）"

        # 无Episode模式
        if self.project_config.get("no_episode", False) and not episode_id:
            if cut_id in self.project_config.get("cuts", []):
                return False, f"Cut {cut_id} 已存在"

            cut_path = self.project_base / "01_vfx" / cut_id
            if not self._create_cut_structure(cut_path, episode_id=None):
                return False, "创建Cut目录失败"

            if "cuts" not in self.project_config:
                self.project_config["cuts"] = []
            self.project_config["cuts"].append(cut_id)

        # Episode模式
        else:
            if not episode_id:
                return False, "请选择Episode"

            if episode_id not in self.project_config.get("episodes", {}):
                return False, f"Episode '{episode_id}' 不存在"

            if cut_id in self.project_config["episodes"][episode_id]:
                return False, f"Cut {cut_id} 已存在于 {episode_id}"

            cut_path = self.project_base / episode_id / "01_vfx" / cut_id
            if not self._create_cut_structure(cut_path, episode_id=episode_id):
                return False, "创建Cut目录失败"

            self.project_config["episodes"][episode_id].append(cut_id)

        # 保存配置（自动更新注册表）
        if not self.save_config():
            return False, "保存配置失败"

        return True, cut_id

    def _create_cut_structure(self, cut_path: Path, episode_id: Optional[str] = None) -> bool:
        """创建Cut目录结构"""
        try:
            # 创建子目录
            for subdir in ["cell", "bg", "prerender"]:
                ensure_dir(cut_path / subdir)

            cut_id = cut_path.name
            proj_name = self.project_base.name

            # 创建render目录
            if episode_id:
                render_path = self.project_base / "06_render" / episode_id / cut_id
            else:
                render_path = self.project_base / "06_render" / cut_id

            for subdir in ["png_seq", "prores", "mp4"]:
                ensure_dir(render_path / subdir)

            # 复制AEP模板
            self._copy_aep_template(cut_path, cut_id, episode_id)

            return True

        except Exception as e:
            print(f"创建Cut结构失败: {e}")
            return False

    def _copy_aep_template(self, cut_path: Path, cut_id: str, episode_id: Optional[str] = None):
        """复制AEP模板到Cut目录"""
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists():
            return

        proj_name = self.project_base.name

        for template in template_dir.glob("*.aep"):
            template_stem = template.stem
            version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"

            if episode_id:
                ep_part = episode_id.upper()
                aep_name = f"{proj_name}_{ep_part}_{cut_id}{version_part}{template.suffix}"
            else:
                aep_name = f"{proj_name}_{cut_id}{version_part}{template.suffix}"

            copy_file_safe(template, cut_path / aep_name)

    # ==================== 兼用卡管理 ====================

    def create_reuse_cut(self, cuts: List[str], episode_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        创建兼用卡

        Args::
            cuts: Cut列表
            episode_id: Episode ID（可选）

        Returns:
            tuple: (是否成功, 消息)
        """
        if len(cuts) < 2:
            return False, "兼用卡至少需要2个Cut"

        sorted_cuts = sorted(cuts, key=lambda c: parse_cut_id(c))
        main_cut = sorted_cuts[0]

        reuse_cut = ReuseCut(
            cuts=sorted_cuts,
            main_cut=main_cut,
            episode_id=episode_id
        )

        # 合并文件
        if not self._merge_reuse_cuts(sorted_cuts, main_cut, episode_id):
            return False, "合并Cut文件失败"

        # 更新配置
        if "reuse_cuts" not in self.project_config:
            self.project_config["reuse_cuts"] = []

        self.project_config["reuse_cuts"].append(reuse_cut.to_dict())

        # 保存配置（自动更新注册表）
        if not self.save_config():
            return False, "保存配置失败"

        return True, f"成功创建兼用卡: {'_'.join(sorted_cuts)}"

    def _merge_reuse_cuts(self, sorted_cuts: List[str], main_cut: str, episode_id: Optional[str]) -> bool:
        """合并兼用卡文件"""
        try:
            base_path = self.project_base / episode_id if episode_id else self.project_base
            main_path = base_path / "01_vfx" / main_cut

            # 合并其他Cut到主Cut
            for cut in sorted_cuts[1:]:
                cut_path = base_path / "01_vfx" / cut
                if cut_path.exists():
                    # 移动文件
                    for item in cut_path.iterdir():
                        if item.is_file():
                            dst = main_path / item.name
                            if not dst.exists():
                                shutil.move(str(item), str(dst))
                        elif item.is_dir():
                            dst_dir = main_path / item.name
                            if not dst_dir.exists():
                                shutil.move(str(item), str(dst_dir))
                            else:
                                for sub_item in item.iterdir():
                                    dst_sub = dst_dir / sub_item.name
                                    if not dst_sub.exists():
                                        shutil.move(str(sub_item), str(dst_sub))

                    # 删除空目录
                    try:
                        shutil.rmtree(cut_path)
                    except Exception as e:
                        print(f"删除文件夹失败 {cut_path}: {e}")

            # 重命名AEP文件
            self._rename_reuse_aep(main_path, sorted_cuts, episode_id)

            return True

        except Exception as e:
            print(f"合并兼用卡失败: {e}")
            return False

    def _rename_reuse_aep(self, main_path: Path, sorted_cuts: List[str], episode_id: Optional[str]):
        """重命名兼用卡的AEP文件"""
        proj_name = self.project_base.name
        cuts_str = "_".join(sorted_cuts)

        for aep_file in main_path.glob("*.aep"):
            if cuts_str not in aep_file.stem:
                version = extract_version_from_filename(aep_file.stem)
                version_str = f"_v{version}" if version is not None else "_v0"

                ep_part = f"{episode_id.upper()}_" if episode_id else ""
                new_name = f"{proj_name}_{ep_part}{cuts_str}{version_str}{aep_file.suffix}"
                new_path = aep_file.parent / new_name

                if not new_path.exists():
                    aep_file.rename(new_path)

    def get_reuse_cut_for_cut(self, cut_id: str) -> Optional[ReuseCut]:
        """获取包含指定Cut的兼用卡"""
        if not self.project_config:
            return None

        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.contains_cut(cut_id):
                return cut
        return None

    # ==================== 工具方法 ====================

    def get_next_version(self, target_dir: Path, pattern: str) -> int:
        """获取下一个版本号"""
        if not target_dir.exists():
            return 1

        max_version = 0
        for file in target_dir.iterdir():
            version = extract_version_from_filename(file.stem)
            if version is not None and file.stem.startswith(pattern):
                max_version = max(max_version, version)

        return max_version + 1

    def get_all_episodes(self) -> List[str]:
        """获取所有Episode ID列表"""
        if not self.project_config:
            return []

        episodes = self.project_config.get("episodes", {})
        return sorted(episodes.keys())

    def get_project_info(self) -> Dict[str, Any]:
        """获取项目信息摘要"""
        if not self.project_config:
            return {}

        episodes = self.project_config.get("episodes", {})
        total_cuts = sum(len(cuts) for cuts in episodes.values())

        if self.project_config.get("no_episode"):
            total_cuts = len(self.project_config.get("cuts", []))

        return {
            "project_name": self.project_config.get("project_name"),
            "display_name": self.project_config.get("project_display_name"),
            "created_time": self.project_config.get("created_time"),
            "last_modified": self.project_config.get("last_modified"),
            "no_episode": self.project_config.get("no_episode"),
            "episode_count": len(episodes),
            "total_cuts": total_cuts,
            "reuse_cuts": len(self.project_config.get("reuse_cuts", []))
        }