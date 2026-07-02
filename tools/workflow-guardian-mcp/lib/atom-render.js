// atom-render.js — atom 內容構造/渲染/驗證（py 鏡像：lib/atom_spec.py，須 byte-identical）。
// server.js re-export buildAtomContent/renderKnowledgeLines/isBlockKnowledge（verify_atom_io_equivalence test_13）。

/** Build atom file content from structured parameters.
 *  V4: scopeLabel may be plain "shared"/"global" or composite "role:art"/"personal:alice".
 *  Optional metadata (audience/author/pending_review_by/merge_strategy/created_at)
 *  written only when present, in SPEC §4 order. */
function isBlockKnowledge(item) {
  // 表格列（| 開頭）或程式碼 fence（三反引號開頭）→ 原樣輸出 block。對拍 atom_spec.py
  const s = item.replace(/^\s+/, "");
  return s.startsWith("|") || s.startsWith("```");
}

function renderKnowledgeLines(knowledge) {
  // block-aware 渲染 ## 知識 區行清單。對拍 lib/atom_spec.py:render_knowledge_lines（須 byte-identical）
  const out = [];
  for (const k of knowledge) {
    if (isBlockKnowledge(k)) {
      if (out.length && out[out.length - 1] !== "") out.push("");
      out.push(...k.split("\n"));
      out.push("");
    } else {
      out.push(k.startsWith("- ") ? k : `- ${k}`);
    }
  }
  while (out.length && out[out.length - 1] === "") out.pop();
  return out;
}

function buildAtomContent({
  title,
  scope,
  confidence,
  triggers,
  knowledge,
  actions,
  related,
  audience,
  author,
  pendingReviewBy,
  mergeStrategy,
  createdAt,
  today,
}) {
  const _today = today || new Date().toISOString().slice(0, 10);
  const lines = [`# ${title}`, ""];
  lines.push(`- Scope: ${scope}`);
  if (audience && audience.length > 0) {
    lines.push(`- Audience: ${audience.join(", ")}`);
  }
  if (author) {
    lines.push(`- Author: ${author}`);
  }
  lines.push(`- Confidence: ${confidence}`);
  lines.push(`- Trigger: ${triggers.join(", ")}`);
  // Last-used / Confirmations / ReadHits 居 <atom>.access.json，不寫入 .md
  if (pendingReviewBy) {
    lines.push(`- Pending-review-by: ${pendingReviewBy}`);
  }
  if (mergeStrategy && mergeStrategy !== "ai-assist") {
    lines.push(`- Merge-strategy: ${mergeStrategy}`);
  }
  lines.push(`- Created-at: ${createdAt || _today}`);
  if (related && related.length > 0) {
    lines.push(`- Related: ${related.join(", ")}`);
  }
  lines.push("", "## 知識", "");
  for (const line of renderKnowledgeLines(knowledge)) {
    lines.push(line);
  }
  lines.push("", "## 行動", "");
  if (actions && actions.length > 0) {
    for (const a of actions) {
      lines.push(a.startsWith("- ") ? a : `- ${a}`);
    }
  } else {
    lines.push("- （依知識內容判斷）");
  }
  lines.push("");
  return lines.join("\n");
}

/** Validate atom content structure. Returns null if valid, error string if invalid. */
function validateAtomContent(content) {
  if (content.includes("---\n") && content.indexOf("---\n") < 5) {
    return "YAML frontmatter (---) is forbidden in atom files";
  }
  if (!content.match(/^# .+/m)) {
    return "Missing # title heading";
  }
  if (!content.includes("## 知識")) {
    return "Missing ## 知識 section";
  }
  if (!content.includes("## 行動")) {
    return "Missing ## 行動 section";
  }
  const confMatch = content.match(/^- Confidence:\s*(.+)$/m);
  if (!confMatch || !["[固]", "[觀]", "[臨]"].includes(confMatch[1].trim())) {
    return "Missing or invalid Confidence metadata";
  }
  return null;
}

module.exports = { isBlockKnowledge, renderKnowledgeLines, buildAtomContent, validateAtomContent };
