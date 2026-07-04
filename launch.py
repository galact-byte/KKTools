"""KKTools 启动器 —— 恋活 / 恋活日光浴 角色卡工具箱。

职责：检查 Python 版本、自动补齐依赖、启动 PyQt6 桌面应用。
所有中文提示集中在这里，start.bat 只做最小引导。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def check_python() -> None:
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[OK] Python 版本: {ver}")
    if sys.version_info < (3, 9):
        print("[X] 需要 Python 3.9+，请升级后重试")
        sys.exit(1)


def check_dependencies() -> None:
    print("\n检查依赖包...")
    # import 名 -> pip 安装名
    packages = {
        "PyQt6": "PyQt6",
        "msgpack": "msgpack",
        "PIL": "Pillow",
        "pyzipper": "pyzipper",
        "send2trash": "Send2Trash",
    }
    for import_name, install_name in packages.items():
        try:
            __import__(import_name)
            print(f"  [OK] {import_name}")
        except ImportError:
            print(f"  [..] {import_name} 未安装，正在安装 {install_name} ...")
            run(f"{sys.executable} -m pip install {install_name} -q")
            try:
                __import__(import_name)
                print(f"  [OK] {import_name} 安装成功")
            except ImportError:
                print(f"  [X] {import_name} 安装失败，请手动执行: pip install {install_name}")
                sys.exit(1)


def start_app() -> None:
    print("\n正在启动 KKTools ...")
    print("=" * 50)
    # 桌面应用，直接以当前解释器运行主程序，继承控制台便于查看日志
    proc = subprocess.run([sys.executable, str(ROOT / "main.py")])
    if proc.returncode != 0:
        print(f"\n[!] 程序退出码 {proc.returncode}")
        sys.exit(proc.returncode)


def main() -> None:
    print("=" * 50)
    print("  KKTools - 恋活角色卡工具箱")
    print("=" * 50)
    print()
    check_python()
    check_dependencies()
    start_app()


if __name__ == "__main__":
    main()
