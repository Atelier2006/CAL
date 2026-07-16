"""キャリアセンター相談予約システム 統合Flaskアプリ

html_20260708(Flask雛形) と login/(Google認証) を統合し、
作業指示書のコア(A/B/C-2/C-4/D-3 + アクセス制御)を実装したもの。

- 認証: 本番用 Google Identity Services(学生=学校ドメイン / 管理者=gmail) +
        オフライン検証用の DEVログイン を併設。
- データ: SQLite(career.db)。起動時に db.init_db() でシード。
"""
import os
import re
import functools
from datetime import date, datetime, timedelta

from flask import (Flask, render_template, request, jsonify, session,
                    redirect, url_for, flash)
from google.oauth2 import id_token
from google.auth.transport import requests        

import db
from db import SLOTS


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Google Cloud Console の Client ID（login.py より引き継ぎ）
CLIENT_ID = "925030125877-fm67bqs95umiksc4kgne98tpkhvakjtb.apps.googleusercontent.com"
SCHOOL_DOMAIN_RE = r"^[a-zA-Z]{2}\.stu\.tokyo-ec\.ac\.jp$"

db.init_db()


# ============================================================
# アクセス制御 (作業指示書 A-1 / E-1)
# ============================================================
def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **k):
        if "user" not in session:
            return redirect(url_for("index"))
        return view(*a, **k)
    return wrapped


def role_required(role):
    def deco(view):
        @functools.wraps(view)
        def wrapped(*a, **k):
            user = session.get("user")
            if not user:
                return redirect(url_for("index"))
            if user["role"] != role:
                return "権限がありません (403)", 403
            return view(*a, **k)
        return wrapped
    return deco


student_required = role_required("student")
admin_required = role_required("admin")


@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}


# ============================================================
# 予約業務ルール (作業指示書 D-3)
# ============================================================
def add_business_days(start, n):
    """start から営業日(月〜金)で n 日後を返す。"""
    d, added = start, 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def booking_window(conn):
    today = date.today()
    deadline_days = int(db.get_setting(conn, "deadline_days", "3"))
    open_days = int(db.get_setting(conn, "open_days", "30"))
    earliest = add_business_days(today, deadline_days)  # 営業日3日前まで
    latest = today + timedelta(days=open_days)
    return earliest, latest


def taken_slots(conn):
    """予約で埋まっている (date, slot) の集合(pending/confirmed)。"""
    rows = conn.execute(
        "SELECT date, slot FROM reservations WHERE status IN ('pending','confirmed')"
    ).fetchall()
    return {(r["date"], r["slot"]) for r in rows}


def student_dates(conn, student_id):
    """学生が既に予約(有効)を持つ日付集合。同日重複防止用。"""
    rows = conn.execute(
        "SELECT date FROM reservations WHERE student_id=? AND status IN ('pending','confirmed')",
        (student_id,),
    ).fetchall()
    return {r["date"] for r in rows}


def daily_count(conn, d):
    row = conn.execute(
        "SELECT COUNT(*) n FROM reservations WHERE date=? AND status IN ('pending','confirmed')",
        (d,),
    ).fetchone()
    return row["n"]


def can_book(conn, student_id, d_str, slot):
    """予約可否を (bool, 理由) で返す。"""
    try:
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        return False, "日付が不正です"
    if slot not in SLOTS:
        return False, "時限が不正です"
    if d.weekday() >= 5:
        return False, "休業日は予約できません"
    earliest, latest = booking_window(conn)
    if d < earliest:
        return False, "受付は営業日3日前までです"
    if d > latest:
        return False, "受付開始前の日付です"
    if (d_str, slot) in taken_slots(conn):
        return False, "その枠はすでに予約されています"
    if d_str in student_dates(conn, student_id):
        return False, "同じ日に複数の予約はできません"
    cap = int(db.get_setting(conn, "daily_cap", "20"))
    if daily_count(conn, d_str) >= cap:
        return False, "その日の予約上限に達しています"
    return True, ""


# ============================================================
# 認証ルート (A-1)
# ============================================================
# Google Cloud Console の Client ID
CLIENT_ID = "925030125877-fm67bqs95umiksc4kgne98tpkhvakjtb.apps.googleusercontent.com"


@app.route('/', methods=['GET'])
def index():
    return render_template('login.html')

@app.route('/admin-login', methods=['GET'])
def admin_login_page():
    # 管理者用ログイン画面を表示（URLを /admin-login に設定）
    return render_template('login2.html')

