from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests
import os,re

app = Flask(__name__)

# セッションを使用するための秘密鍵（推測されにくい文字列）
app.secret_key = os.urandom(24)
# session を使用するためにシークレットキー
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key_here')

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
        print("HD:", idinfo.get("hd"))
        print("EMAIL:", idinfo.get("email"))

        # 学校ドメインのみ許可
        import re

        pattern = r"^[a-zA-Z]{2}\.stu\.tokyo-ec\.ac\.jp$"
        hd = idinfo.get("hd", "")
        if not re.match(pattern, hd):
            return jsonify({
                "success": False,
                "message": "学校のGoogleアカウントでログインしてください。"
            }), 403

        Department = ["2年制", "3年制", "Webメディア科", "高度情報処理科", "セキュリティネットワーク科"]
        # ユーザー情報取得
        students = []
        user_name = idinfo.get("name")
        user_email = idinfo.get("email")
        user_picture = idinfo.get("picture")
        user_ID = user_email[:8] if user_email else ""
        user_grade = user_name[1:2]
        user_name_name = user_name[4:]
        user_Department = user_email[2:4]
        if user_Department == "aa":
            user_Department = Department[0]
        elif user_Department == "ah":
            user_Department = Department[1]
        elif user_Department == "ab":
            user_Department = Department[2]
        elif user_Department == "ae":
            user_Department = Department[3]
        elif user_Department == "af":
            user_Department = Department[4]

        # students[0] = (user_ID,user_name,user_email,user_Department,user_grade)

        # グローバル変数ではなく、セッション（ブラウザごと）にデータを保存
        session['user_data'] = {
            '学籍番号': user_ID,
            '名前': user_name_name,
            'email':user_email,
            '学科': user_Department,
            '学年': user_grade
        }

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

    try:
        # Google ID Token 検証
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            CLIENT_ID
        )
        print("HD:", idinfo.get("hd"))
        print("EMAIL:", idinfo.get("email"))

        # 学校ドメインのみ許可
        import re

        pattern = r"^gmail\.com$"
        user_email = idinfo.get("email", "")

        if not user_email.endswith("@gmail.com"):
            return jsonify({
            "success": False,
            "message": "管理者用のGoogleアカウントでログインしてください。"
            }), 403


        # ユーザー情報取得
        user_name = idinfo.get("name")
        user_name_name = user_name[0:]

        # グローバル変数ではなく、セッション（ブラウザごと）にデータを保存
        session['user_data'] = {
            '名前': user_name_name,
            'email':user_email,
        }

        return jsonify({
            "success": True,
            "name": user_name,
            "email": user_email,
        })

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid token"
        }), 401

if __name__ == "__main__":
    app.run(debug=True)
