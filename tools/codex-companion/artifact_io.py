"""artifact_io.py — 檔案類 artifact 內容實體化（送審輸入組成的規則唯一來源）。

統一原則（凡組給 codex 審查的輸入皆適用）：
1. 引用檔案類 artifact（plan / handoff / diff）必附**實體內容**；
   「工具動作紀錄」不得替代「內容本體」——解析不到 artifact 時明說或直接
   skip 該次審計，不拿 trace 摘要冒充正文。
2. 超長內容採**頭尾採樣**並附 in-band 標記：全文字數、採樣範圍、
   「勿把採樣截斷誤判為文件本身截斷/斷鏈」警語。靜默截斷會讓忠實的
   審查者把輸入殘缺誤報成文件缺陷（可觀測性鐵律：降級必浮出訊號）。
3. 集合類截斷（trace 只取最近 N 條等）附計數標頭 showing last N of M。

採樣預算由 caller 依 artifact 角色決定：主審對象（如 plan_review 的計畫檔）
給大預算，佐證背景（如 handoff）給標準預算。
"""
from __future__ import annotations

from pathlib import Path


def sample_text(text: str, head: int = 4500, tail: int = 1500) -> str:
    """超長文字取頭 head + 尾 tail 字，中段以明確標記省略。

    保尾段的理由：授權/收尾/驗證段常在文末，純頭部截斷會誘發
    「缺收尾段」誤報（handoff 誤報實案的根因之一）。
    """
    if len(text) <= head + tail:
        return text
    return (
        text[:head]
        + f"\n\n…（中段省略：全文共 {len(text)} 字，此處僅含開頭 {head} 字與結尾 {tail} 字；"
        f"審查時勿把此採樣截斷誤判為文件本身截斷/斷鏈）…\n\n"
        + text[-tail:]
    )


def read_artifact_sampled(path: str, head: int = 4500, tail: int = 1500) -> str:
    """讀 artifact 檔全文（utf-8-sig 容 BOM）並經 sample_text 採樣；讀檔失敗回 ''。

    caller 須對空字串給 in-band 說明（「讀取失敗、無正文可依據」），
    不得無聲改拿其他材料替代。
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    return sample_text(text, head=head, tail=tail)
