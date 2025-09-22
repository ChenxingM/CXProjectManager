# -*- coding: utf-8 -*-
"""
工具函数模块 - 完整版本
"""

import shutil
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .constants import VERSION_PATTERN, CUT_PATTERN, IMAGE_EXTENSIONS
from .models import FileInfo


def zero_pad(number: int, width: int = 3) -> str:
    """数字补零"""
    return str(number).zfill(width)


def ensure_dir(path: Path) -> None:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)


def copy_file_safe(src: Path, dst: Path) -> bool:
    """安全复制文件"""
    try:
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"复制文件失败: {e}")
        return False


def open_in_file_manager(path: Path) -> None:
    """在文件管理器中打开路径"""
    if not path or not path.exists():
        return

    system = platform.system()
    try:
        if system == "Windows":
            if path.is_file():
                subprocess.run(["explorer", "/select,", str(path)])
            else:
                subprocess.run(["explorer", str(path)])
        elif system == "Darwin":  # macOS
            if path.is_file():
                subprocess.run(["open", "-R", str(path)])
            else:
                subprocess.run(["open", str(path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(path.parent if path.is_file() else path)])
    except Exception as e:
        print(f"打开文件管理器失败: {e}")


def extract_version_from_filename(filename: str) -> Optional[int]:
    """从文件名中提取版本号（支持不区分大小写）"""
    if "_v0" in filename.lower():
        return 0
    match = VERSION_PATTERN.search(filename)
    return int(match.group(1)) if match else None


def extract_version_string_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取完整版本字符串（如v1, V2, p3, f1等，支持不区分大小写）"""
    # 查找最后一个_后跟字母和数字的模式
    import re
    pattern = re.compile(r'_([a-zA-Z])(\d+)(?:\.\w+)?$')
    match = pattern.search(filename)
    if match:
        prefix = match.group(1).lower()  # 转为小写进行统一处理
        number = match.group(2)
        return f"{prefix}{number}"

    # 处理特殊的v0情况
    if "_v0" in filename.lower():
        return "v0"

    return None


def format_file_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def get_file_info(path: Path) -> FileInfo:
    """获取文件信息"""
    stat = path.stat()
    is_aep = path.suffix.lower() == '.aep'

    # 检查是否是兼用cut文件
    is_reuse_cut = False
    if path.stem.count('_') > 3:
        parts = path.stem.split('_')
        consecutive_nums = sum(1 for part in parts if part.isdigit() and len(part) == 3)
        is_reuse_cut = consecutive_nums > 1

    return FileInfo(
        path=path,
        name=path.name,
        version=extract_version_from_filename(path.stem),
        modified_time=datetime.fromtimestamp(stat.st_mtime),
        size=stat.st_size if path.is_file() else 0,
        is_folder=path.is_dir(),
        is_aep=is_aep,
        is_reuse_cut=is_reuse_cut
    )


def get_png_seq_info(png_seq_path: Path) -> FileInfo:
    """获取PNG序列文件夹信息"""
    stat = png_seq_path.stat()
    png_files = sorted(png_seq_path.glob("*.png"))
    first_png = png_files[0] if png_files else None

    return FileInfo(
        path=png_seq_path,
        name=f"{png_seq_path.name} ({len(png_files)} frames)" if png_files else png_seq_path.name,
        modified_time=datetime.fromtimestamp(stat.st_mtime),
        size=0,
        is_folder=True,
        is_png_seq=True,
        first_png=first_png
    )


def parse_cut_id(cut_id: str) -> Tuple[int, str]:
    """解析Cut编号"""
    match = CUT_PATTERN.match(cut_id)
    if match:
        return int(match.group(1)), match.group(2)
    try:
        return int(cut_id), ""
    except ValueError:
        raise ValueError(f"无效的Cut编号: {cut_id}")


def format_cut_id(num: int, letter: str = "") -> str:
    """格式化Cut编号"""
    return f"{zero_pad(num, 3)}{letter}"