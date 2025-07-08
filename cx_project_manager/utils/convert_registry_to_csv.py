#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将project_registry.json转换为CSV格式供Bridge读取
"""

import json
import csv
import os
from pathlib import Path
from typing import Optional, cast


def convert_registry_to_csv(project_base: Optional[Path] = None) -> bool:
    """将JSON注册表转换为CSV格式"""

    # 路径配置
    json_path = Path(project_base) / 'project_registry.json'
    csv_path = Path(project_base) / 'project_registry.csv'

    # 读取JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取JSON失败: {e}")
        return False

    # 写入CSV
    try:
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow(['project_name', 'project_path', 'no_episode', 'last_accessed'])

            # 写入数据
            for project_name, project_info in data.items():
                writer.writerow([
                    project_name,
                    project_info.get('project_path', ''),
                    'true' if project_info.get('no_episode', False) else 'false',
                    project_info.get('last_accessed', '')
                ])

        print(f"成功创建CSV文件: {csv_path}")
        return True

    except Exception as e:
        print(f"写入CSV失败: {e}")
        return False


def watch_and_convert():
    """监视JSON文件变化并自动转换"""
    json_path = Path("E:/3_Projects/_proj_settings/project_registry.json")
    csv_path = Path("E:/3_Projects/_proj_settings/project_registry.csv")

    # 获取JSON文件的修改时间
    if not json_path.exists():
        print(f"JSON文件不存在: {json_path}")
        return

    json_mtime = json_path.stat().st_mtime

    # 检查CSV是否需要更新
    if csv_path.exists():
        csv_mtime = csv_path.stat().st_mtime
        if csv_mtime >= json_mtime:
            print("CSV文件已是最新")
            return

    # 执行转换
    convert_registry_to_csv()


if __name__ == "__main__":
    watch_and_convert()

# from convert_registry_to_csv import convert_registry_to_csv
# convert_registry_to_csv()