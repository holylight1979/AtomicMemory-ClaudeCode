"""verify_search_terms_to_triggers.py — tools/search-terms-to-triggers.py 的候選判定。

做什麼：用小型假索引斷言：詞在標題／知識段而觸發詞沒涵蓋 → 候選；觸發詞已涵蓋 → 不列；
泛用詞略過；出現在超過 TOO_BROAD_CARDS 張卡 → 只進「太廣」；多詞搜尋只沾到一個詞的卡不列；
英數詞整字比（sandbox 不配 sandboxes）；讀不到檔的卡略過；排序與 md 輸出。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_search_terms_to_triggers.py
       或 python -X utf8 tools/verify/verify_search_terms_to_triggers.py（印 SEARCH_TERMS_TO_TRIGGERS_CHECK PASS/FAIL）
"""
import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "search_terms_to_triggers", Path(__file__).resolve().parents[1] / "search-terms-to-triggers.py")
st = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(st)

# (卡名, 標題, 知識段, 觸發詞)
CARDS = [
    ("a-worktree-filename-too-long", "Windows worktree 放暫存會 filename too long", "- [臨] 路徑太長；跟唯讀沙箱無關的旁註", ["worktree"]),
    ("b-codex-exec-sandbox", "codex 唯讀沙箱起不來", "- [臨] 報 createprocesswithlogonw；sandboxes 都起不來", ["codex exec"]),
    ("c-heredoc", "heredoc 會吃反斜線", "- [臨] 寫檔改用檔案", ["heredoc"]),
] + [(f"d-filler-{i}", f"填充卡 {i}", "- [臨] 路徑 相關；hook 也提到", ["filler"]) for i in range(6)]

QUERIES = [
    "唯讀沙箱 createprocesswithlogonw",  # b 命中 2 詞 → 兩個都是候選；a 只沾到一個詞 → 不列
    "唯讀沙箱",                          # 單詞搜尋：a、b 都列
    "heredoc",                           # c 的觸發詞已涵蓋 → 不列
    "hook 路徑",                         # hook 泛用、路徑出現在 7 張卡 → 太廣
    "sandbox",                           # 整字比，不配 sandboxes
]


def _index(tmp_path: Path) -> Path:
    atoms = []
    for name, title, body, triggers in CARDS:
        rel = f"memory/x/{name}.md"
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(f"# {title}\n\n- Confidence: [臨]\n\n## 知識\n\n{body}\n\n## 行動\n\n- 無\n",
                                    encoding="utf-8")
        atoms.append({"name": name, "path": rel, "triggers": triggers, "scope": "global"})
    atoms.append({"name": "gone", "path": "memory/x/gone.md", "triggers": [], "scope": "global"})
    path = tmp_path / "memory" / "_atom_index.json"
    path.write_text(json.dumps({"version": "3", "atoms": atoms}, ensure_ascii=False), encoding="utf-8")
    return path


def test_candidates(tmp_path, capsys):
    cards = st.load_cards(_index(tmp_path), tmp_path)
    assert len(cards) == len(CARDS)
    assert "1 張卡讀不到檔" in capsys.readouterr().err
    candidates, n_terms, generic, too_broad = st.find_candidates(QUERIES, cards)
    assert candidates == [
        ("b-codex-exec-sandbox", "唯讀沙箱", 2, "標題"),
        ("a-worktree-filename-too-long", "唯讀沙箱", 1, "知識"),
        ("b-codex-exec-sandbox", "createprocesswithlogonw", 1, "知識"),
    ]
    assert (n_terms, generic) == (6, 1)
    assert too_broad == {"路徑": 7}


def test_render_md(tmp_path):
    cards = st.load_cards(_index(tmp_path), tmp_path)
    candidates, n_terms, generic, too_broad = st.find_candidates(QUERIES, cards)
    md = st.render_md(150, len(QUERIES), n_terms, candidates, generic, too_broad)
    assert "| b-codex-exec-sandbox | 唯讀沙箱 | 2 | 標題 |" in md
    assert "memory_search 5 次、切出 6 個詞（略過泛用詞 1 個" in md
    assert md.rstrip().endswith("：路徑（7）")
    empty = st.render_md(150, 0, 0, [], 0, {})
    assert "| （無） | | | |" in empty and "不當觸發詞" not in empty


if __name__ == "__main__":
    import subprocess  # 另開 pytest 行程：本檔已載入的 lib 模組不會跟著 conftest 隔離資料根
    rc = subprocess.call([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", __file__])
    print("SEARCH_TERMS_TO_TRIGGERS_CHECK " + ("PASS" if rc == 0 else "FAIL"))
    sys.exit(1 if rc else 0)
