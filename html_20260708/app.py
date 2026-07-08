from flask import Flask, render_template

app = Flask(__name__)

# --- 学生用ページ ---
@app.route('/')
def index():
    return render_template('user/home.html')

@app.route('/user/home')
def user_home():
    return render_template('user/home.html')

@app.route('/user/info')
def user_info():
    return render_template('user/info.html')

@app.route('/user/mypage')
def user_mypage():
    return render_template('user/mypage.html')

# --- キャリアセンター用ページ ---
@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/check')
def admin_check():
    return render_template('admin/check.html')

@app.route('/admin/notice')
def admin_notice():
    return render_template('admin/notice.html')

@app.route('/admin/reservation')
def admin_reservation():
    return render_template('admin/reservation.html')

@app.route('/admin/reserve_c')
def admin_reserve_c():
    return render_template('admin/reserve_c.html')

@app.route('/admin/reserve_form')
def admin_reserve_form():
    return render_template('admin/reserve_form.html')

@app.route('/admin/setting')
def admin_setting():
    return render_template('admin/setting.html')

@app.route('/admin/staff')
def admin_staff():
    return render_template('admin/staff.html')

if __name__ == '__main__':
    app.run(debug=True)