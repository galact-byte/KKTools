"""解包 / 打包 / 隐写伪装 / 分卷 页。

左：解包（含识别伪装在视频后的压缩包）。右：把文件夹打包并伪装成载体文件，可分卷。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import settings, stego
from ui.applog import log
from core.diagnostics import logger
from ui.widgets import (
    FORM_LABEL_W,
    PageBase,
    field_label,
    hint,
    indent_row,
    install_empty_hint,
    make_card,
    section_title,
)
from ui.worker import Worker


class _DropList(QListWidget):
    """接受拖入文件的列表。"""

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p and Path(p).is_file():
                self.addItem(p)


class PackPage(PageBase):
    def __init__(self):
        super().__init__("解包 / 打包", "压缩、伪装隐写、分卷处理")
        self._worker: Worker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._build_unpack(), 1)
        self.pack_scroll = QScrollArea()
        self.pack_scroll.setWidgetResizable(True)
        self.pack_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.pack_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pack_scroll.setWidget(self._build_pack())
        cols.addWidget(self.pack_scroll, 1)
        self.body_layout.addLayout(cols, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

    # ---- 解包 ----

    def _build_unpack(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)
        v.addWidget(section_title("解包"))
        v.addWidget(hint("拖入或选择压缩包 / 伪装文件（视频后接 zip 也能识别），解压到输出目录。"))
        self.unpack_list = _DropList()
        install_empty_hint(self.unpack_list, "把压缩包或伪装文件拖到这里，或点击下方「选择文件」")
        v.addWidget(self.unpack_list, 1)
        row = QHBoxLayout()
        b_add = QPushButton("选择文件"); b_add.clicked.connect(self._add_unpack)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.unpack_list.clear)
        row.addWidget(b_add); row.addWidget(b_clr); row.addStretch(1)
        v.addLayout(row)
        out = QHBoxLayout()
        self.unpack_out = QLineEdit(settings.get("output_dir", "") or "")
        self.unpack_out.setPlaceholderText("解包输出目录")
        b_out = QPushButton("…"); b_out.setObjectName("MiniBtn"); b_out.setFixedWidth(34)
        b_out.clicked.connect(lambda: self._pick_dir(self.unpack_out))
        out.addWidget(field_label("输出目录", FORM_LABEL_W)); out.addWidget(self.unpack_out, 1); out.addWidget(b_out)
        v.addLayout(out)
        pw_row = QHBoxLayout()
        self.unpack_pwds = QLineEdit()
        self.unpack_pwds.setPlaceholderText("加密包才需要；多个密码用逗号分隔")
        pw_row.addWidget(field_label("解密密码", FORM_LABEL_W)); pw_row.addWidget(self.unpack_pwds, 1)
        v.addLayout(pw_row)
        self.opt_del_src = QCheckBox("解包成功后删除源文件")
        self.opt_clear_queue = QCheckBox("解压完清空队列")
        v.addLayout(indent_row(self.opt_del_src, self.opt_clear_queue))
        b_go = QPushButton("开始解包"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._do_unpack)
        v.addWidget(b_go)
        return card

    def _add_unpack(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择压缩包/伪装文件", "", "所有文件 (*.*)")
        for f in files:
            self.unpack_list.addItem(f)

    def _do_unpack(self) -> None:
        files = [self.unpack_list.item(i).text() for i in range(self.unpack_list.count())]
        out = self.unpack_out.text().strip()
        if not files:
            QMessageBox.warning(self, "无文件", "请先添加要解包的文件。")
            return
        if not out:
            QMessageBox.warning(self, "无输出目录", "请选择解包输出目录。")
            return
        settings.set_value("output_dir", out)
        del_src = self.opt_del_src.isChecked()
        clear_q = self.opt_clear_queue.isChecked()
        pwds = [p.strip() for p in self.unpack_pwds.text().split(",") if p.strip()]

        def job(progress=None):
            results = []
            for idx, f in enumerate(files, 1):
                if not stego.looks_like_zip(f):
                    results.append(f"[跳过] 非压缩包: {Path(f).name}")
                    continue
                sub = Path(out) / Path(f).stem
                seal_layers = stego.read_seal_layers(f)
                try:
                    if seal_layers and seal_layers >= 2:
                        if len(pwds) < seal_layers:
                            results.append(f"[X] {Path(f).name}: 这是 {seal_layers} 层封缄，"
                                           f"需 {seal_layers} 个密码（逗号分隔，从内到外），当前 {len(pwds)} 个")
                            continue
                        names = stego.extract_layered(f, sub, pwds, layers=seal_layers)
                        results.append(f"[OK] {Path(f).name} (解封{seal_layers}层) -> {len(names)} 个文件")
                        if progress:
                            progress(idx, len(files), Path(f).name)
                        if del_src:
                            self._try_delete(f, results)
                        continue
                    names = stego.extract_archive(f, sub, passwords=pwds)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("解包失败: %s", Path(f).name)
                    results.append(f"[X] {Path(f).name}: {exc}（可能需要正确密码）")
                    continue
                results.append(f"[OK] {Path(f).name} -> {len(names)} 个文件")
                if del_src:
                    self._try_delete(f, results)
                if progress:
                    progress(idx, len(files), Path(f).name)
            return results

        self._run(job, "解包")
        if clear_q and self._worker:
            self._worker.finished_ok.connect(lambda *_: self.unpack_list.clear())

    @staticmethod
    def _try_delete(path, results: list) -> None:
        try:
            Path(path).unlink()
            results.append(f"      已删除源文件: {Path(path).name}")
        except OSError as exc:
            results.append(f"      [!] 删除源文件失败: {exc}")

    # ---- 打包伪装 ----

    def _build_pack(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)
        v.addWidget(section_title("打包并伪装"))
        v.addWidget(hint("把文件夹或指定文件压缩后追加到真实视频/图片之后，生成既能播放又能解压的伪装文件。"))

        modes = QWidget()
        mode_row = QHBoxLayout(modes)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(8)
        mode_row.addWidget(field_label("打包来源", FORM_LABEL_W))
        self.pack_by_folder = QRadioButton("整个文件夹", modes)
        self.pack_by_files = QRadioButton("指定文件", modes)
        self.pack_by_folder.setChecked(True)
        mode_row.addWidget(self.pack_by_folder)
        mode_row.addWidget(self.pack_by_files)
        mode_row.addStretch(1)
        v.addWidget(modes)

        self.folder_source = QWidget()
        folder_layout = QVBoxLayout(self.folder_source)
        folder_layout.setContentsMargins(0, 0, 0, 0); folder_layout.setSpacing(8)
        self.pack_folder = self._path_row(folder_layout, "待打包文件夹", pick_dir=True)
        v.addWidget(self.folder_source)

        self.file_source = QWidget()
        file_layout = QVBoxLayout(self.file_source)
        file_layout.setContentsMargins(0, 0, 0, 0); file_layout.setSpacing(8)
        self.pack_file_list = QListWidget()
        install_empty_hint(self.pack_file_list, "点击「添加文件」选择要打包的 Mod")
        self.pack_file_list.setFixedHeight(100)
        self.pack_file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.pack_file_list.setToolTip("包内仅包含列表中的文件；同名文件不能同时打包")
        list_row = QHBoxLayout()
        list_label = field_label("已选文件", FORM_LABEL_W)
        list_row.addWidget(list_label, 0, Qt.AlignmentFlag.AlignTop)
        list_row.addWidget(self.pack_file_list, 1)
        file_layout.addLayout(list_row)
        file_row = QHBoxLayout()
        file_row.addWidget(field_label("", FORM_LABEL_W))
        b_add_files = QPushButton("添加文件")
        b_add_files.clicked.connect(self._add_pack_files)
        b_remove_files = QPushButton("移除所选")
        b_remove_files.clicked.connect(self._remove_pack_files)
        self.pack_file_count = QLabel("已选择 0 个文件")
        file_row.addWidget(b_add_files)
        file_row.addWidget(b_remove_files)
        file_row.addWidget(self.pack_file_count)
        file_row.addStretch(1)
        file_layout.addLayout(file_row)
        v.addWidget(self.file_source)
        self.pack_by_folder.toggled.connect(self._on_pack_source_changed)
        self._on_pack_source_changed(True)

        self.pack_carrier = self._path_row(v, "载体文件", pick_dir=False)
        self.pack_carrier.setPlaceholderText("真实的视频或图片，打包结果仍可正常播放/查看")

        # [高级] 素材池：从一个目录里随机抽载体，每次伪装外壳都不同、更隐蔽
        self.adv_pool = QWidget()
        pv = QVBoxLayout(self.adv_pool); pv.setContentsMargins(0, 0, 0, 0); pv.setSpacing(8)
        self.use_pool = QCheckBox("改用素材池：从目录随机抽一个载体")
        self.use_pool.toggled.connect(self._on_pool_toggled)
        pv.addLayout(indent_row(self.use_pool))
        self.pool_dir = self._path_row(pv, "素材池目录", pick_dir=True)
        self.pool_dir.setEnabled(False)
        v.addWidget(self.adv_pool)

        self.pack_out = self._path_row(v, "输出文件", pick_dir=False, save=True,
                                       start_dir=settings.get("pack_out_dir", "") or "")

        # [高级] 分卷
        self.adv_split = QWidget()
        sv = QHBoxLayout(self.adv_split); sv.setContentsMargins(0, 0, 0, 0); sv.setSpacing(8)
        sv.addWidget(field_label("分卷大小", FORM_LABEL_W))
        self.split_size = QDoubleSpinBox()
        self.split_size.setRange(0, 100000); self.split_size.setValue(0); self.split_size.setDecimals(0)
        self.split_size.setSuffix(" MB"); self.split_size.setSpecialValueText("不分卷")
        self.split_size.setMinimumWidth(120)
        sv.addWidget(self.split_size); sv.addStretch(1)
        v.addWidget(self.adv_split)

        # 单层密码加密（常用，普通模式也显示）
        enc_row = QHBoxLayout()
        self.enc_enable = QCheckBox("密码加密")
        self.enc_enable.setFixedWidth(FORM_LABEL_W)
        self.enc_enable.setToolTip("使用 AES-256 加密压缩包")
        self.enc_pwd = QLineEdit(); self.enc_pwd.setPlaceholderText("勾选左侧后填写（AES-256）")
        self.enc_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        enc_row.addWidget(self.enc_enable); enc_row.addWidget(self.enc_pwd, 1)
        v.addLayout(enc_row)

        # [高级] 多重封缄（多层嵌套加密）+ 恢复校验
        self.adv_seal = QWidget()
        av = QVBoxLayout(self.adv_seal); av.setContentsMargins(0, 0, 0, 0); av.setSpacing(8)
        av.addWidget(section_title("高级（多重封缄）"))
        av.addWidget(hint("封缄 = 用多个密码层层加密，层数越多越难破解；解封需按相同顺序提供全部密码。"
                          "层数 1 时走普通加密。"))
        seal_row = QHBoxLayout()
        seal_row.addWidget(field_label("封缄层数", FORM_LABEL_W))
        self.seal_layers = QDoubleSpinBox()
        self.seal_layers.setRange(1, 5); self.seal_layers.setValue(1); self.seal_layers.setDecimals(0)
        self.seal_layers.setMinimumWidth(120)
        self.seal_layers.valueChanged.connect(self._on_layers_changed)
        seal_row.addWidget(self.seal_layers); seal_row.addStretch(1)
        av.addLayout(seal_row)
        self.seal_pwds = QLineEdit()
        self.seal_pwds.setPlaceholderText("从内到外，用逗号分隔；层数 ≥ 2 时必填")
        self.seal_pwds.setEnabled(False)
        seal_pwd_row = QHBoxLayout()
        seal_pwd_row.addWidget(field_label("各层密码", FORM_LABEL_W))
        seal_pwd_row.addWidget(self.seal_pwds, 1)
        av.addLayout(seal_pwd_row)
        self.rec_enable = QCheckBox("生成恢复校验清单(.kkrec.json)，可检测文件损坏")
        self.rec_redundancy = QCheckBox("额外保存尾部冗余（便于修补中央目录损坏）")
        self.rec_redundancy.setEnabled(False)
        self.rec_enable.toggled.connect(self.rec_redundancy.setEnabled)
        av.addLayout(indent_row(self.rec_enable))
        av.addLayout(indent_row(self.rec_redundancy))
        v.addWidget(self.adv_seal)

        b_go = QPushButton("开始打包伪装"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._do_pack)
        v.addWidget(b_go)
        v.addStretch(1)
        return card

    def apply_ui_mode(self, mode: str) -> None:
        """普通模式收起素材池/分卷/封缄；并复位其开关，避免隐藏状态悄悄影响结果。"""
        adv = mode == "advanced"
        for w in (self.adv_pool, self.adv_split, self.adv_seal):
            w.setVisible(adv)
        if not adv:
            self.use_pool.setChecked(False)
            self.seal_layers.setValue(1)
            self.rec_enable.setChecked(False)
            self.split_size.setValue(0)

    def _on_pool_toggled(self, on: bool) -> None:
        self.pool_dir.setEnabled(on)
        self.pack_carrier.setEnabled(not on)

    def _on_layers_changed(self, val) -> None:
        multi = int(val) >= 2
        self.seal_pwds.setEnabled(multi)
        # 多层封缄与单层 AES 互斥：启用多层时单层加密让位
        if multi:
            self.enc_enable.setChecked(False)
        self.enc_enable.setEnabled(not multi)
        self.enc_pwd.setEnabled(not multi)

    def _path_row(self, parent, label, *, pick_dir, save=False, start_dir="") -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        b = QPushButton("…"); b.setObjectName("MiniBtn"); b.setFixedWidth(34)

        def pick():
            base = edit.text().strip() or start_dir
            if pick_dir:
                d = QFileDialog.getExistingDirectory(self, label, base)
            elif save:
                d, _ = QFileDialog.getSaveFileName(self, label, base)
            else:
                d, _ = QFileDialog.getOpenFileName(self, label, base)
            if d:
                edit.setText(d)

        b.clicked.connect(pick)
        row.addWidget(field_label(label, FORM_LABEL_W))
        row.addWidget(edit, 1)
        row.addWidget(b)
        parent.addLayout(row)
        return edit

    def _on_pack_source_changed(self, by_folder: bool) -> None:
        self.folder_source.setVisible(by_folder)
        self.file_source.setVisible(not by_folder)

    def _add_pack_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要打包的 Mod 文件", "", "Mod 文件 (*.zipmod *.zip);;所有文件 (*.*)"
        )
        existing = {self.pack_file_list.item(i).text().casefold()
                    for i in range(self.pack_file_list.count())}
        for path in files:
            if path.casefold() not in existing:
                self.pack_file_list.addItem(path)
                existing.add(path.casefold())
        self.pack_file_count.setText(f"已选择 {self.pack_file_list.count()} 个文件")

    def _remove_pack_files(self) -> None:
        for item in self.pack_file_list.selectedItems():
            self.pack_file_list.takeItem(self.pack_file_list.row(item))
        self.pack_file_count.setText(f"已选择 {self.pack_file_list.count()} 个文件")

    def _do_pack(self) -> None:
        if self.pack_by_files.isChecked():
            source = [self.pack_file_list.item(i).text()
                      for i in range(self.pack_file_list.count())]
            if not source:
                QMessageBox.warning(self, "无效", "请先添加要打包的文件。")
                return
            if any(not Path(path).is_file() for path in source):
                QMessageBox.warning(self, "无效", "所选文件已不存在，请检查文件列表。")
                return
        else:
            source = self.pack_folder.text().strip()
            if not (source and Path(source).is_dir()):
                QMessageBox.warning(self, "无效", "请选择有效的待打包文件夹。")
                return
        out = self.pack_out.text().strip()

        use_pool = self.use_pool.isChecked()
        carrier = self.pack_carrier.text().strip()
        pool = self.pool_dir.text().strip()
        if use_pool:
            if not (pool and Path(pool).is_dir()):
                QMessageBox.warning(self, "无效", "请选择有效的载体素材池目录。"); return
        else:
            if not (carrier and Path(carrier).is_file()):
                QMessageBox.warning(self, "无效", "请选择有效的载体文件。"); return
        if not out:
            QMessageBox.warning(self, "无效", "请指定输出文件路径。"); return
        settings.set_value("pack_out_dir", str(Path(out).parent))
        split_mb = self.split_size.value()
        layers = int(self.seal_layers.value())
        gen_rec = self.rec_enable.isChecked()
        redundancy = self.rec_redundancy.isChecked()

        if layers >= 2:
            seal_pwds = [p.strip() for p in self.seal_pwds.text().split(",") if p.strip()]
            if len(seal_pwds) != layers:
                QMessageBox.warning(self, "密码数量不符",
                                    f"封缄 {layers} 层需要 {layers} 个密码，当前填了 {len(seal_pwds)} 个。"); return
            password = None
        else:
            seal_pwds = None
            password = self.enc_pwd.text() if self.enc_enable.isChecked() else None
            if self.enc_enable.isChecked() and not password:
                QMessageBox.warning(self, "无密码", "已勾选加密但未填密码。"); return

        def job(progress=None):
            carrier_use = stego.pick_carrier_from_pool(pool) if use_pool else carrier
            if use_pool:
                msgs_prefix = [f"[OK] 已从素材池随机选用载体: {Path(carrier_use).name}"]
            else:
                msgs_prefix = []
            if seal_pwds:
                stego.pack_layered(source, out, seal_pwds, carrier=carrier_use, progress=progress)
                msgs = msgs_prefix + [f"[OK] 已多重封缄({len(seal_pwds)}层)并伪装: {Path(out).name}"]
            else:
                stego.pack_and_disguise(source, carrier_use, out, password=password, progress=progress)
                msgs = msgs_prefix + [f"[OK] 已伪装{'(AES加密)' if password else ''}: {Path(out).name}"]
            if gen_rec:
                sc = stego.write_recovery_sidecar(out, redundancy=redundancy)
                msgs.append(f"[OK] 已生成恢复校验清单: {Path(sc).name}")
            if split_mb > 0:
                parts = stego.split_file(out, split_mb)
                msgs.append(f"[OK] 已分卷为 {len(parts)} 个分片")
            return msgs

        self._run(job, "打包伪装")

    # ---- 公共执行 ----

    def _pick_dir(self, edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择目录", edit.text() or "")
        if d:
            edit.setText(d)

    def _run(self, job, label: str) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "已有任务进行中。"); return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        log(f"{label} 开始")
        self._worker = Worker(job)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(lambda res: self._on_done(label, res))
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, cur, total, desc) -> None:
        if total:
            self.progress.setRange(0, total); self.progress.setValue(cur)

    def _on_done(self, label, results) -> None:
        self.progress.setVisible(False)
        for r in results:
            log(r)
        QMessageBox.information(self, f"{label}完成", "\n".join(results))

    def _on_failed(self, msg) -> None:
        self.progress.setVisible(False)
        log(f"任务失败: {msg.splitlines()[0]}")
        QMessageBox.critical(self, "失败", msg.splitlines()[0])
