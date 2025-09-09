# -*- coding: utf-8 -*-
"""
项目管理核心类模块 - 完整版本（带注册表同步）
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import re

from ..utils.models import ProjectPaths, ReuseCut
from ..utils.utils import (
    ensure_dir, copy_file_safe, zero_pad, parse_cut_id, format_cut_id,
    extract_version_from_filename
)


class ProjectManager:
    """项目管理核心类，负责项目的创建、加载、保存等操作"""

    def __init__(self, project_base: Path = None):
        self.project_base = project_base
        self.project_config = None
        self.paths = ProjectPaths()
        # 注册表路径（可以通过配置设置）
        self.registry_path = None

    def set_registry_path(self, registry_path: Path):
        """设置注册表路径"""
        self.registry_path = registry_path

    def _get_registry_path(self) -> Path:
        """获取注册表路径"""
        if self.registry_path:
            return self.registry_path

        # 默认路径：项目基础文件夹的父目录下的 _proj_settings
        if self.project_base:
            parent = self.project_base.parent
            return parent / "_proj_settings" / "project_registry.json"

        # 如果没有项目基础路径，使用默认路径
        return Path("E:/3_Projects/_proj_settings/project_registry.json")

    def _update_registry(self):
        """更新项目注册表"""
        if not self.project_config or not self.project_base:
            return

        registry_path = self._get_registry_path()

        # 确保注册表目录存在
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取现有注册表
        registry_data = {}
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry_data = json.load(f)
            except Exception as e:
                print(f"读取注册表失败: {e}")
                registry_data = {}

        # 获取项目名称
        project_name = self.project_config.get("project_name")
        if not project_name:
            return

        # 更新或创建项目条目
        if project_name not in registry_data:
            # 新项目
            registry_data[project_name] = {
                "project_name": project_name,
                "project_display_name": self.project_config.get("project_display_name", project_name),
                "project_path": str(self.project_base),
                "config_path": str(self.project_base / "project_config.json"),
                "created_time": self.project_config.get("created_time", datetime.now().isoformat()),
                "episode_count": len(self.project_config.get("episodes", {})),
                "episode_list": sorted(self.project_config.get("episodes", {}).keys()),
                "no_episode": self.project_config.get("no_episode", False),
                "last_accessed": datetime.now().isoformat()
            }
        else:
            # 更新现有项目
            registry_data[project_name].update({
                "project_display_name": self.project_config.get("project_display_name", project_name),
                "episode_count": len(self.project_config.get("episodes", {})),
                "episode_list": sorted(self.project_config.get("episodes", {}).keys()),
                "no_episode": self.project_config.get("no_episode", False),
                "last_accessed": datetime.now().isoformat()
            })

        # 保存注册表
        try:
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存注册表失败: {e}")

    def create_project(
            self,
            project_name: str,  # 实际的项目名称（用于文件系统路径，可能包含前缀）
            project_display_name: str,  # 显示名称（用于UI显示，不含前缀）
            base_folder: Path,
            no_episode: bool = False
    ) -> bool:
        """
        创建新项目

        参数:
            project_name: 实际的项目名称，用于创建文件夹路径（如 "24_09_SSSK_PV"）
            project_display_name: 显示名称，用于UI显示（如 "SSSK_PV"）
            base_folder: 项目的基础文件夹
            no_episode: 是否为无Episode模式

        返回:
            bool: 创建是否成功
        """
        # 使用 project_name 创建实际的文件夹路径
        self.project_base = base_folder / project_name
        self._create_project_structure(no_episode)

        self.project_config = {
            "project_name": project_name,  # 实际项目名（文件系统用）
            "project_display_name": project_display_name,  # 显示名称（UI用）
            "project_path": str(self.project_base),
            "no_episode": no_episode,
            "episodes": {},
            "cuts": [],
            "reuse_cuts": [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "paths": self.paths.__dict__
        }

        self.save_config()
        self._create_readme()
        return True

    def _create_readme(self):
        """创建项目说明文件"""
        readme_path = self.project_base / "README.md"
        config = self.project_config

        readme_content = f"""# {config['project_display_name']}

## 项目信息
- **项目名称**: {config['project_display_name']}
- **项目路径名**: {config['project_name']}
- **创建时间**: {config['created_time']}
- **Episode模式**: {'无Episode模式' if config['no_episode'] else '有Episode模式'}

## 目录结构
```
{config['project_name']}/
├── 00_resource/      # 资源文件
├── 01_vfx/          # VFX文件
├── 02_comp/         # 合成文件
├── 03_render/       # 渲染输出
└── project_config.json
```