#生徒用
@app.route('/login', methods=['POST'])
def login():
    token = request.json.get('credential')
    if not token:
        return jsonify({"success": False, "message": "No token provided"}), 400

    try:
        # Google ID Token 検証
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            CLIENT_ID
        )

        #デバック用print
        # print("HD:", idinfo.get("hd"))
        # print("EMAIL:", idinfo.get("email"))

        # 学校ドメインのみ許可
        import re
        #○○.stu.tokyo-ec.ac.jpのみ許可
        pattern = r"^[a-zA-Z]{2}\.stu\.tokyo-ec\.ac\.jp$"
        hd = idinfo.get("hd", "")
        if not re.match(pattern, hd):
            return jsonify({
                "success": False,
                "message": "学校のGoogleアカウントでログインしてください。"
            }), 403


        # ユーザー情報取得
        user_name = idinfo.get("name")
        user_email = idinfo.get("email")
        user_picture = idinfo.get("picture")

        #取得した情報から分離
        import re

        # 期待するフォーマットの例を仮定しています：
        # user_email = "24ab1234@example.com" (先頭8文字がID、2-4文字目が部署)
        # user_name  = "B200 山田太郎" (1文字目が学年、5文字目以降が名前)

        # 1. メールアドレスからIDと学科（Department）を抽出
        # 先頭の英数字8文字をIDとし、そのうちの3〜4文字目をDepartmentとする場合
        if user_email:
            # @の前を取得
            local_part = user_email.split('@')[0]
            student_ID = local_part  # 完全にローカルパート＝IDの場合

            # 部署コードが「特定のアルファベット2文字」などの場合、正規表現で安全に抜く
            # 数字2桁＋アルファベット2桁＋数字4桁 の構成
            match_email = re.match(r'^\d{2}([a-zA-Z]{2})\d{4}', local_part)
            user_Department = match_email.group(1) if match_email else ""
        else:
            student_ID = ""
            user_Department = ""

        # 2. 名前から氏名を抽出
        if user_name:
            match_name = re.match(r'^.([0-9])..\s*(.*)$', user_name)
            if match_name:
                user_name_name = match_name.group(2)  # 「山田太郎」を取得
            else:
                # パターンにマッチしなかった場合のフォールバック
                user_name_name = user_name

        #学科判定**************************
        Dep = [
            "情報処理科2年制",
            "情報処理科3年制",
            "Webメディア科",
            "高度情報処理科",
            "セキュリティネットワーク科"]

        if user_Department == "aa":
            user_Department = Dep[0]
        elif user_Department == "ah":
            user_Department = Dep[1]
        elif user_Department == "ab":
            user_Department = Dep[2]
        elif user_Department == "ae":
            user_Department = Dep[3]
        elif user_Department == "af":
            user_Department = Dep[4]
        #**********************************

        #セッション（ブラウザごと）にデータを保存
        session['user_data'] = {
            '学籍番号': student_ID,
            '名前': user_name_name,
            '学科': user_Department
        }

        #'学年': user_grade
        #'email':user_email,

        #デバック用print
        print(session['user_data'])

        return jsonify({
            "success": True,
            "name": user_name,
            "email": user_email,
            "picture": user_picture
        })

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid token"
        }), 401


#管理者用
@app.route('/login2', methods=['POST'])
def login2():
    token = request.json.get('credential')
    if not token:
        return jsonify({"success": False, "message": "No token provided"}), 400

    # 管理者用（login2）内の修正
    try:
        # Google ID Token 検証
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            CLIENT_ID
        )

        user_email = idinfo.get("email", "")

        #末尾の文字列をチェック
        # if not user_email.endswith("@gmail.com"):
        #     return jsonify({
        #         "success": False,
        #         "message": "管理者用のGoogleアカウント（Gmail）でログインしてください。"
        #     }), 403

        # 特定のメールアドレスのみに絞る場合
        ALLOWED_ADMINS = ["itejol2020@gmail.com", "vice.principal@gmail.com"]
        if user_email not in ALLOWED_ADMINS:
            return jsonify({"success": False, "message": "権限がありません。"}), 403

        # ユーザー情報取得・セッション保存
        user_name = idinfo.get("name", "管理者")
        session['user_data'] = {
            '名前': user_name,
            'email': user_email,
            'role': 'admin' # 管理者フラグを立てておくと後で便利です
        }

        return jsonify({"success": True, "name": user_name, "email": user_email})

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid token"
        }), 401

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ============================================================
# 学生側 (B)
# ============================================================
@app.route("/user/home")
@student_required
def user_home():
    conn = db.get_db()
    uid = session["user"]["id"]
    ann = conn.execute(
        "SELECT * FROM announcements WHERE status='公開中' ORDER BY publish_date DESC LIMIT 3"
    ).fetchall()
    upcoming = conn.execute(
        "SELECT r.*, c.name cname FROM reservations r LEFT JOIN counselors c ON r.counselor_id=c.id"
        " WHERE r.student_id=? AND r.status='confirmed' AND r.date>=? ORDER BY r.date LIMIT 1",
        (uid, date.today().isoformat()),
    ).fetchone()
    pending = conn.execute(
        "SELECT r.*, c.name cname FROM reservations r LEFT JOIN counselors c ON r.counselor_id=c.id"
        " WHERE r.student_id=? AND r.status='pending' ORDER BY r.date",
        (uid,),
    ).fetchall()
    conn.close()
    return render_template("user/home.html", announcements=ann, upcoming=upcoming, pending=pending)


