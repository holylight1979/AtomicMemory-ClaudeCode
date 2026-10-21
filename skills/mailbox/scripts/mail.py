#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mail — 共用信箱：寄信、收信、解鎖、刪信、總覽（跨專案／跨人員溝通，誰的 AI 都能用）。

設定層：從目前目錄往上找第一個含 .claude 的資料夾（專案根）；它的 .claude/skills/mailbox/config.json 存在就整層用它
（信箱路徑與 .local 帳號都讀寫那層），否則用本 skill 自己的資料夾。config 子命令會印出用的是哪一層。
信箱根目錄＝設定層 config.json 的 mailbox_root（全員共用、進版控；路徑改了只改這裡）。
環境變數 MAILBOX_ROOT 可臨時覆蓋（測試用）。
身分＝記在設定層 .local/mailbox.json 的帳號（沒記錄時印 [需要帳號] 並以 exit 4 結束：問使用者後用 config --account 記下；
環境變數 MAILBOX_USER 可臨時覆蓋）。收件資料夾＝帳號名；project＝不指定對象、誰都能處理，使用者明講「專案」才用。

用法：
  python mail.py config [--account 帳號] [--log-keep-days 天數]   看設定／記下自己的帳號／改紀錄保留天數
  python mail.py roster [--add 帳號 簡稱 ...] [--drop 簡稱] [--drop-account 帳號]  名單：簡稱對帳號（不認得的收件者印 [不認得收件者]、exit 5）
  python mail.py check                                    連線與讀寫權限自測（第一次用先跑）
  python mail.py init                                     信箱資料夾被刪掉時重建骨架（信件與名單簡稱救不回）
  python mail.py list [--to 收件者 ...] [--all]            列信；預設＝只看自己的未讀（--to project、--to me project）
  python mail.py read <編號>                               讀信；未讀的信同時搬進 _archive（＝領取）
  python mail.py send --body-file 內文.md [--to 收件者 ...] [--subject 標題] [--re 編號] [--attach 檔案 ...]
  python mail.py unlock <編號> [<編號> ...] [--to 收件者]   已讀的信退回未讀；多人信要用 --to 指定哪一位
  python mail.py delete <編號> [<編號> ...] [--to 收件者] [--yes]   刪信；不加 --to＝整封收回，不加 --yes 只預覽
  python mail.py overview [--to 收件者] [--status unread|read]   全部信件總覽，並重產 Overview.md