## 使用说明
1. 所有AEP文件存放在 01_vfx/ 对应的Cut文件夹中
2. 渲染输出保存到 03_render/ 对应的Cut文件夹中
3. 资源文件统一管理在 00_resource/ 目录下
"""

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)

    def load_project(self, project_path: Path) -> bool:
        """加载项目"""
        config_file = project_path / "project_config.json"

        if not config_file.exists():
            return False

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self.project_config = json.load(f)
            self.project_base = project_path

            # 兼容性处理
            if "reuse_cuts" not in self.project_config:
                self.project_config["reuse_cuts"] = self.project_config.get("reuse_cards", [])
                if "reuse_cards" in self.project_config:
                    del self.project_config["reuse_cards"]

            return True
        except Exception as e:
            print(f"加载项目配置失败：{e}")
            return False

    def save_config(self):
        """保存项目配置并更新注册表"""
        if not self.project_base or not self.project_config:
            return

        # 更新修改时间
        self.project_config["last_modified"] = datetime.now().isoformat()

        # 保存项目配置
        config_file = self.project_base / "project_config.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.project_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存项目配置失败: {e}")
            return

        # 同步更新注册表
        self._update_registry()

    def _create_project_structure(self, no_episode: bool):
        """创建项目目录结构"""
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

        for dir_path in dirs:
            ensure_dir(self.project_base / dir_path)

    def create_episode(self, ep_type: str, ep_identifier: str = "") -> Tuple[bool, str]:
        """创建Episode"""
        # 构建 Episode ID
        if ep_type == "ep" and ep_identifier and ep_identifier.isdigit():
            ep_id = f"ep{zero_pad(int(ep_identifier), 2)}"
        elif ep_identifier:
            safe_identifier = re.sub(r'[/\\]', '_', ep_identifier.replace(" ", "_"))
            ep_id = f"{ep_type}_{safe_identifier}" if ep_type and ep_type != ep_identifier.lower() else safe_identifier
        else:
            ep_id = ep_type

        if ep_id in self.project_config.get("episodes", {}):
            return False, f"Episode '{ep_id}' 已存在"

        # 创建目录
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

        ensure_dir(self.project_base / "06_render" / ep_id)

        if "episodes" not in self.project_config:
            self.project_config["episodes"] = {}
        self.project_config["episodes"][ep_id] = []
        self.save_config()  # 这会同时更新注册表

        return True, ep_id

    def create_cut(self, cut_num: str, episode_id: str = None) -> Tuple[bool, str]:
        """创建Cut"""
        try:
            num_part, letter_part = parse_cut_id(cut_num)
            cut_id = format_cut_id(num_part, letter_part)
        except ValueError:
            return False, "请输入有效的 Cut 编号（数字或数字+字母）"

        if self.project_config.get("no_episode", False) and not episode_id:
            if cut_id in self.project_config.get("cuts", []):
                return False, f"Cut {cut_id} 已存在"

            cut_path = self.project_base / "01_vfx" / cut_id
            self._create_cut_structure(cut_path, episode_id=None)

            if "cuts" not in self.project_config:
                self.project_config["cuts"] = []
            self.project_config["cuts"].append(cut_id)
        else:
            if not episode_id:
                return False, "请选择 Episode"

            if episode_id not in self.project_config.get("episodes", {}):
                return False, f"Episode '{episode_id}' 不存在"

            if cut_id in self.project_config["episodes"][episode_id]:
                return False, f"Cut {cut_id} 已存在于 {episode_id}"

            cut_path = self.project_base / episode_id / "01_vfx" / cut_id
            self._create_cut_structure(cut_path, episode_id=episode_id)
            self.project_config["episodes"][episode_id].append(cut_id)

        self.save_config()  # 这会同时更新注册表
        return True, cut_id

    def _create_cut_structure(self, cut_path: Path, episode_id: Optional[str] = None):
        """创建Cut目录结构"""
        for subdir in ["cell", "bg", "prerender"]:
            ensure_dir(cut_path / subdir)

        cut_id = cut_path.name
        proj_name = self.project_base.name

        # 创建render目录
        render_path = (self.project_base / "06_render" / episode_id / cut_id if episode_id
                       else self.project_base / "06_render" / cut_id)

        for subdir in ["png_seq", "prores", "mp4"]:
            ensure_dir(render_path / subdir)

        # 复制AEP模板
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if template_dir.exists():
            for template in template_dir.glob("*.aep"):
                template_stem = template.stem

                if episode_id:
                    ep_part = episode_id.upper()
                    version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"
                    aep_name = f"{proj_name}_{ep_part}_{cut_id}{version_part}{template.suffix}"
                else:
                    version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"
                    aep_name = f"{proj_name}_{cut_id}{version_part}{template.suffix}"

                copy_file_safe(template, cut_path / aep_name)

    def create_reuse_cut(self, cuts: List[str], episode_id: Optional[str] = None) -> Tuple[bool, str]:
        """创建兼用卡"""
        if len(cuts) < 2:
            return False, "兼用卡至少需要2个Cut"

        sorted_cuts = sorted(cuts, key=lambda c: parse_cut_id(c))
        main_cut = sorted_cuts[0]

        reuse_cut = ReuseCut(
            cuts=sorted_cuts,
            main_cut=main_cut,
            episode_id=episode_id
        )

        # 合并文件到主Cut
        base_path = self.project_base / episode_id if episode_id else self.project_base
        main_path = base_path / "01_vfx" / main_cut

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

                try:
                    shutil.rmtree(cut_path)
                except Exception as e:
                    print(f"删除文件夹失败 {cut_path}: {e}")

        # 重命名AEP文件
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

        if "reuse_cuts" not in self.project_config:
            self.project_config["reuse_cuts"] = []

        self.project_config["reuse_cuts"].append(reuse_cut.to_dict())
        self.save_config()  # 这会同时更新注册表

        return True, f"成功创建兼用卡: {cuts_str}"

    def get_reuse_cut_for_cut(self, cut_id: str) -> Optional[ReuseCut]:
        """获取包含指定Cut的兼用卡"""
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.contains_cut(cut_id):
                return cut
        return None

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
        """获取所有 Episode ID 列表"""
        if not self.project_base:
            return []

        episodes = self.project_config.get("episodes", {})
        return sorted(episodes.keys())