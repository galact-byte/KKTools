"""分享整理导入页：生成分享包 / 导入恢复 / 整理 / 离线对账 四个标签页。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import identity, manifest, mod_index, settings, share
from ui.applog import log
from ui.widgets import CardDropList, PageBase, hint, make_card, make_dir_row, section_title
from ui.worker import Worker

_INDEX_CACHE = settings.app_dir() / "mod_index.json"


class SharePage(PageBase):
    def __init__(self):
        super().__init__("分享整理导入", "生成分享包、导入恢复、整理文件、离线对账")
        self._worker: Worker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_generate_tab(), "生成分享包")
        tabs.addTab(self._build_restore_tab(), "导入 / 恢复")
        tabs.addTab(self._build_organize_tab(), "整理")
        tabs.addTab(self._build_reconcile_tab(), "离线对账")
        self.body_layout.addWidget(tabs, 1)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

    # ---------- 生成分享包 ----------

    def _build_generate_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("生成分享包"))
        v.addWidget(hint("依赖的 mod 取自 Mod 仓库索引；缺失的会记录在分享包的 README。请先在「Mod 仓库」建好索引。"))
        self.queue = CardDropList()
        v.addWidget(self.queue, 1)
        row = QHBoxLayout()
        b_add = QPushButton("加入角色卡"); b_add.clicked.connect(self._add)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.queue.clear)
        row.addWidget(b_add); row.addWidget(b_clr); row.addStretch(1)
        v.addLayout(row)
        _d, self.out_edit = make_dir_row("输出目录", settings.get("output_dir", "") or "", parent=self)
        v.addLayout(_d)
        self.chk_group = QCheckBox("按角色分组（每张卡一个子目录）"); self.chk_group.setChecked(True)
        v.addWidget(self.chk_group)

        # 排除参考清单（大整合）里已有的 mod，避免分享包塞入对方多半已有的 mod
        self.chk_exclude = QCheckBox("排除参考清单中已有的 mod（如大整合包，减小体积）")
        self.chk_exclude.toggled.connect(lambda on: self.exclude_row.setEnabled(on))
        v.addWidget(self.chk_exclude)
        erow = QHBoxLayout()
        self.exclude_edit = QLineEdit()
        self.exclude_edit.setPlaceholderText("参考清单文件（.json 清单或每行一个 GUID 的 .txt）")
        b_pick = QPushButton("…"); b_pick.setObjectName("MiniBtn"); b_pick.setFixedWidth(34)
        b_pick.clicked.connect(self._pick_exclude_list)
        erow.addWidget(QLabel("参考清单")); erow.addWidget(self.exclude_edit, 1); erow.addWidget(b_pick)
        self.exclude_row = QWidget(); self.exclude_row.setLayout(erow); self.exclude_row.setEnabled(False)
        v.addWidget(self.exclude_row)

        b_go = QPushButton("生成分享包"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._build)
        v.addWidget(b_go)
        self.result = QPlainTextEdit(); self.result.setReadOnly(True); self.result.setMaximumHeight(140)
        v.addWidget(self.result)
        return card

    def _add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择角色卡", "", "角色卡 PNG (*.png)")
        for f in files:
            self.queue.addItem(f)

    def _pick_exclude_list(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择参考清单（大整合）", "", "清单文件 (*.json *.txt);;所有文件 (*.*)")
        if path:
            self.exclude_edit.setText(path)

    def _build(self) -> None:
        files = [self.queue.item(i).text() for i in range(self.queue.count())]
        out = self.out_edit.text().strip()
        if not files:
            QMessageBox.warning(self, "队列为空", "请先加入角色卡。"); return
        if not out:
            QMessageBox.warning(self, "无输出目录", "请选择输出目录。"); return
        index = mod_index.ModIndex.load(_INDEX_CACHE)
        if index.count == 0:
            ret = QMessageBox.question(
                self, "索引为空",
                "尚未建立 Mod 索引，分享包将只含卡片、不含 mod。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        settings.set_value("output_dir", out)
        group = self.chk_group.isChecked()

        exclude_guids: set[str] = set()
        if self.chk_exclude.isChecked():
            ref = self.exclude_edit.text().strip()
            if not (ref and Path(ref).is_file()):
                QMessageBox.warning(self, "无参考清单", "已勾选排除，但未选择有效的参考清单文件。"); return
            try:
                exclude_guids = set(manifest.load_manifest(ref).get("guids", []))
            except OSError as exc:
                QMessageBox.critical(self, "读取失败", f"无法读取参考清单：{exc}"); return
            if not exclude_guids:
                QMessageBox.warning(self, "参考清单为空", "参考清单里没有解析到任何 GUID。"); return

        def job(progress=None):
            return share.build_share_package(
                files, index, out, group_by_char=group,
                exclude_guids=exclude_guids, progress=progress)

        self._run(job, self._on_built)

    def _on_built(self, report: dict) -> None:
        self.progress.setVisible(False)
        lines = [f"完成：{len(report['cards'])} 张卡",
                 f"复制 mod 种类: {len(report['copied_mods'])}",
                 f"总缺失 mod: {len(report['total_missing'])}"]
        if report.get("excluded_mods"):
            lines.append(f"按参考清单排除 mod 种类: {len(report['excluded_mods'])}")
        lines.append("")
        for c in report["cards"]:
            lines.append(f"[{c['name']}] 依赖{c['required']} 含{c['copied']} 缺{len(c['missing'])}")
        self.result.setPlainText("\n".join(lines))
        log("分享包生成完成")
        QMessageBox.information(self, "完成", "分享包已生成，详见输出目录的 README.txt。")

    # ---------- 导入 / 恢复 ----------

    def _build_restore_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("导入 / 恢复分享包"))
        v.addWidget(hint("从分享包(或任意含卡片/zipmod 的目录)把卡片复制回游戏角色目录、mod 复制回游戏 mods 目录。已存在同名则跳过。"))
        _d, self.rs_pkg = make_dir_row("分享包目录", parent=self); v.addLayout(_d)
        _d, self.rs_card = make_dir_row("卡片目标目录", parent=self); v.addLayout(_d)
        _d, self.rs_mod = make_dir_row("Mod 目标目录(可空)", parent=self); v.addLayout(_d)
        b = QPushButton("开始导入 / 恢复"); b.setProperty("accent", "primary")
        b.clicked.connect(self._do_restore)
        v.addWidget(b)
        self.rs_result = QPlainTextEdit(); self.rs_result.setReadOnly(True); self.rs_result.setMaximumHeight(120)
        v.addWidget(self.rs_result)
        v.addStretch(1)
        return card

    def _do_restore(self) -> None:
        pkg = self.rs_pkg.text().strip()
        card_t = self.rs_card.text().strip()
        mod_t = self.rs_mod.text().strip() or None
        if not (pkg and Path(pkg).is_dir()):
            QMessageBox.warning(self, "无效", "请选择有效的分享包目录。"); return
        if not card_t:
            QMessageBox.warning(self, "无效", "请选择卡片目标目录。"); return

        def job(progress=None):
            return share.restore_package(pkg, card_t, mod_t, progress=progress)

        def done(r):
            self.progress.setVisible(False)
            self.rs_result.setPlainText(
                f"恢复完成：\n卡片 复制 {r['cards']} / 跳过 {r['cards_skipped']}\n"
                f"Mod 复制 {r['mods']} / 跳过 {r['mods_skipped']}")
            log(f"导入恢复完成: {r}")
            QMessageBox.information(self, "完成", "导入 / 恢复完成。")

        self._run(job, done)

    # ---------- 整理 ----------

    def _build_organize_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("整理卡片"))
        v.addWidget(hint("扫描卡片目录，按类型或角色名归类到输出目录。默认复制(不动原目录)。"))
        _d, self.or_src = make_dir_row("卡片源目录", parent=self); v.addLayout(_d)
        _d, self.or_out = make_dir_row("整理输出目录", parent=self); v.addLayout(_d)
        opt = QHBoxLayout()
        self.or_by = QComboBox(); self.or_by.addItem("按类型", "type"); self.or_by.addItem("按角色名", "character")
        self.or_move = QCheckBox("移动(而非复制)")
        opt.addWidget(QLabel("方式")); opt.addWidget(self.or_by); opt.addWidget(self.or_move); opt.addStretch(1)
        v.addLayout(opt)
        b = QPushButton("开始整理"); b.setProperty("accent", "primary")
        b.clicked.connect(self._do_organize)
        v.addWidget(b)
        self.or_result = QPlainTextEdit(); self.or_result.setReadOnly(True); self.or_result.setMaximumHeight(100)
        v.addWidget(self.or_result)
        v.addStretch(1)
        return card

    def _do_organize(self) -> None:
        src = self.or_src.text().strip()
        out = self.or_out.text().strip()
        if not (src and Path(src).is_dir()):
            QMessageBox.warning(self, "无效", "请选择有效的卡片源目录。"); return
        if not out:
            QMessageBox.warning(self, "无效", "请选择整理输出目录。"); return
        by = self.or_by.currentData()
        move = self.or_move.isChecked()

        def job(progress=None):
            return share.organize_cards(src, out, by=by, move=move, progress=progress)

        def done(r):
            self.progress.setVisible(False)
            self.or_result.setPlainText(
                f"整理完成（{'移动' if r['move'] else '复制'}/{r['by']}）：处理 {r['processed']}，归类 {r['organized']}。")
            log(f"整理完成: {r}")
            QMessageBox.information(self, "完成", "整理完成。")

        self._run(job, done)

    # ---------- 离线对账 ----------

    def _build_reconcile_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)

        # ---- 模式一：目录对账（原有，按文件名比对） ----
        v.addWidget(section_title("目录对账（按文件名）"))
        v.addWidget(hint("比对两个目录的文件(按文件名)，列出只在A/只在B/共有，便于核对 mod 或卡片差异。"))
        _d, self.rc_a = make_dir_row("目录 A", parent=self); v.addLayout(_d)
        _d, self.rc_b = make_dir_row("目录 B", parent=self); v.addLayout(_d)
        b = QPushButton("开始对账"); b.setProperty("accent", "primary")
        b.clicked.connect(self._do_reconcile)
        v.addWidget(b)

        # ---- 模式二：清单对账（带身份戳，按 GUID 比对） ----
        v.addWidget(section_title("清单对账（带身份戳，按 GUID）"))
        ident = identity.get_identity()
        v.addWidget(hint(f"本机身份：{ident['display_name']}（{ident['library_id']}）。"
                         "导出清单发给朋友，或导入朋友的清单，按 mod 的 GUID 精确比对——"
                         "比文件名更可靠（同一 mod 改了文件名也能认出）。"))
        mrow = QHBoxLayout()
        b_exp = QPushButton("导出我的清单"); b_exp.clicked.connect(self._export_manifest)
        b_imp = QPushButton("导入对方清单并对账"); b_imp.clicked.connect(self._import_and_reconcile)
        self.b_fill = QPushButton("复制我能补给对方的 Mod"); self.b_fill.setEnabled(False)
        self.b_fill.clicked.connect(self._copy_fillable_for_peer)
        mrow.addWidget(b_exp); mrow.addWidget(b_imp); mrow.addWidget(self.b_fill); mrow.addStretch(1)
        v.addLayout(mrow)
        self._peer_mine_only: list[str] = []  # 上次对账得到的“我可补给对方”的 guid

        self.rc_result = QPlainTextEdit(); self.rc_result.setReadOnly(True)
        v.addWidget(self.rc_result, 1)
        return card

    def _load_index(self) -> mod_index.ModIndex:
        return mod_index.ModIndex.load(_INDEX_CACHE)

    def _export_manifest(self) -> None:
        index = self._load_index()
        if index.count == 0:
            QMessageBox.warning(self, "索引为空", "请先在「Mod 仓库」建立索引再导出清单。"); return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出我的清单", "我的Mod清单.kkmanifest.json", "清单文件 (*.json)")
        if not path:
            return
        n = manifest.export_manifest(index, path, identity.get_identity())
        log(f"已导出清单：{n} 个 mod -> {path}")
        QMessageBox.information(self, "已导出", f"清单已导出（{n} 个 mod）。\n可发给朋友用于对账互助。")

    def _import_and_reconcile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择对方的清单", "", "清单文件 (*.json *.txt);;所有文件 (*.*)")
        if not path:
            return
        index = self._load_index()
        if index.count == 0:
            QMessageBox.warning(self, "索引为空", "请先在「Mod 仓库」建立索引，才能与对方清单比对。"); return
        try:
            theirs = manifest.load_manifest(path)
        except OSError as exc:
            QMessageBox.critical(self, "读取失败", f"无法读取清单：{exc}"); return
        mine = manifest.build_manifest(index, identity.get_identity())
        rec = manifest.reconcile_manifests(mine, theirs)

        self._peer_mine_only = rec["mine_only"]
        self.b_fill.setEnabled(bool(rec["mine_only"]))
        peer = rec["theirs_identity"].get("display_name") or "对方"
        lines = [
            f"对方：{peer}    我方：{rec['mine_identity'].get('display_name','我')}",
            f"我方 {rec['mine_count']} 个 / 对方 {rec['theirs_count']} 个 / 共有 {rec['both']} 个",
            "",
            f"[我有、对方缺，共 {len(rec['mine_only'])}（可补给对方）]",
        ]
        lines += [f"  {g}" for g in rec["mine_only"][:300]]
        lines += ["", f"[对方有、我缺，共 {len(rec['theirs_only'])}（可向对方索取）]"]
        lines += [f"  {g}" for g in rec["theirs_only"][:300]]
        self.rc_result.setPlainText("\n".join(lines))
        log(f"清单对账：我{rec['mine_count']} 对方{rec['theirs_count']} 可补{len(rec['mine_only'])}")

    def _copy_fillable_for_peer(self) -> None:
        if not self._peer_mine_only:
            return
        target = QFileDialog.getExistingDirectory(self, "选择存放“补给对方 Mod”的目录")
        if not target:
            return
        index = self._load_index()
        copied, skipped = mod_index.copy_fillable(self._peer_mine_only, index, target)
        log(f"补给对方 mod：复制 {copied} / 跳过 {skipped}")
        QMessageBox.information(self, "完成", f"已复制 {copied} 个 mod 到目标目录（跳过 {skipped}）。\n打包发给对方即可。")

    def _do_reconcile(self) -> None:
        a = self.rc_a.text().strip(); b = self.rc_b.text().strip()
        if not (a and Path(a).is_dir() and b and Path(b).is_dir()):
            QMessageBox.warning(self, "无效", "请选择两个有效目录。"); return
        rec = share.reconcile_dirs(a, b)
        lines = [
            f"目录A: {rec['count_a']} 个文件   目录B: {rec['count_b']} 个文件   共有: {rec['both']}",
            "",
            f"[只在 A，共 {len(rec['only_a'])}]",
        ]
        lines += [f"  {n}" for n in rec["only_a"][:300]]
        lines += ["", f"[只在 B，共 {len(rec['only_b'])}]"]
        lines += [f"  {n}" for n in rec["only_b"][:300]]
        self.rc_result.setPlainText("\n".join(lines))
        log(f"离线对账: A{rec['count_a']} B{rec['count_b']} 只在A{len(rec['only_a'])} 只在B{len(rec['only_b'])}")

    # ---------- 公共后台执行 ----------

    def _run(self, job, on_done) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "已有任务进行中。"); return
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self._worker = Worker(job)
        self._worker.progress.connect(
            lambda c, t, d: (self.progress.setRange(0, t), self.progress.setValue(c)) if t else None)
        self._worker.finished_ok.connect(on_done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        QMessageBox.critical(self, "失败", msg.splitlines()[0])
