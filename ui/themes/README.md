# KKTools 主题编写说明

主题是一个 JSON 文件。内置主题放在本目录（`ui/themes/`）；你也可以在「软件设置 → 外观」里
指定一个**用户主题目录**，把自己的主题 JSON 放进去，程序会自动扫到。同 `id` 时用户主题覆盖内置。

## 设计理念：角色化令牌

不必给每个控件单独定义颜色。只需写十来个**角色令牌**（背景、文字、强调色……），
hover / pressed / disabled 等派生色由程序按明暗变体自动算出。所以一个主题文件可以很短。

## 最小可用模板

把下面这段存成 `my_theme.json`，改 `id`、`name` 和颜色即可：

```json
{
  "id": "my_theme",
  "name": "我的主题",
  "variant": "dark",
  "author": "你的名字",
  "tokens": {
    "bg":         "#101216",
    "bg_deep":    "#0a0c0f",
    "surface":    "#181b21",
    "surface_alt":"#1f232b",
    "border":     "#2b303a",
    "border_soft":"#21252d",
    "text":       "#d9d6ce",
    "text_strong":"#f1eee7",
    "text_muted": "#9a958b",
    "text_dim":   "#6a665e",
    "accent":     "#c0392b",
    "selection":  "#7a2d22",
    "primary":    "#b5402f",
    "on_primary": "#fbf3ee",
    "danger":     "#c0392b",
    "success":    "#5a7d63"
  },
  "shape": { "radius": 6, "radius_sm": 4, "radius_lg": 10 }
}
```

## 字段说明

| 字段 | 含义 |
| :--- | :--- |
| `id` | 唯一标识（英文/数字，存配置用） |
| `name` | 下拉里显示的名字 |
| `variant` | `dark` 或 `light`，决定 hover 是调亮还是调暗 |
| `tokens.bg` / `bg_deep` | 主背景 / 更深的背景（侧栏、状态栏） |
| `tokens.surface` / `surface_alt` | 卡片面 / 次级面（按钮底等） |
| `tokens.border` / `border_soft` | 主描边 / 弱描边 |
| `tokens.text` / `text_strong` / `text_muted` / `text_dim` | 正文 / 标题 / 次要 / 暗淡 |
| `tokens.accent` | 强调色（聚焦框、选中条、选项卡下划线） |
| `tokens.primary` / `on_primary` | 主操作按钮底色 / 其上的文字色 |
| `tokens.selection` | 文本选区底色 |
| `tokens.danger` / `success` | 危险 / 成功色 |
| `shape.radius*` | 圆角（建议 ≤ 12，功能型 UI 克制为宜） |
| `font.ui` / `font.serif` / `font.mono` | 界面 / 标题 / 等宽字体（可省，走默认） |

> 缺哪个令牌就回退到默认值（墨色·夜），所以半成品主题也能加载，方便边调边看。

内置主题（墨色和风系，均为单一强调色、对比度过 WCAG AA）可作为起点，复制一份改色最快：

| id | 名称 | 明暗 | 强调色 |
| :--- | :--- | :--- | :--- |
| `ink_dark` | 墨色·夜 | 深 | 朱砂红 |
| `indigo_dark` | 靛青·夜 | 深 | 靛青蓝 |
| `pine_dark` | 松烟·夜 | 深 | 松绿 |
| `sakura_dark` | 樱·夜 | 深 | 樱粉 |
| `amber_dark` | 琥珀·夜 | 深 | 琥珀金 |
| `seiji_dark` | 青磁·夜 | 深 | 青瓷 |
| `ink_light` | 宣纸·昼 | 浅 | 朱砂红 |
| `snow_light` | 雪·昼 | 浅 | 朱砂红 |

> 新增主题建议跑一遍 `tests/test_theme.py`：会校验 QSS 无残留占位符，并断言正文/主按钮文字对比 ≥4.5:1。
