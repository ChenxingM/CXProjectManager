# -*- coding: utf-8 -*-
"""
常量定义模块 - 完整版本
"""

import re
from enum import Enum
from typing import List

# ================================ 文件扩展名 ================================ #

# 图片文件扩展名
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.psd', '.tiff', '.bmp', '.gif', '.tga', '.exr', '.dpx'}

# 视频文件扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm'}

# 3D文件扩展名
THREED_EXTENSIONS = {
    '.ma', '.mb',  # Maya
    '.max', '.3ds',  # 3ds Max
    '.blend',  # Blender
    '.c4d',  # Cinema 4D
    '.fbx', '.obj', '.dae',  # 通用格式
    '.abc',  # Alembic
    '.usd', '.usda', '.usdc',  # USD
    '.pld'  # 特殊格式
}

# ================================ 正则表达式 ================================ #

# 版本号正则表达式
VERSION_PATTERN = re.compile(r'_[TVtv](\d+)(?:\.\w+)?$')

# Cut编号正则表达式（支持数字+字母后缀）
CUT_PATTERN = re.compile(r'^(\d+)([A-Za-z]?)$')

# ================================ 文件名常量 ================================ #

# 项目注册文件名
PROJECT_REGISTRY_FILE = "project_registry.json"
PROJECT_SETTINGS_DIR = "_proj_settings"

# ================================ 枚举定义 ================================ #

class EpisodeType(Enum):
    """Episode 类型枚举"""
    EP = "ep"
    PV = "pv"
    OP = "op"
    ED = "ed"
    SP = "sp"
    OVA = "ova"
    CM = "cm"
    SV = "sv"
    EX = "ex"
    NC = "nc"

    @classmethod
    def get_all_types(cls) -> List[str]:
        """获取所有类型"""
        return [t.value for t in cls]

    @classmethod
    def get_special_types(cls) -> List[str]:
        """获取特殊类型（非 ep）"""
        return [t.value for t in cls if t != cls.EP]


class MaterialType:
    """素材类型定义"""
    BG = "bg"
    CELL = "cell"
    CG_3D = "3dcg"
    TIMESHEET = "timesheet"
    AEP = "aep"