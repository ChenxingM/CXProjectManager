# -*- coding: utf-8 -*-
"""
数据类定义模块 - 完整版本
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .constants import CUT_PATTERN


@dataclass
class ProjectInfo:
    """项目注册信息"""
    project_name: str
    project_path: str
    config_path: str
    created_time: str
    episode_count: int = 0
    episode_list: List[str] = field(default_factory=list)
    no_episode: bool = False
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectInfo':
        """从字典创建"""
        return cls(**data)


@dataclass
class ProjectPaths:
    """项目路径配置"""
    reference: str = "00_reference_project"
    render: str = "06_render"
    assets: str = "07_master_assets"
    aep_templates: str = "07_master_assets/aep_templates"
    tools: str = "08_tools"
    vfx: str = "01_vfx"
    cg: str = "02_3dcg"
    tmp: str = "98_tmp"
    other: str = "99_other"


@dataclass
class ReuseCut:
    """兼用cut信息"""
    cuts: List[str]
    main_cut: str
    episode_id: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "cuts": self.cuts,
            "main_cut": self.main_cut,
            "episode_id": self.episode_id
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ReuseCut':
        """从字典创建"""
        return cls(
            cuts=data["cuts"],
            main_cut=data["main_cut"],
            episode_id=data.get("episode_id")
        )

    def get_display_name(self) -> str:
        """获取显示名称"""
        return "_".join(self.cuts)

    def contains_cut(self, cut_id: str) -> bool:
        """检查是否包含指定cut"""
        for cut in self.cuts:
            if cut == cut_id:
                return True
            match1 = CUT_PATTERN.match(cut)
            match2 = CUT_PATTERN.match(cut_id)
            if match1 and match2 and match1.group(1) == match2.group(1):
                return True
        return False


@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    name: str
    version: Optional[int] = None
    modified_time: datetime = field(default_factory=datetime.now)
    size: int = 0
    is_folder: bool = False
    is_aep: bool = False
    is_png_seq: bool = False
    first_png: Optional[Path] = None
    is_no_render: bool = False
    is_reuse_cut: bool = False

    @property
    def version_str(self) -> str:
        """获取版本字符串"""
        if self.version is not None:
            if self.is_aep:
                return "T摄" if self.version == 0 else f"本摄V{self.version}"
            else:
                prefix = "V" if "V" in self.name or "v" in self.name else "T"
                return f"{prefix}{self.version}"
        return ""