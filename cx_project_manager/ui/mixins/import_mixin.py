# -*- coding: utf-8 -*-
"""素材导入功能混入类"""

import shutil
from pathlib import Path
from typing import Dict, Optional
from functools import partial

from PySide6.QtWidgets import QMessageBox, QFileDialog, QDialog, QApplication, QProgressDialog
from PySide6.QtCore import Qt

from cx_project_manager.utils.utils import ensure_dir, copy_file_safe, open_in_file_manager, \
    extract_version_from_filename
from cx_project_manager.utils.models import ReuseCut
from cx_project_manager.utils.constants import IMAGE_EXTENSIONS
from cx_project_manager.ui.dialogs import VersionConfirmDialog, BatchAepDialog


class ImportMixin:
    """素材导入相关功能"""

    # 需要在主类中定义的属性
    project_base: Optional[Path]
    project_config: Optional[dict]
    project_manager: any
    material_paths: dict
    material_buttons: dict
    cmb_target_episode: any
    cmb_target_cut: any
    tabs: any
    current_cut_id: any
    current_episode_id: any
    skip_version_confirmation: dict
    app_settings: any

    def browse_material(self, material_type: str):
        """浏览选择素材"""
        if material_type in ["cell", "3dcg"]:
            path = QFileDialog.getExistingDirectory(
                self, f"选择 {material_type.upper()} 文件夹", ""
            )
            if path:
                self.material_paths[material_type].setText(path)
        else:
            file_filter = {
                "bg": "图像文件 (*.psd *.png *.jpg *.jpeg *.tga *.tiff *.bmp *.exr *.dpx)",
                "timesheet": "CSV 文件 (*.csv)",
            }.get(material_type, "所有文件 (*.*)")

            file_path, _ = QFileDialog.getOpenFileName(
                self, f"选择 {material_type.upper()} 文件", "", file_filter
            )
            if file_path:
                self.material_paths[material_type].setText(file_path)

    def import_single(self):
        """导入单个选中的素材"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
            if self.cmb_target_episode.currentText():
                target_ep = self.cmb_target_episode.currentText()
                target_cut = self.cmb_target_cut.currentText()
                if not target_cut:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                target = f"{target_ep}|{target_cut}"
            else:
                target_cut = self.cmb_target_cut.currentText()
                if not target_cut:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                target = target_cut
        else:
            target_ep = self.cmb_target_episode.currentText()
            target_cut = self.cmb_target_cut.currentText()
            if not target_ep or not target_cut:
                QMessageBox.warning(self, "错误", "请选择目标 Episode 和 Cut")
                return
            target = f"{target_ep}|{target_cut}"

        # 收集要导入的素材
        imports = []
        for mt in ["bg", "cell", "3dcg", "timesheet"]:
            if self.material_paths[mt].text():
                imports.append((mt, self.material_paths[mt].text()))

        if not imports:
            QMessageBox.warning(self, "错误", "请先选择要导入的素材")
            return

        # 执行导入
        success_count = 0
        for material_type, path in imports:
            if self._import_material(material_type, path, target):
                success_count += 1

        if success_count > 0:
            message = f"已导入 {success_count} 个素材"
            if any(mt == "3dcg" for mt, _ in imports):
                message += "（已创建 3DCG 目录）"

            QMessageBox.information(self, "成功", message)
            self._refresh_tree()

            # 清空已导入的路径
            for mt, _ in imports:
                self.material_paths[mt].clear()

            # 重置版本确认跳过设置
            self.skip_version_confirmation = {"bg": False, "cell": False, "3dcg": False}

    def import_all(self):
        """批量导入所有已选择的素材"""
        self.import_single()

    def _import_material(self, material_type: str, source_path: str, target: str) -> bool:
        """执行素材导入"""
        try:
            src = Path(source_path)
            if not src.exists():
                return False

            display_name = self.project_config.get("project_display_name", self.project_base.name)

            # 解析目标路径
            if "|" in target:
                ep_id, cut_id = target.split("|")
                vfx_base = self.project_base / ep_id / "01_vfx"
                cg_base = self.project_base / ep_id / "02_3dcg"
                ep_part = ep_id.upper() + "_"
            else:
                cut_id = target
                vfx_base = self.project_base / "01_vfx"
                cg_base = self.project_base / "02_3dcg"
                ep_part = ""

            # 检查是否是兼用卡
            reuse_cut = self.project_manager.get_reuse_cut_for_cut(cut_id)
            if reuse_cut:
                cut_id = reuse_cut.main_cut
                base_name = f"{display_name}_{ep_part}{reuse_cut.get_display_name()}"
            else:
                base_name = f"{display_name}_{ep_part}{cut_id}"

            # 根据类型处理
            if material_type == "bg":
                bg_dir = vfx_base / cut_id / "bg"
                ensure_dir(bg_dir)

                version = self.project_manager.get_next_version(bg_dir, base_name)

                if not self.skip_version_confirmation["bg"] and bg_dir.exists() and any(bg_dir.iterdir()):
                    dialog = VersionConfirmDialog("BG", version, self)
                    if dialog.exec() == QDialog.Accepted:
                        version = dialog.get_version()
                        if dialog.should_skip_confirmation():
                            self.skip_version_confirmation["bg"] = True
                    else:
                        return False

                file_name = f"{base_name}_T{version}{src.suffix.lower()}"
                dst = bg_dir / file_name
                copy_file_safe(src, dst)

            elif material_type == "cell":
                cell_dir = vfx_base / cut_id / "cell"
                ensure_dir(cell_dir)

                version = self.project_manager.get_next_version(cell_dir, base_name)

                if not self.skip_version_confirmation["cell"] and cell_dir.exists() and any(cell_dir.iterdir()):
                    dialog = VersionConfirmDialog("Cell", version, self)
                    if dialog.exec() == QDialog.Accepted:
                        version = dialog.get_version()
                        if dialog.should_skip_confirmation():
                            self.skip_version_confirmation["cell"] = True
                    else:
                        return False

                folder_name = f"{base_name}_T{version}"
                dst_folder = cell_dir / folder_name
                if dst_folder.exists():
                    shutil.rmtree(dst_folder)
                shutil.copytree(src, dst_folder)

            elif material_type == "3dcg":
                ensure_dir(cg_base)
                cg_cut_dir = cg_base / cut_id
                ensure_dir(cg_cut_dir)

                for item in src.iterdir():
                    if item.is_file():
                        copy_file_safe(item, cg_cut_dir / item.name)
                    elif item.is_dir():
                        target_dir = cg_cut_dir / item.name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(item, target_dir)

            else:  # timesheet
                if reuse_cut:
                    dst = vfx_base / "timesheets" / f"{reuse_cut.get_display_name()}.csv"
                else:
                    dst = vfx_base / "timesheets" / f"{cut_id}.csv"
                ensure_dir(dst.parent)
                copy_file_safe(src, dst)

            return True

        except Exception as e:
            print(f"导入失败 ({material_type}): {e}")
            return False

    def copy_aep_template(self):
        """复制AEP模板"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取目标
        if self.project_config.get("no_episode", False):
            if self.cmb_target_episode.currentText():
                ep_id = self.cmb_target_episode.currentText()
                cut_id = self.cmb_target_cut.currentText()
                if not cut_id:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                cut_path = self.project_base / ep_id / "01_vfx" / cut_id
            else:
                cut_id = self.cmb_target_cut.currentText()
                if not cut_id:
                    QMessageBox.warning(self, "错误", "请选择目标 Cut")
                    return
                cut_path = self.project_base / "01_vfx" / cut_id
                ep_id = None
        else:
            ep_id = self.cmb_target_episode.currentText()
            cut_id = self.cmb_target_cut.currentText()
            if not ep_id or not cut_id:
                QMessageBox.warning(self, "错误", "请选择目标 Episode 和 Cut")
                return
            cut_path = self.project_base / ep_id / "01_vfx" / cut_id

        # 检查是否是兼用卡
        reuse_cut = self.project_manager.get_reuse_cut_for_cut(cut_id)
        if reuse_cut:
            if ep_id:
                cut_path = self.project_base / ep_id / "01_vfx" / reuse_cut.main_cut
            else:
                cut_path = self.project_base / "01_vfx" / reuse_cut.main_cut

        # 检查模板目录
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists() or not list(template_dir.glob("*.aep")):
            open_tmp_aep = QMessageBox.question(
                self, "提示",
                "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件\n是否手动选择AEP模板？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if open_tmp_aep == QMessageBox.Yes:
                default_aep_template = self.app_settings.value("default_aep_template", "")
                aep_path, _ = QFileDialog.getOpenFileName(
                    self, "选择 AEP 模板", default_aep_template, "AEP 文件 (*.aep)"
                )
                if aep_path:
                    self.app_settings.setValue("default_aep_template", aep_path)
                    cut_path.mkdir(parents=True, exist_ok=True)
                    if copy_file_safe(Path(aep_path), cut_path / Path(aep_path).name):
                        QMessageBox.information(self, "成功", "已复制 AEP 模板")
                        self._refresh_tree()
                    return
                else:
                    QMessageBox.warning(self, "错误", "未选择 AEP 模板文件")
                    return
            return

        # 复制模板
        display_name = self.project_config.get("project_display_name", self.project_base.name)
        copied = 0

        for template in template_dir.glob("*.aep"):
            template_stem = template.stem

            if reuse_cut:
                cuts_str = reuse_cut.get_display_name()
                base_name = f"{display_name}_{ep_id.upper() + '_' if ep_id else ''}{cuts_str}"
            else:
                base_name = f"{display_name}_{ep_id.upper() + '_' if ep_id else ''}{cut_id}"

            version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"
            aep_name = f"{base_name}{version_part}{template.suffix}"

            if copy_file_safe(template, cut_path / aep_name):
                copied += 1

        message = f"已复制 {copied} 个 AEP 模板到 {'兼用卡 ' + reuse_cut.get_display_name() if reuse_cut else 'Cut ' + cut_id}"
        QMessageBox.information(self, "成功", message)
        self._refresh_tree()

        if self.tabs.currentIndex() == 1 and self.current_cut_id == cut_id:
            self._load_cut_files(cut_id, ep_id)

    def batch_copy_aep_template(self):
        """批量复制AEP模板"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        if not template_dir.exists() or not list(template_dir.glob("*.aep")):
            open_tmp_aep = QMessageBox.question(
                self, "提示",
                "07_master_assets/aep_templates 文件夹不存在或没有 AEP 模板文件\n是否手动选择AEP模板？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if open_tmp_aep == QMessageBox.Yes:
                aep_path, _ = QFileDialog.getOpenFileName(
                    self, "选择 AEP 模板", "", "AEP 文件 (*.aep)"
                )
                if template_dir:
                    copy_file_safe(Path(aep_path), template_dir / Path(aep_path).name)
                else:
                    QMessageBox.warning(self, "错误", "未选择 AEP 模板文件")
                    return

        dialog = BatchAepDialog(self.project_config, self)
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            self._batch_copy_with_settings(settings)

    def _batch_copy_with_settings(self, settings: Dict):
        """根据设置批量复制"""
        template_dir = self.project_base / "07_master_assets" / "aep_templates"
        templates = list(template_dir.glob("*.aep"))
        display_name = self.project_config.get("project_display_name", self.project_base.name)

        # 收集目标
        targets = []

        # 获取兼用卡信息
        reuse_cuts_map = {}
        for cut_data in self.project_config.get("reuse_cuts", []):
            cut = ReuseCut.from_dict(cut_data)
            for cut_id in cut.cuts:
                reuse_cuts_map[cut_id] = cut

        if settings["scope"] == 0:  # 所有
            if self.project_config.get("no_episode", False):
                for cut_id in self.project_config.get("cuts", []):
                    if cut_id in reuse_cuts_map and reuse_cuts_map[cut_id].main_cut != cut_id:
                        continue
                    targets.append((None, cut_id))

            for ep_id, cuts in self.project_config.get("episodes", {}).items():
                for cut_id in cuts:
                    if cut_id in reuse_cuts_map and reuse_cuts_map[cut_id].main_cut != cut_id:
                        continue
                    targets.append((ep_id, cut_id))

        elif settings["scope"] >= 1:  # 指定Episode
            ep_id = settings["episode"]
            if not ep_id and self.project_config.get("no_episode", False):
                # 没有episode的项目，使用cuts列表
                cuts = self.project_config.get("cuts", [])
            else:
                # 有episode的项目或者指定了episode
                cuts = self.project_config["episodes"][ep_id]

            if settings["scope"] == 2:
                cut_from = settings["cut_from"]
                cut_to = settings["cut_to"]
                cuts = [cut for cut in cuts if cut.isdigit() and cut_from <= int(cut) <= cut_to]

            for cut_id in cuts:
                if cut_id in reuse_cuts_map and reuse_cuts_map[cut_id].main_cut != cut_id:
                    continue
                # 如果ep_id是空字符串且项目没有episode，传递None
                episode_id = None if (not ep_id and self.project_config.get("no_episode", False)) else ep_id
                targets.append((episode_id, cut_id))

        # 执行复制
        counts = {"success": 0, "skip": 0, "overwrite": 0, "reuse_skip": 0}

        for ep_id, cut_id in targets:
            is_reuse = cut_id in reuse_cuts_map
            reuse_cut = reuse_cuts_map.get(cut_id)

            if settings["skip_reuse"] and is_reuse:
                counts["reuse_skip"] += 1
                continue

            actual_cut_id = reuse_cut.main_cut if is_reuse else cut_id
            cut_path = (self.project_base / ep_id / "01_vfx" / actual_cut_id if ep_id
                        else self.project_base / "01_vfx" / actual_cut_id)

            if not cut_path.exists():
                continue

            if settings["skip_existing"] and list(cut_path.glob("*.aep")):
                counts["skip"] += len(list(cut_path.glob("*.aep")))
                continue

            cut_copied = 0
            for template in templates:
                template_stem = template.stem

                if is_reuse:
                    cuts_str = reuse_cut.get_display_name()
                    base_name = f"{display_name}_{ep_id.upper() + '_' if ep_id else ''}{cuts_str}"
                else:
                    base_name = f"{display_name}_{ep_id.upper() + '_' if ep_id else ''}{cut_id}"

                version_part = template_stem[template_stem.rfind('_v'):] if '_v' in template_stem else "_v0"
                aep_name = f"{base_name}{version_part}{template.suffix}"
                dst = cut_path / aep_name

                if dst.exists():
                    if settings["overwrite"]:
                        counts["overwrite"] += 1
                    else:
                        counts["skip"] += 1
                        continue

                if copy_file_safe(template, dst):
                    cut_copied += 1

            if cut_copied > 0:
                counts["success"] += 1

        # 显示结果
        message_lines = [f"✅ 成功为 {counts['success']} 个 Cut 复制了模板"]
        if counts["overwrite"] > 0:
            message_lines.append(f"🔄 覆盖了 {counts['overwrite']} 个文件")
        if counts["skip"] > 0:
            message_lines.append(f"⏭️ 跳过了 {counts['skip']} 个文件")
        if counts["reuse_skip"] > 0:
            message_lines.append(f"🔗 跳过了 {counts['reuse_skip']} 个兼用卡")

        QMessageBox.information(self, "批量复制完成", "\n".join(message_lines))
        self._refresh_tree()

    def copy_mov_to_cut_folder(self):
        """复制所有MOV文件到剪辑文件夹"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        render_dir = self.project_base / "06_render"
        if not render_dir.exists():
            QMessageBox.warning(self, "错误", "06_render 文件夹不存在")
            return

        # 创建目标文件夹
        footage_dir = self.project_base / "09_edit" / "footage"
        ensure_dir(footage_dir)

        # 统计信息
        mov_files_by_episode = {}  # {episode_id: [(source_path, filename), ...]}
        total_count = 0
        total_size = 0

        # 判断项目模式
        no_episode = self.project_config.get("no_episode", False)

        # 收集所有MOV文件并筛选最新版本
        def get_latest_versions(mov_files):
            """从MOV文件列表中获取每个cut的最新版本"""
            # 按基础名称（不含版本号）分组
            files_by_base = {}

            for mov_file in mov_files:
                filename = mov_file.stem
                # 提取版本号
                version = extract_version_from_filename(filename)

                # 获取基础名称（去掉版本号部分）
                if version is not None:
                    # 查找 _v 的位置
                    version_index = filename.rfind('_v')
                    if version_index != -1:
                        base_name = filename[:version_index]
                    else:
                        base_name = filename
                else:
                    base_name = filename
                    version = 0  # 没有版本号的文件视为版本0

                # 分组存储
                if base_name not in files_by_base:
                    files_by_base[base_name] = []
                files_by_base[base_name].append((mov_file, version))

            # 选择每组中版本号最高的文件
            latest_files = []
            for base_name, file_versions in files_by_base.items():
                # 按版本号排序，取最高版本
                file_versions.sort(key=lambda x: x[1], reverse=True)
                latest_files.append(file_versions[0][0])  # 只取文件路径

            return latest_files

        if no_episode:
            # 单集模式：直接在06_render下查找cut文件夹
            cuts = self.project_config.get("cuts", [])

            # 处理根目录下的cuts
            root_mov_files = []
            for cut_id in cuts:
                cut_render_path = render_dir / cut_id / "prores"
                if cut_render_path.exists():
                    root_mov_files.extend(cut_render_path.glob("*.mov"))

            if root_mov_files:
                latest_files = get_latest_versions(root_mov_files)
                mov_files_by_episode["root"] = [(f, f.name) for f in latest_files]
                total_count += len(latest_files)
                total_size += sum(f.stat().st_size for f in latest_files)

            # 处理特殊episodes
            episodes = self.project_config.get("episodes", {})
            for ep_id, ep_cuts in episodes.items():
                ep_render_path = render_dir / ep_id
                if ep_render_path.exists():
                    ep_mov_files = []
                    for cut_id in ep_cuts:
                        cut_render_path = ep_render_path / cut_id / "prores"
                        if cut_render_path.exists():
                            ep_mov_files.extend(cut_render_path.glob("*.mov"))

                    if ep_mov_files:
                        latest_files = get_latest_versions(ep_mov_files)
                        mov_files_by_episode[ep_id] = [(f, f.name) for f in latest_files]
                        total_count += len(latest_files)
                        total_size += sum(f.stat().st_size for f in latest_files)
        else:
            # 标准Episode模式
            episodes = self.project_config.get("episodes", {})
            for ep_id, cuts in episodes.items():
                ep_render_path = render_dir / ep_id
                if ep_render_path.exists():
                    ep_mov_files = []
                    for cut_id in cuts:
                        cut_render_path = ep_render_path / cut_id / "prores"
                        if cut_render_path.exists():
                            ep_mov_files.extend(cut_render_path.glob("*.mov"))

                    if ep_mov_files:
                        latest_files = get_latest_versions(ep_mov_files)
                        mov_files_by_episode[ep_id] = [(f, f.name) for f in latest_files]
                        total_count += len(latest_files)
                        total_size += sum(f.stat().st_size for f in latest_files)

        if total_count == 0:
            QMessageBox.information(self, "提示", "没有找到任何 MOV 文件")
            return

        # 显示确认对话框
        size_mb = total_size / (1024 * 1024)
        episode_info = []

        for ep_id, files in sorted(mov_files_by_episode.items()):
            if ep_id == "root":
                episode_info.append(f"根目录: {len(files)} 个文件（最新版本）")
            else:
                episode_info.append(f"{ep_id}: {len(files)} 个文件（最新版本）")

        message = f"找到 {total_count} 个最新版本 MOV 文件（总大小: {size_mb:.1f} MB）\n\n"
        message += "分布情况:\n" + "\n".join(episode_info)
        message += "\n\n注意：只会复制每个Cut的最新版本（版本号最高的文件）"
        message += "\n是否继续复制？"

        reply = QMessageBox.question(
            self, "确认复制",
            message,
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 执行复制
        copied_count = 0
        skipped_count = 0
        error_count = 0

        progress = QProgressDialog("正在复制最新版本 MOV 文件...", "取消", 0, total_count, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        file_index = 0

        try:
            for ep_id, files in mov_files_by_episode.items():
                # 创建episode子文件夹
                if ep_id == "root":
                    target_dir = footage_dir
                else:
                    target_dir = footage_dir / ep_id
                    ensure_dir(target_dir)

                for source_path, filename in files:
                    if progress.wasCanceled():
                        break

                    progress.setValue(file_index)
                    progress.setLabelText(f"正在复制: {filename}")
                    QApplication.processEvents()

                    target_path = target_dir / filename

                    # 处理重名文件
                    if target_path.exists():
                        # 比较文件大小和修改时间
                        source_stat = source_path.stat()
                        target_stat = target_path.stat()

                        if (source_stat.st_size == target_stat.st_size and
                                source_stat.st_mtime <= target_stat.st_mtime):
                            skipped_count += 1
                            file_index += 1
                            continue

                        # 如果文件不同，添加序号
                        base_name = target_path.stem
                        suffix = target_path.suffix
                        counter = 1

                        while target_path.exists():
                            new_name = f"{base_name}_{counter}{suffix}"
                            target_path = target_dir / new_name
                            counter += 1

                    # 复制文件
                    try:
                        if copy_file_safe(source_path, target_path):
                            copied_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        print(f"复制失败 {filename}: {e}")
                        error_count += 1

                    file_index += 1

                if progress.wasCanceled():
                    break

        finally:
            progress.close()

        # 显示结果
        result_lines = [f"✅ 成功复制: {copied_count} 个最新版本文件"]

        if skipped_count > 0:
            result_lines.append(f"⏭️ 跳过相同文件: {skipped_count} 个")

        if error_count > 0:
            result_lines.append(f"❌ 复制失败: {error_count} 个")

        result_lines.append(f"\n目标文件夹: 09_edit/footage/")
        result_lines.append("（只复制了每个Cut的最新版本）")

        QMessageBox.information(
            self, "复制完成",
            "\n".join(result_lines)
        )

        # 询问是否打开文件夹
        open_folder = QMessageBox.question(
            self, "打开文件夹",
            "是否打开 footage 文件夹查看？",
            QMessageBox.Yes | QMessageBox.No
        )

        if open_folder == QMessageBox.Yes:
            open_in_file_manager(footage_dir)

    def _update_import_combos(self):
        """更新导入面板的下拉列表"""
        self.cmb_target_episode.clear()
        self.cmb_target_cut.clear()

        if not self.project_config:
            return

        if self.project_config.get("no_episode", False):
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                self.cmb_target_episode.setCurrentIndex(-1)

            cuts = self.project_config.get("cuts", [])
            if cuts:
                self.cmb_target_cut.addItems(sorted(cuts))
        else:
            episodes = self.project_config.get("episodes", {})
            if episodes:
                self.cmb_target_episode.addItems(sorted(episodes.keys()))
                self.cmb_target_episode.setCurrentIndex(-1)

    def _import_to_folder(self, target_folder: Path):
        """导入文件到指定文件夹"""
        files, _ = QFileDialog.getOpenFileNames(
            self, f"选择要导入到 {target_folder.name} 的文件", ""
        )

        if not files:
            return

        imported_count = 0
        for file_path in files:
            src = Path(file_path)
            dst = target_folder / src.name

            if dst.exists():
                reply = QMessageBox.question(
                    self, "文件已存在",
                    f"文件 {src.name} 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    continue

            if copy_file_safe(src, dst):
                imported_count += 1

        if imported_count > 0:
            QMessageBox.information(
                self, "导入完成",
                f"成功导入 {imported_count} 个文件到 {target_folder.name}"
            )
            self._refresh_tree()

    def _import_aep_template(self, target_folder: Path):
        """导入AEP模板"""
        # 确定aep_templates文件夹路径
        if target_folder.name == "aep_templates":
            template_dir = target_folder
        else:
            template_dir = self.project_base / "07_master_assets" / "aep_templates"

        ensure_dir(template_dir)

        files, _ = QFileDialog.getOpenFileNames(
            self, "选择AEP模板文件", "", "AEP文件 (*.aep)"
        )

        if not files:
            return

        imported_count = 0
        for file_path in files:
            src = Path(file_path)
            dst = template_dir / src.name

            if dst.exists():
                reply = QMessageBox.question(
                    self, "文件已存在",
                    f"模板 {src.name} 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    continue

            if copy_file_safe(src, dst):
                imported_count += 1

        if imported_count > 0:
            QMessageBox.information(
                self, "导入完成",
                f"成功导入 {imported_count} 个AEP模板"
            )
            self._refresh_tree()