#!/usr/bin/env python3
"""定期清理 Claude Code 環境中的堆積檔案。

Usage:
    python cleanup-old-files.py --dry-run    # 預覽要刪的檔案
    python cleanup-old-files.py --execute    # 實際刪除
"""
import argparse
import os
import time
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"

# (目錄, glob pattern, 保留天數)
CLEANUP_RULES = [
    (CLAUDE_DIR / "shell-snapshots", "snapshot-*.sh", 30),
    (CLAUDE_DIR / "debug", "*.txt", 14),
    (CLAUDE_DIR / "workflow", "state-*.json", 30),
]


def find_old_files(directory: Path, pattern: str, max_age_days: int):
    """找出超過 max_age_days 的檔案。"""
    if not directory.exists():
        return []
    cutoff = time.time() - max_age_days * 86400
    old = []
    for f in directory.glob(pattern):
        if f.is_file() and f.stat().st_mtime < cutoff:
            old.append(f)
    return sorted(old, key=lambda f: f.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(description="清理 Claude Code 堆積檔案")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="只預覽，不刪除")
    group.add_argument("--execute", action="store_true", help="實際刪除")
    args = parser.parse_args()

    total_count = 0
    total_bytes = 0

    for directory, pattern, max_age_days in CLEANUP_RULES:
        old_files = find_old_files(directory, pattern, max_age_days)
        if not old_files:
            print(f"  {directory.name}/: 無需清理 (>{max_age_days}天: 0 個)")
            continue

        size = sum(f.stat().st_size for f in old_files)
        print(f"  {directory.name}/: {len(old_files)} 個檔案 >{max_age_days}天 ({size/1024:.1f} KB)")

        for f in old_files:
            age_days = (time.time() - f.stat().st_mtime) / 86400
            print(f"    {'[DEL]' if args.execute else '[DRY]'} {f.name} ({age_days:.0f}天前)")
            if args.execute:
                f.unlink()

        total_count += len(old_files)
        total_bytes += size

    action = "已刪除" if args.execute else "將刪除"
    print(f"\n總計：{action} {total_count} 個檔案，釋放 {total_bytes/1024:.1f} KB")


if __name__ == "__main__":
    main()