一封信一個編號；寄給多人時每位收件者各一份副本、各自已讀。編號寫 M0012、12、#12 都可以。內文檔第一行是「# 標題」且沒給 --subject 時，就拿它當標題。
回信：send --re <編號>，收件者預設回給原寄件人、標題預設「Re: 原標題」。
各子命令細節：python mail.py <子命令> --help
"""
import argparse
import datetime
import getpass
import json
import os
import re
import shutil
import sys

for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_DIR = None                                                  # main() 選定設定層後填入
SETTINGS_LAYER = None                                                # 「專案層」或「skill 自帶」
CONFIG_FILE = None                                                   # 全員共用：信箱路徑
ACCOUNT_FILE = None                                                  # 每台電腦自己的帳號，不進版控
ROOT = None                                                          # main() 讀設定後填入
LOG_KEEP_DAYS = None                                                 # main() 讀設定後填入
PUBLIC_BOX = "project"
PUBLIC_BOX_ALIASES = {"專案"}
SELF_ALIASES = {"me", "我", "自己"}
RESERVED_NAMES = PUBLIC_BOX_ALIASES | SELF_ALIASES | {PUBLIC_BOX}
NEED_ACCOUNT_EXIT = 4
UNKNOWN_RECIPIENT_EXIT = 5
ARCHIVE_DIR = "_archive"
IDS_DIR = "_ids"
LOG_DIR = "_log"                                                     # 動作紀錄：一天一檔 YYYY-MM-DD.txt
LOG_KEEP_DAYS_DEFAULT = 30
LOG_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.txt$")
ROSTER_FILE = "_roster.json"                                         # 名單：帳號→簡稱，全員共用
OVERVIEW_FILE = "Overview.md"
STATUS_TITLE = "## 狀態紀錄"
SUBJECT_FILENAME_MAX = 40
ID_ALLOCATE_TRIES = 50

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
MAIL_FILE_RE = re.compile(r"^(\d{8}-\d{6})_M(\d+)_(.+)\.md$")
ID_FILE_RE = re.compile(r"^M(\d+)$")
ID_ARG_RE = re.compile(r"^[#Mm]?0*(\d+)$")
HEADER_RE = re.compile(r"^- (編號|寄件人|收件者|時間|回覆|附件)：(.*)$")
# 底線是檔名欄位分隔，標題裡的底線也換掉
FILENAME_FORBIDDEN_RE = re.compile(r'[\\/:*?"<>|\r\n\t_]+')


def fail(message):
    print(f"[錯誤] {message}", file=sys.stderr)
    sys.exit(1)


def warn(message):
    print(f"[警告] {message}", file=sys.stderr)


def now():
    return datetime.datetime.now()


def stamp_text(moment):
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def fmt_id(mail_id):
    return f"M{mail_id:04d}"


def parse_id(text):
    match = ID_ARG_RE.match(text.strip())
    if not match:
        fail(f"看不懂的信件編號：{text}（寫 M0012、12 或 #12）")
    return int(match.group(1))


def clean_name(name):
    normalized = name.strip().lower().replace("_", "-")
    if not NAME_RE.match(normalized):
        fail(f"收件者／帳號名只能用英數、點、減號：{name}")
    return normalized


def resolve_box(name):
    """--to 的值：「專案」＝project、「me／我／自己」＝自己、名單上的帳號或簡稱、已有收件資料夾的帳號；其餘停下來問。"""
    stripped = name.strip()
    if stripped in PUBLIC_BOX_ALIASES or stripped.lower() == PUBLIC_BOX:
        return PUBLIC_BOX
    if stripped.lower() in SELF_ALIASES:
        return me()
    account = lookup_roster(load_roster(), stripped)
    if account:
        return clean_name(account)                                   # 名單檔在共用資料夾、可能被手改：帳號不合規就停，不變成信箱外的路徑
    candidate = stripped.lower().replace("_", "-")
    if NAME_RE.match(candidate) and os.path.isdir(box_dir(candidate)):
        return candidate
    print(f"[不認得收件者] 「{stripped}」不在名單裡。請問使用者這是誰、信箱帳號是什麼", file=sys.stderr)
    print("問到後記下來：python mail.py roster --add <帳號> <簡稱>（只有帳號沒有簡稱也可以）", file=sys.stderr)
    sys.exit(UNKNOWN_RECIPIENT_EXIT)


def find_settings_dir():
    """回傳 (設定資料夾, 層名)。同名 skill 個人層會蓋過專案層，所以全域這份也要先認專案層的設定。"""
    folder = os.getcwd()
    while not os.path.isdir(os.path.join(folder, ".claude")):
        parent = os.path.dirname(folder)
        if parent == folder:
            return SKILL_DIR, "skill 自帶"
        folder = parent
    candidate = os.path.join(folder, ".claude", "skills", "mailbox")
    is_self = os.path.normcase(os.path.realpath(candidate)) == os.path.normcase(os.path.realpath(SKILL_DIR))
    if is_self or not os.path.isfile(os.path.join(candidate, "config.json")):
        return SKILL_DIR, "skill 自帶"
    return candidate, "專案層"


def load_config():
    """回傳 (信箱根目錄, 紀錄保留天數)；根目錄可被環境變數 MAILBOX_ROOT 覆蓋。"""
    try:
        with open(CONFIG_FILE, encoding="utf-8-sig") as handle:
            config = json.load(handle)
    except (OSError, ValueError) as error:
        fail(f"讀不到信箱設定 {CONFIG_FILE}：{error}")
    root = os.environ.get("MAILBOX_ROOT") or config.get("mailbox_root")
    if not root:
        fail(f"{CONFIG_FILE} 沒有填 mailbox_root：第一次用先填上共用資料夾路徑（全員同一個）")
    keep_days = config.get("log_keep_days", LOG_KEEP_DAYS_DEFAULT)
    if not isinstance(keep_days, int) or keep_days < 1:
        fail(f"{CONFIG_FILE} 的 log_keep_days 要是 ≥1 的整數：{keep_days}")
    return root, keep_days


def load_account():
    if not os.path.isfile(ACCOUNT_FILE):
        return None
    try:
        with open(ACCOUNT_FILE, encoding="utf-8") as handle:
            return json.load(handle).get("account")
    except (OSError, ValueError) as error:
        warn(f"帳號記錄檔讀不到（{ACCOUNT_FILE}）：{error}")
        return None


def me():
    override = os.environ.get("MAILBOX_USER")
    if override:
        return clean_name(override)
    account = load_account()
    if account:
        return clean_name(account)
    suggestion = getpass.getuser().strip().lower().replace("_", "-")
    print(f"[需要帳號] 還不知道你的信箱帳號（＝你的收件資料夾名）。請問使用者，建議值：{suggestion}", file=sys.stderr)
    print("問到後記下來：python mail.py config --account <帳號>", file=sys.stderr)
    sys.exit(NEED_ACCOUNT_EXIT)


_roster_cache = None


def load_roster():
    """名單＝{帳號: [簡稱, ...]}，放在信箱根目錄，所有人共用。"""
    global _roster_cache
    if _roster_cache is not None:
        return _roster_cache
    path = os.path.join(ROOT, ROSTER_FILE)
    if not os.path.isfile(path):
        _roster_cache = {}
        return _roster_cache
    try:
        with open(path, encoding="utf-8-sig") as handle:
            _roster_cache = json.load(handle)
    except (OSError, ValueError) as error:
        fail(f"名單檔讀不到或格式壞了（{path}）：{error}")
    return _roster_cache


def save_roster(roster):
    global _roster_cache
    write_text_atomic(os.path.join(ROOT, ROSTER_FILE),
                      json.dumps(roster, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _roster_cache = roster


def lookup_roster(roster, name):
    lowered = name.strip().lower()
    for account, nicknames in roster.items():
        if lowered == account or lowered in (nickname.lower() for nickname in nicknames):
            return account
    return None


def display_name(account):
    nicknames = load_roster().get(account) or []
    return f"{account}（{'、'.join(nicknames)}）" if nicknames else account


def box_dir(box):
    return os.path.join(ROOT, box)


def archive_dir(box):
    return os.path.join(ROOT, box, ARCHIVE_DIR)


def require_root():
    if os.path.isdir(ROOT):
        return
    if os.path.isdir(os.path.dirname(ROOT.rstrip("\\/"))):
        fail(f"信箱資料夾不存在：{ROOT}（上一層連得到：可能被刪了，或 config.json 路徑打錯）；"
             "跟使用者確認路徑沒錯後跑 python mail.py init 重建")
    fail(f"連不上信箱：{ROOT}（網路磁碟／VPN 有連上嗎？）")


def list_boxes():
    names = []
    for name in os.listdir(ROOT):
        if name.startswith(("_", ".")):
            continue
        if os.path.isdir(os.path.join(ROOT, name)):
            names.append(name)
    return sorted(names)


def write_text_atomic(path, text):
    temp_path = f"{path}.tmp-{os.getpid()}"
    with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temp_path, path)


class Mail:
    """一封信＝收件資料夾（或其 _archive）裡的一個 .md；附件在同名資料夾。"""

    def __init__(self, box, archived, file_name):
        match = MAIL_FILE_RE.match(file_name)
        self.box = box
        self.archived = archived
        self.file_name = file_name
        self.id = int(match.group(2))
        folder = archive_dir(box) if archived else box_dir(box)
        self.path = os.path.join(folder, file_name)
        self.attach_dir = self.path[:-3]
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        with open(self.path, encoding="utf-8-sig") as handle:
            self._text = handle.read()
        lines = self._text.splitlines()
        first = lines[0] if lines else ""
        self._subject = first[2:].strip() if first.startswith("# ") else "（無標題）"
        self._fields = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            match = HEADER_RE.match(line)
            if match:
                self._fields[match.group(1)] = match.group(2).strip()
        self._statuses = []
        if STATUS_TITLE in lines:
            status_start = len(lines) - lines[::-1].index(STATUS_TITLE)
            self._statuses = [line[2:] for line in lines[status_start:] if line.startswith("- ")]
        self._loaded = True

    @property
    def text(self):
        self._load()
        return self._text

    @property
    def subject(self):
        self._load()
        return self._subject

    def field(self, name):
        self._load()
        return self._fields.get(name, "-")

    @property
    def last_status(self):
        self._load()
        return self._statuses[-1] if self._statuses else "-"

    @property
    def status_label(self):
        if not self.archived:
            return "未讀"
        return f"已讀（{self.last_status}）"

    def attachments(self):
        if not os.path.isdir(self.attach_dir):
            return []
        return sorted(os.listdir(self.attach_dir))


def scan(only_box=None):
    mails = []
    for box in list_boxes():
        if only_box and box != only_box:
            continue
        for archived, folder in ((False, box_dir(box)), (True, archive_dir(box))):
            if os.path.isdir(folder):
                mails += [Mail(box, archived, name) for name in os.listdir(folder) if MAIL_FILE_RE.match(name)]
    mails.sort(key=lambda mail: mail.id)
    return mails


def find_copies(mail_id, only_box=None):
    """同一個編號＝同一封信；寄給幾個人就有幾份副本，各在各的收件資料夾、各有各的已讀狀態。"""
    copies = [mail for mail in scan(only_box) if mail.id == mail_id]
    if not copies:
        where = f"（收件者 {only_box}）" if only_box else ""
        fail(f"找不到 {fmt_id(mail_id)}{where}（可能已被刪除；用 overview 看全部）")
    return copies


def append_status(path, text):
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"- {stamp_text(now())} {text}\n")


def move(mail, to_archive):
    """搬進／搬出 _archive。同一台主機內的改名只會有一個人成功，所以搬檔本身就是領取鎖。"""
    target_folder = archive_dir(mail.box) if to_archive else box_dir(mail.box)
    os.makedirs(target_folder, exist_ok=True)
    target = os.path.join(target_folder, mail.file_name)
    os.rename(mail.path, target)
    if os.path.isdir(mail.attach_dir):
        os.rename(mail.attach_dir, target[:-3])
    return Mail(mail.box, to_archive, mail.file_name)


def log_action(action, mail_id, box, detail):
    mail_label = fmt_id(mail_id) if mail_id is not None else "-"
    line = "\t".join([stamp_text(now()), me(), action, mail_label, box, detail])
    log_folder = os.path.join(ROOT, LOG_DIR)
    try:
        os.makedirs(log_folder, exist_ok=True)
        with open(os.path.join(log_folder, f"{now():%Y-%m-%d}.txt"), "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    except OSError as error:
        warn(f"動作紀錄沒寫進去（{log_folder}）：{error}")
        return
    prune_logs(log_folder)


def prune_logs(log_folder):
    """刪掉超過 log_keep_days 的整天紀錄檔；一天一檔不必重寫檔案，多人同時寫也不會吃掉別人的行。"""
    cutoff = f"{now() - datetime.timedelta(days=LOG_KEEP_DAYS):%Y-%m-%d}"
    for name in os.listdir(log_folder):
        match = LOG_FILE_RE.match(name)
        if not match or match.group(1) > cutoff:
            continue
        try:
            os.remove(os.path.join(log_folder, name))
        except FileNotFoundError:
            continue
        except OSError as error:
            warn(f"過期紀錄 {name} 刪不掉：{error}")


def allocate_id():
    ids_folder = os.path.join(ROOT, IDS_DIR)
    os.makedirs(ids_folder, exist_ok=True)
    used = [int(match.group(1)) for match in map(ID_FILE_RE.match, os.listdir(ids_folder)) if match]
    # _ids 被清掉時還有現存信件撐住最大編號，新信不會跟舊信撞號
    used += [mail.id for mail in scan()]
    candidate = max(used, default=0) + 1
    for _ in range(ID_ALLOCATE_TRIES):
        try:
            handle = os.open(os.path.join(ids_folder, fmt_id(candidate)), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(handle)
            return candidate
        except FileExistsError:
            candidate += 1
    fail(f"配不到信件編號（{ids_folder} 連續 {ID_ALLOCATE_TRIES} 個都被佔）")


def mail_line(mail):
    attach_count = len(mail.attachments())
    attach_mark = f" [附件 {attach_count}]" if attach_count else ""
    sent_at = mail.field("時間")[:16]
    state = f"  ← {mail.status_label}" if mail.archived else ""
    return f"  {fmt_id(mail.id)}  {sent_at}  {display_name(mail.field('寄件人')):<12} {mail.subject}{attach_mark}{state}"


def build_overview(mails):
    out = [
        "# MailBox 總覽",
        "",
        f"> 由 `mail.py` 自動產生，勿手改。產生時間：{stamp_text(now())}",
        "",
        "| 收件者 | 未讀 | 已讀 |",
        "|---|---|---|",
    ]
    boxes = list_boxes()
    for box in boxes:
        unread = sum(1 for mail in mails if mail.box == box and not mail.archived)
        read = sum(1 for mail in mails if mail.box == box and mail.archived)
        out.append(f"| {display_name(box)} | {unread} | {read} |")
    for box in boxes:
        box_mails = [mail for mail in mails if mail.box == box]
        out += ["", f"## {display_name(box)}", ""]
        if not box_mails:
            out.append("（沒有信）")
            continue
        out += ["| 編號 | 時間 | 寄件人 | 標題 | 狀態 | 附件 | 回覆 |", "|---|---|---|---|---|---|---|"]
        for mail in box_mails:
            subject = mail.subject.replace("|", "／")
            attach_count = len(mail.attachments()) or "-"
            out.append(
                f"| {fmt_id(mail.id)} | {mail.field('時間')} | {display_name(mail.field('寄件人'))} | {subject}"
                f" | {mail.status_label} | {attach_count} | {mail.field('回覆')} |"
            )
    return "\n".join(out) + "\n"


def refresh_overview():
    try:
        write_text_atomic(os.path.join(ROOT, OVERVIEW_FILE), build_overview(scan()))
    except OSError as error:
        warn(f"{OVERVIEW_FILE} 沒更新：{error}（下次任何動作或 overview 會重產）")


def cmd_check(args):
    user = me()
    print(f"身分：{user}")
    print(f"信箱：{ROOT}")
    require_root()
    own_box = box_dir(user)
    if not os.path.isdir(own_box):
        os.makedirs(own_box)
        print(f"已建立你的收件資料夾：{own_box}")
    ping_path = os.path.join(own_box, f".ping_{user}.txt")
    try:
        with open(ping_path, "w", encoding="utf-8") as handle:
            handle.write("ping")
        with open(ping_path, encoding="utf-8") as handle:
            readable = handle.read() == "ping"
        os.remove(ping_path)
    except OSError as error:
        fail(f"讀寫測試失敗：{error}")
    if not readable:
        fail(f"讀寫測試失敗：{ping_path} 讀回內容不對")
    unread = sum(1 for mail in scan(user) if not mail.archived)
    print("讀寫測試：建檔／讀回／刪除都成功")
    print(f"收件者：{', '.join(list_boxes())}")
    print(f"你的未讀：{unread} 封")
    return 0


def cmd_init(args):
    """信箱被整個刪掉時重建骨架；信件與名單簡稱救不回（共用資料夾通常不備份），名單靠之後「不認得就問」補回。"""
    user = me()
    if os.path.isdir(ROOT):
        print(f"信箱已存在：{ROOT}")
    else:
        parent = os.path.dirname(ROOT.rstrip("\\/"))
        if not os.path.isdir(parent):
            fail(f"連不上信箱的上一層：{parent}（網路磁碟／VPN 有連上嗎？）；不會往上建資料夾")
        os.mkdir(ROOT)
        print(f"[已重建] {ROOT}")
    for box in (PUBLIC_BOX, user):
        if not os.path.isdir(box_dir(box)):
            os.makedirs(box_dir(box))
            print(f"  建立收件資料夾 {box}")
    roster = load_roster()
    if user not in roster:
        roster[user] = []
        save_roster(roster)
    log_action("init", None, "-", ROOT)
    refresh_overview()
    print("骨架就緒；其他收件者資料夾會在寄信時自動建立")
    return 0


def cmd_config(args):
    if args.account:
        account = clean_name(args.account)
        os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
        with open(ACCOUNT_FILE, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"account": account}, handle, ensure_ascii=False)
            handle.write("\n")
        print(f"已記下帳號：{account}（{ACCOUNT_FILE}）")
        if not os.path.isdir(ROOT):
            warn(f"連不上信箱 {ROOT}，帳號只記在本機；連得上後跑 check")
            return 0
        roster = load_roster()
        if account not in roster:
            roster[account] = []
            save_roster(roster)
            log_action("roster-add", None, account, "-")
        if account not in list_boxes():
            print(f"信箱裡還沒有 {account} 資料夾（現有：{', '.join(list_boxes()) or '無'}）；"
                  "名字沒打錯就跑 check 建立，打錯就重新 --account")
        return 0
    if args.log_keep_days is not None:
        if args.log_keep_days < 1:
            fail(f"保留天數要 ≥1：{args.log_keep_days}")
        with open(CONFIG_FILE, encoding="utf-8-sig") as handle:
            config = json.load(handle)
        config["log_keep_days"] = args.log_keep_days
        write_text_atomic(CONFIG_FILE, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
        print(f"動作紀錄保留改成 {args.log_keep_days} 天（{CONFIG_FILE}）；這是全員共用設定，進版控後別人才生效")
        return 0
    account_source = "環境變數 MAILBOX_USER" if os.environ.get("MAILBOX_USER") else ACCOUNT_FILE
    root_source = "環境變數 MAILBOX_ROOT" if os.environ.get("MAILBOX_ROOT") else CONFIG_FILE
    print(f"設定層：{SETTINGS_LAYER}（{SETTINGS_DIR}）")
    print(f"帳號：{me()}（來源：{account_source}）")
    print(f"信箱：{ROOT}（來源：{root_source}）")
    print(f"動作紀錄保留：{LOG_KEEP_DAYS} 天（{CONFIG_FILE} 的 log_keep_days）")
    return 0


def cmd_roster(args):
    require_root()
    if args.add or args.drop or args.drop_account:
        me()                                                         # 動作紀錄要記是誰改的：沒帳號就在改名單之前停
    roster = load_roster()
    if args.add:
        account = clean_name(args.add[0])
        nicknames = [name.strip() for name in args.add[1:] if name.strip()]
        for nickname in nicknames:
            if nickname.lower() in RESERVED_NAMES:
                fail(f"「{nickname}」是保留字（專案／自己用），不能當簡稱")
            owner = lookup_roster(roster, nickname)
            if owner and owner != account:
                fail(f"「{nickname}」已經對到 {owner}；確定要改先 roster --drop {nickname}")
        known = roster.setdefault(account, [])
        added = [nickname for nickname in nicknames if nickname not in known]
        known.extend(added)
        save_roster(roster)
        log_action("roster-add", None, account, "、".join(added) or "-")
        print(f"[已記錄] {display_name(account)}")
        return 0
    if args.drop:
        owner = next((account for account, names in roster.items() if args.drop in names), None)
        if not owner:
            fail(f"名單裡沒有簡稱「{args.drop}」（帳號本身不能 drop）")
        roster[owner].remove(args.drop)
        save_roster(roster)
        log_action("roster-drop", None, owner, args.drop)
        print(f"[已移除] {args.drop}；{display_name(owner)}")
        return 0
    if args.drop_account:
        account = clean_name(args.drop_account)
        if account not in roster:
            fail(f"名單裡沒有帳號「{account}」")
        if os.path.isdir(box_dir(account)):
            fail(f"帳號 {account} 已有收件資料夾（有人寄過信），不能從名單移除；只要改簡稱用 --drop／--add")
        if account == me():
            fail(f"{account} 是本機自己的帳號，不能從名單移除")
        nicknames = "、".join(roster.pop(account)) or "-"
        save_roster(roster)
        log_action("roster-drop-account", None, account, nicknames)
        print(f"[已移除帳號] {account}（簡稱：{nicknames}）")
        return 0
    boxes =[box for box in list_boxes() if box != PUBLIC_BOX]
    for account in sorted(set(roster) | set(boxes)):
        nicknames = "、".join(roster.get(account) or []) or "-"
        note = "" if account in roster else "  ← 有收件資料夾但不在名單"
        print(f"  {account:<14} {nicknames}{note}")
    print(f"名單檔：{os.path.join(ROOT, ROSTER_FILE)}")
    return 0


def cmd_list(args):
    require_root()
    targets = list(dict.fromkeys(resolve_box(name) for name in args.to)) if args.to else [me()]
    mails = scan()
    shown = []
    for box in targets:
        print(f"[{display_name(box)}]")
        if not os.path.isdir(box_dir(box)):
            print("  （沒有這個收件資料夾＝還沒人寄過）")
            continue
        box_mails = [mail for mail in mails if mail.box == box and (args.all or not mail.archived)]
        if not box_mails:
            print("  （沒有未讀）" if not args.all else "  （沒有信）")
        for mail in box_mails:
            print(mail_line(mail))
        shown += box_mails
    unread = [mail for mail in shown if not mail.archived]
    print(f"共 {len(unread)} 封未讀")
    if len(unread) == 1:
        print(f"只有一封，直接讀：python mail.py read {fmt_id(unread[0].id)}")
    return 0


def print_mail(mail):
    print(f"--- {fmt_id(mail.id)} 原文（{mail.path}）---")
    print(mail.text.rstrip("\n"))
    print("--- 原文結束 ---")
    for name in mail.attachments():
        print(f"附件：{os.path.join(mail.attach_dir, name)}")


def cmd_read(args):
    require_root()
    user = me()
    copies = find_copies(parse_id(args.id))
    own = [mail for mail in copies if mail.box == user] or [mail for mail in copies if mail.box == PUBLIC_BOX]
    if not own:
        mail = copies[0]
        print(f"（這封寄給 {mail.field('收件者')}，沒有寄給你或 project：只顯示，不領取）")
        print_mail(mail)
        return 0
    mail = own[0]
    if mail.archived:
        print(f"（這封已讀：{mail.last_status}；以下為封存內容，狀態不變）")
        print_mail(mail)
        return 0
    try:
        mail = move(mail, True)
    except FileNotFoundError:
        mail = find_copies(mail.id, mail.box)[0]
        print(f"（{fmt_id(mail.id)} 剛被別人搶先領走；以下只顯示，誰領的看最後的狀態紀錄）")
        print_mail(mail)
        return 0
    append_status(mail.path, f"已讀（{user}）")
    log_action("read", mail.id, mail.box, mail.subject)
    refresh_overview()
    print(f"[已領取] {fmt_id(mail.id)} 已搬進 {mail.box}/{ARCHIVE_DIR}；"
          f"要退回未讀：python mail.py unlock {fmt_id(mail.id)} --to {mail.box}")
    print_mail(mail)
    return 0


def read_body(path):
    if not os.path.isfile(path):
        fail(f"找不到內文檔：{path}")
    with open(path, encoding="utf-8-sig") as handle:
        body = handle.read().replace("\r\n", "\n")
    lines = body.split("\n")
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).strip("\n")
    return None, body.strip("\n")


def cmd_send(args):
    require_root()
    sender = me()
    original = find_copies(parse_id(args.re))[0] if args.re else None
    body_subject, body = read_body(args.body_file)
    if args.to:
        recipients = list(dict.fromkeys(resolve_box(name) for name in args.to))
    elif original:
        recipients = [clean_name(original.field("寄件人"))]
    else:
        fail("要給 --to 收件者（回信 --re 時可省略，預設回給原寄件人）")
    subject = (args.subject or body_subject or (f"Re: {original.subject}" if original else "")).strip()
    subject = " ".join(subject.split())
    if not subject:
        fail("沒有標題：給 --subject，或把內文檔第一行寫成「# 標題」")
    attach_paths = args.attach or []
    attach_names = [os.path.basename(path) for path in attach_paths]
    missing = [path for path in attach_paths if not os.path.isfile(path)]
    if missing:
        fail(f"找不到附件：{', '.join(missing)}")
    if len(set(attach_names)) != len(attach_names):
        fail(f"附件檔名重複：{', '.join(attach_names)}")

    for recipient in recipients:
        if not os.path.isdir(box_dir(recipient)):
            existing = list_boxes()
            os.makedirs(box_dir(recipient))
            print(f"[新收件者] 已建立資料夾 {recipient}（原有：{', '.join(existing) or '無'}）")

    mail_id = allocate_id()
    sent_at = now()
    filename_subject = FILENAME_FORBIDDEN_RE.sub("-", subject)[:SUBJECT_FILENAME_MAX].strip(" .-") or "無標題"
    stem = f"{sent_at.strftime('%Y%m%d-%H%M%S')}_{fmt_id(mail_id)}_{sender}_{filename_subject}"
    reply_text = f"{fmt_id(original.id)}（{original.subject}）" if original else "-"
    content = "\n".join([
        f"# {subject}",
        "",
        f"- 編號：{fmt_id(mail_id)}",
        f"- 寄件人：{sender}",
        f"- 收件者：{', '.join(recipients)}",
        f"- 時間：{stamp_text(sent_at)}",
        f"- 回覆：{reply_text}",
        f"- 附件：{', '.join(attach_names) or '-'}",
        "",
        "---",
        "",
        body,
        "",
        "---",
        "",
        STATUS_TITLE,
        "",
        f"- {stamp_text(sent_at)} 寄出（{sender}）",
        "",
    ])
    for recipient in recipients:
        if attach_paths:
            attach_folder = os.path.join(box_dir(recipient), stem)
            os.makedirs(attach_folder)
            for path in attach_paths:
                shutil.copy2(path, attach_folder)
        mail_path = os.path.join(box_dir(recipient), f"{stem}.md")
        write_text_atomic(mail_path, content)
        log_action("send", mail_id, recipient, subject)
        print(f"檔案：{mail_path}")
    refresh_overview()
    print(f"[已寄出] {fmt_id(mail_id)} → {'、'.join(display_name(recipient) for recipient in recipients)}：{subject}")
    if len(recipients) > 1:
        print("每位收件者各一份副本、各自已讀；解鎖或刪除某一位的那份要加 --to <收件者>")
    return 0


def cmd_unlock(args):
    require_root()
    user = me()
    only_box = resolve_box(args.to) if args.to else None
    for text in args.ids:
        mail_id = parse_id(text)
        archived = [mail for mail in find_copies(mail_id, only_box) if mail.archived]
        if not archived:
            print(f"{fmt_id(mail_id)} 沒有已讀的副本，略過")
            continue
        if len(archived) > 1:
            readers = "、".join(display_name(mail.box) for mail in archived)
            print(f"{fmt_id(mail_id)} 有 {len(archived)} 位收件者已讀（{readers}）：加 --to <收件者> 指定解鎖哪一位，略過")
            continue
        mail = archived[0]
        try:
            mail = move(mail, False)
        except FileNotFoundError:
            warn(f"{fmt_id(mail.id)} 狀態剛被別人改過，略過；用 overview 看現況")
            continue
        append_status(mail.path, f"解鎖，退回未讀（{user}）")
        log_action("unlock", mail.id, mail.box, mail.subject)
        print(f"[已解鎖] {fmt_id(mail.id)} 退回 {mail.box} 收件匣：{mail.subject}")
    refresh_overview()
    return 0


def cmd_delete(args):
    require_root()
    me()                                                             # 動作紀錄要記是誰刪的：沒帳號就在預覽時停，不要刪到一半才停
    only_box = resolve_box(args.to) if args.to else None
    mails = []
    for text in args.ids:
        mails += find_copies(parse_id(text), only_box)
    if not args.yes:
        scope = f"只刪 {display_name(only_box)} 那份" if only_box else "整封收回：所有收件者的副本都刪"
        print(f"預覽（還沒刪；{scope}）：")
        for mail in mails:
            print(f"  {fmt_id(mail.id)}  {mail.box}  {mail.status_label}  {mail.subject}")
            print(f"      {mail.path}")
            for name in mail.attachments():
                print(f"      附件 {name}")
        print("共用資料夾通常不備份，刪了救不回來；確定要刪就加 --yes 重跑")
        return 0
    for mail in mails:
        subject = mail.subject
        os.remove(mail.path)
        if os.path.isdir(mail.attach_dir):
            shutil.rmtree(mail.attach_dir)
        log_action("delete", mail.id, mail.box, subject)
        print(f"[已刪除] {fmt_id(mail.id)}  {mail.box}  {subject}")
    refresh_overview()
    return 0


def cmd_overview(args):
    require_root()
    mails = scan()
    refresh_overview()
    only_box = resolve_box(args.to) if args.to else None
    shown = [mail for mail in mails if not only_box or mail.box == only_box]
    if args.status == "unread":
        shown = [mail for mail in shown if not mail.archived]
    elif args.status == "read":
        shown = [mail for mail in shown if mail.archived]
    for box in list_boxes():
        if only_box and box != only_box:
            continue
        box_mails = [mail for mail in shown if mail.box == box]
        unread = sum(1 for mail in mails if mail.box == box and not mail.archived)
        read = sum(1 for mail in mails if mail.box == box and mail.archived)
        print(f"[{display_name(box)}] 未讀 {unread}／已讀 {read}")
        for mail in box_mails:
            print(f"{mail_line(mail)}{'' if mail.archived else '  ← 未讀'}")
    print(f"總覽檔：{os.path.join(ROOT, OVERVIEW_FILE)}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mail.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    config_parser = sub.add_parser("config", help="看帳號與信箱路徑；--account 記下自己的帳號")
    config_parser.add_argument("--account", help="記下自己的信箱帳號（寫進 .local/mailbox.json）")
    config_parser.add_argument("--log-keep-days", type=int, help="動作紀錄保留天數（寫進 config.json，全員共用）")
    config_parser.set_defaults(func=cmd_config)

    roster_parser = sub.add_parser("roster", help="名單：簡稱對帳號；不加參數＝列出")
    roster_parser.add_argument("--add", nargs="+", metavar="帳號 簡稱", help="記下帳號與簡稱（簡稱可多個、可省略）")
    roster_parser.add_argument("--drop", metavar="簡稱", help="移除一個簡稱")
    roster_parser.add_argument("--drop-account", metavar="帳號", help="整筆移除記錯的帳號（已有收件資料夾或是自己的帳號時拒絕）")
    roster_parser.set_defaults(func=cmd_roster)

    sub.add_parser("check", help="連線與讀寫權限自測").set_defaults(func=cmd_check)
    sub.add_parser("init", help="信箱資料夾被刪掉時重建骨架（只往下建一層）").set_defaults(func=cmd_init)

    list_parser = sub.add_parser("list", help="列信（預設只看自己的未讀）")
    list_parser.add_argument("--to", nargs="+", help="看哪些收件者：帳號、project（或「專案」）、me（或「我」）")
    list_parser.add_argument("--all", action="store_true", help="連已讀（_archive）一起列")
    list_parser.set_defaults(func=cmd_list)

    read_parser = sub.add_parser("read", help="讀信；未讀的信會被領取（搬進 _archive）")
    read_parser.add_argument("id", help="信件編號")
    read_parser.set_defaults(func=cmd_read)

    send_parser = sub.add_parser("send", help="寄信")
    send_parser.add_argument("--body-file", required=True, help="內文 .md（UTF-8）；第一行「# 標題」可當標題")
    send_parser.add_argument("--to", nargs="+", help="收件者（可多位）：帳號、簡稱、project（或「專案」）；沒有資料夾會自動建")
    send_parser.add_argument("--subject", help="標題；省略時用內文第一行「# 標題」")
    send_parser.add_argument("--re", help="回覆哪封（編號）；收件者、標題可省略")
    send_parser.add_argument("--attach", nargs="+", help="附件檔案路徑（可多個）")
    send_parser.set_defaults(func=cmd_send)

    unlock_parser = sub.add_parser("unlock", help="已讀的信退回未讀")
    unlock_parser.add_argument("ids", nargs="+", help="信件編號（可多個）")
    unlock_parser.add_argument("--to", help="只解鎖這位收件者的那份（多人信必填）")
    unlock_parser.set_defaults(func=cmd_unlock)

    delete_parser = sub.add_parser("delete", help="刪信；不加 --yes 只預覽")
    delete_parser.add_argument("ids", nargs="+", help="信件編號（可多個）")
    delete_parser.add_argument("--to", help="只刪這位收件者的那份；不給＝整封收回")
    delete_parser.add_argument("--yes", action="store_true", help="真的刪除")
    delete_parser.set_defaults(func=cmd_delete)

    overview_parser = sub.add_parser("overview", help="全部信件總覽，並重產 Overview.md")
    overview_parser.add_argument("--to", help="只看這個收件者")
    overview_parser.add_argument("--status", choices=["unread", "read"], help="只看未讀或已讀")
    overview_parser.set_defaults(func=cmd_overview)
    return parser


def main():
    global SETTINGS_DIR, SETTINGS_LAYER, CONFIG_FILE, ACCOUNT_FILE, ROOT, LOG_KEEP_DAYS
    args = build_parser().parse_args()
    SETTINGS_DIR, SETTINGS_LAYER = find_settings_dir()
    CONFIG_FILE = os.path.join(SETTINGS_DIR, "config.json")
    ACCOUNT_FILE = os.path.join(SETTINGS_DIR, ".local", "mailbox.json")
    ROOT, LOG_KEEP_DAYS = load_config()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
