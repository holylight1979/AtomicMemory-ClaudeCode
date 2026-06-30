"""game_taxonomy.py — 使用者導向遊戲開發起手勢分類種子(seed lexicon)。

純資料 + render；不碰檔案系統、不寫索引、不寫詞庫。供：
  (a) draft batch-classify prompt 奠基（render_seed_for_prompt）
  (b) jury 後處理判 slug∈seed（seed_slugs）
  (c) 人快速增類 anchor（SEED_IS_OPEN：開放清單，非 allow-list）

與 lib/atom_locations.LOCAL_REALM_LEXICON 互補且**正交**：那是『實例專屬詞』
（realm 路由 = 軸3 詞庫學習面），本檔是『組織性分類軸』（folder placement = 軸1）。
兩者不同層、物理不可混寫（見 memory/_staging/next-phase-draft-taxonomy-engine.md §2 四軸分離）。
"""
from __future__ import annotations

from typing import NamedTuple


class Cat(NamedTuple):
    slug: str          # 資料夾安全段名(ASCII)，= _drafts/by-class/<slug>/ 與晉升後 _atoms/<slug>/
    name: str          # 人類可讀(中文)
    scope_hint: str    # 'project' | 'core' | 'both' — 給 LLM 的先驗，非硬規則
    sensitive: bool    # True → seed 級先驗；實際 sensitive 由 draft 級獨立旗標(只升不降)覆寫
    covers: str        # 一句話邊界 + 與鄰類切分


# 23 類（user 原始 14 + 補 9）。
# 註：slug 'Tooling'（非 'Toolchain'）——避撞 atom_locations 核心保護前綴 'toolchain'
#     （CI 不變式 seed_slugs() ∩ 保護前綴 = ∅，見 verify_taxonomy_caging）。
GAME_TAXONOMY_SEED = [
    Cat("Engineering", "程式/工程", "both", False, "客戶端/伺服端/引擎/gameplay 程式、架構、API、編譯、版控"),
    Cat("Design", "企劃/設計", "project", False, "系統設計/玩法/關卡/敘事/規格書/design doc，多綁特定 title"),
    Cat("Art", "美術", "project", False, "2D/3D/UI/動畫/特效/concept、美術規範、資產 pipeline 美術端"),
    Cat("Audio", "音效音樂", "project", False, "BGM/SFX/配音/Wwise/FMOD/混音，與美術不同職能不同工具鏈"),
    Cat("GameBalance", "數值與經濟平衡", "project", False, "數值表/掉落/戰鬥公式/經濟/付費點，建模法可重用→容 core"),
    Cat("PM", "PM/專案管理", "both", False, "排程/里程碑/風險/資源/會議決議/跨職能協調(非組織文化)"),
    Cat("QA", "QA/測試", "both", False, "測試計畫/bug repro/回歸/自動化測試/release 驗收，方法論可重用"),
    Cat("DevOps", "維運部署/DevOps", "both", False, "CI/CD/build pipeline/伺服器部署/監控/live ops 維運"),
    Cat("Security", "資安", "both", False, "弱點/防駭/加密/帳號安全/滲透/合規技術控制(技術主題,非治理屬性)"),
    Cat("Web", "網頁部", "both", False, "官網/活動頁/後台/CMS/前端框架/SEO，使用者既有分類保留"),
    Cat("Marketing", "行銷", "project", False, "宣傳/買量/素材/活動檔期/市場定位/KOL(拉新)"),
    Cat("Community", "客服與社群", "project", False, "客服/社群經營/輿情/Discord/論壇/玩家回饋(留存與服務)"),
    Cat("BizOps", "商業營運", "project", True, "營收/KPI/商業模式/發行合約/市場分析/商業決策，多含敏感數字"),
    Cat("Legal", "法務合規", "both", True, "授權/隱私GDPR個資/年齡分級/平台條款/合約審閱，罕見高風險"),
    Cat("Research", "研究與技術探索", "core", False, "新技術評估/原型/論文吸收/可行性/技術選型，探索性偏跨專案"),
    Cat("Tooling", "工具鏈", "core", False, "編輯器/引擎/外掛/腳本/CLI 實戰踩坑，對映核心 toolchain atom+local Tools"),
    Cat("OS", "作業系統/環境", "both", False, "OS/shell/WSL/檔案系統/環境變數/跨平台差異(遊戲專案目標平台側)"),
    Cat("Culture", "辦公室文化", "project", False, "團隊慣例/溝通風氣/流程約定/非正式知識，組織專屬"),
    Cat("CrossTeam", "跨單位合作", "project", False, "跨部門交接/介面約定/協作摩擦與解法/責任邊界"),
    Cat("WorkflowLog", "工作流紀實", "both", False, "做事過程流程紀錄/事件誌(非規則本身)，對映 workflow-*/episodic"),
    Cat("Personal", "個人", "project", True, "個人筆記/偏好/私人TODO，對映 V4 personal/{user} 層"),
    Cat("Permissions", "權限", "both", True, "存取控制/角色白名單/可見性規則(治理維度,非技術主題)"),
    Cat("Sensitive", "敏感", "both", True, "需管理職裁決高風險內容,對映 _pending_review 路由(治理維度,與主題正交)"),
]

SEED_IS_OPEN = True             # 開放清單非 allow-list：LLM 可提新類，須回 理由+scope_hint+sensitive
TAXONOMY_CATCHALL = "_Unsorted"  # 軸1 安全閥；遊戲側用 _Unsorted 區隔 realm 側 'Else'


def render_seed_for_prompt() -> str:
    """渲染 seed 成 prompt 奠基文字（供 batch-classify LLM 認知既有分類 + 提示如何增類）。"""
    lines = ["遊戲開發分類種子(可增補,新類須附理由+scope_hint+sensitive)："]
    for c in GAME_TAXONOMY_SEED:
        sens = " [敏感]" if c.sensitive else ""
        lines.append(f"- {c.slug}({c.name}){sens} «{c.scope_hint}» {c.covers}")
    return "\n".join(lines)


def seed_slugs() -> frozenset:
    return frozenset(c.slug for c in GAME_TAXONOMY_SEED)


def reserved_lexicon_seed() -> frozenset:
    """sink 端保留集：seed slug 整批併入 realm 詞庫保留集，防泛用職能詞污染 learned-lexicon
    （belt-and-suspenders，對應 INV-NO-LEXICON-WRITE）。"""
    return seed_slugs()