@app.route("/user/info")
@student_required
def user_info():
    q = request.args.get("q", "").strip()
    conn = db.get_db()
    sql = ("SELECT * FROM announcements WHERE status='公開中'"
           " AND (expiration_date IS NULL OR expiration_date>=?)")
    params = [date.today().isoformat()]
    if q:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY publish_date DESC"
    ann = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template("user/info.html", announcements=ann, q=q)


@app.route("/user/mypage")
@student_required
def user_mypage():
    conn = db.get_db()
    uid = session["user"]["id"]
    nxt = conn.execute(
        "SELECT r.*, c.name cname FROM reservations r LEFT JOIN counselors c ON r.counselor_id=c.id"
        " WHERE r.student_id=? AND r.status='confirmed' AND r.date>=? ORDER BY r.date LIMIT 1",
        (uid, date.today().isoformat()),
    ).fetchone()
    conn.close()
    return render_template("user/mypage.html", nxt=nxt)


@app.route("/user/check")
@student_required
def user_check():
    tab = request.args.get("tab", "all")
    q = request.args.get("q", "").strip()
    conn = db.get_db()
    uid = session["user"]["id"]
    rows = conn.execute(
        "SELECT r.*, c.name cname FROM reservations r LEFT JOIN counselors c ON r.counselor_id=c.id"
        " WHERE r.student_id=? ORDER BY r.date DESC",
        (uid,),
    ).fetchall()
    conn.close()
    today = date.today().isoformat()
    items = []
    for r in rows:
        d = dict(r)
        d["is_past"] = r["date"] < today
        items.append(d)

    def match(d):
        if q and q not in (d["content"] or "") and q not in (d["date"] or ""):
            return False
        if tab == "all":
            return True
        if tab == "past":
            return d["is_past"]
        if tab == "done":
            return d["status"] == "confirmed"
        if tab == "pending":
            return d["status"] == "pending"
        if tab == "cancel":
            return d["status"] in ("cancelled", "rejected")
        return True

    items = [d for d in items if match(d)]
    return render_template("user/check.html", items=items, tab=tab, q=q)


@app.route("/user/reserve_c")
@student_required
def user_reserve_c():
    """空き枠カレンダー(DB由来)。今後14日の営業日×4枠。"""
    conn = db.get_db()
    uid = session["user"]["id"]
    taken = taken_slots(conn)
    sdates = student_dates(conn, uid)
    earliest, latest = booking_window(conn)
    conn.close()
    wd = ["月", "火", "水", "木", "金", "土", "日"]
    rows = []
    d = date.today()
    count = 0
    while count < 10:
        if d.weekday() < 5:  # 営業日のみ
            cells = []
            for slot in SLOTS:
                ds = d.isoformat()
                ok = (earliest <= d <= latest) and (ds, slot) not in taken and ds not in sdates
                cells.append({"slot": slot, "available": ok, "date": ds})
            rows.append({"date": d, "label": f"{d.month}/{d.day}", "wd": wd[d.weekday()], "cells": cells})
            count += 1
        d += timedelta(days=1)
    return render_template("user/reserve_c.html", rows=rows, slots=SLOTS)


