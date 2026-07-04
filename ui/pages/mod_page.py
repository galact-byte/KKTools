"""Mod 仓库 / 缺失检测 页。

扫描 mod 目录建立 GUID 索引（可缓存），把角色卡加入检查队列，比对依赖找出缺失。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import mod_index, settings
from ui.applog import log
from ui.widgets import CardDropList, PageBase, hint, make_card, section_title
from ui.worker import Worker

_INDEX_CACHE = settings.app_dir() / "mod_index.json"


class ModPage(PageBase):
    def __init__(self):
        super().__init__("Mod 仓库", "扫描本地 zipmod 建立 GUID 索引，检测角色卡缺失的 mod")
        self.index = mod_index.ModIndex.load(_INDEX_CACHE)
        self._worker: Worker | None = None
        self._build_ui()
        self._refresh_index_status()

    def _build_ui(self) -> None:
        # 索引区
        idx_card = make_card()
        iv = QVBoxLayout(idx_card)
        iv.setContentsMargins(14, 14, 14, 14)
        iv.addWidget(section_title("Mod 索引"))
        self.index_status = QLabel()
        self.index_status.setObjectName("HintLabel")
        iv.addWidget(self.index_status)
        row = QHBoxLayout()
        b_build = QPushButton("建立 / 重建索引"); b_build.setProperty("accent", "primary")
        b_build.clicked.connect(self._build_index)
        b_dirs = QPushButton("配置 Mod 目录")
        b_dirs.clicked.connect(self._config_dirs)
        b_author = QPushButton("按作者名整理Mod")
        b_author.clicked.connect(self._organize_by_author)
        b_archive = QPushButton("归档未引用Mod")
        b_archive.clicked.connect(self._archive_unreferenced)
        b_clear = QPushButton("清空索引数据")
        b_clear.clicked.connect(self._clear_index)
        row.addWidget(b_build); row.addWidget(b_dirs)
        row.addWidget(b_author); row.addWidget(b_archive); row.addWidget(b_clear)
        row.addStretch(1)
        iv.addLayout(row)
        row_share = QHBoxLayout()
        b_exp_list = QPushButton("导出本机Mod清单")
        b_exp_list.clicked.connect(self._export_my_list)
        b_imp_cmp = QPushButton("导入清单比对")
        b_imp_cmp.clicked.connect(self._import_compare)
        b_exp_zip = QPushButton("按清单导出压缩包")
        b_exp_zip.clicked.connect(self._export_list_zip)
        row_share.addWidget(QLabel("清单互助"))
        row_share.addWidget(b_exp_list); row_share.addWidget(b_imp_cmp); row_share.addWidget(b_exp_zip)
        row_share.addStretch(1)
        iv.addLayout(row_share)
        iv.addWidget(hint(f"索引缓存: {_INDEX_CACHE.name}（关闭后保留，下次直接加载）"))
        self.body_layout.addWidget(idx_card)

        # 检查区
        chk = make_card()
        cv = QVBoxLayout(chk)
        cv.setContentsMargins(14, 14, 14, 14)
        cv.addWidget(section_title("卡片 Mod 检查队列"))
        cv.addWidget(hint("拖入或选择角色卡 / 场景卡 PNG，检查它们依赖的 mod 在本地索引中是否齐全。"))
        body = QHBoxLayout()
        self.queue = CardDropList()
        body.addWidget(self.queue, 1)
        self.result = QPlainTextEdit(); self.result.setReadOnly(True)
        body.addWidget(self.result, 2)
        cv.addLayout(body, 1)
        row2 = QHBoxLayout()
        b_add = QPushButton("加入角色卡"); b_add.clicked.connect(self._add_cards)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.queue.clear)
        b_chk = QPushButton("检查队列"); b_chk.setProperty("accent", "primary")
        b_chk.clicked.connect(self._check)
        b_fill = QPushButton("复制可补 Mod"); b_fill.clicked.connect(self._copy_fillable)
        b_exp = QPushButton("导出缺失清单"); b_exp.clicked.connect(self._export_missing)
        row2.addWidget(b_add); row2.addWidget(b_clr); row2.addStretch(1)
        row2.addWidget(b_chk); row2.addWidget(b_fill); row2.addWidget(b_exp)
        cv.addLayout(row2)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        cv.addWidget(self.progress)
        self.body_layout.addWidget(chk, 1)

        self._last_missing: dict[str, list[str]] = {}
        self._last_present: list[str] = []

    # ---- 索引 ----

    def _refresh_index_status(self) -> None:
        self.index_status.setText(f"当前索引：{self.index.count} 个 mod（按 guid 去重）")

    def _config_dirs(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择一个 Mod 目录加入仓库")
        if not d:
            return
        cfg = settings.load()
        dirs = list(cfg.get("mod_dirs", []))
        if d not in dirs:
            dirs.append(d)
            settings.set_value("mod_dirs", dirs)
            QMessageBox.information(self, "已添加", f"已加入 Mod 目录：\n{d}\n请重建索引生效。")

    def _build_index(self) -> None:
        dirs = settings.guess_mod_dirs()
        if not dirs:
            QMessageBox.warning(
                self, "无 Mod 目录",
                "未配置 Mod 目录。请先在「软件设置」填游戏目录，或点「配置 Mod 目录」添加。")
            return
        if self._worker and self._worker.isRunning():
            return
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        first = self.index.count == 0
        self.index_status.setText(
            "首次建立索引中…（mod 多时较慢，机械硬盘上万个 mod 可能数分钟，仅此一次）"
            if first else "增量更新索引中…（只扫新增/变动的 mod，通常很快）")
        log(f"建立 Mod 索引，目录: {dirs}，增量={not first}")

        previous = self.index   # 增量：复用已加载缓存中未变动的条目

        def job(progress=None):
            idx = mod_index.ModIndex().build(
                dirs,
                progress=lambda c, f: progress(c, 0, f) if progress else None,
                previous=previous,
            )
            idx.save(_INDEX_CACHE)
            return idx

        self._worker = Worker(job)
        self._worker.progress.connect(lambda c, t, f: self.index_status.setText(f"扫描中… 已处理 {c}  {Path(f).name}"))
        self._worker.finished_ok.connect(self._on_indexed)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_indexed(self, idx) -> None:
        self.index = idx
        self.progress.setVisible(False)
        self._refresh_index_status()
        log(f"Mod 索引完成：{idx.count} 个")
        QMessageBox.information(self, "完成", f"索引建立完成，共 {idx.count} 个 mod。")

    # ---- 检查 ----

    def _add_cards(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择角色卡 / 场景卡", "", "卡片 PNG (*.png)")
        for f in files:
            self.queue.addItem(f)

    def _check(self) -> None:
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        files = [self.queue.item(i).text() for i in range(self.queue.count())]
        if not files:
            QMessageBox.warning(self, "队列为空", "请先加入角色卡。"); return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "已有任务进行中。"); return

        index = self.index

        def job(progress=None):
            lines, missing, present = [], {}, set()
            total = len(files)
            for i, f in enumerate(files, 1):
                try:
                    rep = mod_index.check_card(f, index)
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"[X] {Path(f).name}: {exc}")
                    if progress:
                        progress(i, total, Path(f).name)
                    continue
                present.update(rep.present)
                lines.append(
                    f"[{'OK' if rep.missing_count == 0 else '缺'}] {Path(f).name}  "
                    f"所需 {rep.required_count} | 命中 {len(rep.present)} | 缺失 {rep.missing_count}")
                if rep.missing:
                    missing[f] = rep.missing
                    lines.extend(f"      - {g}" for g in rep.missing)
                if progress:
                    progress(i, total, Path(f).name)
            return lines, missing, sorted(present)

        self.progress.setVisible(True); self.progress.setRange(0, len(files))
        self.result.setPlainText("检查中…")
        self._worker = Worker(job)
        self._worker.progress.connect(lambda c, t, d: self.progress.setValue(c))
        self._worker.finished_ok.connect(self._on_checked)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_checked(self, result) -> None:
        lines, missing, present = result
        self.progress.setVisible(False)
        self._last_missing = missing
        self._last_present = present
        self.result.setPlainText("\n".join(lines))
        log(f"检查完成，缺失记录 {len(missing)} 张，可补 {len(present)} 个")

    def _export_missing(self) -> None:
        if not self._last_missing:
            QMessageBox.information(self, "无缺失", "没有缺失记录可导出（先检查队列）。"); return
        path, _ = QFileDialog.getSaveFileName(self, "导出缺失清单", "missing_mods.txt", "文本 (*.txt)")
        if not path:
            return
        out = []
        for card, miss in self._last_missing.items():
            out.append(f"# {Path(card).name}")
            out.extend(miss)
            out.append("")
        Path(path).write_text("\n".join(out), encoding="utf-8")
        log(f"导出缺失清单: {path}")
        QMessageBox.information(self, "已导出", f"已导出到:\n{path}")

    def _on_failed(self, msg) -> None:
        self.progress.setVisible(False)
        self.index_status.setText("索引失败")
        QMessageBox.critical(self, "失败", msg.splitlines()[0])

    # ---- 整理 / 归档 / 复制 / 清空 ----

    def _clear_index(self) -> None:
        ret = QMessageBox.question(
            self, "清空索引数据",
            "确定清空索引（含缓存文件 mod_index.json）？卡片检查将需要重新建立索引。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.index = mod_index.ModIndex()
        try:
            if _INDEX_CACHE.exists():
                _INDEX_CACHE.unlink()
        except OSError:
            pass
        self._refresh_index_status()
        log("已清空 Mod 索引数据")
        QMessageBox.information(self, "已清空", "索引数据已清空。")

    def _ask_move(self):
        """返回 True=移动 / False=复制 / None=取消。"""
        box = QMessageBox(self)
        box.setWindowTitle("整理方式")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("复制 = 安全，不改动原 mod 库（占额外磁盘）\n移动 = 就地整理，省空间但会改动原库（之后需重建索引）")
        copy_btn = box.addButton("复制(推荐)", QMessageBox.ButtonRole.AcceptRole)
        move_btn = box.addButton("移动", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        c = box.clickedButton()
        if c is copy_btn:
            return False
        if c is move_btn:
            return True
        return None

    def _run_bg(self, job, label, on_done) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "已有任务进行中。"); return
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self.index_status.setText(f"{label}中…")
        self._worker = Worker(job)
        self._worker.progress.connect(
            lambda c, t, d: (self.progress.setRange(0, t), self.progress.setValue(c)) if t else None)
        self._worker.finished_ok.connect(on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _organize_by_author(self) -> None:
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        move = self._ask_move()
        if move is None:
            return
        target = QFileDialog.getExistingDirectory(self, "选择整理输出目录")
        if not target:
            return
        idx = self.index

        def job(progress=None):
            return mod_index.organize_by_author(idx, target, move=move, progress=progress)

        def done(res):
            self.progress.setVisible(False)
            self._refresh_index_status()
            log(f"按作者整理完成: {res}")
            msg = f"按作者整理完成（{'移动' if res['move'] else '复制'}）：成功 {res['done']}，跳过 {res['skipped']}。"
            if res["move"]:
                msg += "\n原库已变动，请重建索引。"
            QMessageBox.information(self, "完成", msg)

        self._run_bg(job, "按作者整理", done)

    def _archive_unreferenced(self) -> None:
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        card_dir = QFileDialog.getExistingDirectory(self, "选择卡片目录（归档没被这些卡引用的 mod）")
        if not card_dir:
            return
        cards = [str(p) for p in Path(card_dir).rglob("*.png")]
        if not cards:
            QMessageBox.warning(self, "无卡片", "该目录下没有 PNG 卡片。"); return
        move = self._ask_move()
        if move is None:
            return
        archive = QFileDialog.getExistingDirectory(self, "选择归档输出目录")
        if not archive:
            return
        ret = QMessageBox.question(
            self, "确认归档",
            f"将扫描 {len(cards)} 张卡片，把没被它们引用的 mod {'移动' if move else '复制'}到归档目录。\n"
            "（未引用是相对于所选卡片而言，请确保卡片齐全）继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        idx = self.index

        def job(progress=None):
            return mod_index.archive_unreferenced(idx, cards, archive, move=move, progress=progress)

        def done(res):
            self.progress.setVisible(False)
            self._refresh_index_status()
            log(f"归档未引用完成: {res}")
            msg = (f"归档完成（{'移动' if res['move'] else '复制'}）：被引用 {res['used']}，"
                   f"归档 {res['archived']} / 共 {res['total']}。")
            if res["move"]:
                msg += "\n原库已变动，请重建索引。"
            QMessageBox.information(self, "完成", msg)

        self._run_bg(job, "归档未引用", done)

    def _copy_fillable(self) -> None:
        if not self._last_present:
            QMessageBox.information(self, "无可补 Mod", "请先「检查队列」，本小姐会记录命中(可补)的 mod。"); return
        target = QFileDialog.getExistingDirectory(self, "选择复制目标目录（如游戏 mods 目录）")
        if not target:
            return
        copied, skipped = mod_index.copy_fillable(self._last_present, self.index, target)
        log(f"复制可补 Mod: 复制 {copied}，跳过 {skipped} -> {target}")
        QMessageBox.information(self, "完成", f"已复制 {copied} 个可补 mod（跳过 {skipped} 个已存在/缺失）到:\n{target}")

    # ---- 清单互助 ----

    def _export_my_list(self) -> None:
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        path, _ = QFileDialog.getSaveFileName(self, "导出本机 Mod 清单", "my_mods.txt", "文本 (*.txt)")
        if not path:
            return
        n = mod_index.export_guid_list(self.index, path)
        log(f"导出本机 Mod 清单 {n} 条 -> {path}")
        QMessageBox.information(self, "已导出", f"已导出本机 {n} 个 mod 的 guid 清单到:\n{path}\n可发给朋友比对。")

    def _export_list_zip(self) -> None:
        """按一份 GUID 清单，把本机索引里存在的对应 zipmod 直接打成一个 zip。"""
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        list_path, _ = QFileDialog.getOpenFileName(
            self, "选择要导出的 Mod 清单", "", "清单文件 (*.txt *.json);;所有文件 (*.*)")
        if not list_path:
            return
        guids = mod_index.parse_guid_list(list_path)
        if not guids:
            QMessageBox.warning(self, "空清单", "未从该文件解析到任何 guid。"); return
        have = [g for g in guids if g in self.index]
        if not have:
            QMessageBox.information(self, "无可导出", "清单里的 mod 本机一个都没有，无法导出。"); return
        out_zip, _ = QFileDialog.getSaveFileName(self, "导出压缩包", "mods_export.zip", "Zip (*.zip)")
        if not out_zip:
            return
        idx = self.index

        def job(progress=None):
            return mod_index.export_as_zip(have, idx, out_zip, progress=progress)

        def done(res):
            self.progress.setVisible(False)
            self._refresh_index_status()
            added, skipped = res
            log(f"按清单导出压缩包: 打入 {added}，跳过 {skipped} -> {out_zip}")
            QMessageBox.information(
                self, "完成",
                f"清单 {len(guids)} 个 / 本机有 {len(have)} 个，已打入压缩包 {added} 个（跳过 {skipped}）：\n{out_zip}")

        self._run_bg(job, "按清单导出压缩包", done)

    def _import_compare(self) -> None:
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        path, _ = QFileDialog.getOpenFileName(self, "导入清单比对", "", "文本 (*.txt);;所有文件 (*.*)")
        if not path:
            return
        guids = mod_index.parse_guid_list(path)
        if not guids:
            QMessageBox.warning(self, "空清单", "未从该文件解析到任何 guid。"); return
        res = mod_index.compare_guid_list(guids, self.index)
        lines = [
            f"清单比对：{path}",
            f"清单共 {res['total']} 个 mod。",
            f"本机已有(可补给对方): {len(res['have'])} 个",
            f"本机也缺: {len(res['lack'])} 个",
            "",
            "[本机已有 —— 可复制出来给对方]",
        ]
        lines += [f"  {g}" for g in res["have"][:200]]
        if len(res["have"]) > 200:
            lines.append(f"  …另有 {len(res['have']) - 200} 个")
        lines += ["", "[本机也缺]"]
        lines += [f"  {g}" for g in res["lack"][:200]]
        self.result.setPlainText("\n".join(lines))
        log(f"清单比对: 清单{res['total']} 本机有{len(res['have'])} 缺{len(res['lack'])}")
        if res["have"]:
            ret = QMessageBox.question(
                self, "复制可补给对方的 Mod",
                f"本机有 {len(res['have'])} 个对方清单需要的 mod，是否复制出来打包给对方？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.Yes:
                target = QFileDialog.getExistingDirectory(self, "选择复制目标目录")
                if target:
                    copied, skipped = mod_index.copy_fillable(res["have"], self.index, target)
                    QMessageBox.information(self, "完成", f"已复制 {copied} 个（跳过 {skipped}）到:\n{target}")
