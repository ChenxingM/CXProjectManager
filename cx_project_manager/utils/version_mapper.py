# -*- coding: utf-8 -*-
"""
CXProjectManager 全局版本映射管理器
用于统一管理整个应用程序中所有文件类型的版本标签映射
这是应用程序级别的全局设置，所有项目共享同一套版本映射规则
"""

from typing import Dict, Optional


class VersionMapper:
    """CXProjectManager 全局版本映射管理器"""

    # 版本映射配置
    VERSION_MAPPING = {
        # 特定版本号映射
        "V0": "假本摄",
        # 字母前缀映射（用于v1, v2, V1, V2等）
        "G": "线摄G{}",
        "S": "线摄S{}",
        "T": "T摄T{}",
        "P": "CG摄P{}",
        "V": "本摄V{}",
    }

    def __init__(self):
        """初始化版本映射器"""
        # 使用类级别的固定映射配置
        self.version_mapping = self.VERSION_MAPPING.copy()

    def get_version_label(self, version_str: str) -> str:
        """
        根据版本号生成显示标签

        Args:
            version_str: 版本字符串，如 "v1", "V2", "P3" 等

        Returns:
            str: 映射后的显示标签，如 "本摄V1", "T摄" 等
        """
        if not version_str or version_str == "未知版本":
            return ""

        # 先检查特定版本号映射（不区分大小写）
        for mapping_key, mapping_value in self.version_mapping.items():
            if version_str.lower() == mapping_key.lower():
                return mapping_value

        # 检查字母前缀映射（不区分大小写）
        if len(version_str) >= 2:
            prefix = version_str[0]  # 获取前缀字母 (v, V, p, f等)
            number_part = version_str[1:]  # 获取数字部分

            # 查找匹配的前缀（不区分大小写）
            for mapping_key, mapping_value in self.version_mapping.items():
                if len(mapping_key) == 1 and prefix.lower() == mapping_key.lower():
                    template = mapping_value
                    if "{}" in template:
                        return template.format(number_part)
                    else:
                        return template

        # 如果没有匹配的映射，返回原版本号
        return version_str

    def get_version_mapping(self) -> Dict[str, str]:
        """获取当前版本映射配置"""
        return self.version_mapping.copy()

    @classmethod
    def update_global_mapping(cls, version_mapping: Dict[str, str]):
        """
        更新应用程序级别的版本映射配置
        注意：这会影响所有新创建的映射器实例

        Args:
            version_mapping: 新的版本映射字典
        """
        if version_mapping:
            cls.VERSION_MAPPING.update(version_mapping)

    def get_supported_prefixes(self) -> list:
        """
        获取支持的版本前缀列表

        Returns:
            list: 支持的前缀列表，如 ['v', 'V', 'p', 'P']
        """
        prefixes = []
        for key in self.version_mapping.keys():
            if len(key) == 1:  # 单字母前缀
                prefixes.append(key)
        return sorted(set(prefixes))

    def get_special_versions(self) -> list:
        """
        获取特殊版本号列表（非前缀模式）

        Returns:
            list: 特殊版本号列表，如 ['v0', 'V0']
        """
        special_versions = []
        for key in self.version_mapping.keys():
            if len(key) > 1:  # 完整版本号
                special_versions.append(key)
        return sorted(special_versions)


# 全局版本映射器实例
_global_version_mapper = None


def get_global_version_mapper() -> VersionMapper:
    """
    获取全局版本映射器实例

    Returns:
        VersionMapper: 全局版本映射器实例
    """
    global _global_version_mapper
    if _global_version_mapper is None:
        _global_version_mapper = VersionMapper()
    return _global_version_mapper


def get_version_label_global(version_str: str) -> str:
    """
    全局版本标签获取函数

    Args:
        version_str: 版本字符串

    Returns:
        str: 映射后的显示标签
    """
    mapper = get_global_version_mapper()
    return mapper.get_version_label(version_str)