@app.route("/user/reserve_form", methods=["GET", "POST"])
@student_required
def user_reserve_form():
    conn = db.get_db()
    uid = session["user"]["id"]
    if request.method == "POST":
        d = request.form.get("date", "")
        slot = request.form.get("slot", "")
        rtype = request.form.get("purpose", "")
        content = request.form.get("content", "").strip()
        counselor_id = request.form.get("counselor_id") or None
        if rtype == "その他" and not content:
            flash("「その他」の場合は内容を入力してください")
            conn.close()
            return redirect(url_for("user_reserve_form", date=d, slot=slot))
        ok, reason = can_book(conn, uid, d, slot)
        if not ok:
            flash(reason)
            conn.close()
            return redirect(url_for("user_reserve_c"))
        conn.execute(
            "INSERT INTO reservations(student_id,counselor_id,date,slot,rtype,content,status,created_at)"
            " VALUES (?,?,?,?,?,?, 'pending', ?)",
            (uid, counselor_id, d, slot, rtype, content or rtype, date.today().isoformat()),
        )
        conn.commit()
        conn.close()
        flash("予約を申請しました。承認をお待ちください。")
        return redirect(url_for("user_check", tab="pending"))
    # GET
    sel_date = request.args.get("date", "")
    sel_slot = request.args.get("slot", "")
    counselors = conn.execute(
        "SELECT * FROM counselors WHERE status='対応中' ORDER BY id"
    ).fetchall()
    conn.close()
    return render_template("user/reserve_form.html", sel_date=sel_date, sel_slot=sel_slot,
                           counselors=counselors)


@app.route("/user/reserve/<int:rid>/cancel", methods=["POST"])
@student_required
def user_cancel(rid):
    conn = db.get_db()
    uid = session["user"]["id"]
    conn.execute(
        "UPDATE reservations SET status='cancelled' WHERE id=? AND student_id=?",
        (rid, uid),
    )
    conn.commit()
    conn.close()
    flash("予約をキャンセルしました。")
    return redirect(url_for("user_check"))


# ============================================================
# 管理者側 (C)
# ============================================================
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = db.get_db()

    def cnt(where, *p):
        return conn.execute(f"SELECT COUNT(*) n FROM reservations WHERE {where}", p).fetchone()["n"]

    stats = {
        "total": cnt("1=1"),
        "confirmed": cnt("status='confirmed'"),
        "pending": cnt("status='pending'"),
        "cancelled": cnt("status IN ('cancelled','rejected')"),
        "announcements": conn.execute(
            "SELECT COUNT(*) n FROM announcements WHERE status='公開中'").fetchone()["n"],
    }
    reservations = conn.execute(
        "SELECT r.*, u.name sname, c.name cname FROM reservations r"
        " LEFT JOIN users u ON r.student_id=u.user_id"
        " LEFT JOIN counselors c ON r.counselor_id=c.id"
        " ORDER BY r.date DESC LIMIT 10"
    ).fetchall()
    ann = conn.execute(
        "SELECT * FROM announcements WHERE status='公開中' ORDER BY publish_date DESC LIMIT 3"
    ).fetchall()
    conn.close()
    return render_template("admin/dashboard.html", stats=stats, reservations=reservations,
                           announcements=ann)


@app.route("/admin/reservation")
@admin_required
def admin_reservation():
    conn = db.get_db()
    rows = conn.execute(
        "SELECT r.*, u.name sname, u.department sdept, c.name cname FROM reservations r"
        " LEFT JOIN users u ON r.student_id=u.user_id"
        " LEFT JOIN counselors c ON r.counselor_id=c.id"
        " WHERE r.status IN ('pending','confirmed') ORDER BY r.date, r.slot"
    ).fetchall()
    conn.close()
    return render_template("admin/reservation.html", reservations=rows, slots=SLOTS)


@app.route("/admin/reservation/<int:rid>/approve", methods=["POST"])
@admin_required
def admin_approve(rid):
    location = request.form.get("location", "").strip()
    if not location:
        flash("承認には場所(部屋)の入力が必須です")  # §6-1
        return redirect(url_for("admin_reservation"))
    conn = db.get_db()
    conn.execute("UPDATE reservations SET status='confirmed', location=? WHERE id=?", (location, rid))
    conn.commit()
    conn.close()
    flash("予約を承認しました。")
    return redirect(url_for("admin_reservation"))


