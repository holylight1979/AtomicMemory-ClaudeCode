<#
console-window-trace.ps1 — Forensic 追蹤器：抓「可見 console 視窗」的出現/翻轉並記錄完整父鏈。

用途：根除 Windows 上來路不明的黑色 console 視窗。逐 tick 列舉所有 console-class 視窗，
偵測 (a) 新建可見窗 (b) 既有窗 隱藏→可見 的翻轉 → 記下時間、標題、owner、完整父行程鏈、命令列。

執行：pwsh -NoProfile -File console-window-trace.ps1 [-DurationSec 1800] [-PollMs 250]
停止：建立 stop flag 檔（見 $StopFlag）或等 DurationSec 到。
日誌：~/.claude/Logs/console-window-trace.log
#>
param(
  [int]$DurationSec = 1800,
  [int]$PollMs = 250,
  [string]$LogPath = "$HOME\.claude\Logs\console-window-trace.log",
  [string]$StopFlag = "$HOME\.claude\Logs\console-trace.stop"
)

New-Item -ItemType Directory -Force -Path (Split-Path $LogPath) | Out-Null
if (Test-Path $StopFlag) { Remove-Item $StopFlag -Force -ErrorAction SilentlyContinue }

$sig = @'
using System;using System.Text;using System.Collections.Generic;using System.Runtime.InteropServices;
public class CWT{
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
 delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] static extern int GetClassName(IntPtr h, StringBuilder s, int m);
 [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int m);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
 public struct R{public long hwnd;public string cls;public bool vis;public uint pid;public string title;}
 public static List<R> Go(){
  var res=new List<R>();
  EnumWindows((h,l)=>{
   var cn=new StringBuilder(256); GetClassName(h,cn,256); string c=cn.ToString();
   if(c.Contains("Console")||c.Contains("Pseudo")||c.Contains("CASCADIA")){
    var t=new StringBuilder(512); GetWindowText(h,t,512);
    uint q; GetWindowThreadProcessId(h,out q);
    res.Add(new R{hwnd=(long)h,cls=c,vis=IsWindowVisible(h),pid=(uint)q,title=t.ToString()});
   } return true;
  },IntPtr.Zero); return res;
 }
}
'@
Add-Type -TypeDefinition $sig -ReferencedAssemblies System.Runtime,System.Collections

function Get-Chain([int]$startPid){
  $parts=@(); $cur=$startPid; $guard=0
  while($cur -and $cur -ne 0 -and $guard -lt 6){
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue
    if(-not $p){ break }
    $parts += "$($p.Name)($cur)"
    $cur = [int]$p.ParentProcessId; $guard++
  }
  return ($parts -join ' <- ')
}

function Write-Log([string]$msg){
  $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss.fff')
  # 一律 LF（Add-Content 預設寫 CRLF）
  [IO.File]::AppendAllText($LogPath, "[$ts] $msg`n", [Text.UTF8Encoding]::new($false))
}

Write-Log "==================== TRACE START (dur=${DurationSec}s poll=${PollMs}ms pidSelf=$PID) ===================="
# baseline：記下起始所有 console 視窗（含隱藏），之後對照
$state = @{}
foreach($w in [CWT]::Go()){
  $state[$w.hwnd] = $w.vis
  $vtag = if($w.vis){'VISIBLE'}else{'hidden '}
  $pr = Get-CimInstance Win32_Process -Filter "ProcessId=$($w.pid)" -ErrorAction SilentlyContinue
  Write-Log ("  baseline {0} cls={1,-20} pid={2,-6} owner={3} :: {4}" -f $vtag,$w.cls,$w.pid,$pr.Name,$w.title)
}
Write-Log "-------------------- watching for NEW / hidden->VISIBLE transitions --------------------"

$deadline = (Get-Date).AddSeconds($DurationSec)
while((Get-Date) -lt $deadline){
  if(Test-Path $StopFlag){ Write-Log "STOP flag 命中，結束。"; break }
  Start-Sleep -Milliseconds $PollMs
  $cur = [CWT]::Go()
  $seen = @{}
  foreach($w in $cur){
    $seen[$w.hwnd] = $true
    $prev = $null
    if($state.ContainsKey($w.hwnd)){ $prev = $state[$w.hwnd] }
    # 觸發條件：此 hwnd 沒見過且可見  OR  之前隱藏現在可見
    if($w.vis -and ($prev -eq $null -or $prev -eq $false)){
      $pr = Get-CimInstance Win32_Process -Filter "ProcessId=$($w.pid)" -ErrorAction SilentlyContinue
      $kind = if($prev -eq $null){'NEW-WINDOW'}else{'HIDDEN->VISIBLE'}
      Write-Log "★ CAUGHT [$kind] hwnd=$($w.hwnd) class=$($w.cls)"
      Write-Log "    title = $($w.title)"
      Write-Log "    owner = $($pr.Name) (pid=$($w.pid))"
      Write-Log "    cmd   = $($pr.CommandLine)"
      Write-Log "    chain = $(Get-Chain ([int]$w.pid))"
    }
    $state[$w.hwnd] = $w.vis
  }
  # 清掉已消失的 hwnd（避免關閉再開誤判為 transition；下次重開算 NEW）
  foreach($k in @($state.Keys)){ if(-not $seen.ContainsKey($k)){ $state.Remove($k) } }
}
Write-Log "==================== TRACE END ===================="
