# -*- coding: utf-8 -*-
"""版本管理功能混入类"""

import shutil
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QApplication, QProgressDialog, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from cx_project_manager.utils.models import FileInfo
from cx_project_manager.utils.utils import get_file_info
from cx_project_manager.utils.constants import IMAGE_EXTENSIONS


class VersionMixin:
    """版本管理相关功能"""

    # 需要在主类中定义的属性
    project_base: Path
    project_config: dict
    current_cut_id: any
    current_episode_id: any
    file_lists: dict

    def _show_file_context_menu(self, position, file_type: str):
        """显示文件列表的右键菜单"""
        list_widget = self.file_lists[file_type]
        item = list_widget.itemAt(position)
        if not item:
            return

        # 获取文件信息
        user_data = item.data(Qt.UserRole)
        if not user_data:
            return

        # 判断数据类型并获取FileInfo
        if isinstance(user_data, str):
            # 如果是路径字符串，创建FileInfo对象
            file_path = Path(user_data)
            if not file_path.exists():
                return
            file_info = get_file_info(file_path)
            # 检查是否有锁定文件
            lock_file = file_path.parent / f".{file_path.name}.lock"
            if lock_file.exists():
                file_info.is_locked = True
        elif isinstance(user_data, FileInfo):
            # 如果已经是FileInfo对象
            file_info = user_data
        else:
            return

        menu = QMenu(self)

        # 打开文件/文件夹
        act_open = QAction("🚀 打开", self)
        act_open.triggered.connect(lambda: self._on_file_item_double_clicked(item))
        menu.addAction(act_open)

        # 在文件管理器中显示
        act_show = QAction("📂 在文件管理器中显示", self)
        act_show.triggered.connect(lambda: self._open_in_manager(file_info.path.parent))
        menu.addAction(act_show)

        menu.addSeparator()

        # 删除操作
        act_delete = QAction("❌ 删除", self)
        act_delete.triggered.connect(lambda: self._delete_file(file_info, file_type))
        menu.addAction(act_delete)

        # 检查文件是否已锁定
        actual_filename = file_info.name.replace("🔒 ", "") if file_info.name.startswith("🔒 ") else file_info.name
        lock_file = file_info.path.parent / f".{actual_filename}.lock"
        is_locked = lock_file.exists()

        # 如果有版本号，添加版本相关操作
        if file_info.version is not None:
            menu.addSeparator()

            # 锁定/解锁当前版本
            if is_locked:
                act_unlock = QAction(f"🔓 解锁版本 v{file_info.version}", self)
                act_unlock.triggered.connect(lambda: self._unlock_version(file_info, file_type))
                menu.addAction(act_unlock)
            else:
                act_lock = QAction(f"🔒 锁定版本 v{file_info.version}", self)
                act_lock.triggered.connect(lambda: self._lock_version(file_info, file_type))
                menu.addAction(act_lock)

            # 获取所有版本
            all_versions = self._get_all_versions(file_info, file_type)
            if len(all_versions) > 1:
                # 锁定最新版本
                latest_version = max(v.version for v in all_versions)
                latest_file = next(v for v in all_versions if v.version == latest_version)
                latest_filename = latest_file.name.replace("🔒 ", "") if latest_file.name.startswith(
                    "🔒 ") else latest_file.name
                latest_lock_file = latest_file.path.parent / f".{latest_filename}.lock"

                if not latest_lock_file.exists():
                    act_lock_latest = QAction(f"🔒 锁定最新版本 v{latest_version}", self)
                    act_lock_latest.triggered.connect(
                        lambda: self._lock_latest_version(file_info, file_type, all_versions)
                    )
                    menu.addAction(act_lock_latest)
                elif latest_file.path != file_info.path:
                    act_unlock_latest = QAction(f"🔓 解锁最新版本 v{latest_version}", self)
                    act_unlock_latest.triggered.connect(
                        lambda: self._unlock_latest_version(file_info, file_type, all_versions)
                    )
                    menu.addAction(act_unlock_latest)

                # 删除所有非最新版本
                act_delete_old = QAction("❌ 删除所有非最新版本", self)
                act_delete_old.triggered.connect(
                    lambda: self._delete_old_versions(file_info, file_type, all_versions)
                )
                menu.addAction(act_delete_old)

        menu.exec_(list_widget.mapToGlobal(position))

    def _delete_file(self, file_info: FileInfo, file_type: str):
        """删除文件"""
        # 检查是否有锁定
        if file_info.is_locked:
            QMessageBox.warning(
                self, "错误",
                f"无法删除已锁定的文件: {file_info.name}\n请先解锁此版本"
            )
            return

        # 获取实际文件名（去掉锁定图标）
        actual_name = file_info.name.replace("🔒 ", "") if file_info.name.startswith("🔒 ") else file_info.name

        msg = f"确定要删除 {actual_name} 吗？\n此操作不可恢复！"
        reply = QMessageBox.warning(
            self, "确认删除", msg,
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            if file_info.is_folder:
                shutil.rmtree(file_info.path)
            else:
                file_info.path.unlink()

            # 如果有锁定文件，也删除它
            lock_file = file_info.path.parent / f".{actual_name}.lock"
            if lock_file.exists():
                lock_file.unlink()

            QMessageBox.information(self, "成功", f"已删除 {actual_name}")
            # 刷新文件列表
            self._load_cut_files(self.current_cut_id, self.current_episode_id)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")

    def _lock_version(self, file_info: FileInfo, file_type: str):
        """锁定版本（添加.lock标记）"""
        actual_filename = file_info.name.replace("🔒 ", "") if file_info.name.startswith("🔒 ") else file_info.name
        lock_file = file_info.path.parent / f".{actual_filename}.lock"

        try:
            lock_file.touch()
            QMessageBox.information(
                self, "成功",
                f"已锁定 {actual_filename}\n锁定后此版本将不会被自动删除"
            )
            # 刷新文件列表
            self._load_cut_files(self.current_cut_id, self.current_episode_id)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"锁定失败: {str(e)}")

    def _unlock_version(self, file_info: FileInfo, file_type: str):
        """解锁版本（删除.lock标记）"""
        actual_filename = file_info.name.replace("🔒 ", "") if file_info.name.startswith("🔒 ") else file_info.name
        lock_file = file_info.path.parent / f".{actual_filename}.lock"

        try:
            if lock_file.exists():
                lock_file.unlink()
            QMessageBox.information(
                self, "成功",
                f"已解锁 {actual_filename}"
            )
            # 刷新文件列表
            self._load_cut_files(self.current_cut_id, self.current_episode_id)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解锁失败: {str(e)}")

    def _lock_latest_version(self, file_info: FileInfo, file_type: str, all_versions: List[FileInfo]):
        """锁定最新版本"""
        latest_file = max(all_versions, key=lambda f: f.version)
        self._lock_version(latest_file, file_type)

    def _unlock_latest_version(self, file_info: FileInfo, file_type: str, all_versions: List[FileInfo]):
        """解锁最新版本"""
        latest_file = max(all_versions, key=lambda f: f.version)
        self._unlock_version(latest_file, file_type)

    def _get_all_versions(self, file_info: FileInfo, file_type: str) -> List[FileInfo]:
        """获取同一文件的所有版本"""
        parent_dir = file_info.path.parent

        # 去掉锁定图标获取实际文件名
        actual_name = file_info.name.replace("🔒 ", "") if file_info.name.startswith("🔒 ") else file_info.name

        # 获取基础名称（去掉版本号部分）
        if '_T' in actual_name:
            base_name = actual_name[:actual_name.rfind('_T')]
        elif '_v' in actual_name:
            base_name = actual_name[:actual_name.rfind('_v')]
        else:
            # 如果没有版本号，返回仅包含自身的列表
            return [file_info]

        all_versions = []

        if file_type == "cell":
            # Cell文件夹
            for item in parent_dir.iterdir():
                if item.is_dir() and item.name.startswith(base_name):
                    info = get_file_info(item)
                    if info.version is not None:
                        # 检查是否有锁定文件
                        lock_file = item.parent / f".{item.name}.lock"
                        if lock_file.exists():
                            info.is_locked = True
                            info.name = f"🔒 {info.name}"
                        all_versions.append(info)
        else:
            # 其他文件
            pattern = f"{base_name}_*"
            for item in parent_dir.glob(pattern):
                if item.is_file():
                    info = get_file_info(item)
                    if info.version is not None:
                        # 检查是否有锁定文件
                        lock_file = item.parent / f".{item.name}.lock"
                        if lock_file.exists():
                            info.is_locked = True
                            info.name = f"🔒 {info.name}"
                        all_versions.append(info)

        return all_versions if all_versions else [file_info]

    def _delete_old_versions(self, file_info: FileInfo, file_type: str, all_versions: List[FileInfo]):
        """删除所有非最新版本"""
        # 找出最新版本
        latest_version = max(v.version for v in all_versions)
        old_versions = [v for v in all_versions if v.version != latest_version]

        if not old_versions:
            QMessageBox.information(self, "提示", "没有旧版本需要删除")
            return

        # 检查锁定文件
        locked_versions = []
        deletable_versions = []

        for v in old_versions:
            # 获取实际文件名（去掉锁定图标）
            actual_name = v.name.replace("🔒 ", "") if v.name.startswith("🔒 ") else v.name
            lock_file = v.path.parent / f".{actual_name}.lock"
            if lock_file.exists():
                locked_versions.append(v)
            else:
                deletable_versions.append(v)

        if not deletable_versions:
            QMessageBox.information(
                self, "提示",
                f"所有旧版本都已被锁定，无法删除\n被锁定的版本: {', '.join(v.name for v in locked_versions)}"
            )
            return

        # 构建确认消息
        msg = f"将删除以下 {len(deletable_versions)} 个旧版本:\n\n"
        msg += "\n".join(f"- {v.name} (v{v.version})" for v in deletable_versions)

        if locked_versions:
            msg += f"\n\n以下 {len(locked_versions)} 个版本已锁定，将被保留:\n"
            msg += "\n".join(f"- {v.name} (v{v.version})" for v in locked_versions)

        msg += "\n\n此操作不可恢复，确定要继续吗？"

        reply = QMessageBox.warning(
            self, "确认删除旧版本", msg,
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 执行删除
        deleted_count = 0
        failed_count = 0

        for v in deletable_versions:
            try:
                if v.is_folder:
                    shutil.rmtree(v.path)
                else:
                    v.path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"删除失败 {v.name}: {e}")
                failed_count += 1

        # 显示结果
        result_msg = f"删除完成:\n✅ 成功删除: {deleted_count} 个版本"
        if failed_count > 0:
            result_msg += f"\n❌ 删除失败: {failed_count} 个版本"
        if locked_versions:
            result_msg += f"\n🔒 保留锁定: {len(locked_versions)} 个版本"

        QMessageBox.information(self, "删除结果", result_msg)

        # 刷新文件列表
        self._load_cut_files(self.current_cut_id, self.current_episode_id)

    # 项目级批量操作
    def lock_all_latest_versions(self):
        """锁定项目中所有最新版本"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # reply = QMessageBox.question(
        #     self, "确认",
        #     "将锁定项目中所有文件的最新版本。\n锁定后这些版本将不会被自动删除。\n\n是否继续？",
        #     QMessageBox.Yes | QMessageBox.No
        # )
        #
        # if reply != QMessageBox.Yes:
        #     return

        locked_count = 0
        error_count = 0

        # 遍历所有VFX目录
        for vfx_dir in self.project_base.rglob("01_vfx"):
            # 检查AEP文件
            aep_files = list(vfx_dir.glob("*/*.aep"))
            aep_by_cut = {}
            for aep in aep_files:
                cut_dir = aep.parent.name
                if cut_dir not in aep_by_cut:
                    aep_by_cut[cut_dir] = []
                file_info = get_file_info(aep)
                if file_info.version is not None:
                    aep_by_cut[cut_dir].append(file_info)

            # 锁定每个cut的最新版本
            for cut, files in aep_by_cut.items():
                if files:
                    latest = max(files, key=lambda f: f.version)
                    lock_file = latest.path.parent / f".{latest.path.name}.lock"
                    try:
                        if not lock_file.exists():
                            lock_file.touch()
                            locked_count += 1
                    except:
                        error_count += 1

            # 检查BG文件
            for bg_dir in vfx_dir.glob("*/bg"):
                bg_files = []
                for ext in IMAGE_EXTENSIONS:
                    bg_files.extend(bg_dir.glob(f"*{ext}"))

                bg_by_base = {}
                for bg in bg_files:
                    file_info = get_file_info(bg)
                    if file_info.version is not None:
                        base_name = bg.stem[:bg.stem.rfind('_T')] if '_T' in bg.stem else bg.stem
                        if base_name not in bg_by_base:
                            bg_by_base[base_name] = []
                        bg_by_base[base_name].append(file_info)

                for base, files in bg_by_base.items():
                    if files:
                        latest = max(files, key=lambda f: f.version)
                        lock_file = latest.path.parent / f".{latest.path.name}.lock"
                        try:
                            if not lock_file.exists():
                                lock_file.touch()
                                locked_count += 1
                        except:
                            error_count += 1

            # 检查Cell文件夹
            for cell_dir in vfx_dir.glob("*/cell"):
                cell_folders = [f for f in cell_dir.iterdir() if f.is_dir()]
                cell_by_base = {}

                for folder in cell_folders:
                    file_info = get_file_info(folder)
                    if file_info.version is not None:
                        base_name = folder.name[:folder.name.rfind('_T')] if '_T' in folder.name else folder.name
                        if base_name not in cell_by_base:
                            cell_by_base[base_name] = []
                        cell_by_base[base_name].append(file_info)

                for base, folders in cell_by_base.items():
                    if folders:
                        latest = max(folders, key=lambda f: f.version)
                        lock_file = latest.path.parent / f".{latest.path.name}.lock"
                        try:
                            if not lock_file.exists():
                                lock_file.touch()
                                locked_count += 1
                        except:
                            error_count += 1

        # 处理06_render目录
        for render_dir in self.project_base.rglob("06_render"):
            # 定义需要处理的文件扩展名
            render_extensions = ['.mov', '.mp4', '.png']

            # 遍历所有子目录
            for subdir in render_dir.rglob("*"):
                if subdir.is_dir():
                    # 收集该目录下的所有渲染文件
                    render_files = []
                    for ext in render_extensions:
                        render_files.extend(subdir.glob(f"*{ext}"))

                    # 按基础名称分组
                    files_by_base = {}
                    for file in render_files:
                        file_info = get_file_info(file)
                        if file_info.version is not None:
                            # 获取基础名称
                            if '_T' in file.stem:
                                base_name = file.stem[:file.stem.rfind('_T')]
                            elif '_v' in file.stem:
                                base_name = file.stem[:file.stem.rfind('_v')]
                            else:
                                continue

                            # 创建分组key（包含扩展名以区分不同类型的文件）
                            group_key = f"{base_name}{file.suffix}"

                            if group_key not in files_by_base:
                                files_by_base[group_key] = []
                            files_by_base[group_key].append(file_info)

                    # 锁定每组的最新版本
                    for group_key, files in files_by_base.items():
                        if files:
                            latest = max(files, key=lambda f: f.version)
                            lock_file = latest.path.parent / f".{latest.path.name}.lock"
                            try:
                                if not lock_file.exists():
                                    lock_file.touch()
                                    locked_count += 1
                            except:
                                error_count += 1

        # 显示结果
        msg = f"锁定完成:\n✅ 成功锁定: {locked_count} 个最新版本"
        if error_count > 0:
            msg += f"\n❌ 锁定失败: {error_count} 个文件"

        QMessageBox.information(self, "完成", msg)

        # 刷新当前视图
        if self.current_cut_id:
            self._load_cut_files(self.current_cut_id, self.current_episode_id)

    def unlock_all_versions(self):
        """解锁项目中所有版本"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # reply = QMessageBox.question(
        #     self, "确认",
        #     "将解锁项目中所有已锁定的版本。\n解锁后这些版本可以被删除。\n\n是否继续？",
        #     QMessageBox.Yes | QMessageBox.No
        # )
        #
        # if reply != QMessageBox.Yes:
        #     return

        unlocked_count = 0

        # 查找所有锁定文件
        for lock_file in self.project_base.rglob(".*.lock"):
            try:
                lock_file.unlink()
                unlocked_count += 1
            except:
                pass

        QMessageBox.information(
            self, "完成",
            f"已解锁 {unlocked_count} 个文件"
        )

        # 刷新当前视图
        if self.current_cut_id:
            self._load_cut_files(self.current_cut_id, self.current_episode_id)

    def delete_all_old_versions(self):
        """删除项目中所有旧版本"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 先统计
        stats = self._get_version_statistics()

        if stats["old_versions"] == 0:
            QMessageBox.information(self, "提示", "项目中没有旧版本需要删除")
            return

        msg = f"即将删除项目中的所有旧版本文件:\n\n"
        msg += f"📊 总文件数: {stats['total_files']}\n"
        msg += f"🔒 锁定文件: {stats['locked_files']}\n"
        msg += f"📁 最新版本: {stats['latest_versions']}\n"
        msg += f"🗑️ 可删除旧版本: {stats['deletable_old']}\n"
        msg += f"\n总计将删除 {stats['deletable_old']} 个文件，释放 {stats['deletable_size_mb']:.1f} MB 空间"
        msg += f"\n\n此操作不可恢复，是否继续？"

        reply = QMessageBox.warning(
            self, "确认删除",
            msg,
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 执行删除
        deleted_count = 0
        failed_count = 0

        # 创建进度对话框
        progress = QProgressDialog(
            "正在删除旧版本文件...", "取消",
            0, stats['deletable_old'], self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        file_index = 0

        try:
            # 遍历所有VFX目录
            for vfx_dir in self.project_base.rglob("01_vfx"):
                if progress.wasCanceled():
                    break

                # 处理AEP文件
                result = self._delete_old_versions_in_dir(
                    vfx_dir, "*.aep", progress, file_index
                )
                deleted_count += result[0]
                failed_count += result[1]
                file_index = result[2]

                # 处理BG文件
                for bg_dir in vfx_dir.glob("*/bg"):
                    if progress.wasCanceled():
                        break
                    for ext in IMAGE_EXTENSIONS:
                        result = self._delete_old_versions_in_dir(
                            bg_dir, f"*{ext}", progress, file_index
                        )
                        deleted_count += result[0]
                        failed_count += result[1]
                        file_index = result[2]

                # 处理Cell文件夹
                for cell_dir in vfx_dir.glob("*/cell"):
                    if progress.wasCanceled():
                        break
                    result = self._delete_old_cell_versions(
                        cell_dir, progress, file_index
                    )
                    deleted_count += result[0]
                    failed_count += result[1]
                    file_index = result[2]

        finally:
            progress.close()

        # 显示结果
        result_msg = f"删除完成:\n✅ 成功删除: {deleted_count} 个旧版本"
        if failed_count > 0:
            result_msg += f"\n❌ 删除失败: {failed_count} 个文件"

        QMessageBox.information(self, "完成", result_msg)

        # 刷新视图
        self._refresh_tree()
        if self.current_cut_id:
            self._load_cut_files(self.current_cut_id, self.current_episode_id)

    def show_version_statistics(self):
        """显示版本统计信息"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        version_stats = self._get_version_statistics()

        from cx_project_manager.ui.mixins.version_statistics_dialog import ProjectStatisticsDialog

        # 显示综合统计对话框
        dialog = ProjectStatisticsDialog(self.project_config, version_stats, self)
        dialog.exec_()

    def _get_version_statistics(self) -> Dict[str, int]:
        """获取项目版本统计信息"""
        stats = {
            'total_files': 0,
            'versioned_files': 0,
            'latest_versions': 0,
            'old_versions': 0,
            'locked_files': 0,
            'locked_latest': 0,
            'locked_old': 0,
            'deletable_old': 0,
            'total_size_mb': 0,
            'latest_size_mb': 0,
            'old_size_mb': 0,
            'deletable_size_mb': 0,
            'aep_count': 0,
            'bg_count': 0,
            'cell_count': 0
        }

        # 遍历所有VFX目录
        for vfx_dir in self.project_base.rglob("01_vfx"):
            # AEP文件
            for aep in vfx_dir.glob("*/*.aep"):
                stats['total_files'] += 1
                stats['aep_count'] += 1
                file_info = get_file_info(aep)
                self._update_file_stats(stats, file_info, aep)

            # BG文件
            for bg_dir in vfx_dir.glob("*/bg"):
                for ext in IMAGE_EXTENSIONS:
                    for bg in bg_dir.glob(f"*{ext}"):
                        stats['total_files'] += 1
                        stats['bg_count'] += 1
                        file_info = get_file_info(bg)
                        self._update_file_stats(stats, file_info, bg)

            # Cell文件夹
            for cell_dir in vfx_dir.glob("*/cell"):
                for folder in cell_dir.iterdir():
                    if folder.is_dir():
                        stats['total_files'] += 1
                        stats['cell_count'] += 1
                        file_info = get_file_info(folder)
                        self._update_folder_stats(stats, file_info, folder)

        return stats

    def _update_file_stats(self, stats: Dict, file_info: FileInfo, file_path: Path):
        """更新文件统计信息"""
        size_mb = file_path.stat().st_size / (1024 * 1024)
        stats['total_size_mb'] += size_mb

        if file_info.version is not None:
            stats['versioned_files'] += 1

            # 检查是否是最新版本
            all_versions = self._get_all_versions_for_file(file_path)
            is_latest = file_info.version == max(v.version for v in all_versions)

            # 检查锁定状态
            lock_file = file_path.parent / f".{file_path.name}.lock"
            is_locked = lock_file.exists()

            if is_locked:
                stats['locked_files'] += 1

            if is_latest:
                stats['latest_versions'] += 1
                stats['latest_size_mb'] += size_mb
                if is_locked:
                    stats['locked_latest'] += 1
            else:
                stats['old_versions'] += 1
                stats['old_size_mb'] += size_mb
                if is_locked:
                    stats['locked_old'] += 1
                else:
                    stats['deletable_old'] += 1
                    stats['deletable_size_mb'] += size_mb

    def _update_folder_stats(self, stats: Dict, file_info: FileInfo, folder_path: Path):
        """更新文件夹统计信息"""
        # 计算文件夹大小
        size_mb = sum(f.stat().st_size for f in folder_path.rglob("*") if f.is_file()) / (1024 * 1024)
        stats['total_size_mb'] += size_mb

        if file_info.version is not None:
            stats['versioned_files'] += 1

            # 检查是否是最新版本
            all_versions = []
            for item in folder_path.parent.iterdir():
                if item.is_dir() and item.name.startswith(folder_path.name[:folder_path.name.rfind('_T')]):
                    info = get_file_info(item)
                    if info.version is not None:
                        all_versions.append(info)

            is_latest = file_info.version == max(v.version for v in all_versions) if all_versions else True

            # 检查锁定状态
            lock_file = folder_path.parent / f".{folder_path.name}.lock"
            is_locked = lock_file.exists()

            if is_locked:
                stats['locked_files'] += 1

            if is_latest:
                stats['latest_versions'] += 1
                stats['latest_size_mb'] += size_mb
                if is_locked:
                    stats['locked_latest'] += 1
            else:
                stats['old_versions'] += 1
                stats['old_size_mb'] += size_mb
                if is_locked:
                    stats['locked_old'] += 1
                else:
                    stats['deletable_old'] += 1
                    stats['deletable_size_mb'] += size_mb

    def _get_all_versions_for_file(self, file_path: Path) -> List[FileInfo]:
        """获取文件的所有版本"""
        if '_T' in file_path.stem:
            base_name = file_path.stem[:file_path.stem.rfind('_T')]
        elif '_v' in file_path.stem:
            base_name = file_path.stem[:file_path.stem.rfind('_v')]
        else:
            return [get_file_info(file_path)]

        all_versions = []
        pattern = f"{base_name}_*{file_path.suffix}"
        for item in file_path.parent.glob(pattern):
            if item.is_file():
                info = get_file_info(item)
                if info.version is not None:
                    all_versions.append(info)

        return all_versions if all_versions else [get_file_info(file_path)]

    def _delete_old_versions_in_dir(self, directory: Path, pattern: str,
                                    progress: 'QProgressDialog', start_index: int) -> tuple:
        """删除目录中的旧版本文件"""
        deleted = 0
        failed = 0
        index = start_index

        # 收集文件并按基础名称分组
        files_by_base = {}
        for file in directory.rglob(pattern):
            file_info = get_file_info(file)
            if file_info.version is not None:
                if '_T' in file.stem:
                    base_name = file.stem[:file.stem.rfind('_T')]
                elif '_v' in file.stem:
                    base_name = file.stem[:file.stem.rfind('_v')]
                else:
                    continue

                if base_name not in files_by_base:
                    files_by_base[base_name] = []
                files_by_base[base_name].append((file, file_info))

        # 删除每组的旧版本
        for base_name, files in files_by_base.items():
            if len(files) > 1:
                # 找出最新版本
                latest_version = max(f[1].version for f in files)

                for file_path, file_info in files:
                    if file_info.version < latest_version:
                        # 检查是否锁定
                        lock_file = file_path.parent / f".{file_path.name}.lock"
                        if not lock_file.exists():
                            progress.setValue(index)
                            progress.setLabelText(f"正在删除: {file_path.name}")
                            QApplication.processEvents()

                            try:
                                file_path.unlink()
                                deleted += 1
                            except:
                                failed += 1

                            index += 1

                            if progress.wasCanceled():
                                return deleted, failed, index

        return deleted, failed, index

    def _delete_old_cell_versions(self, cell_dir: Path,
                                  progress: 'QProgressDialog', start_index: int) -> tuple:
        """删除Cell目录中的旧版本"""
        deleted = 0
        failed = 0
        index = start_index

        # 收集文件夹并按基础名称分组
        folders_by_base = {}
        for folder in cell_dir.iterdir():
            if folder.is_dir():
                file_info = get_file_info(folder)
                if file_info.version is not None:
                    base_name = folder.name[:folder.name.rfind('_T')] if '_T' in folder.name else folder.name

                    if base_name not in folders_by_base:
                        folders_by_base[base_name] = []
                    folders_by_base[base_name].append((folder, file_info))

        # 删除每组的旧版本
        for base_name, folders in folders_by_base.items():
            if len(folders) > 1:
                # 找出最新版本
                latest_version = max(f[1].version for f in folders)

                for folder_path, file_info in folders:
                    if file_info.version < latest_version:
                        # 检查是否锁定
                        lock_file = folder_path.parent / f".{folder_path.name}.lock"
                        if not lock_file.exists():
                            progress.setValue(index)
                            progress.setLabelText(f"正在删除: {folder_path.name}")
                            QApplication.processEvents()

                            try:
                                shutil.rmtree(folder_path)
                                deleted += 1
                            except:
                                failed += 1

                            index += 1

                            if progress.wasCanceled():
                                return deleted, failed, index

        return deleted, failed, index

    def _open_in_manager(self, path: Path):
        """在文件管理器中打开"""
        from cx_project_manager.utils.utils import open_in_file_manager
        open_in_file_manager(path)