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
    QVBoxLayout,
    QWidget,
)

from core import settings, stego
from ui.applog import log
from ui.widgets import PageBase, hint, make_card, section_title
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
        cols.addWidget(self._build_pack(), 1)
        self.body_layout.addLayout(cols, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

    # ---- 解包 ----

    def _build_unpack(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("解包"))
        v.addWidget(hint("拖入或选择压缩包 / 伪装文件（视频后接 zip 也能识别），解压到输出目录。"))
        self.unpack_list = _DropList()
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
        out.addWidget(QLabel("输出")); out.addWidget(self.unpack_out, 1); out.addWidget(b_out)
        v.addLayout(out)
        opt = QHBoxLayout()
        self.opt_del_src = QCheckBox("解包成功后删除源文件")
        self.opt_clear_queue = QCheckBox("解压完清空队列")
        opt.addWidget(self.opt_del_src); opt.addWidget(self.opt_clear_queue); opt.addStretch(1)
        v.addLayout(opt)
        pw_row = QHBoxLayout()
        self.unpack_pwds = QLineEdit()
        self.unpack_pwds.setPlaceholderText("解密密码（加密包用，多个用逗号分隔；不加密可留空）")
        pw_row.addWidget(QLabel("密码")); pw_row.addWidget(self.unpack_pwds, 1)
        v.addLayout(pw_row)
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
        v.addWidget(section_title("打包并伪装"))
        v.addWidget(hint("把文件夹压缩后追加到一个真实视频/图片之后，生成既能播放又能解压的伪装文件。"))

        self.pack_folder = self._path_row(v, "待打包文件夹", pick_dir=True)
        self.pack_carrier = self._path_row(v, "载体文件(视频/图片)", pick_dir=False)

        # [高级] 素材池：从一个目录里随机抽载体，每次伪装外壳都不同、更隐蔽
        self.adv_pool = QWidget()
        pv = QVBoxLayout(self.adv_pool); pv.setContentsMargins(0, 0, 0, 0); pv.setSpacing(8)
        self.use_pool = QCheckBox("改用素材池：从目录随机抽一个载体")
        self.use_pool.toggled.connect(self._on_pool_toggled)
        pv.addWidget(self.use_pool)
        self.pool_dir = self._path_row(pv, "载体素材池目录", pick_dir=True)
        self.pool_dir.setEnabled(False)
        v.addWidget(self.adv_pool)

        self.pack_out = self._path_row(v, "输出文件", pick_dir=False, save=True,
                                       start_dir=settings.get("pack_out_dir", "") or "")

        # [高级] 分卷
        self.adv_split = QWidget()
        sv = QHBoxLayout(self.adv_split); sv.setContentsMargins(0, 0, 0, 0)
        sv.addWidget(QLabel("分卷大小(MB，0=不分卷)"))
        self.split_size = QDoubleSpinBox()
        self.split_size.setRange(0, 100000); self.split_size.setValue(0); self.split_size.setDecimals(0)
        sv.addWidget(self.split_size); sv.addStretch(1)
        v.addWidget(self.adv_split)

        # 单层密码加密（常用，普通模式也显示）
        enc_row = QHBoxLayout()
        self.enc_enable = QCheckBox("启用密码加密(AES-256)")
        self.enc_pwd = QLineEdit(); self.enc_pwd.setPlaceholderText("加密密码")
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
        seal_row.addWidget(QLabel("封缄层数"))
        self.seal_layers = QDoubleSpinBox()
        self.seal_layers.setRange(1, 5); self.seal_layers.setValue(1); self.seal_layers.setDecimals(0)
        self.seal_layers.valueChanged.connect(self._on_layers_changed)
        seal_row.addWidget(self.seal_layers); seal_row.addStretch(1)
        av.addLayout(seal_row)
        self.seal_pwds = QLineEdit()
        self.seal_pwds.setPlaceholderText("各层密码，从内到外，用逗号分隔（层数≥2 时必填）")
        self.seal_pwds.setEnabled(False)
        av.addWidget(self.seal_pwds)
        self.rec_enable = QCheckBox("生成恢复校验清单(.kkrec.json)，可检测文件损坏")
        self.rec_redundancy = QCheckBox("额外保存尾部冗余（便于修补中央目录损坏）")
        self.rec_redundancy.setEnabled(False)
        self.rec_enable.toggled.connect(self.rec_redundancy.setEnabled)
        av.addWidget(self.rec_enable)
        av.addWidget(self.rec_redundancy)
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
        row.addWidget(QLabel(label))
        row.addWidget(edit, 1)
        row.addWidget(b)
        parent.addLayout(row)
        return edit

    def _do_pack(self) -> None:
        folder = self.pack_folder.text().strip()
        out = self.pack_out.text().strip()
        if not (folder and Path(folder).is_dir()):
            QMessageBox.warning(self, "无效", "请选择有效的待打包文件夹。"); return

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
                stego.pack_layered(folder, out, seal_pwds, carrier=carrier_use, progress=progress)
                msgs = msgs_prefix + [f"[OK] 已多重封缄({len(seal_pwds)}层)并伪装: {Path(out).name}"]
            else:
                stego.pack_and_disguise(folder, carrier_use, out, password=password, progress=progress)
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
