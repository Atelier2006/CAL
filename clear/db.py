"""DB接続・初期化・シード・共通ヘルパ。
起動時に career.db が無ければ schema.sql を流し、ダミーデータを投入する。
(作業指示書 A-3 / E-3 のデータ名寄せ)
"""
import os
import sqlite3
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "career.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

SLOTS = ["午前", "昼", "午後", "放課後"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _iso(d):
    return d.isoformat()


def init_db(force=False):
    """DBが無ければ（またはforce時は）作成しシードする。"""
    if os.path.exists(DB_PATH) and not force:
        return
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_db()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    _seed(conn)
    conn.commit()
    conn.close()


def _seed(conn):
    today = date.today()
    c = conn.cursor()

    # --- users（管理者 + 学生。名寄せ済み）---
    users = [
        ("admin",     "キャリアセンター管理者", "career@tokyo-ec.ac.jp", "-", "-", "admin"),
        ("24AH9999", "東京 電子",  "ah24tokyo@ah.stu.tokyo-ec.ac.jp",   "情報処理科3年制", "3", "student"),
        ("24AH1001", "山田 太郎",  "ah24yamada@ah.stu.tokyo-ec.ac.jp",  "情報処理科3年制", "2", "student"),
        ("24AB1003", "佐藤 裕子",  "ab24sato@ab.stu.tokyo-ec.ac.jp",    "Webメディア科",   "3", "student"),
        ("24AE1004", "高橋 健太",  "ae24takahashi@ae.stu.tokyo-ec.ac.jp","高度情報処理科",  "1", "student"),
    ]
    c.executemany(
        "INSERT INTO users(user_id,name,email,department,grade,role) VALUES (?,?,?,?,?,?)",
        users,
    )

    # --- counselors ---
    counselors = [
        ("C-2026-001", "鈴木 一郎", "就職相談",   "月・水・金", "suzuki@career.ac.jp",  "03-1234-5678", "対応中"),
        ("C-2026-002", "田中 花子", "履歴書添削", "火・木",     "tanaka@career.ac.jp",  "03-1234-5679", "対応中"),
        ("C-2026-003", "佐藤 健一", "面接対策",   "月・火・金", "sato@career.ac.jp",    "03-1234-5680", "対応中"),
        ("C-2026-004", "山本 美咲", "自己分析",   "水・木",     "yamamoto@career.ac.jp","03-1234-5681", "休止中"),
        ("C-2026-005", "中村 翔",   "業界研究",   "月・金",     "nakamura@career.ac.jp","03-1234-5682", "対応中"),
    ]
    c.executemany(
        "INSERT INTO counselors(id,name,field,work_days,email,tel,status) VALUES (?,?,?,?,?,?,?)",
        counselors,
    )

    # --- reservations（過去・確定・申請中を混在）---
    def d(offset):
        return _iso(today + timedelta(days=offset))

    reservations = [
        # 過去（履歴用）
        ("24AH9999", "C-2026-001", d(-14), "午後", "相談", "就職相談（個別）", "2号館13階", "confirmed"),
        ("24AH9999", "C-2026-002", d(-5),  "昼",   "添削", "履歴書添削",       "2号館6階",  "cancelled"),
        # 確定済み（今後）
        ("24AH9999", "C-2026-001", d(5),  "午後", "相談", "就職相談（個別）", "2号館13階", "confirmed"),
        ("24AB1003", "C-2026-003", d(6),  "昼",   "面接", "模擬面接",         "2号館6階",  "confirmed"),
        # 申請中（管理者の承認待ち）
        ("24AH9999", "C-2026-002", d(7),  "午前", "添削", "履歴書添削",       None,        "pending"),
        ("24AE1004", "C-2026-005", d(8),  "放課後","相談", "業界研究相談",     None,        "pending"),
    ]
    for r in reservations:
        c.execute(
            "INSERT INTO reservations(student_id,counselor_id,date,slot,rtype,content,location,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (*r, _iso(today)),
        )

    # --- announcements ---
    ann = [
        ("ゴールデンウィーク期間中の開室時間について",
         "GW期間中、キャリアセンター窓口は完全閉室となります。証明書発行等はお早めに。",
         "重要", d(-30), d(30), "公開中"),
        ("履歴書・エントリーシートの添削について",
         "添削は事前予約制です。予約管理からお申し込みください。",
         "その他", d(-20), d(40), "公開中"),
        ("利用者アンケートご協力のお願い",
         "より良いサービス提供のため、アンケートにご協力ください。",
         "その他", d(-10), d(20), "公開中"),
        ("自己分析セミナーの開催について",
         "自己分析セミナーを開催予定です。詳細は追ってお知らせします。",
         "イベント", d(-2), d(30), "下書き"),
        ("4月の就職相談予約を開始しました",
         "今年度の就職相談予約を開始しました。",
         "重要", d(-90), d(-60), "終了"),
    ]
    c.executemany(
        "INSERT INTO announcements(title,content,category,publish_date,expiration_date,status)"
        " VALUES (?,?,?,?,?,?)",
        ann,
    )

    # --- inquiries ---
    c.execute(
        "INSERT INTO inquiries(student_id,question_text,answer_text,response_status,created_at)"
        " VALUES (?,?,?,?,?)",
        ("24AH9999", "OB訪問の相談も予約できますか？", "はい、就職相談枠でご相談いただけます。", "answered", _iso(today)),
    )
    c.execute(
        "INSERT INTO inquiries(student_id,question_text,answer_text,response_status,created_at)"
        " VALUES (?,?,?,?,?)",
        ("24AB1003", "予約のキャンセルはいつまで可能ですか？", None, "waiting", _iso(today)),
    )

    # --- settings（予約ロジックと共有）---
    settings = [
        ("open_days", "30"),      # 何日前から受付開始
        ("deadline_days", "3"),   # 営業日3日前まで (§D-3)
        ("daily_cap", "20"),      # 1日の上限件数
        ("center_name", "東京電子大学 キャリアセンター"),
        ("center_email", "career@tokyo-ec.ac.jp"),
        ("center_tel", "03-1234-5678"),
        ("mail_notify", "0"),     # 通知はフェーズ2（準備中）
        ("remind_notify", "0"),
    ]
    c.executemany("INSERT INTO settings(key,value) VALUES (?,?)", settings)


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default
