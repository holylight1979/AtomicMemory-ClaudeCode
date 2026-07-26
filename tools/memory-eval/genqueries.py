"""genqueries.py — 檢索回歸評估：合成查詢集生成器。

對 memory/_atom_index.json（SoT）中每顆 atom 生成 2-3 條「應命中此 atom」的
模擬使用者 prompt，另按每 5 顆 atom 1 條的比例生成「不應命中任何 atom」的負例。

兩種生成模式：
- llm：本地 Ollama 在線時，用 LLM 生成貼近真實口吻的查詢（繁中混英文技術詞）
- template：離線 fallback，從 triggers/標題/知識首行確定性組裝模板句

輸出 queries.jsonl，每行：
    {"q": "...", "expect": "<atom name>"|null, "cls": "direct"|"negative", "gen": "llm"|"template"}

冪等：預設保留既有 queries、只補索引中尚無查詢的 atom；--regen 全部重生。

用法：
    python genqueries.py                 # auto：Ollama 在線用 llm，否則 template
    python genqueries.py --mode template # 強制模板模式（完全離線、確定性）
    python genqueries.py --regen         # 丟棄既有 queries 全重生
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

CLAUDE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CLAUDE_DIR / "lib"))
sys.path.insert(0, str(CLAUDE_DIR / "tools"))

from atom_index_json import load_atom_index_json  # noqa: E402

DEFAULT_MEMORY_DIR = CLAUDE_DIR / "memory"
DEFAULT_OUT = Path(__file__).resolve().parent / "queries.jsonl"

# 負例池：閒聊/生活/無關技術詞，避開索引中任何 trigger 字串。
NEGATIVE_POOL = [
    "今天天氣如何？隨便聊聊",
    "幫我想三個晚餐菜色",
    "翻譯這句話成英文：早安，祝你有美好的一天",
    "1 加到 100 的總和是多少",
    "推薦幾部好看的科幻電影",
    "寫一首關於海的短詩",
    "台北到高雄的高鐵大概要多久",
    "什麼是光合作用？",
    "幫我把這段話改得更有禮貌：請盡快回覆",
    "貓為什麼喜歡紙箱？",
    "解釋一下棒球的內野高飛球規則",
    "早餐吃燕麥好還是吐司好",
    "幫我規劃三天兩夜的花蓮行程",
    "為什麼天空是藍色的",
    "咖啡和茶哪個咖啡因比較多",
    "講一個冷笑話",
    "如何醃出好吃的糖醋排骨",
    "地球到月球的距離是多少",
    "推薦一本適合睡前讀的小說",
    "跑步前要不要做暖身",
]


# ─── Atom 讀取 ───────────────────────────────────────────────────────────────

def load_atoms(mem_dir: Path) -> List[Dict]:
    """從 _atom_index.json 讀 active atom 清單。"""
    data = load_atom_index_json(mem_dir)
    return [
        {
            "name": a.get("name", ""),
            "path": a.get("path", ""),
            "triggers": [t for t in a.get("triggers", []) if t],
        }
        for a in data.get("atoms", [])
        if a.get("name")
    ]


def read_atom_context(claude_dir: Path, rel_path: str) -> Dict[str, str]:
    """讀 atom 檔取標題與知識首行（供 LLM 語境 / 模板補充）。讀不到回空字串。"""
    ctx = {"title": "", "knowledge": ""}
    if not rel_path:
        return ctx
    p = claude_dir / rel_path
    try:
        text = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ctx
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        ctx["title"] = m.group(1).strip()
    # 知識首行：## 知識 區塊下第一個 bullet；沒有該區塊則取第一個 [固/觀/臨] bullet
    km = re.search(r"^##\s+知識\s*\n([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    body = km.group(1) if km else text
    bm = re.search(r"^[-*]\s+(.+)$", body, re.MULTILINE)
    if bm:
        ctx["knowledge"] = bm.group(1).strip()[:200]
    return ctx


# ─── Template 模式（確定性、離線） ───────────────────────────────────────────

def template_queries(name: str, triggers: List[str], title: str = "") -> List[str]:
    """從 triggers/標題確定性組裝 2-3 條查詢。

    ASCII trigger 前後留空白：實際 trigger match 對 ASCII 詞用 word-boundary，
    而 Python re 的 \\w 含 CJK，緊貼中文字會讓 boundary 失效。
    """
    qs: List[str] = []
    t = triggers
    if len(t) >= 2:
        qs.append(f"幫我檢查 {t[0]} 相關的部分")
        qs.append(f"{t[1]} 這塊是怎麼運作的？")
        qs.append(f"我在處理一個跟 {t[0]} 和 {t[1]} 有關的問題")
    elif len(t) == 1:
        qs.append(f"幫我檢查 {t[0]} 相關的部分")
        qs.append(f"{t[0]} 這塊是怎麼運作的？")
    else:
        # 無 trigger：退用標題/名稱（靠 BM25 對 atom name 的評分）
        label = title or name.replace("-", " ")
        qs.append(f"關於 {label} ，說明一下現況")
        qs.append(f"我想了解 {label} 的細節")
    return qs


# ─── LLM 模式 ────────────────────────────────────────────────────────────────

_LLM_PROMPT = """你在為一套記憶檢索系統生成回歸測試查詢。
以下是一顆記憶 atom 的資訊：
- 名稱：{name}
- 觸發詞：{triggers}
- 標題：{title}
- 知識摘要：{knowledge}

