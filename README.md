# KKTools

恋活 KK / KKS 的角色卡与 Mod 管理工具。在一个工作台里浏览卡片、修改角色档案、检查缺失 Mod，以及打包分享。

![KKTools 卡片画廊](docs/images/kktools.png)

## 下载与使用

从 [最新版本](https://github.com/galact-byte/KKTools/releases/latest) 下载 `KKTools.exe`，放进可写的独立文件夹，双击运行，无需安装 Python。

适用于 Windows 10 / 11（64 位），需要 Microsoft Edge WebView2 Runtime；启动提示缺少组件时，请安装[微软官方运行时](https://developer.microsoft.com/microsoft-edge/webview2/#download-section)。

1. 在「外观与设置」配置 KK / KKS 游戏目录和额外 Mod 目录。
2. 在「Mod 仓库」扫描索引，再去「卡片画廊」选择卡片目录。
3. 点击卡片查看预览，双击角色卡原地编辑；保存前可选择另存，覆盖原卡时自动保留 `.bak` 备份。

## 能做什么

- **卡片与场景**：浏览、搜索和筛选 KK / KKS 卡片；编辑角色档案与封面；分析 Studio 场景并提取内嵌角色。
- **Mod 管理**：扫描 zipmod、检查卡片缺失依赖、按作者整理、归档所选卡片未引用的 Mod，以及通过清单对账和导出补齐包。
- **打包与分享**：普通 ZIP、加密、图片/视频载体、分卷；按角色导出卡片与依赖 Mod、导入分享包、分类整理卡片。
- **工作台**：四套主题、壁纸融合、操作日志与版本更新。

服装卡支持识别和整理；档案编辑仅针对角色卡。缺失检测依据卡内记录与本地索引，不会联网下载 Mod。未引用归档只以本次选中的卡片为依据，请先检查范围。图片和视频载体采用本工具的封装方式，不保证与其他工具的专有格式互通。

## 升级与反馈

可以在设置中检查更新，也可以退出程序后用新版 EXE 替换旧文件。保留同目录的 `config.json` 和 `mod_index.json`，即可保留设置与索引。

遇到错误，可在「运行日志」打开日志目录，将出错时间和相关日志附到 [Issues](https://github.com/galact-byte/KKTools/issues)。

## 从源码运行

需要 Python 3.10+、Node.js 22+ 和 WebView2 Runtime：

```powershell
python -m pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
python main.py
```

运行测试：`python -m pytest -q`。构建单文件程序：`python -m PyInstaller --noconfirm KKTools.spec`。
