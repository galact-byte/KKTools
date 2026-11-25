<p align="center">
  <img src="assets/kktools.png" alt="KKTools Logo" width="96" height="96">
</p>

<h1 align="center">KKTools</h1>

<p align="center"><strong>恋活角色卡与 Mod 工具箱</strong></p>
<p align="center">浏览收藏、编辑角色、检查依赖、打包分享，在一个工作台里完成。</p>

<p align="center">
  <a href="https://github.com/galact-byte/KKTools/releases/latest"><img src="https://img.shields.io/github/v/release/galact-byte/KKTools?style=flat&amp;label=Release&amp;color=7b9fc4" alt="最新版本"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%2F%2011%20x64-7b9fc4?style=flat" alt="Windows 10 / 11 64 位">
  <img src="https://img.shields.io/badge/游戏-KK%20%2F%20KKS-c28fa7?style=flat" alt="支持 KK / KKS">
</p>

<p align="center">
  <a href="https://github.com/galact-byte/KKTools/releases/latest"><strong>下载最新版</strong></a> ·
  <a href="#开始使用">开始使用</a> ·
  <a href="#功能一览">功能一览</a> ·
  <a href="https://github.com/galact-byte/KKTools/issues">问题反馈</a>
</p>

<p align="center">
  <img src="docs/images/kktools.png" alt="KKTools 卡片画廊，展示角色卡预览、筛选和角色档案" width="100%">
</p>

## 开始使用

从 [最新版本](https://github.com/galact-byte/KKTools/releases/latest) 下载 **KKTools.exe**，放进可写的独立文件夹，双击运行，无需安装 Python。

适用于 **Windows 10 / 11（64 位）**，需要 Microsoft Edge WebView2 Runtime；启动提示缺少组件时，请安装[微软官方运行时](https://developer.microsoft.com/microsoft-edge/webview2/#download-section)。

1. **设置目录** — 在「外观与设置」配置 KK / KKS 游戏目录和额外 Mod 目录。
2. **加载收藏** — 在「Mod 仓库」扫描索引，再去「卡片画廊」选择卡片目录。
3. **浏览与编辑** — 点击卡片查看预览，双击角色卡原地编辑。保存时可选择另存，覆盖原卡时自动保留 `.bak` 备份。

## 功能一览

| 功能 | 可以做什么 |
| :--- | :--- |
| **卡片画廊** | 浏览、搜索和筛选 KK / KKS 卡片，按作者分组、本机修正作者信息，添加自定义标签。 |
| **角色与场景** | 编辑角色档案和封面，单张或批量转换 KK / KKS 角色卡；分析 Studio 场景、提取内嵌角色。 |
| **Mod 管理** | 扫描 zipmod、检查缺失依赖、按作者整理、归档所选卡片未引用的 Mod，通过清单对账并导出补齐包。 |
| **打包分享** | 普通 ZIP、加密、图片或视频载体、分卷；按角色导出卡片与依赖，也可为每个文件单独生成分享包。 |
| **导入与整理** | 导入分享包，预览后自动归位到游戏目录，分类整理卡片。 |
| **工作台** | 四套主题、壁纸融合、操作日志与版本更新；导出卡片列表 CSV、角色档案 JSON 和场景分析 JSON / TXT。 |

### 使用范围

- **卡片兼容**：服装卡支持识别和整理；档案编辑和 KK / KKS 互转仅针对角色卡，转换默认另存。游戏内及全部第三方卡片、Mod 的兼容性尚未验证。
- **依赖检查**：依据卡内记录与本地索引检测，不会联网下载 Mod。未引用归档只以本次选中的卡片为依据，请先检查范围。
- **载体格式**：图片和视频载体采用本工具的封装方式，不保证与其他工具的专有格式互通。
- **损坏恢复**：打包时勾选附带恢复记录，并将 `.kkrec.json` 与产物一起保留。「解包与打包 → 校验与修复」可尝试修复末尾最多 64 KiB 的损坏或截断，整文件校验通过后生成新副本；其他位置的损坏无法恢复。

## 升级与反馈

**升级** — 在设置中检查更新，或退出程序后用新版 EXE 替换旧文件。保留同目录的以下文件即可保留本地数据：

| 文件 | 保存内容 |
| :--- | :--- |
| `config.json` | 设置 |
| `mod_index.json` | Mod 索引 |
| `card_tags.sqlite3` | 卡片标签 |

标签按本地文件路径关联，不写入卡片；移动或改名后不会自动跟随。

**反馈** — 遇到错误，可在「运行日志」打开日志目录，将出错时间和相关日志附到 [Issues](https://github.com/galact-byte/KKTools/issues)。

## 从源码运行

<details>
<summary>从源码运行、测试与打包</summary>

需要 Python 3.10+、Node.js 22+ 和 WebView2 Runtime：

```powershell
python -m pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
python main.py
```

运行测试：`python -m pytest -q`。

构建单文件程序：`python -m PyInstaller --noconfirm KKTools.spec`。

</details>
