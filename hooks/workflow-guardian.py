#!/usr/bin/env python3
"""
workflow-guardian.py — V5 shim

V4.1 → V5 重構：dispatcher 邏輯搬到 dispatcher.py + handlers/。
保留本檔以兼容 settings.json / 文件中既有的 workflow-guardian.py 路徑引用。

完整 V4.1 原版見 hooks/_v4_archive/workflow-guardian.py（P6 GA 後可刪本 shim 並改寫
settings.json 直接指 dispatcher.py）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dispatcher import main

if __name__ == "__main__":
    main()
