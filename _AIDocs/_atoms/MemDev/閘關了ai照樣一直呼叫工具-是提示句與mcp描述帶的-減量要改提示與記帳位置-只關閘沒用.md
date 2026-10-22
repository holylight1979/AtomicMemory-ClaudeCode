# 閘關了AI照樣一直呼叫工具-是提示句與MCP描述帶的-減量要改提示與記帳位置-只關閘沒用

- Scope: global
- Author: holylight
- Source: track-cost-cut 001 交付（a322b3e1）
- Confidence: [臨]
- Trigger: goal_gate, need_goal update, 提示句, MCP 描述, 減量, token 消耗, 關閘沒用
- Created-at: 2026-10-22

## 知識

- [臨] live 的 reconcile_gate.goal_gate=false，目標樹那兩道檢查本來就不擋；但 AI 每跑仍呼叫 need_goal 約 10.5 次（update×3、reconcile×4 等），是注入的提示句與 MCP 工具描述帶的。要減這塊消耗，改提示句與記帳位置（進度由程式記），只關閘沒用。

## 行動

- 量到某工具呼叫多→先查它是被擋出來的還是被提示帶出來的
