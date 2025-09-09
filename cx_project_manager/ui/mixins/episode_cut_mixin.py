# -*- coding: utf-8 -*-
"""Episode和Cut管理功能混入类"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QMessageBox, QInputDialog, QDialog
from PySide6.QtCore import Qt

from ...utils.models import ReuseCut
from ...ui.dialogs import ReuseCutDialog


class EpisodeCutMixin:
    """Episode和Cut管理相关功能"""

    # 需要在主类中定义的属性
    project_base: Optional[Path]
    project_config: Optional[dict]
    project_manager: any
    cmb_episode_type: any
    txt_episode: any
    chk_auto_prefix: any
    chk_no_episode: any
    spin_ep_from: any
    spin_ep_to: any
    txt_cut: any
    cmb_cut_episode: any
    spin_cut_from: any
    spin_cut_to: any
    episode_group: any
    btn_create_episode: any
    btn_batch_episode: any
    statusbar: any

    def create_episode(self):
        """创建单个Episode"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        ep_type = self.cmb_episode_type.currentText().strip().lower()
        ep_identifier = self.txt_episode.text().strip()

        if self.chk_no_episode.isChecked() and ep_type == "ep":
            QMessageBox.information(
                self, "提示",
                "单集/PV 模式下不支持创建标准集数 (ep)，\n"
                "但可以创建其他类型如 op、ed、pv 等。"
            )
            return

        success, result = self.project_manager.create_episode(ep_type, ep_identifier)

        if success:
            self._refresh_all_views()
            self.statusbar.showMessage(f"已创建 Episode: {result}", 3000)
        else:
            QMessageBox.warning(self, "错误", result)

    def batch_create_episodes(self):
        """批量创建Episode"""
        if self.cmb_episode_type.currentText().lower() != "ep":
            QMessageBox.warning(self, "错误", "批量创建仅支持 'ep' 类型")
            return

        start = self.spin_ep_from.value()
        end = self.spin_ep_to.value()

        if start > end:
            QMessageBox.warning(self, "错误", "起始编号不能大于结束编号")
            return

        created_count = 0
        for i in range(start, end + 1):
            success, _ = self.project_manager.create_episode("ep", str(i))
            if success:
                created_count += 1

        if created_count > 0:
            QMessageBox.information(self, "完成", f"成功创建 {created_count} 个 Episode")
            self._refresh_all_views()

    def create_cut(self, show_error=True):
        """创建单个Cut"""
        if not self.project_base:
            if show_error:
                QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        cut_num = self.txt_cut.text().strip()

        # 获取Episode ID
        episode_id = None
        if self.chk_no_episode.isChecked():
            ep_text = self.cmb_cut_episode.currentText().strip()
            if ep_text and ep_text in self.project_config.get("episodes", {}):
                episode_id = ep_text
        else:
            episode_id = self.cmb_cut_episode.currentText().strip()

        success, result = self.project_manager.create_cut(cut_num, episode_id)

        if success:
            if show_error:
                self._refresh_all_views()
                self.statusbar.showMessage(f"已创建 Cut: {result} (含 06_render 输出目录)", 3000)
        else:
            if show_error:
                QMessageBox.warning(self, "错误", result)

    def batch_create_cuts(self):
        """批量创建Cut"""
        start = self.spin_cut_from.value()
        end = self.spin_cut_to.value()

        if start > end:
            QMessageBox.warning(self, "错误", "起始编号不能大于结束编号")
            return

        episode_id = None
        if self.chk_no_episode.isChecked():
            ep_text = self.cmb_cut_episode.currentText().strip()
            if ep_text and ep_text in self.project_config.get("episodes", {}):
                episode_id = ep_text
        else:
            episode_id = self.cmb_cut_episode.currentText().strip()
            if not episode_id:
                QMessageBox.warning(self, "错误", "批量创建需要先选择 Episode")
                return

        created_count = 0
        for i in range(start, end + 1):
            success, _ = self.project_manager.create_cut(str(i), episode_id)
            if success:
                created_count += 1

        if created_count > 0:
            QMessageBox.information(self, "完成", f"成功创建 {created_count} 个 Cut")
            self._refresh_all_views()

    def create_reuse_cut(self):
        """创建兼用卡"""
        if not self.project_base:
            QMessageBox.warning(self, "错误", "请先打开或创建项目")
            return

        # 获取Episode ID
        episode_id = None
        if not self.chk_no_episode.isChecked():
            episode_id = self.cmb_cut_episode.currentText().strip()
            if not episode_id:
                episodes = list(self.project_config.get("episodes", {}).keys())
                if not episodes:
                    QMessageBox.warning(self, "错误", "请先创建Episode")
                    return

                episode_id, ok = QInputDialog.getItem(
                    self, "选择Episode",
                    "请选择要创建兼用卡的Episode:",
                    episodes, 0, False
                )
                if not ok:
                    return
        else:
            selected_ep = self.cmb_cut_episode.currentText().strip()
            if selected_ep and selected_ep in self.project_config.get("episodes", {}):
                episode_id = selected_ep

        # 显示对话框
        dialog = ReuseCutDialog(self.project_config, episode_id, self)
        if dialog.exec() == QDialog.Accepted:
            cuts = dialog.get_cuts()
            success, message = self.project_manager.create_reuse_cut(cuts, episode_id)

            if success:
                QMessageBox.information(self, "成功", message)
                self._refresh_all_views()
                self.statusbar.showMessage(message, 5000)
            else:
                QMessageBox.warning(self, "错误", message)

    def _on_episode_type_changed(self, episode_type: str):
        """Episode类型变化时的处理"""
        if self.chk_no_episode.isChecked() and episode_type.lower() == "ep":
            self.btn_create_episode.setEnabled(False)
            self.btn_batch_episode.setEnabled(False)
            self.spin_ep_from.setEnabled(False)
            self.spin_ep_to.setEnabled(False)
            self.btn_create_episode.setToolTip("单集模式下不能创建标准集数(ep)")
        else:
            self.btn_create_episode.setEnabled(True)
            self.btn_create_episode.setToolTip("")

        if episode_type.lower() == "ep" and not self.chk_no_episode.isChecked():
            self.txt_episode.setPlaceholderText("编号 (如: 01, 02) - 可留空")
            self.btn_batch_episode.setEnabled(True)
            self.spin_ep_from.setEnabled(True)
            self.spin_ep_to.setEnabled(True)
        else:
            self.txt_episode.setPlaceholderText("名称或编号 (可选) - 可留空")
            self.btn_batch_episode.setEnabled(False)
            self.spin_ep_from.setEnabled(False)
            self.spin_ep_to.setEnabled(False)

    def _on_episode_changed(self, episode: str):
        """Episode选择变化时更新Cut列表"""
        self.cmb_target_cut.clear()

        if not self.project_config or not episode:
            if self.project_config and self.project_config.get("no_episode", False):
                cuts = self.project_config.get("cuts", [])
                if cuts:
                    self.cmb_target_cut.addItems(sorted(cuts))
            return

        cuts = self.project_config.get("episodes", {}).get(episode, [])
        if cuts:
            self.cmb_target_cut.addItems(sorted(cuts))

    def _toggle_episode_mode(self, state: int):
        """切换Episode模式"""
        no_episode = self.chk_no_episode.isChecked()

        if no_episode:
            self.episode_group.setEnabled(True)
            self.episode_group.setTitle("🎬 特殊 Episode 管理 (op/ed/pv等)")
            if self.cmb_episode_type.currentText().lower() == "ep":
                self.cmb_episode_type.setCurrentText("pv")
        else:
            self.episode_group.setEnabled(True)
            self.episode_group.setTitle("🎬 Episode 管理")

        self.cmb_cut_episode.setVisible(True)
        if no_episode:
            self.cmb_cut_episode.setPlaceholderText("选择特殊 Episode (可选)")
        else:
            self.cmb_cut_episode.setPlaceholderText("选择 Episode")

        self.cmb_target_episode.setVisible(True)

        if self.project_config:
            self.project_config["no_episode"] = no_episode
            self.project_manager.project_config = self.project_config
            self.project_manager.save_config()
            self._update_import_combos()
            self._update_cut_episode_combo()

    def _update_cut_episode_combo(self):
        """更新Cut管理中的Episode下拉列表"""
        self.cmb_cut_episode.clear()

        if not self.project_config:
            return

        episodes = self.project_config.get("episodes", {})
        if episodes:
            self.cmb_cut_episode.addItems(sorted(episodes.keys()))
            self.cmb_cut_episode.setCurrentIndex(-1)