# -*- coding: utf-8 -*-
"""文件浏览器功能混入类"""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont

from cx_project_manager.utils.models import FileInfo, ReuseCut
from cx_project_manager.utils.utils import open_in_file_manager, get_file_info, get_png_seq_info
from cx_project_manager.utils.constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS


class BrowserMixin:
    """文件浏览器相关功能"""

    # 需要在主类中定义的属性
    project_base: Optional[Path]
    project_config: Optional[dict]
    project_manager: any
    browser_tree: QTreeWidget
    txt_project_stats: any
    txt_cut_search: any
    file_tabs: any
    file_lists: dict
    lbl_current_cut: any
    current_cut_id: any
    current_episode_id: any
    current_path: any

    def _update_project_stats(self):
        """更新项目统计信息"""
        if not self.project_config:
            return

        stats_lines = []
        stats_lines.append(f"项目名称: {self.project_config.get('project_name', 'Unknown')}")
        stats_lines.append(f"创建时间: {self.project_config.get('created_time', 'Unknown')[:10]}")
        stats_lines.append(f"最后修改: {self.project_config.get('last_modified', 'Unknown')[:10]}")
        stats_lines.append("")

        reuse_cuts = self.project_config.get("reuse_cuts", [])
        if reuse_cuts:
            stats_lines.append(f"兼用卡数量: {len(reuse_cuts)}")
            total_reuse_cuts = sum(len(cut["cuts"]) for cut in reuse_cuts)
            stats_lines.append(f"兼用Cut总数: {total_reuse_cuts}")
            stats_lines.append("")

        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            stats_lines.append(f"模式: 单集/PV 模式")
            stats_lines.append(f"根目录 Cut 数: {len(cuts)}")

            episodes = self.project_config.get("episodes", {})
            if episodes:
                special_count = sum(len(cuts) for cuts in episodes.values())
                stats_lines.append(f"特殊 Episode 数: {len(episodes)}")
                stats_lines.append(f"特殊 Episode 内 Cut 数: {special_count}")
                stats_lines.append("")
                stats_lines.append("特殊 Episode 详情:")
                for ep_id in sorted(episodes.keys()):
                    cut_count = len(episodes[ep_id])
                    stats_lines.append(f"  {ep_id}: {cut_count} cuts" if cut_count > 0 else f"  {ep_id}: (空)")
        else:
            episodes = self.project_config.get("episodes", {})
            total_cuts = sum(len(cuts) for cuts in episodes.values())

            stats_lines.append(f"模式: Episode 模式")
            stats_lines.append(f"Episode 总数: {len(episodes)}")
            stats_lines.append(f"Cut 总数: {total_cuts}")

            if episodes:
                stats_lines.append("")
                stats_lines.append("Episode 详情:")
                for ep_id in sorted(episodes.keys()):
                    cut_count = len(episodes[ep_id])
                    stats_lines.append(f"  {ep_id}: {cut_count} cuts" if cut_count > 0 else f"  {ep_id}: (空)")

        if reuse_cuts:
            stats_lines.append("")
            stats_lines.append("兼用卡详情:")
            for cut_data in reuse_cuts:
                cut = ReuseCut.from_dict(cut_data)
                ep_info = f" ({cut.episode_id})" if cut.episode_id else ""
                stats_lines.append(f"  {cut.get_display_name()}{ep_info}")

        self.txt_project_stats.setText("\n".join(stats_lines))

    def _update_browser_tree(self):
        """更新浏览器的Episode/Cut树"""
        self.browser_tree.clear()

        if not self.project_config:
            return

        # 获取兼用卡信息
        reuse_cuts_map = {}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.episode_id:
                for cut_id in cut.cuts:
                    reuse_cuts_map[f"{cut.episode_id}:{cut_id}"] = cut
            else:
                for cut_id in cut.cuts:
                    reuse_cuts_map[f"root:{cut_id}"] = cut

        # 单集模式
        if self.project_config.get("no_episode", False):
            cuts = self.project_config.get("cuts", [])
            if cuts:
                root_item = QTreeWidgetItem(["根目录 Cuts"])
                root_item.setData(0, Qt.UserRole, {"type": "root"})
                self.browser_tree.addTopLevelItem(root_item)

                for cut_id in sorted(cuts):
                    key = f"root:{cut_id}"
                    if key in reuse_cuts_map:
                        cut = reuse_cuts_map[key]
                        display_name = f"{cut_id} [兼用卡: {cut.get_display_name()}]"
                        item = QTreeWidgetItem([display_name])
                        item.setForeground(0, QBrush(QColor("#FF9800")))
                    else:
                        item = QTreeWidgetItem([cut_id])

                    item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": None})
                    root_item.addChild(item)

                root_item.setExpanded(True)

            # 特殊Episodes
            episodes = self.project_config.get("episodes", {})
            if episodes:
                for ep_id in sorted(episodes.keys()):
                    ep_item = QTreeWidgetItem([f"📁 {ep_id}"])
                    ep_item.setData(0, Qt.UserRole, {"episode": ep_id})
                    self.browser_tree.addTopLevelItem(ep_item)

                    for cut_id in sorted(episodes[ep_id]):
                        key = f"{ep_id}:{cut_id}"
                        if key in reuse_cuts_map:
                            cut = reuse_cuts_map[key]
                            display_name = f"{cut_id} [兼用卡: {cut.get_display_name()}]"
                            cut_item = QTreeWidgetItem([display_name])
                            cut_item.setForeground(0, QBrush(QColor("#FF9800")))
                        else:
                            cut_item = QTreeWidgetItem([cut_id])

                        cut_item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": ep_id})
                        ep_item.addChild(cut_item)

                    ep_item.setExpanded(True)
        else:
            # 标准模式
            episodes = self.project_config.get("episodes", {})
            for ep_id in sorted(episodes.keys()):
                ep_item = QTreeWidgetItem([ep_id])
                ep_item.setData(0, Qt.UserRole, {"episode": ep_id})
                self.browser_tree.addTopLevelItem(ep_item)

                for cut_id in sorted(episodes[ep_id]):
                    key = f"{ep_id}:{cut_id}"
                    if key in reuse_cuts_map:
                        cut = reuse_cuts_map[key]
                        display_name = f"{cut_id} [兼用卡: {cut.get_display_name()}]"
                        cut_item = QTreeWidgetItem([display_name])
                        cut_item.setForeground(0, QBrush(QColor("#FF9800")))
                    else:
                        cut_item = QTreeWidgetItem([cut_id])

                    cut_item.setData(0, Qt.UserRole, {"cut": cut_id, "episode": ep_id})
                    ep_item.addChild(cut_item)

                ep_item.setExpanded(True)

        # 如果搜索框有内容，重新应用搜索
        if self.txt_cut_search and self.txt_cut_search.text().strip():
            self._on_cut_search_changed(self.txt_cut_search.text())

    def _on_browser_tree_clicked(self, item: QTreeWidgetItem):
        """处理浏览器树的点击事件"""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if "cut" in data and data["cut"]:
            self.current_cut_id = data["cut"]
            self.current_episode_id = data.get("episode")
            self._load_cut_files(self.current_cut_id, self.current_episode_id)
            self._update_current_path_label()
        else:
            self._clear_file_lists()
            self.current_cut_id = None
            self.current_episode_id = data.get("episode")
            if self.current_episode_id:
                self.lbl_current_cut.setText(f"当前位置：{self.current_episode_id} (请选择具体的 Cut)")
            elif data.get("type") == "root":
                self.lbl_current_cut.setText("当前位置：根目录 (请选择具体的 Cut)")

    def _on_file_tab_changed(self, index: int):
        """处理文件Tab切换"""
        self._update_current_path_label()

    def _update_current_path_label(self):
        """更新当前路径标签"""
        if not self.project_base or not self.current_cut_id:
            self.lbl_current_cut.setText("当前位置：未选择")
            self.current_path = None
            return

        current_index = self.file_tabs.currentIndex()
        tab_names = ["VFX", "Cell", "BG", "Render", "3DCG"]

        if current_index < 0 or current_index >= len(tab_names):
            return

        tab_name = tab_names[current_index]

        # 检查是否是兼用卡
        reuse_cut = self.project_manager.get_reuse_cut_for_cut(self.current_cut_id)
        if reuse_cut:
            actual_cut_id = reuse_cut.main_cut
            display_cut_id = reuse_cut.get_display_name()
        else:
            actual_cut_id = self.current_cut_id
            display_cut_id = self.current_cut_id

        # 构建路径
        if self.current_episode_id:
            if tab_name in ["VFX", "Cell", "BG"]:
                path = self.project_base / self.current_episode_id / "01_vfx" / actual_cut_id
                if tab_name == "Cell":
                    path = path / "cell"
                elif tab_name == "BG":
                    path = path / "bg"
            elif tab_name == "Render":
                path = self.project_base / "06_render" / self.current_episode_id / actual_cut_id
            elif tab_name == "3DCG":
                path = self.project_base / self.current_episode_id / "02_3dcg" / actual_cut_id
        else:
            if tab_name in ["VFX", "Cell", "BG"]:
                path = self.project_base / "01_vfx" / actual_cut_id
                if tab_name == "Cell":
                    path = path / "cell"
                elif tab_name == "BG":
                    path = path / "bg"
            elif tab_name == "Render":
                path = self.project_base / "06_render" / actual_cut_id
            elif tab_name == "3DCG":
                path = self.project_base / "02_3dcg" / actual_cut_id

        self.current_path = path
        path_str = str(path).replace("\\", "/")

        # 如果路径太长，显示缩略版本
        if len(path_str) > 100:
            relative_path = path.relative_to(self.project_base.parent)
            display_path = f".../{relative_path}"
        else:
            display_path = path_str

        if reuse_cut:
            self.lbl_current_cut.setText(f"📁 {tab_name} [兼用卡 {display_cut_id}]: {display_path}")
        else:
            self.lbl_current_cut.setText(f"📁 {tab_name}: {display_path}")
        self.lbl_current_cut.setToolTip(path_str)

    def _show_path_context_menu(self, position):
        """显示路径标签的右键菜单"""
        if not self.current_path:
            return

        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)

        act_copy = QAction("复制路径", self)
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(str(self.current_path)))
        menu.addAction(act_copy)

        act_open = QAction("在文件管理器中打开", self)
        act_open.triggered.connect(lambda: open_in_file_manager(self.current_path))
        menu.addAction(act_open)

        menu.exec_(self.lbl_current_cut.mapToGlobal(position))

    def _load_cut_files(self, cut_id: str, episode_id: Optional[str] = None):
        """加载指定Cut的文件列表"""
        self._clear_file_lists()

        if not self.project_base:
            return

        # 检查是否是兼用卡
        reuse_cut = self.project_manager.get_reuse_cut_for_cut(cut_id)
        actual_cut_id = reuse_cut.main_cut if reuse_cut else cut_id

        # 确定路径
        if episode_id:
            vfx_path = self.project_base / episode_id / "01_vfx" / actual_cut_id
            render_path = self.project_base / "06_render" / episode_id / actual_cut_id
            cg_path = self.project_base / episode_id / "02_3dcg" / actual_cut_id
        else:
            vfx_path = self.project_base / "01_vfx" / actual_cut_id
            render_path = self.project_base / "06_render" / actual_cut_id
            cg_path = self.project_base / "02_3dcg" / actual_cut_id

        # 加载文件
        self._load_vfx_files(vfx_path)
        self._load_cell_files(vfx_path / "cell")
        self._load_bg_files(vfx_path / "bg")
        self._load_render_files(render_path)
        self._load_cg_files(cg_path)

        self._update_file_tab_titles()

    def _load_vfx_files(self, vfx_path: Path):
        """加载VFX文件"""
        list_widget = self.file_lists["vfx"]
        if vfx_path.exists():
            # 获取所有AEP文件
            files = []
            for file in vfx_path.glob("*.aep"):
                file_info = get_file_info(file)
                # 检查是否有锁定文件
                lock_file = file.parent / f".{file.name}.lock"
                if lock_file.exists():
                    file_info.is_locked = True
                files.append(file_info)

            # 按修改时间排序
            files.sort(key=lambda f: f.modified_time, reverse=True)

            # 添加到列表
            for file_info in files:
                if hasattr(file_info, 'is_locked') and file_info.is_locked:
                    # 在文件名前加锁定图标
                    original_name = file_info.name
                    file_info.name = f"🔒 {original_name}"
                list_widget.add_file_item(file_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 AEP 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _load_cell_files(self, cell_path: Path):
        """加载Cell文件"""
        list_widget = self.file_lists["cell"]
        if not cell_path.exists():
            return

        folders = []
        for folder in cell_path.iterdir():
            if folder.is_dir():
                file_info = get_file_info(folder)
                if file_info.version is not None:
                    # 检查是否有锁定文件
                    lock_file = folder.parent / f".{folder.name}.lock"
                    if lock_file.exists():
                        file_info.is_locked = True
                        file_info.name = f"🔒 {file_info.name}"
                    folders.append(file_info)

        folders.sort(key=lambda f: f.modified_time, reverse=True)

        for folder_info in folders:
            list_widget.add_file_item(folder_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 Cell 文件夹)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _load_bg_files(self, bg_path: Path):
        """加载BG文件"""
        list_widget = self.file_lists["bg"]
        if not bg_path.exists():
            return

        files = []
        for file in bg_path.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                file_info = get_file_info(file)
                # 检查是否有锁定文件
                lock_file = file.parent / f".{file.name}.lock"
                if lock_file.exists():
                    file_info.is_locked = True
                    file_info.name = f"🔒 {file_info.name}"
                files.append(file_info)

        files.sort(key=lambda f: f.modified_time, reverse=True)

        for file_info in files:
            list_widget.add_file_item(file_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 BG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _load_render_files(self, render_path: Path):
        """加载渲染文件"""
        list_widget = self.file_lists["render"]

        if not render_path.exists():
            no_render_info = FileInfo(
                path=render_path,
                name="未渲染",
                modified_time=datetime.now(),
                size=0,
                is_folder=False,
                is_no_render=True
            )
            list_widget.add_file_item(no_render_info)
            return

        render_items = []
        has_any_render = False

        # PNG序列
        png_path = render_path / "png_seq"
        if png_path.exists() and any(png_path.glob("*.png")):
            render_items.append(get_png_seq_info(png_path))
            has_any_render = True

        # ProRes视频
        prores_path = render_path / "prores"
        if prores_path.exists():
            for file in prores_path.glob("*.mov"):
                file_info = get_file_info(file)
                # 检查是否有锁定文件
                lock_file = file.parent / f".{file.name}.lock"
                if lock_file.exists():
                    file_info.is_locked = True
                    file_info.name = f"🔒 {file_info.name}"
                render_items.append(file_info)
                has_any_render = True

        # MP4视频
        mp4_path = render_path / "mp4"
        if mp4_path.exists():
            for file in mp4_path.glob("*.mp4"):
                file_info = get_file_info(file)
                # 检查是否有锁定文件
                lock_file = file.parent / f".{file.name}.lock"
                if lock_file.exists():
                    file_info.is_locked = True
                    file_info.name = f"🔒 {file_info.name}"
                render_items.append(file_info)
                has_any_render = True

        if has_any_render:
            render_items.sort(key=lambda f: f.modified_time, reverse=True)

        for item_info in render_items:
            list_widget.add_file_item(item_info)

    def _load_cg_files(self, cg_path: Path):
        """加载3DCG文件"""
        list_widget = self.file_lists["3dcg"]
        if not cg_path.exists():
            return

        files = []
        for item in cg_path.rglob("*"):
            if item.is_file():
                file_info = get_file_info(item)
                # 检查是否有锁定文件
                lock_file = item.parent / f".{item.name}.lock"
                if lock_file.exists():
                    file_info.is_locked = True
                    file_info.name = f"🔒 {file_info.name}"
                files.append(file_info)

        files.sort(key=lambda f: f.modified_time, reverse=True)

        for file_info in files:
            list_widget.add_file_item(file_info)

        if list_widget.count() == 0:
            item = QListWidgetItem("(没有 3DCG 文件)")
            item.setData(Qt.UserRole, None)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

    def _update_file_tab_titles(self):
        """更新文件Tab的标题"""
        tab_info = [
            (0, "VFX", self.file_lists["vfx"]),
            (1, "Cell", self.file_lists["cell"]),
            (2, "BG", self.file_lists["bg"]),
            (3, "Render", self.file_lists["render"]),
            (4, "3DCG", self.file_lists["3dcg"]),
        ]

        for index, name, list_widget in tab_info:
            count = list_widget.count()
            if count > 0 and list_widget.item(0).data(Qt.UserRole) is not None:
                self.file_tabs.setTabText(index, f"{name} ({count})")
            else:
                self.file_tabs.setTabText(index, name)

    def _clear_file_lists(self):
        """清空所有文件列表"""
        for list_widget in self.file_lists.values():
            list_widget.clear()

        for i, name in enumerate(["VFX", "Cell", "BG", "Render", "3DCG"]):
            self.file_tabs.setTabText(i, name)

    def _on_file_item_double_clicked(self, item: QListWidgetItem):
        """处理文件项目双击"""
        file_path = item.data(Qt.UserRole)
        if not file_path:
            return

        path = Path(file_path)
        if not path.exists():
            return

        if path.suffix.lower() in VIDEO_EXTENSIONS:
            self._play_video(path)
        else:
            open_in_file_manager(path)

    def _play_video(self, video_path: Path):
        """使用默认播放器播放视频"""
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(str(video_path))
            elif system == "Darwin":
                subprocess.run(["open", str(video_path)])
            else:
                subprocess.run(["xdg-open", str(video_path)])
        except Exception as e:
            print(f"播放视频失败: {e}")

    def _on_cut_search_changed(self, text: str):
        """处理Cut搜索框内容变化"""
        search_text = text.strip().lower()

        if not search_text:
            self._show_all_tree_items()
            self.browser_tree.setHeaderLabel("选择要浏览的 Cut")
            return

        match_count = 0
        first_match = None

        # 获取兼用卡信息
        reuse_cuts_by_location = {"root": [], "episodes": {}}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.episode_id:
                if cut.episode_id not in reuse_cuts_by_location["episodes"]:
                    reuse_cuts_by_location["episodes"][cut.episode_id] = []
                reuse_cuts_by_location["episodes"][cut.episode_id].append(cut)
            else:
                reuse_cuts_by_location["root"].append(cut)

        def search_items(item: QTreeWidgetItem):
            nonlocal match_count, first_match
            item_text = item.text(0).lower()

            data = item.data(0, Qt.UserRole)
            cut_id = data.get("cut") if data else None
            episode_id = data.get("episode") if data else None

            has_match = False
            if search_text in item_text:
                has_match = True
            elif search_text.isdigit() and cut_id:
                if search_text in cut_id:
                    has_match = True

                # 检查兼用卡
                if episode_id:
                    for cut in reuse_cuts_by_location["episodes"].get(episode_id, []):
                        if cut.contains_cut(cut_id):
                            for reuse_cut in cut.cuts:
                                if search_text in reuse_cut:
                                    has_match = True
                                    break
                else:
                    for cut in reuse_cuts_by_location["root"]:
                        if cut.contains_cut(cut_id):
                            for reuse_cut in cut.cuts:
                                if search_text in reuse_cut:
                                    has_match = True
                                    break

            has_child_match = False

            for i in range(item.childCount()):
                child = item.child(i)
                if search_items(child):
                    has_child_match = True

            should_show = has_match or has_child_match
            item.setHidden(not should_show)

            if has_match and item.childCount() == 0:
                item.setForeground(0, QBrush(QColor("#4CAF50")))
                item.setFont(0, QFont("MiSans", -1, QFont.Bold))
                match_count += 1
                if first_match is None:
                    first_match = item
            else:
                # 恢复原始样式
                if cut_id:
                    is_reuse = False
                    if episode_id:
                        for cut in reuse_cuts_by_location["episodes"].get(episode_id, []):
                            if cut.contains_cut(cut_id):
                                is_reuse = True
                                break
                    else:
                        for cut in reuse_cuts_by_location["root"]:
                            if cut.contains_cut(cut_id):
                                is_reuse = True
                                break

                    if is_reuse:
                        item.setForeground(0, QBrush(QColor("#FF9800")))
                    else:
                        item.setForeground(0, QBrush())
                else:
                    item.setForeground(0, QBrush())
                item.setFont(0, QFont())

            if has_child_match:
                item.setExpanded(True)

            return should_show

        for i in range(self.browser_tree.topLevelItemCount()):
            search_items(self.browser_tree.topLevelItem(i))

        if match_count > 0:
            self.browser_tree.setHeaderLabel(f"搜索结果: {match_count} 个Cut")
        else:
            self.browser_tree.setHeaderLabel("没有找到匹配的Cut")

    def _select_first_match(self):
        """选择第一个匹配的Cut"""

        def find_first_visible_leaf(item: QTreeWidgetItem):
            if not item.isHidden():
                if item.childCount() == 0:
                    return item
                for i in range(item.childCount()):
                    result = find_first_visible_leaf(item.child(i))
                    if result:
                        return result
            return None

        for i in range(self.browser_tree.topLevelItemCount()):
            result = find_first_visible_leaf(self.browser_tree.topLevelItem(i))
            if result:
                self.browser_tree.setCurrentItem(result)
                self._on_browser_tree_clicked(result)
                break

    def _show_all_tree_items(self):
        """显示所有树项目"""
        reuse_cuts_by_location = {"root": [], "episodes": {}}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            if cut.episode_id:
                if cut.episode_id not in reuse_cuts_by_location["episodes"]:
                    reuse_cuts_by_location["episodes"][cut.episode_id] = []
                reuse_cuts_by_location["episodes"][cut.episode_id].append(cut)
            else:
                reuse_cuts_by_location["root"].append(cut)

        def show_items(item: QTreeWidgetItem):
            item.setHidden(False)

            data = item.data(0, Qt.UserRole)
            cut_id = data.get("cut") if data else None
            episode_id = data.get("episode") if data else None

            if cut_id:
                is_reuse = False
                if episode_id:
                    for cut in reuse_cuts_by_location["episodes"].get(episode_id, []):
                        if cut.contains_cut(cut_id):
                            is_reuse = True
                            break
                else:
                    for cut in reuse_cuts_by_location["root"]:
                        if cut.contains_cut(cut_id):
                            is_reuse = True
                            break

                if is_reuse:
                    item.setForeground(0, QBrush(QColor("#FF9800")))
                else:
                    item.setForeground(0, QBrush())
            else:
                item.setForeground(0, QBrush())

            item.setFont(0, QFont())

            for i in range(item.childCount()):
                show_items(item.child(i))

        for i in range(self.browser_tree.topLevelItemCount()):
            show_items(self.browser_tree.topLevelItem(i))

        self.browser_tree.setHeaderLabel("选择要浏览的 Cut")

    def _focus_cut_search(self):
        """聚焦到Cut搜索框"""
        if self.txt_cut_search:
            self.tabs.setCurrentIndex(1)
            self.txt_cut_search.setFocus()
            self.txt_cut_search.selectAll()