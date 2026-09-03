#!/usr/bin/env python3
"""
rag-engine.py — Memory Vector Service CLI

用法：
  python rag-engine.py index [--incremental] [--layer global|project]
  python rag-engine.py search "查詢" [--top-k 5] [--include-distant] [--enhanced] [--rerank]
  python rag-engine.py search "查詢" --direct    (不經 daemon, 直接載入模型)
  python rag-engine.py status
  python rag-engine.py health
  python rag-engine.py start                     (啟動 daemon)
  python rag-engine.py stop                      (停止 daemon)

預設透過 HTTP 呼叫 daemon (port 3849)，加 --direct 可獨立運作。
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent / "memory-vector-service"
SERVICE_URL = "http://127.0.0.1:{port}"
VECTORDB_DIR = Path.home() / ".claude" / "memory" / "_vectordb"

sys.path.insert(0, str(SERVICE_DIR))


def _get_port():
    """Get configured port."""
    try:
        from config import load_config
        return load_config().get("service_port", 3849)
    except Exception:
        return 3849


def _http_get(path: str, params: dict = None, timeout: int = 30) -> dict:
    """GET request to daemon."""
    port = _get_port()
    url = f"http://127.0.0.1:{port}{path}"
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _http_post(path: str, body: dict = None, timeout: int = 120) -> dict:
    """POST request to daemon."""
    port = _get_port()
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _daemon_running() -> bool:
    """Check if daemon is running."""
    try:
        _http_get("/health", timeout=2)
        return True
    except Exception:
        return False


# ─── Commands ────────────────────────────────────────────────────────────────


def cmd_index(args):
    """Build or update the vector index."""
    if args.direct or not _daemon_running():
        # Direct mode
        from config import load_config
        from indexer import build_index
        cfg = load_config()
        stats = build_index(
            cfg,
            incremental=args.incremental,
            layer_filter=args.layer,
            verbose=True,
        )
    else:
        # Via daemon
        path = "/index/incremental" if args.incremental else "/index"
        print(f"[rag-engine] Sending index request to daemon...")
        stats = _http_post(path, timeout=120)

    print(json.dumps(stats, indent=2, ensure_ascii=False))


def cmd_search(args):
    """Semantic search."""
    query = " ".join(args.query)
    if not query:
        print("Error: query is required", file=sys.stderr)
        sys.exit(1)

    if args.direct or not _daemon_running():
        # Direct mode
        from config import load_config
        cfg = load_config()

        if args.enhanced:
            from reranker import enhanced_search
            results = enhanced_search(query, cfg, top_k=args.top_k)
        elif args.rerank:
            from reranker import rerank
            results = rerank(query, cfg, top_k=args.top_k)
        else:
            from searcher import search
            results = search(
                query, cfg,
                top_k=args.top_k,
                min_score=args.min_score,
                layer_filter=args.layer,
            )
    else:
        # Via daemon
        if args.enhanced:
            results = _http_post("/search/enhanced", {"q": query, "top_k": args.top_k})
        elif args.rerank:
            results = _http_post("/rerank", {"q": query, "top_k": args.top_k})
        else:
            params = {"q": query, "top_k": str(args.top_k), "min_score": str(args.min_score)}
            if args.layer:
                params["layer"] = args.layer
            results = _http_get("/search", params)

    # Pretty print
    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        score = r.get("combined_score") or r.get("score", 0)
        print(f"\n{'─' * 60}")
        print(f"  #{i}  {r.get('atom_name', '?')} ({r.get('layer', '?')})  score={score}")
        print(f"  section: {r.get('section', '?')}  confidence: {r.get('confidence', '?')}")
        print(f"  file: {r.get('file_path', '?')}  line: {r.get('line_number', '?')}")
        if r.get("rewritten_query"):
            print(f"  rewritten: {r['rewritten_query']}")
        print(f"  text: {r.get('text', '')[:200]}")
    print(f"\n{'─' * 60}")
    print(f"Total: {len(results)} results")


def cmd_status(args):
    """Show index and service status."""
    if _daemon_running():
        status = _http_get("/status")
        print("Service: RUNNING")
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print("Service: NOT RUNNING")
        # Direct status
        from config import load_config
        from indexer import get_index_status
        cfg = load_config()
        status = get_index_status(cfg)
        print(json.dumps(status, indent=2, ensure_ascii=False))


def cmd_health(args):
    """Health check."""
    if _daemon_running():
        health = _http_get("/health")
        print(f"OK: {json.dumps(health)}")
    else:
        print("Service not running.")
        sys.exit(1)


def cmd_start(args):
    """Start the daemon."""
    if _daemon_running():
        print("Service is already running.")
        return

    service_py = SERVICE_DIR / "service.py"
    if not service_py.exists():
        print(f"Error: {service_py} not found", file=sys.stderr)
        sys.exit(1)

    # daemon 用「目前這個直譯器」起：PATH 上若是別的 venv（沒裝 lancedb/pyarrow），
    # 起來的 daemon health 會回 OK 但 index/search 全掛。先驗依賴，缺就不起。
    missing = []
    for mod in ("lancedb", "pyarrow"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(
            f"Error: interpreter {sys.executable} lacks {', '.join(missing)}; "
            f"daemon would start crippled. Run with the python that has the vector deps.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Starting Memory Vector Service...")
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            [sys.executable, str(service_py)],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=open(VECTORDB_DIR / "service.log", "a"),  # lf-exempt: fd 交給子行程寫 log，Python 端不寫入
        )
    else:
        subprocess.Popen(
            [sys.executable, str(service_py)],
            stdout=subprocess.DEVNULL,
            stderr=open(VECTORDB_DIR / "service.log", "a"),  # lf-exempt: fd 交給子行程寫 log，Python 端不寫入
            start_new_session=True,
        )

    # Wait for startup
    for _ in range(20):
        time.sleep(0.5)
        if _daemon_running():
            print("Service started successfully.")
            return
    print("Warning: Service may not have started. Check service.log", file=sys.stderr)


def cmd_stop(args):
    """Stop the daemon."""
    if not _daemon_running():
        print("Service is not running.")
        return

    try:
        _http_post("/shutdown", timeout=5)
        print("Shutdown signal sent.")
    except Exception:
        # Try PID file
        pid_file = VECTORDB_DIR / "service.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to PID {pid}")
            except (ValueError, OSError) as e:
                print(f"Failed to stop: {e}", file=sys.stderr)
        else:
            print("Could not stop service.", file=sys.stderr)


def cmd_extract(args):
    """Extract knowledge from text."""
    text = " ".join(args.text)
    if not text:
        print("Error: text is required", file=sys.stderr)
        sys.exit(1)

    if _daemon_running():
        result = _http_post("/extract", {"text": text})
    else:
        from config import load_config
        from reranker import extract_knowledge
        cfg = load_config()
        result = extract_knowledge(text, cfg)

    print(json.dumps(result, indent=2, ensure_ascii=False))


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Memory Vector Service CLI — 原子記憶語意搜尋工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # index
    p_index = sub.add_parser("index", help="建立/更新向量索引")
    p_index.add_argument("--incremental", "-i", action="store_true", help="增量索引")
    p_index.add_argument("--layer", "-l", default=None, help="只索引指定層 (global|project)")
    p_index.add_argument("--direct", "-d", action="store_true", help="不經 daemon")

    # search
    p_search = sub.add_parser("search", help="語意搜尋")
    p_search.add_argument("query", nargs="+", help="查詢文字")
    p_search.add_argument("--top-k", "-k", type=int, default=5, help="回傳筆數")
    p_search.add_argument("--min-score", "-s", type=float, default=0.5, help="最低相似度")
    p_search.add_argument("--layer", "-l", default=None, help="限定層")
    p_search.add_argument("--include-distant", action="store_true", help="含遙遠記憶")
    p_search.add_argument("--enhanced", "-e", action="store_true", help="LLM 查詢改寫")
    p_search.add_argument("--rerank", "-r", action="store_true", help="LLM re-ranking")
    p_search.add_argument("--direct", "-d", action="store_true", help="不經 daemon")

    # status
    sub.add_parser("status", help="索引與服務狀態")

    # health
    sub.add_parser("health", help="健康檢查")

    # start / stop
    sub.add_parser("start", help="啟動 daemon")
    sub.add_parser("stop", help="停止 daemon")

    # extract
    p_extract = sub.add_parser("extract", help="知識萃取")
    p_extract.add_argument("text", nargs="+", help="要萃取的文字")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "index": cmd_index,
        "search": cmd_search,
        "status": cmd_status,
        "health": cmd_health,
        "start": cmd_start,
        "stop": cmd_stop,
        "extract": cmd_extract,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
