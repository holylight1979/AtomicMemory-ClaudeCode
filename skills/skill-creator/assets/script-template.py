#!/usr/bin/env python3
"""<腳本名稱>: <一句話用途>。

用法:
  python <script>.py <args>
  python <script>.py <args> --flag

輸出 JSON 到 stdout (UTF-8)，錯誤到 stderr。
exit 0 = 成功，1 = 業務邏輯失敗，2 = 內部錯誤。
"""
import argparse
import json
import sys
from pathlib import Path

# Windows Python 預設 cp950 stdout 中文會亂碼 → 強制 UTF-8（必備）
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def do_work(arg1: str) -> dict:
    """核心邏輯。回 dict，main 負責序列化 JSON。"""
    # TODO: 實作
    return {"status": "ok", "data": None}


def main():
    p = argparse.ArgumentParser(description="<簡短描述>")
    p.add_argument("arg1", type=str, help="<說明>")
    p.add_argument("--flag", action="store_true", help="<說明>")
    args = p.parse_args()

    try:
        result = do_work(args.arg1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("status") == "ok" else 1)
    except Exception as e:
        # silent failure 風險點：所有未預期錯誤都要走這條，吐 JSON 到 stderr 才能被上層捕捉
        print(json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
