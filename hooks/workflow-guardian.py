#!/usr/bin/env python3
"""
workflow-guardian.py — shim

dispatcher 邏輯在 dispatcher.py + handlers/。
保留本檔以兼容 settings.json / 文件中既有的 workflow-guardian.py 路徑引用。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dispatcher import main

if __name__ == "__main__":
    main()
