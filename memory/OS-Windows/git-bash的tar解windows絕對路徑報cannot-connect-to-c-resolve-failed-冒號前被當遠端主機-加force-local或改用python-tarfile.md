# git-bash的tar解windows絕對路徑報cannot-connect-to-c-resolve-failed-冒號前被當遠端主機-加force-local或改用python-tarfile

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: tar -xf, tar --force-local, Cannot connect to C, resolve failed, Git Bash tar, tarfile, 解壓 Windows 絕對路徑
- Created-at: 2026-10-27
- Related: 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-回放樹放repo外-並行工作樹時不用stash
- Source: session:17c8cd5c 2026-10-27

## 知識

- [臨] Git Bash 的 GNU tar 把 `C:/…` 冒號前那段當成遠端主機（host:path 寫法），`tar -xf C:/x/a.tar` 報「Cannot connect to C: resolve failed」。
- [臨] 解法：加 `--force-local`；或用相對路徑；或改用 Python `tarfile.open(p).extractall(dst, filter='data')`，直接吃 Windows 絕對路徑。

## 行動

- Windows 上在 Git Bash 跑 tar 一律帶 --force-local，或改用 Python tarfile
