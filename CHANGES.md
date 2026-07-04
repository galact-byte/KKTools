# 修改记录 — KKTools 恋活角色卡工具箱

> **修订记录**
>
> - v0.5.5: **仓库独立 + GitHub Actions 自动构建**。①从父仓库 `E:/Python/Programs/test` 独立为单独 git 仓库，父仓库 `.gitignore` 添加 `bat/game/KK/` 排除规则；②新增 `.github/workflows/build.yml`：Windows PyInstaller 单文件构建，tag push 自动发布 Release；③全面真卡验证通过——KK1 代 8 张/2 代 KKS 3 张女卡全部字节级往返一致，KKS 4 张男卡一致，KK1/KKS 参数编辑（外科手术写回）正常，场景卡提取正常（KK1 6 角色/KKS 1 角色），24/24 单测 + 10 主题 WCAG 对比度全绿。
> - v0.5.4: **视觉身份重定为「朱红·墨·昼」，从根上切断与 OnionProtocol 的相似性**。用户实测后反馈"还是太像"，分析发现骨架相似（暗色+卡片堆叠+Dashboard感）才是问题根源，仅换色换字不够。本轮三板斧彻底切割：①**默认亮色**——从 `bone_light` 骨白·昼启动，亮色工具与对方冷紫蓝暗色形成天然代差；②**彻底去卡片化**——`make_card()` 从"带边框+投影的卡片容器"改为透明无边框容器；QSS 删除 `QFrame[card="true"]` 规则（已无代码引用）；设置页移除全部卡片包裹；③**全局默认令牌链**——`settings.py`/`main.py`/`main_window.py`/`settings_page.py` 所有 `jade_dark` 回退引用统一改为 `bone_light`。**回归红线**：未碰 `kk_card.py`，`test_kk_card` 7/7；24 用例全绿。
> - v0.5.2: **视觉身份重定为「骨白·青玉」，逃离 AI 默认皮**。用户提醒：项目身份("墨色/朱砂")是 init 时 AI 自拟、非用户要求，应以全局规范为准、可随时改。正式调用 `frontend-design` skill 后发现关键事实——它把"**奶油+赤陶**""**近黑+朱砂**"明列为当下 AI 生成设计的默认聚类；而本工具原 `ink_light`(奶油+朱砂)/`ink_dark`(近黑+朱砂)恰好撞这两套默认。①**新默认身份**：新增 `jade_dark`(青玉·夜)+ `bone_light`(骨白·昼)——中性暖石墨/骨白基底 + **青玉绿** accent（让彩色卡片缩略图跳出、避开红/绿酸/科技蓝），经用户在三方案(石墨鸢尾紫/骨白青玉/青灰绯桃)中选定；设为 `settings` 默认与代码兜底，`DEFAULT_TOKENS` 同步改青玉；10 套主题全过 WCAG（青玉主按钮白字先天偏低，primary 加深至墨绿 `#1f6e57`/浅 `#297a61` 达标）。②**修用户三连吐槽**：卡片**彻底去描边**（`QFrame[card]` border:none，消除浅色"一圈白"框，靠柔填充+留白分隔，依 `ui-ux-pro-max` elevation/whitespace 原则）；下拉箭头补 `width/height:0` 修正"渲染成方点"；路径选择「…」按钮全挂 `#MiniBtn`（极小内边距 + min-width，修"被 16px 内边距挤没字符"），全局按钮内边距 16→14。③更新项目 CLAUDE.md 身份段。**双规范交叉**：正式 Skill 调用 `frontend-design`（AI 默认聚类裁决 + 主题方向）×`ui-ux-pro-max`（elevation-consistent / whitespace-balance / visual-hierarchy / nav-state-active）。**回归**：未碰 `kk_card.py`，`test_kk_card` 7/7；24 用例全绿（WCAG 断言覆盖全部 10 主题）；多主题×多页离屏渲染验证（字体/下拉箭头真容需本机确认）。
> - v0.5.1: **视觉系统 v2 重构（用户反馈驱动：去 boxy / 治字体 / 修溢出）**。v0.5.0 的"精修"被用户实测打回——浅色发灰、白卡米框互陷、设置页溢出重叠、品牌字别扭。本轮重做表现层（不碰任何业务逻辑）：①**字体根治**：定位"怪"的根因是品牌/标题用 `font_serif`（宋体系渲染拉丁"KKTools"字形别扭、无思源宋体时回退 SimSun 显旧）——功能型全改**微软雅黑**单族靠字号/字重拉层级（标题 22/700、区块 15/600、标签 13、正文 14），品牌字标改 **Bahnschrift**（Win 自带 DIN 风、不在禁用名单）。**实跑了 `ui-ux-pro-max` 的查询脚本**（`search.py --domain typography/style -ds`）：其功能型推荐"单一无衬线 + 厚字重扛层级"印证本方案，唯独它推的 Inter 被 `frontend-design-integrated` 禁用、按 §14 冲突裁决不采用。②**治"米框陷白卡"**：新增 `input_bg` 派生令牌（浅色=比白卡略沉的灰白、深色=比卡片更暗的内凹底），输入框/列表/树/进度条统一改用，不再沿用页面底色导致脏框。③**去 boxy**：卡片描边由 `card_border` 退回更轻的 `border_soft`、区块标题改"左侧 accent 短竖标识"取代整条背景带、`QPushButton#NavTab` 选中态改**实色填充**强化当前页（nav-state-active）。④**修设置页溢出**：内容超窗高却无滚动→卡片被压扁重叠，已用 `QScrollArea` 包裹（横向滚动条关闭）。⑤新增 `surface_hover` 令牌用于列表/树悬浮。**回归**：未碰 `kk_card.py`，`test_kk_card` 7/7；24 用例全绿；8 主题 × 多页 × 普通/高级离屏渲染验证（中文离屏为豆腐块，字体真容需本机确认）。前端按 `frontend-design-integrated`（功能型 + 禁用字体裁决）× `ui-ux-pro-max`（实跑 search.py 取 typography/style/design-system；P1-A11y/P6-Typo&Color/P9-Nav 当前项高亮）交叉验证。
> - v0.5.0: **自用顺手化升级（界面精修 · 模式分级 · 鸡肋收纳 · 顺手优化）**。①**界面精修**：诊断出浅色主题真正的病根不是文字对比（v0.4.2 已修）而是 `bg/surface` 太接近、白卡陷在米黄里没浮起感——令牌层新增 `card_border`（主/弱描边之间，全主题卡片轮廓清晰）、卡片圆角改 `radius_lg`、`#SectionTitle` 13→15px 强化层级；重做 `ink_light` 为"略深纸背 + 干净白卡 + 近黑墨字"，白卡终于浮起。②**主题扩充**：修 `ink_light`，新增 4 套和风主题（樱·夜/琥珀·夜/青磁·夜/雪·昼），共 8 套，单一强调色、无渐变；用 WCAG 脚本逐主题实测正文/主按钮文字全部 ≥4.5:1（青磁·夜主按钮一度 4.09 已加深达标），并把该断言固化进 `tests/test_theme.py`。③**普通/高级模式**（`settings.ui_mode` + 主窗口 `apply_ui_mode` 广播）：普通模式把打包页的 多重封缄/恢复校验/载体素材池/分卷 整段收起（切回普通自动复位其开关，避免隐藏态偷偷影响结果），要用进高级，功能一个不删。④**默认改回系统原生窗口**（`frameless` 默认 False，更稳；设置页加"标题栏样式"开关保留自绘为可选，重启生效）。⑤**KK↔KKS 转换实测定去留**：拿真 KK + 真 KKS 卡比对，证实两作结构本就不同（KKS 多 `About` 块 + `interest` 字段，捏脸/服装/mod 的 ID 体系也不同），光换 marker 注定不可靠——按钮降级到高级模式、改名"切换 KK/KKS 标识(实验)"、提示讲清结构差异并强制另存为。⑥**顺手优化**：全局快捷键（Ctrl+O 读卡 / Ctrl+S 另存 / Ctrl+F 聚焦搜索 / Ctrl+1~8 切页，用 Ctrl 组合避免抢输入框数字）、启动直达浏览器页（`start_page`）、编辑器"最近打开"菜单（去重限长 12，记住卡所在目录）、浏览器右键加 复制路径/删除（优先 send2trash 回收站、二次确认）、打包页记住上次输出目录。⑦清除残留对手痕迹（`editor_page`/`kk_card` 注释中"参考工具"措辞，仅改注释不动逻辑）；新增 `Send2Trash` 依赖（launch 自动补齐）。**回归红线**：未碰 `kk_card.py` 写回逻辑，`test_kk_card` 仍 7/7；全套 24 用例绿（`test_theme` 增至 6，含 8 主题 WCAG 断言）；8 主题 × 8 页 × 普通/高级两模式离屏冒烟全过。前端按 `frontend-design-integrated`（功能型语境 + 组件基线）× `ui-ux-pro-max`（P1-A11y 对比度脚本实测 / P6-Typo&Color / P8-渐进式披露 / P4-Style 一致性）交叉验证。
> - v0.4.2: **对比度与焦点态可达性精修（ui-ux-pro-max 实测驱动）**。用 WCAG 对比公式审计 4 套主题色对发现并修复：①`text_dim`（提示/副标题）对比偏低——深色 3.1~3.3、宣纸·昼仅 2.59 不达标，调整后全部 ≥4.5（4.69~5.21）；②主按钮文字在靛青/松烟主题略低于 4.5（3.95/3.68），微调主色后达 4.87~5.25；③全局 `outline:none` 抹掉了键盘焦点环——为按钮/主按钮/危险按钮/复选框/导航标签补**非位移焦点态**（仅改边框色/底色不改尺寸）。字体维持微软雅黑+宋体（按本地规范禁用 Inter 类通用字体）。回归：6 组单测全绿、8 页 × 4 主题冒烟通过。
> - v0.4.1: **导航布局改版 + 全局放宽留白**。把左侧栏导航改为**顶部横向导航**（品牌 + 文字标签 + 窗控合为一条顶栏，下方全宽内容区），整体剪影焕然一新；按 8px 间距节奏与 12/14/16/18/21 字号阶梯**全局放宽**——基础字号 13→14px、页头/内容区留白加大、按钮内边距放宽、导航当前项用强调色下划线高亮。`main_window.py` 重构为 `_TopBar` + `QButtonGroup` 标签（保留无边框拖动/边缘缩放/`frameless` 兜底），删除孤立的 `ui/titlebar.py`。设计依 `frontend-design-integrated`（功能型语境）× `ui-ux-pro-max`（P5-Layout 间距节奏 / P6-Typo 字号阶梯 / P9-Nav 当前项高亮）交叉校验。回归：6 组单测全绿、8 页 × 4 主题集成冒烟通过。
> - v0.4.0: **四项能力升级：主题系统 / 自绘标题栏 / 多重封缄 / 库身份对账**。①**令牌化主题引擎**——把单一 `style.qss` 改造成 `${令牌}` 模板（`string.Template` 注入，规避 QSS 花括号与 `str.format` 冲突），新增 `core/theme.py`（约15个角色令牌 + 色彩派生 hover/pressed/disabled，主题文件可写得很短）、`ui/theme_qss.py`、4 套**墨色和风**主题（墨色·夜[默认]/宣纸·昼/靛青·夜/松烟·夜，朱砂红为强调色），支持用户主题目录热加载、设置页实时换肤。②**自绘无边框标题栏 + 导航图标**——`ui/titlebar.py`（品牌+窗控，拖动/双击最大化）、11 个自绘极简 SVG 图标 + `SourceIn` 按主题着色、主窗手动 8 向边缘缩放；带 `frameless=False` 兜底开关可退回系统原生窗口。③**多重封缄打包**——`stego.pack_layered/extract_layered` 用 pyzipper 嵌套 N 层 AES，外层写极小明文头记层数（不含密码），解封无需猜层数；加 `write_recovery_sidecar/verify_recovery` 完整性校验清单（SHA256 逐文件定位损坏 + 可选尾部冗余，**诚实标注为校验+轻冗余、非 WinRAR 级奇偶纠错**）；解包侧自动识别封缄包逐层剥离。④**库身份对账**——`core/identity.py`（uuid 生成稳定 holder/library id + 展示名）、`core/manifest.py`（带身份戳的 GUID 清单导出/对账，复用 mod_index 的 `copy_fillable`），分享页"离线对账"标签新增清单模式（导出本机清单 / 导入比对 / 复制可补 mod），设置页加展示名。⑤**浏览器文件树 + 库统计面板**——`browser_page` 加左侧目录树导航（每文件夹带卡片计数、点击筛选缩略图墙）+ 库统计（全库/KK/KKS/各类卡计数），用 `QSplitter` 分栏。⑥**分享包按参考清单排除 mod**——`share.build_share_package` 加 `exclude_guids`，生成分享包时跳过参考清单（如大整合包）里已有的 mod、减小体积，README 记录排除数。⑦**载体素材池 + 按清单导出压缩包**——`stego.pick_carrier_from_pool` 从目录随机抽载体（每次外壳不同更隐蔽）；`mod_index.export_as_zip` 按 GUID 清单把本机存在的 zipmod 直接打成一个 zip（ZIP_STORED 不二次压缩），Mod 仓库加"按清单导出压缩包"。**回归红线**：未碰 `core/kk_card.py`，`test_kk_card.py` 仍 7/7；新增 `test_theme`(5)/`test_stego_layered`(4)/`test_manifest`(3)/`test_share_exclude`(1)/`test_gap3`(3) 共 16 用例全绿，全窗口 8 页 × 4 主题集成冒烟通过。旧 `ui/style.qss` 保留为回退基线（已无运行引用）。
> - v0.3.5: **恶性 bug 全面体检 + 潜伏地雷加锁**。系统排查两类致命风险：①写回静默损坏、②破坏性文件操作误删/误改真实卡库。结论——除 v0.3.4 已修的 float32 外无新增活跃恶性 bug：破坏性操作（按作者整理/归档未引用/分享整理的移动）均默认复制、移动需弹窗二次确认、目标已存在不覆盖；解包删源为可选项且仅成功后执行；解包用 Python `zipfile.extract` 自带消毒，无 zip 路径穿越；全局无 `except: pass` 静默吞异常，保存失败会真实抛错弹窗；`save()` 覆盖前自动备份。唯一处理：给已无人调用但仍危险的 `set_block_dict` 上锁——检测到字典含浮点直接拒绝（避免将来误用整块重打包重蹈 float32→float64 覆辙），改块请走 `update_parameter` 字节级写回。新增 `_contains_float` 递归检测（bool 不误判）。回归 7/7，KK/KKS 真卡写回字节级验证通过。
> - v0.3.4: **修复"游戏读不出卡"的致命 bug（游戏源码级定位）**。现象：编辑器另存的卡，KK 本体提示 "Corrupted character card" 拒绝加载。逐字节验尸发现：容器层（缩略图/脸图/其它块/lstInfo 偏移）全部正确，唯一变化是 Parameter 块——`set_block_dict` 整块用 `msgpack.packb` 重打包时，把 `voiceRate` 的 **float32(0xCA) 升成了 float64(0xCB)**。反编译 `Assembly-CSharp-firstpass.dll` 坐实：`ChaFileParameter.voiceRate` 是 C# `float`，其 `MessagePackBinary.ReadSingle` 的解码表**只注册了 0xCA 一个合法码**（`singleDecoders[202]=Float32Single`，其余 255 个全是抛 `InvalidOperationException` 的 `InvalidSingle`），float64 直接令整卡反序列化失败。修复：Parameter 改用**字节级外科手术写回**（`patch_msgpack_map`+`_skip_msgpack`），未改字段一个比特不动（float32 精确保留），改动浮点强制按 C# `float` 写回 0xCA。KK/KKS 真卡验证：零改动整文件字节一致、改名后仅 nickname 字节变化、voiceRate 原值 `0.7099999785423279` 一位不差。
> - v0.3.3: 对齐参考图二级功能 + 修复一个浮点恶性 bug。**编辑器**新增「预览写回差异」(并借此抓出 voiceRate 经 spinbox 丢精度的静默损坏——已改为只写回用户真正改动的字段；不改即存=整文件字节级完全一致，严格无容差验证通过)。**Mod 仓库**新增 清空索引/复制可补Mod/按作者整理/归档未引用/清单互助(导出本机清单·导入比对)，检查移至后台并支持场景卡。**解包打包**新增 AES-256 密码加密与多密码解密(pyzipper)、解包操作选项(删源/清队列)。**分享整理**扩成四标签页(生成/导入恢复/整理/离线对账)。破坏性操作默认复制+确认，均在真卡/真mod/临时副本上验证。
> - v0.3.2: KK 整合版（1 万 mod / 1434 角色卡 / 12918 场景卡）压力适配。① Mod 索引增量化：缓存文件指纹(mtime+size)，加 mod 后重建从 ~247s 降到 ~0.5s；② Mod 检查移至后台线程，并支持场景卡（聚合内嵌角色 + 场景级 studio 道具依赖）；③ 浏览器轻量流式扫描（只读首图+头部，seek 读 Parameter 取名，跳过大块），1434 角色卡扫描 150s→38s；④ 缩略图降采样+图标缓存+显示上限 3000，避免上万卡撑爆内存；⑤ 场景卡 mod 依赖解析（UAR）并入分析。KK 本体兼容性全面验证（向上兼容，以 KK 为主）。
> - v0.3.1: 恶性 Bug 排查与修复。① 修复血型静默损坏（mod 扩展血型索引≥4 时下拉显示不出会被保存成 A，现改为 itemData 驱动+越界兜底）；② 修复 looks_like_zip 逻辑/性能 Bug（去掉永真的 testzip 全量校验，伪装大文件不再卡顿）；③ get_block_dict 重写为多策略解码链，KK Custom 等多段二进制块不再抛错。KK 本体目录全面体检通过（分类/依赖提取/manifest/Custom 容错）。
> - v0.3.0: 补齐全部剩余模块——卡片浏览器、解包/打包+隐写伪装、Mod仓库缺失检测、场景卡提取、分享整理。新增后台线程 Worker、日志总线、目录扫描、配置存储等基础设施。内核增加卡片分类(角色/服装/场景)与 Sideloader 依赖 GUID 提取。样式精修(等宽数据视图/进度条/复选框/类型色标等)。新增 README.md，补全 .gitignore。全部模块经真实 KK/KKS 卡与真 mod 库验证。
> - v0.2.0: 「角色卡编辑」升级为丰富版——新增 提问/特点/H相关 三个标签页（按真卡字段动态生成中文勾选项）、完整名、备注(条件)、敏感部位/积极性/勤奋/温柔/音调 数值项、卡片详情表、捏脸数据只读摘要、KK↔KKS 标识转换（实验性）、报告含 提问/特点/H接受 统计。内核 get_block_dict 增加二进制块容错(UTF-8 失败退回 raw)。
> - v0.1.0: 立项。搭建项目骨架 + PyQt6 桌面应用框架；实现并验证 KK/KKS 角色卡解析内核（地基）；完成「角色卡编辑」模块。

