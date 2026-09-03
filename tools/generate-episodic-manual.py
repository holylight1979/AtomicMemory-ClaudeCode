"""
generate-episodic-manual.py — 手動觸發 episodic atom 生成

從最近的 active state file 生成 episodic atom。
用於 SessionEnd 未觸發的情境。

Usage: python generate-episodic-manual.py [--session-id UUID]
"""

import json
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
HOOKS_DIR = CLAUDE_DIR / "hooks"

# Add hooks and tools to path for imports
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR / "tools"))


def find_best_state(target_sid: str = None):
    """Find the most recent state file with actual work."""
    states = sorted(WORKFLOW_DIR.glob("state-*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    for f in states:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        sid = f.stem.replace("state-", "")
        if target_sid and sid != target_sid:
            continue

        mod = len(data.get("modified_files", []))
        read = len(data.get("accessed_files", []))
        kq = len(data.get("knowledge_queue", []))

        # Skip empty sessions
        if mod == 0 and read < 5 and kq == 0:
            continue

        # Skip if episodic already generated
        if data.get("episodic_checkpoint_done"):
            if not target_sid:
                continue  # try next state
            print(f"[INFO] Session {sid[:12]} already has episodic checkpoint")
            return None, None

        return sid, data

    return None, None


def main():
    target_sid = None
    if len(sys.argv) > 2 and sys.argv[1] == "--session-id":
        target_sid = sys.argv[2]

    sid, state = find_best_state(target_sid)
    if not sid:
        print("[SKIP] No eligible session found (no work or already has episodic)")
        return

    mod = len(state.get("modified_files", []))
    read = len(state.get("accessed_files", []))
    kq = len(state.get("knowledge_queue", []))
    print(f"[INFO] Session: {sid[:12]}  mod={mod}  read={read}  kq={kq}")

    # Load config
    config = {}
    config_path = WORKFLOW_DIR / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Import and call
    from wg_episodic import _generate_episodic_atom, _should_generate_episodic

    if not _should_generate_episodic(state, config):
        print("[SKIP] Session doesn't meet episodic generation threshold")
        return

    try:
        result = _generate_episodic_atom(sid, state, config)
        if result:
            print(f"[OK] Generated: {result}")
            # Mark in state to prevent duplicates
            state["episodic_checkpoint_done"] = True
            state_path = WORKFLOW_DIR / f"state-{sid}.json"
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        else:
            print("[SKIP] Generation returned None (threshold not met)")
    except Exception as e:
        print(f"[ERROR] {e}")
        raise


if __name__ == "__main__":
    main()
