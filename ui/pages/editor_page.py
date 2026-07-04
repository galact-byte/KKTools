"""角色卡编辑页（丰富版）。

基本信息 + 提问 / 特点 / H相关 三个标签页的勾选项，
右侧信息面板含 报告 / 卡片详情 / 解析JSON / 捏脸数据 四个视图，并支持 KK<->KKS
标识切换（实验）、更换预览图、另存为/覆盖备份、导出 JSON。

安全策略不变：只写回已知低风险字段，其余块字节级保留；嵌套布尔字典（提问/特点/
H相关）按 key 原样回填，KKEx 占位键 ExtendedSaveData 保留不动。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import kk_enums, kk_fields, settings
from core.kk_card import KKCardError, KoikatuCard

_RECENT_LIMIT = 12
from ui.widgets import PageBase, field_label, hint, make_card, section_title

NOTE_KEYS = ("note", "memo", "comment")


class EditorPage(PageBase):
    def __init__(self):
        super().__init__(
            "角色卡编辑",
            "读取 KK / KKS 角色卡，安全写回低风险字段，默认另存为并支持覆盖前自动备份",
        )
        self.card: KoikatuCard | None = None
        self.answer_checks: dict[str, QCheckBox] = {}
        self.attr_checks: dict[str, QCheckBox] = {}
        self.denial_checks: dict[str, QCheckBox] = {}
        self._note_key: str | None = None
        self._club_was_int = False
        self._build_ui()
        self._set_enabled(False)

    # ---------- 构建界面 ----------

    def _build_ui(self) -> None:
        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("读卡")
        self.btn_open.setProperty("accent", "primary")
        self.btn_recent = QPushButton("最近")
        self.recent_menu = QMenu(self)
        self.recent_menu.aboutToShow.connect(self._populate_recent)
        self.btn_recent.setMenu(self.recent_menu)
        self.btn_save_as = QPushButton("另存为新卡")
        self.btn_overwrite = QPushButton("覆盖原卡并备份")
        self.btn_overwrite.setProperty("accent", "danger")
        self.btn_diff = QPushButton("预览写回差异")
        self.btn_convert = QPushButton("切换 KK/KKS 标识(实验)")
        self.btn_preview = QPushButton("更换预览图")
        self.btn_export = QPushButton("导出 JSON")
        for b in (
            self.btn_open, self.btn_recent, self.btn_save_as, self.btn_overwrite,
            self.btn_diff, self.btn_convert, self.btn_preview, self.btn_export,
        ):
            toolbar.addWidget(b)
        toolbar.addStretch(1)
        self.body_layout.addLayout(toolbar)

        self.btn_open.clicked.connect(self._open_card)
        self.btn_save_as.clicked.connect(self._save_as_new)
        self.btn_overwrite.clicked.connect(self._overwrite)
        self.btn_diff.clicked.connect(self._preview_diff)
        self.btn_convert.clicked.connect(self._convert_game)
        self.btn_preview.clicked.connect(self._change_preview)
        self.btn_export.clicked.connect(self._export_json)

        main = QHBoxLayout()
        main.setSpacing(14)
        self.body_layout.addLayout(main, 1)

        main.addWidget(self._build_left())
        main.addWidget(self._build_middle(), 1)
        main.addWidget(self._build_right(), 1)

    def apply_ui_mode(self, mode: str) -> None:
        """普通模式隐藏实验性「切换标识」入口；高级模式显示。"""
        self.btn_convert.setVisible(mode == "advanced")

    def _build_left(self) -> QWidget:
        left = make_card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        ll.addWidget(section_title("当前角色卡"))
        self.thumb = QLabel("未读取")
        self.thumb.setObjectName("ThumbPreview")
        self.thumb.setFixedSize(220, 248)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignHCenter)
        self.summary = QLabel("拖一张卡进来，或点「读卡」")
        self.summary.setObjectName("HintLabel")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        ll.addWidget(self.summary)
        ll.addStretch(1)
        left.setFixedWidth(252)
        return left

    def _build_middle(self) -> QWidget:
        mid = make_card()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(14, 14, 14, 14)
        ml.addWidget(section_title("基本信息"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 6, 0)
        il.setSpacing(10)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        self.ed_lastname = QLineEdit()
        self.ed_firstname = QLineEdit()
        self.ed_nickname = QLineEdit()
        self.ed_fullname = QLineEdit()
        self.ed_fullname.setReadOnly(True)
        self.ed_fullname.setToolTip("由 姓 + 名 自动合成，仅供参考")
        self.cb_personality = QComboBox()
        self.cb_blood = QComboBox()  # 选项在 _populate 中按卡片填充（含 mod 越界兜底）
        self.ed_club = QLineEdit()
        self.ed_note = QLineEdit()
        self.ed_note.setPlaceholderText("仅在原卡存在备注字段时可写回")
        self.sp_month = QSpinBox(); self.sp_month.setRange(0, 12)
        self.sp_day = QSpinBox(); self.sp_day.setRange(0, 31)
        birth = QHBoxLayout()
        birth.addWidget(QLabel("月")); birth.addWidget(self.sp_month)
        birth.addSpacing(8)
        birth.addWidget(QLabel("日")); birth.addWidget(self.sp_day)
        birth.addStretch(1)
        birth_w = QWidget(); birth_w.setLayout(birth)

        self.ed_lastname.textChanged.connect(self._refresh_fullname)
        self.ed_firstname.textChanged.connect(self._refresh_fullname)

        form.addRow(field_label("姓"), self.ed_lastname)
        form.addRow(field_label("名"), self.ed_firstname)
        form.addRow(field_label("昵称"), self.ed_nickname)
        form.addRow(field_label("完整名"), self.ed_fullname)
        form.addRow(field_label("性格"), self.cb_personality)
        form.addRow(field_label("血型"), self.cb_blood)
        form.addRow(field_label("社团"), self.ed_club)
        form.addRow(field_label("备注"), self.ed_note)
        form.addRow(field_label("生日"), birth_w)
        il.addLayout(form)

        # 提问 / 特点 / H相关 标签页
        self.tabs_edit = QTabWidget()
        self.tab_answer = QWidget(); self.grid_answer = QGridLayout(self.tab_answer)
        self.grid_answer.setContentsMargins(10, 10, 10, 10)
        self.tab_attr = QWidget(); self.grid_attr = QGridLayout(self.tab_attr)
        self.grid_attr.setContentsMargins(10, 10, 10, 10)
        self.tab_h = QWidget(); self.vbox_h = QVBoxLayout(self.tab_h)
        self.vbox_h.setContentsMargins(10, 10, 10, 10)
        self.tabs_edit.addTab(self.tab_answer, "提问")
        self.tabs_edit.addTab(self.tab_attr, "特点")
        self.tabs_edit.addTab(self.tab_h, "H 相关")
        il.addWidget(self.tabs_edit)
        il.addStretch(1)

        scroll.setWidget(inner)
        ml.addWidget(scroll, 1)
        return mid

    def _build_right(self) -> QWidget:
        right = make_card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 14, 14, 14)
        rl.addWidget(section_title("信息"))
        tabs = QTabWidget()
        self.report = QPlainTextEdit(); self.report.setReadOnly(True)
        self.detail = QPlainTextEdit(); self.detail.setReadOnly(True)
        self.json_view = QPlainTextEdit(); self.json_view.setReadOnly(True)
        self.custom_view = QPlainTextEdit(); self.custom_view.setReadOnly(True)
        tabs.addTab(self.report, "报告")
        tabs.addTab(self.detail, "卡片详情")
        tabs.addTab(self.json_view, "解析 JSON")
        tabs.addTab(self.custom_view, "捏脸数据")
        rl.addWidget(tabs, 1)
        return right

    def _set_enabled(self, on: bool) -> None:
        for b in (self.btn_save_as, self.btn_overwrite, self.btn_convert,
                  self.btn_diff, self.btn_preview, self.btn_export):
            b.setEnabled(on)

    # ---------- 读卡与填充 ----------

    def _open_card(self) -> None:
        start = settings.get("last_browse_dir", "") or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择角色卡", start, "角色卡 PNG (*.png);;所有文件 (*.*)")
        if path:
            self.load_card(path)

    def _record_recent(self, path: str) -> None:
        """把刚打开的卡记入最近列表（去重置顶、限长），并记住其所在目录。"""
        recent = [p for p in settings.get("recent_cards", []) if p != path]
        recent.insert(0, path)
        settings.set_value("recent_cards", recent[:_RECENT_LIMIT])
        settings.set_value("last_browse_dir", str(Path(path).parent))

    def _populate_recent(self) -> None:
        self.recent_menu.clear()
        recent = [p for p in settings.get("recent_cards", []) if Path(p).is_file()]
        if not recent:
            act = self.recent_menu.addAction("（暂无最近记录）")
            act.setEnabled(False)
            return
        for p in recent:
            self.recent_menu.addAction(Path(p).name, lambda _=False, x=p: self.load_card(x))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction("清空最近记录",
                                   lambda: settings.set_value("recent_cards", []))

    def load_card(self, path: str) -> None:
        try:
            card = KoikatuCard.load(path)
        except KKCardError as exc:
            QMessageBox.warning(self, "读取失败", f"这不像一张角色卡：\n{exc}")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "读取异常", str(exc))
            return
        if card.get_block_dict("Parameter") is None:
            QMessageBox.warning(self, "无法编辑", "该卡片没有 Parameter 块，可能是服装卡或场景卡。")
            return
        self.card = card
        self._record_recent(path)
        self._populate()
        self._set_enabled(True)

    def _populate(self) -> None:
        card = self.card
        assert card is not None
        param = card.parameter or {}

        self._set_thumb(card.thumbnail)
        self.summary.setText(self._summary_html(card, param))

        self.ed_lastname.setText(str(param.get("lastname", "")))
        self.ed_firstname.setText(str(param.get("firstname", "")))
        self.ed_nickname.setText(str(param.get("nickname", "")))
        self._refresh_fullname()

        # 性格
        self.cb_personality.clear()
        choices = kk_enums.personality_choices(card.game)
        cur = param.get("personality")
        if isinstance(cur, int) and cur not in [v for v, _ in choices]:
            choices.append((cur, f"{cur:02d} - 未知(mod扩展)"))
        for val, text in choices:
            self.cb_personality.addItem(text, val)
        if isinstance(cur, int):
            i = self.cb_personality.findData(cur)
            if i >= 0:
                self.cb_personality.setCurrentIndex(i)
        self.cb_personality.setEnabled("personality" in param)

        # 血型：用 itemData 存真实数值，mod 扩展的越界值加兜底项，避免保存时被静默改写
        self.cb_blood.clear()
        for i, name in enumerate(kk_enums.BLOOD_TYPES):
            self.cb_blood.addItem(name, i)
        bt = param.get("bloodType")
        if isinstance(bt, int) and bt not in range(len(kk_enums.BLOOD_TYPES)):
            self.cb_blood.addItem(f"{bt} - 未知(mod扩展)", bt)
        if isinstance(bt, int):
            idx = self.cb_blood.findData(bt)
            if idx >= 0:
                self.cb_blood.setCurrentIndex(idx)
        self.cb_blood.setEnabled("bloodType" in param)

        self.ed_club.setText(str(param.get("clubActivities", "")))
        self._club_was_int = isinstance(param.get("clubActivities"), int)
        self.ed_club.setEnabled("clubActivities" in param)

        # 备注（仅当原卡存在该类字段）
        self._note_key = next((k for k in NOTE_KEYS if k in param), None)
        if self._note_key:
            self.ed_note.setText(str(param.get(self._note_key, "")))
            self.ed_note.setEnabled(True)
        else:
            self.ed_note.clear()
            self.ed_note.setEnabled(False)

        self.sp_month.setValue(int(param.get("birthMonth", 0) or 0))
        self.sp_day.setValue(int(param.get("birthDay", 0) or 0))

        self._build_check_grid(self.grid_answer, param.get("answer") or param.get("awnser"),
                               kk_fields.ANSWER_LABELS, self.answer_checks)
        self._build_check_grid(self.grid_attr, param.get("attribute"),
                               kk_fields.ATTRIBUTE_LABELS, self.attr_checks)
        self._build_h_tab(param)

        self._render_report(card, param)
        self._render_detail(card, param)
        self.json_view.setPlainText(
            json.dumps(self._jsonable(param), ensure_ascii=False, indent=2))
        self._render_custom(card)

    def _set_thumb(self, png: bytes) -> None:
        pix = QPixmap()
        pix.loadFromData(png)
        if pix.isNull():
            self.thumb.setText("无缩略图")
        else:
            self.thumb.setPixmap(pix.scaled(
                self.thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def _refresh_fullname(self) -> None:
        self.ed_fullname.setText(
            f"{self.ed_lastname.text()}{self.ed_firstname.text()}".strip())

    # ---------- 勾选网格 ----------

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _build_check_grid(self, grid: QGridLayout, data, label_map, store: dict) -> None:
        self._clear_layout(grid)
        store.clear()
        items = kk_fields.editable_items(data)
        if not items:
            grid.addWidget(QLabel("该卡无此类字段"), 0, 0)
            return
        cols = 3
        for idx, (key, val) in enumerate(items):
            cb = QCheckBox(kk_fields.label_for(key, label_map))
            cb.setChecked(bool(val))
            cb.setToolTip(key)
            store[key] = cb
            grid.addWidget(cb, idx // cols, idx % cols)

    def _build_h_tab(self, param: dict) -> None:
        self._clear_layout(self.vbox_h)
        self.denial_checks.clear()
        self.vbox_h.addWidget(field_label("H 接受项（拒否解除）"))
        denial_w = QWidget()
        dg = QGridLayout(denial_w)
        dg.setContentsMargins(0, 0, 0, 0)
        items = kk_fields.editable_items(param.get("denial"))
        if items:
            for idx, (key, val) in enumerate(items):
                cb = QCheckBox(kk_fields.label_for(key, kk_fields.DENIAL_LABELS))
                cb.setChecked(bool(val)); cb.setToolTip(key)
                self.denial_checks[key] = cb
                dg.addWidget(cb, idx // 3, idx % 3)
        else:
            dg.addWidget(QLabel("该卡无 H 接受项字段"), 0, 0)
        self.vbox_h.addWidget(denial_w)

        # 数值型 H/性格倾向字段
        num_w = QWidget()
        nf = QFormLayout(num_w)
        nf.setContentsMargins(0, 8, 0, 0)
        self.h_spins: dict[str, QSpinBox | QDoubleSpinBox] = {}
        # 范围放宽，避免 mod 扩展的大数值被 spinbox 截断造成静默损坏
        for key, lbl, lo, hi in [
            ("weakPoint", "敏感部位(索引)", 0, 99999),
            ("aggressive", "积极性", 0, 99999),
            ("diligence", "勤奋", 0, 99999),
            ("kindness", "温柔", 0, 99999),
        ]:
            if key in param and isinstance(param[key], int):
                sp = QSpinBox(); sp.setRange(lo, hi); sp.setValue(int(param[key]))
                self.h_spins[key] = sp
                nf.addRow(field_label(lbl), sp)
        if "voiceRate" in param and isinstance(param["voiceRate"], (int, float)):
            dsp = QDoubleSpinBox(); dsp.setRange(0.0, 2.0); dsp.setSingleStep(0.05)
            dsp.setDecimals(3); dsp.setValue(float(param["voiceRate"]))
            self.h_spins["voiceRate"] = dsp
            nf.addRow(field_label("声音音调"), dsp)
        self.vbox_h.addWidget(num_w)
        self.vbox_h.addStretch(1)

    # ---------- 报告 / 详情 / 捏脸 ----------

    def _render_report(self, card: KoikatuCard, param: dict) -> None:
        g = card.game
        a_c, a_t = kk_fields.count_true(param.get("answer") or param.get("awnser"))
        t_c, t_t = kk_fields.count_true(param.get("attribute"))
        h_c, h_t = kk_fields.count_true(param.get("denial"))
        blocks = card.block_names
        lines = [
            "读取成功。",
            f"路径: {card.path}",
            f"卡片类型: {g} / {card.game_name}",
            f"标识 (marker): {card.marker}",
            f"版本: {card.version}    ProductNo: {card.product_no}",
            f"缩略图: {len(card.thumbnail)} B    脸图: {len(card.face)} B",
            "",
            f"姓名: {param.get('lastname','')} {param.get('firstname','')}".rstrip(),
            f"昵称: {param.get('nickname','')}",
            f"性格: {kk_enums.personality_name(param.get('personality'), g)}",
            f"血型: {kk_enums.blood_type_name(param.get('bloodType'))}",
            f"社团: {param.get('clubActivities','')}",
            f"生日: {param.get('birthMonth','?')}-{param.get('birthDay','?')}",
            f"敏感部位(索引): {param.get('weakPoint','-')}",
            "",
            f"提问: {a_c} / {a_t}    特点: {t_c} / {t_t}    H接受项: {h_c} / {h_t}",
            "",
            "块存在性:",
            f"  Parameter: {'存在' if 'Parameter' in blocks else '缺失'}",
            f"  Custom: {'存在' if 'Custom' in blocks else '缺失'}",
            f"  Coordinate: {'存在' if 'Coordinate' in blocks else '缺失'}",
            f"  KKEx: {'存在' if 'KKEx' in blocks else '缺失'}",
            f"  About: {'存在' if 'About' in blocks else '缺失'}",
            f"数据块 ({len(blocks)}): {', '.join(blocks)}",
        ]
        self.report.setPlainText("\n".join(lines))

    def _render_detail(self, card: KoikatuCard, param: dict) -> None:
        rows = []
        for key, lbl in kk_fields.SCALAR_LABELS.items():
            if key in param and not isinstance(param[key], (dict, list)):
                val = param[key]
                if key == "personality":
                    val = f"{val}  ({kk_enums.personality_name(val, card.game)})"
                elif key == "bloodType":
                    val = f"{val}  ({kk_enums.blood_type_name(val)})"
                rows.append(f"{lbl:<14}: {val}")
        self.detail.setPlainText("\n".join(rows) if rows else "无标量字段")

    def _render_custom(self, card: KoikatuCard) -> None:
        raw = card.blocks.get("Custom")
        if raw is None:
            self.custom_view.setPlainText("该卡无 Custom 块")
            return
        lines = [
            "捏脸数据 (Custom 块) —— 二进制嵌套结构，当前仅作只读摘要：",
            f"  原始大小: {len(raw)} 字节",
        ]
        try:
            cu = card.get_block_dict("Custom")
            if isinstance(cu, dict):
                lines.append(f"  顶层键: {list(cu.keys())}")
            elif isinstance(cu, (list, tuple)):
                lines.append(f"  顶层为数组，长度: {len(cu)}")
        except KKCardError as exc:
            lines.append(f"  (无法进一步解析: {exc})")
        lines.append("")
        lines.append("提示：脸型/体型滑条等细粒度编辑涉及深度逆向，后续版本再支持。")
        self.custom_view.setPlainText("\n".join(lines))

    @staticmethod
    def _jsonable(obj):
        if isinstance(obj, dict):
            return {(k.decode("utf-8", "replace") if isinstance(k, bytes) else k):
                    EditorPage._jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [EditorPage._jsonable(v) for v in obj]
        if isinstance(obj, bytes):
            return f"<bytes:{len(obj)}>"
        return obj

    # ---------- 收集与保存 ----------

    def _collect_updates(self) -> dict:
        """只收集用户**真正改动过**的字段。

        关键：未改动的字段一律不写回，由 update_parameter 保留精确原值——
        尤其浮点(voiceRate)经 spinbox 会丢精度，只有当用户把它从初始显示值挪开
        才采用 spinbox 值，否则保留原始精确浮点。这样"不改即存"= 字节级原样。
        """
        param = self.card.parameter or {}
        updates: dict = {}

        def put(key, value):
            if param.get(key) != value:
                updates[key] = value

        put("lastname", self.ed_lastname.text())
        put("firstname", self.ed_firstname.text())
        put("nickname", self.ed_nickname.text())
        put("birthMonth", self.sp_month.value())
        put("birthDay", self.sp_day.value())
        if self.cb_personality.isEnabled() and self.cb_personality.currentData() is not None:
            put("personality", int(self.cb_personality.currentData()))
        if self.cb_blood.isEnabled() and self.cb_blood.currentData() is not None:
            put("bloodType", int(self.cb_blood.currentData()))
        if self.ed_club.isEnabled():
            txt = self.ed_club.text()
            if self._club_was_int:
                try:
                    put("clubActivities", int(txt))
                except ValueError:
                    pass
            else:
                put("clubActivities", txt)
        if self._note_key:
            put(self._note_key, self.ed_note.text())

        # 嵌套布尔字典：仅当确有勾选变化才写回，保留 ExtendedSaveData 等占位键
        def merge(field_name, checks):
            src = param.get(field_name)
            if isinstance(src, dict) and checks:
                d = copy.deepcopy(src)
                changed = False
                for k, cb in checks.items():
                    if k in d and d[k] != cb.isChecked():
                        d[k] = cb.isChecked()
                        changed = True
                if changed:
                    updates[field_name] = d

        merge("answer" if "answer" in param else "awnser", self.answer_checks)
        merge("attribute", self.attr_checks)
        merge("denial", self.denial_checks)

        # 数值/浮点：未挪动则不写回，保留精确原值
        for key, sp in getattr(self, "h_spins", {}).items():
            if key not in param:
                continue
            orig = param.get(key)
            val = sp.value()
            if isinstance(sp, QDoubleSpinBox):
                # 浮点：与"原值按显示精度四舍五入"比较，相等视为未改动
                if isinstance(orig, (int, float)) and abs(val - round(float(orig), sp.decimals())) < 10 ** (-sp.decimals() - 1):
                    continue
                put(key, float(val))
            else:
                if orig != val:
                    updates[key] = int(val)
        return updates

    def _apply_updates(self) -> bool:
        try:
            updates = self._collect_updates()
            if updates:   # 无改动则完全不碰 Parameter 块，保证字节级原样
                self.card.update_parameter(updates)
            return True
        except KKCardError as exc:
            QMessageBox.warning(self, "写入失败", str(exc))
            return False

    # ---------- 预览写回差异 ----------

    _NESTED_LABELS = {
        "awnser": ("提问", kk_fields.ANSWER_LABELS),
        "answer": ("提问", kk_fields.ANSWER_LABELS),
        "attribute": ("特点", kk_fields.ATTRIBUTE_LABELS),
        "denial": ("H接受", kk_fields.DENIAL_LABELS),
    }

    def _fmt_val(self, key: str, val) -> str:
        if isinstance(val, bool):
            return "是" if val else "否"
        if key == "personality":
            return f"{val}({kk_enums.personality_name(val, self.card.game)})"
        if key == "bloodType":
            return f"{val}({kk_enums.blood_type_name(val)})"
        return str(val)

    def _preview_diff(self) -> None:
        if not self.card:
            return
        current = self.card.parameter or {}
        pending = self._collect_updates()
        lines: list[str] = []
        for key, new_val in pending.items():
            old_val = current.get(key)
            if isinstance(new_val, dict) and isinstance(old_val, dict):
                cat, lblmap = self._NESTED_LABELS.get(key, (key, {}))
                for sk, nv in new_val.items():
                    if sk in kk_fields.SKIP_KEYS:
                        continue
                    ov = old_val.get(sk)
                    if ov != nv:
                        name = kk_fields.label_for(sk, lblmap)
                        lines.append(f"  {cat}·{name}: {self._fmt_val(sk, ov)} → {self._fmt_val(sk, nv)}")
            elif old_val != new_val:
                lbl = kk_fields.SCALAR_LABELS.get(key, key)
                lines.append(f"  {lbl}: {self._fmt_val(key, old_val)} → {self._fmt_val(key, new_val)}")
        if not lines:
            QMessageBox.information(self, "预览写回差异", "没有字段变更，写回后与原卡一致。")
            return
        QMessageBox.information(
            self, "预览写回差异",
            f"将写回以下 {len(lines)} 处变更（其余块字节级保留）：\n\n" + "\n".join(lines))

    def _save_as_new(self) -> None:
        if not self.card or not self._apply_updates():
            return
        src = Path(self.card.path) if self.card.path else Path("card.png")
        default = str(src.with_name(src.stem + "_edited.png"))
        path, _ = QFileDialog.getSaveFileName(self, "另存为新卡", default, "角色卡 PNG (*.png)")
        if not path:
            return
        try:
            saved = self.card.save(path, backup=False)
            QMessageBox.information(self, "已保存", f"已另存为:\n{saved}")
            self._refresh_after_save()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))

    def _overwrite(self) -> None:
        if not self.card or not self.card.path:
            return
        ret = QMessageBox.question(
            self, "确认覆盖",
            f"将覆盖原卡并自动备份为 .bak：\n{self.card.path}\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        if not self._apply_updates():
            return
        try:
            self.card.save(self.card.path, backup=True)
            QMessageBox.information(self, "已覆盖", "已覆盖原卡，原文件备份为同名 .bak。")
            self._refresh_after_save()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))

    def _refresh_after_save(self) -> None:
        """保存后刷新报告/详情/JSON，反映最新值。"""
        param = self.card.parameter or {}
        self._render_report(self.card, param)
        self._render_detail(self.card, param)
        self.json_view.setPlainText(
            json.dumps(self._jsonable(param), ensure_ascii=False, indent=2))

    def _convert_game(self) -> None:
        if not self.card:
            return
        cur = self.card.game
        mapping = {"KK": ("【KoiKatuCharaSun】", "KKS"), "KKS": ("【KoiKatuChara】", "KK")}
        if cur not in mapping:
            QMessageBox.warning(self, "不支持", f"当前卡片类型 {cur} 暂不支持转换。")
            return
        new_marker, target = mapping[cur]
        ret = QMessageBox.warning(
            self, "实验性：仅切换标识",
            f"将把卡片标识从 {cur} 切换为 {target}。\n\n"
            "这只改容器标识(marker)，不是真正的跨作转换：两作卡片结构本就不同"
            "（KKS 多出 About 块与 interest 字段，捏脸/服装/mod 的 ID 体系也不一样），"
            "光换标识后角色到对方游戏里大概率读取异常或显示错乱。\n\n"
            "仅供实验，务必【另存为新卡】，不要覆盖原卡。\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.card.marker = new_marker
        self.card.version = "0.0.0"
        param = self.card.parameter or {}
        self._render_report(self.card, param)
        self.summary.setText(self._summary_html(self.card, param))
        QMessageBox.information(self, "已切换", f"已切换为 {target}，请用「另存为新卡」保存。")

    def _change_preview(self) -> None:
        if not self.card:
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择新预览图 (PNG)", "", "PNG 图片 (*.png)")
        if not path:
            return
        try:
            self.card.set_thumbnail_from_png(Path(path).read_bytes())
        except KKCardError as exc:
            QMessageBox.warning(self, "更换失败", str(exc))
            return
        self._set_thumb(self.card.thumbnail)
        QMessageBox.information(self, "已更换", "预览图已更换（保存后生效）。")

    def _export_json(self) -> None:
        if not self.card:
            return
        param = self.card.parameter or {}
        path, _ = QFileDialog.getSaveFileName(self, "导出 Parameter JSON", "parameter.json", "JSON (*.json)")
        if not path:
            return
        Path(path).write_text(
            json.dumps(self._jsonable(param), ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "已导出", f"Parameter 已导出到:\n{path}")

    def _summary_html(self, card: KoikatuCard, param: dict) -> str:
        name = f"{param.get('lastname','')}{param.get('firstname','')}".strip() or "(无名)"
        h_c, h_t = kk_fields.count_true(param.get("denial"))
        return (
            f"<b>{name}</b><br>{card.game_name}<br>"
            f"性格: {kk_enums.personality_name(param.get('personality'), card.game)}<br>"
            f"血型: {kk_enums.blood_type_name(param.get('bloodType'))} &nbsp; "
            f"社团: {param.get('clubActivities','')}<br>"
            f"生日: {param.get('birthMonth','?')}-{param.get('birthDay','?')} &nbsp; "
            f"H接受: {h_c}/{h_t}"
        )