## v0.3.0 变更明细

### 新增核心模块

- **core/settings.py**：JSON 配置（游戏目录 / Mod 目录 / 输出目录），含 mods 目录推断。
- **core/card_scan.py**：目录扫描，识别角色/服装/场景卡并提取缩略图与角色名。
- **core/mod_index.py**：扫描 .zipmod 读 manifest.xml 建 GUID 索引（可缓存 JSON）；check_card 比对卡片依赖找缺失。
- **core/stego.py**：zip 打包/解包；把压缩包追加到载体后伪装（zipfile 原生支持带前缀 zip）；分卷/合并。
- **core/scene_card.py**：扫描场景卡内嵌角色 marker，以脸图作封面重建为独立角色卡；analyze_scene 聚合依赖。
- **core/share.py**：把角色卡与其依赖 mod 复制成分享包，写 README。

### 内核增强 (core/kk_card.py)

- 新增服装卡 marker、`classify()`（角色/服装/场景/其它判别）、`peek_header()`、`extract_mod_ids()`（解 KKEx→UAR→info blob 的 ModID）。

### 新增 UI

- **ui/worker.py**：通用后台线程，自动注入 progress 回调，信号回报结果/异常。
- **ui/applog.py**：全局日志总线。
- **ui/pages/**：browser / pack / mod / scene / share / settings / log 七个功能页。
- **ui/main_window.py**：接入 8 个真实页面，打通浏览器双击→编辑器。
- **ui/style.qss**：精修——等宽只读数据视图、进度条、复选框、列表/菜单/工具提示样式。
- **ui/pages/browser_page.py**：类型色标（角色蓝/服装绿/场景琥珀）。

### 文档

- 新增 **README.md**；.gitignore 补充 config.json / mod_index.json。

### 验证

- 真 KK 卡(5.27MB)、真 KKS 卡(27.9MB)、真服装卡、真场景卡(提取2角色)、真 mod 库(manifest解析+缺失检测54依赖)、隐写打包往返、分卷合并字节一致——全部通过；核心单元测试 7/7 绿。

## v0.2.0 变更明细

### 新增 core/kk_fields.py — 提问/特点/H相关 字段中文标签映射

- ANSWER_LABELS(提问9项) / ATTRIBUTE_LABELS(特点KK18+KKS并集) / DENIAL_LABELS(H接受5项) / SCALAR_LABELS(详情表)。
- `count_true` / `editable_items` 跳过 KKEx 占位键 `ExtendedSaveData`（展示跳过、写回保留）。

### 修改 core/kk_card.py — get_block_dict 二进制容错

- Custom 等内含二进制的块用 UTF-8 解码会抛 UnicodeDecodeError，现退回 `raw=True` 保留原始字节，避免上层崩溃。

### 重写 ui/pages/editor_page.py — 丰富版编辑器

- 字段区滚动化；新增 完整名(只读合成)、备注(仅原卡有该字段才可写)、提问/特点/H相关 三标签页勾选项（按真卡 key 动态生成）、H 数值项。
- 右侧信息面板四视图：报告(含 提问/特点/H接受 统计 + 块存在性) / 卡片详情(标量表) / 解析JSON / 捏脸数据(只读摘要)。
- 工具条新增「转换 KK/KKS」(实验性，仅切 marker，强提示另存为)。
- 嵌套布尔字典按 key 在原副本上回填，保留占位键；真 KK/KKS 卡验证编辑翻转持久化、其它块字节保持。

## 新增文件

### core/kk_card.py — KK/KKS 角色卡解析内核（地基）

- **功能**：解析恋活 (KK) / 恋活日光浴 (KKS) 角色卡 PNG，读取与安全写回。
- **实现原理**：角色卡 = 缩略图 PNG + 尾部追加二进制（productNo / marker / version / 脸图PNG / lstInfo(MessagePack块索引) / data(各块拼接，块本身也是 MessagePack)）。字符串用 C# BinaryWriter 的 7-bit 变长前缀 + UTF-8。
- **安全写回策略**：未编辑任何块时数据区与块索引**原样字节吐回**（保证读→存与原文件完全一致）；编辑过块时按物理顺序重排、只更新 pos/size，且仅重打包被改的块，其余块字节级保留。
- **真卡验证**：KK(5.27MB)、KKS(27.9MB) 真卡均通过「干净往返字节级一致」「块铺排无空隙」「编辑后重载有效且其它块字节保持」。

### core/kk_enums.py — 枚举友好名映射

- 性格 / 血型 等枚举的中文名映射，仅内置基础游戏取值，mod 扩展值回退为「未知(数值)」绝不报错。

### tests/test_kk_card.py — 内核往返单元测试

- 手工按格式规范拼合成卡验证解析正确性；覆盖字节级往返、编辑持久化、备份、非卡拒绝等 7 个用例，全部通过。

### main.py / launch.py / start.bat — 入口与启动器

- 遵循 bat-launcher 规范：start.bat 仅做引导（无中文），launch.py 负责 Python 版本检查、依赖自动补齐（PyQt6/msgpack/Pillow）、启动桌面应用。

### ui/ — PyQt6 界面

- **main_window.py**：左侧导航 + 右侧页面堆叠；支持拖拽角色卡直接进编辑器。
- **style.qss**：功能型暗色主题（GitHub-Dark 风），克制扁平、无渐变/无发光/无 AI 味。
- **widgets.py**：PageBase 页头基类 + 卡片/标题/提示等复用部件。
- **pages/editor_page.py**：角色卡编辑页（读卡、改姓名/昵称/性格/血型/社团/生日、另存为新卡、覆盖+备份、更换预览图、导出 JSON、报告/JSON 双视图）。
- **pages/placeholder.py**：其余 6 模块的占位页，保证应用整体可运行。

---

## 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| 新增 | core/kk_card.py, core/kk_enums.py, core/__init__.py |
| 新增 | tests/test_kk_card.py |
| 新增 | main.py, launch.py, start.bat, requirements.txt, .gitignore |
| 新增 | ui/main_window.py, ui/style.qss, ui/widgets.py, ui/__init__.py |
| 新增 | ui/pages/editor_page.py, ui/pages/placeholder.py, ui/pages/__init__.py |

---

## 测试方式

1. 双击 `start.bat`（或 `python launch.py`）启动；首次运行会自动补齐依赖。
2. 点「读卡」或把角色卡 PNG 拖入窗口 → 应显示缩略图、姓名/性格/血型/生日、右侧报告。
3. 改昵称 → 「另存为新卡」→ 用游戏或本工具重新读取，确认昵称已变、其它信息无损。
4. 命令行回归：`python tests/test_kk_card.py`（应 7 通过 0 失败）。

## 待办（后续模块）

- 卡片浏览器 / 解包打包+隐写 / Mod 仓库缺失检测 / 场景卡工具 / 分享整理导入 / 运行日志 / 设置。
