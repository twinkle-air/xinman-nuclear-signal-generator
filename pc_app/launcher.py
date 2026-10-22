"""PyInstaller入口。

入口位于包外并使用绝对导入，确保冻结后的程序仍保留nucsignal_app包上下文。
"""

from nucsignal_app.main import main


if __name__ == "__main__":
    raise SystemExit(main())