@app.route("/admin/reservation/<int:rid>/reject", methods=["POST"])
@admin_required
def admin_reject(rid):
    conn = db.get_db()
    conn.execute("UPDATE reservations SET status='rejected' WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    flash("予約を却下しました。")
    return redirect(url_for("admin_reservation"))


@app.route("/admin/notice")
@admin_required
def admin_notice():
    conn = db.get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM announcements ORDER BY publish_date DESC")]
    conn.close()
    return render_template("admin/notice.html", announcements=rows)


@app.route("/admin/notice/save", methods=["POST"])
@admin_required
def admin_notice_save():
    conn = db.get_db()
    nid = request.form.get("id")
    vals = (request.form.get("title", "").strip(), request.form.get("content", "").strip(),
            request.form.get("category", "その他"), request.form.get("publish_date") or date.today().isoformat(),
            request.form.get("expiration_date") or None, request.form.get("status", "公開中"))
    if nid:
        conn.execute("UPDATE announcements SET title=?,content=?,category=?,publish_date=?,"
                     "expiration_date=?,status=? WHERE id=?", (*vals, nid))
    else:
        conn.execute("INSERT INTO announcements(title,content,category,publish_date,expiration_date,status)"
                     " VALUES (?,?,?,?,?,?)", vals)
    conn.commit()
    conn.close()
    flash("お知らせを保存しました。")
    return redirect(url_for("admin_notice"))


@app.route("/admin/notice/<int:nid>/delete", methods=["POST"])
@admin_required
def admin_notice_delete(nid):
    conn = db.get_db()
    conn.execute("DELETE FROM announcements WHERE id=?", (nid,))
    conn.commit()
    conn.close()
    flash("お知らせを削除しました。")
    return redirect(url_for("admin_notice"))


@app.route("/admin/staff")
@admin_required
def admin_staff():
    conn = db.get_db()
    counselors = [dict(r) for r in conn.execute("SELECT * FROM counselors ORDER BY id")]
    # 本日予約数を相談員ごとに集計
    today = date.today().isoformat()
    today_counts = {}
    for r in conn.execute(
        "SELECT counselor_id, COUNT(*) n FROM reservations"
        " WHERE date=? AND status IN ('pending','confirmed') GROUP BY counselor_id", (today,)):
        today_counts[r["counselor_id"]] = r["n"]
    stats = {
        "total": len(counselors),
        "active": sum(1 for c in counselors if c["status"] == "対応中"),
        "today": conn.execute(
            "SELECT COUNT(*) n FROM reservations WHERE date=? AND status IN ('pending','confirmed')",
            (today,)).fetchone()["n"],
        "paused": sum(1 for c in counselors if c["status"] == "休止中"),
    }
    conn.close()
    return render_template("admin/staff.html", counselors=counselors, stats=stats,
                           today_counts=today_counts)


@app.route("/admin/staff/save", methods=["POST"])
@admin_required
def admin_staff_save():
    conn = db.get_db()
    cid = request.form.get("id", "").strip()
    vals = (request.form.get("name", "").strip(), request.form.get("field", "").strip(),
            request.form.get("work_days", "").strip(), request.form.get("email", "").strip(),
            request.form.get("tel", "").strip(), request.form.get("status", "対応中"))
    exists = conn.execute("SELECT 1 FROM counselors WHERE id=?", (cid,)).fetchone()
    if exists:
        conn.execute("UPDATE counselors SET name=?,field=?,work_days=?,email=?,tel=?,status=? WHERE id=?",
                     (*vals, cid))
    else:
        if not cid:
            n = conn.execute("SELECT COUNT(*) n FROM counselors").fetchone()["n"]
            cid = f"C-2026-{n+1:03d}"
        conn.execute("INSERT INTO counselors(id,name,field,work_days,email,tel,status)"
                     " VALUES (?,?,?,?,?,?,?)", (cid, *vals))
    conn.commit()
    conn.close()
    flash("相談員情報を保存しました。")
    return redirect(url_for("admin_staff"))


@app.route("/admin/setting")
@admin_required
def admin_setting():
    conn = db.get_db()
    s = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
    conn.close()
    return render_template("admin/setting.html", s=s)


@app.route("/admin/setting/save", methods=["POST"])
@admin_required
def admin_setting_save():
    conn = db.get_db()
    for key in ["open_days", "deadline_days", "daily_cap", "center_name", "center_email", "center_tel"]:
        if key in request.form:
            conn.execute("UPDATE settings SET value=? WHERE key=?", (request.form[key], key))
    # トグルは存在すれば1
    for key in ["mail_notify", "remind_notify"]:
        conn.execute("UPDATE settings SET value=? WHERE key=?",
                     ("1" if request.form.get(key) else "0", key))
    conn.commit()
    conn.close()
    flash("設定を保存しました。")
    return redirect(url_for("admin_setting"))


if __name__ == "__main__":
    app.run(debug=True)