請生成 3 條「真實使用者可能輸入、且應該檢索到這顆 atom」的 prompt。
要求：
- 繁體中文為主，技術詞可保留英文（貼近真實開發者口吻）
- 每條 10-60 字，是自然的請求或提問，不是關鍵字堆疊
- 至少 2 條要包含觸發詞中的字詞（英文詞前後留半形空白）
- 只輸出 JSON 字串陣列，例如 ["...", "...", "..."]"""


def llm_queries(client, atom: Dict, ctx: Dict[str, str]) -> Optional[List[str]]:
    """用本地 LLM 生成查詢；解析失敗或輸出不合格回 None（caller 落回 template）。"""
    prompt = _LLM_PROMPT.format(
        name=atom["name"],
        triggers=", ".join(atom["triggers"]) or "(無)",
        title=ctx["title"] or atom["name"],
        knowledge=ctx["knowledge"] or "(無)",
    )
    raw = client.generate(prompt, format="json", think=False, timeout=60)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):  # 有些模型包一層 {"queries": [...]}
        for v in data.values():
            if isinstance(v, list):
                data = v
                break
    if not isinstance(data, list):
        return None
    out = [q.strip() for q in data if isinstance(q, str) and 5 <= len(q.strip()) <= 120]
    return out[:3] if len(out) >= 2 else None


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def negatives_needed(n_atoms: int) -> int:
    return max(1, n_atoms // 5)


def load_existing(out_path: Path) -> List[Dict]:
    if not out_path.exists():
        return []
    rows: List[Dict] = []
    try:
        for line in out_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows


def generate(
    atoms: List[Dict],
    existing: List[Dict],
    mode: str,
    claude_dir: Path,
    limit: int = 0,
) -> List[Dict]:
    """回傳完整 query 清單（保留 existing + 補新）。mode: llm|template。"""
    rows = list(existing)
    covered = {r.get("expect") for r in rows if r.get("cls") == "direct"}
    existing_neg_qs = {r.get("q") for r in rows if r.get("cls") == "negative"}

    client = None
    if mode == "llm":
        from ollama_client import get_client
        client = get_client()

    added = 0
    for atom in atoms:
        if atom["name"] in covered:
            continue
        if limit and added >= limit:
            break
        ctx = read_atom_context(claude_dir, atom["path"])
        qs: Optional[List[str]] = None
        gen = "template"
        if client is not None:
            qs = llm_queries(client, atom, ctx)
            if qs:
                gen = "llm"
        if not qs:
            qs = template_queries(atom["name"], atom["triggers"], ctx["title"])
        for q in qs:
            rows.append({"q": q, "expect": atom["name"], "cls": "direct", "gen": gen})
        added += 1
        print(f"  + {atom['name']} ({gen}, {len(qs)} queries)")

    # 負例補足到目標數（固定池、確定性；不足時循環加序號）
    target_neg = negatives_needed(len(atoms))
    have_neg = sum(1 for r in rows if r.get("cls") == "negative")
    i = 0
    while have_neg < target_neg:
        base = NEGATIVE_POOL[i % len(NEGATIVE_POOL)]
        q = base if i < len(NEGATIVE_POOL) else f"{base}（{i // len(NEGATIVE_POOL) + 1}）"
        i += 1
        if q in existing_neg_qs:
            continue
        rows.append({"q": q, "expect": None, "cls": "negative", "gen": "template"})
        existing_neg_qs.add(q)
        have_neg += 1
    return rows


def save(rows: List[Dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="生成檢索回歸評估查詢集")
    ap.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--mode", choices=["auto", "llm", "template"], default="auto")
    ap.add_argument("--regen", action="store_true", help="丟棄既有 queries 全重生")
    ap.add_argument("--limit", type=int, default=0, help="本次最多補幾顆 atom（0=不限）")
    args = ap.parse_args(argv)

    atoms = load_atoms(args.memory_dir)
    if not atoms:
        print(f"index 無 atom：{args.memory_dir}", file=sys.stderr)
        return 1

    mode = args.mode
    if mode == "auto":
        try:
            from ollama_client import get_client
            mode = "llm" if get_client().is_available("llm") else "template"
        except Exception:
            mode = "template"
    print(f"atoms={len(atoms)} mode={mode} out={args.out}")

    existing = [] if args.regen else load_existing(args.out)
    rows = generate(atoms, existing, mode, CLAUDE_DIR, limit=args.limit)
    save(rows, args.out)

    n_direct = sum(1 for r in rows if r["cls"] == "direct")
    n_neg = sum(1 for r in rows if r["cls"] == "negative")
    print(f"完成：direct={n_direct} negative={n_neg} 總 {len(rows)} 條")
    return 0


if __name__ == "__main__":
    sys.exit(main())
