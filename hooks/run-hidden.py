#!/usr/bin/env pythonw
"""run-hidden.py — 通用隱窗 stdio 啟動器（Windows console host 視窗根除）。

問題：Windows 11「預設終端機=Windows Terminal」下，claude.exe（GUI subsystem、無 console）
spawn console-subsystem 子行程（node / cmd / uvx / python）且未帶 CREATE_NO_WINDOW 時，
Windows 會替它彈一個 `WindowsTerminal.exe -Embedding` host 視窗（標題=被托管 exe 路徑）。
stdio MCP server 因此每次啟動就閃一個黑窗。與 CC hook 無關（hook 已用 pythonw 解決 layer-1）。

修法：用本啟動器當中介——
  claude → pythonw run-hidden.py <real-exe> <args...>
pythonw 是 GUI subsystem（無 console）→ 不彈窗；再以 CREATE_NO_WINDOW 接力 spawn 真子行程。

關鍵坑：pythonw 下 Python 的 sys.stdin/stdout/stderr 皆為 None，且**裸繼承不會把 claude 餵進來的
MCP pipe 接力給子行程**（實測 stdin/stdout 雙向皆斷）。故必須顯式取 OS 標準handle
（GetStdHandle）再經 STARTUPINFO/STARTF_USESTDHANDLES 直接交給子行程 → 真透傳、免 byte pump。

與 run-bash-hidden.py 的差異：bash 走 python proxy（MSYS bash 讀不了原生 pipe）；node/python/cmd
等原生 console app 可直接吃這些 handle，故這裡用 STARTUPINFO 直傳即可，無需 pump 執行緒。

用法：pythonw run-hidden.py <command> [args...]
退出碼：透傳子行程退出碼；無參數 2；啟動失敗 127。
"""
from __future__ import annotations

import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000  # Windows-only


def _win_startupinfo():
    """取本行程 OS 標準handle，包成 STARTUPINFO 供子行程直接繼承（pythonw 下 sys.std* 為 None）。"""
    import ctypes

    STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE = -10, -11, -12
    k32 = ctypes.windll.kernel32
    k32.GetStdHandle.restype = ctypes.c_void_p

    INVALID = (None, 2 ** 64 - 1, 2 ** 32 - 1)

    def std(which):
        h = k32.GetStdHandle(which)
        return None if h in INVALID else h

    hin, hout, herr = std(STD_INPUT_HANDLE), std(STD_OUTPUT_HANDLE), std(STD_ERROR_HANDLE)
    si = subprocess.STARTUPINFO()
    if hin is not None and hout is not None:
        si.dwFlags |= subprocess.STARTF_USESTDHANDLES
        si.hStdInput = hin
        si.hStdOutput = hout
        si.hStdError = herr if herr is not None else hout
    return si


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("run-hidden.py: no command given\n")
        return 2

    kwargs = {"close_fds": False}
    if sys.platform == "win32":
        kwargs["startupinfo"] = _win_startupinfo()
        kwargs["creationflags"] = CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(sys.argv[1:], **kwargs)
    except FileNotFoundError as exc:
        sys.stderr.write(f"run-hidden.py: cannot launch {sys.argv[1]!r}: {exc}\n")
        return 127
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 130


if __name__ == "__main__":
    sys.exit(main())
