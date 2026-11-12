import os
import re
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///drinkhelper.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 20款指定飲料與價格
DRINKS_MENU = [
    {"name": "青檸烏龍", "price": 45},
    {"name": "桂花青茶", "price": 35},
    {"name": "四季春茶", "price": 30},
    {"name": "冷泡金萱", "price": 40},
    {"name": "鮮橙綠茶", "price": 55},
    {"name": "多多綠", "price": 50},
    {"name": "葡萄柚綠", "price": 55},
    {"name": "荔枝烏龍", "price": 50},
    {"name": "金桔檸檬", "price": 45},
    {"name": "百香果綠", "price": 50},
    {"name": "蜂蜜檸檬", "price": 45},
    {"name": "水蜜桃青茶", "price": 50},
    {"name": "芒果綠茶", "price": 55},
    {"name": "鳳梨青茶", "price": 50},
    {"name": "梅子綠茶", "price": 45},
    {"name": "草莓果茶", "price": 55},
    {"name": "黑糖鮮奶", "price": 60},
    {"name": "焦糖奶茶", "price": 55},
    {"name": "芋頭鮮奶", "price": 65},
    {"name": "珍珠奶茶", "price": 50}
]

# 固定 20 組唯一糖冰推薦矩陣 (對應 5 種甜度 × 4 種冰塊 = 20 款飲料)
RECOMMENDATION_MATRIX = {
    ("無糖", "去冰"): "青檸烏龍",
    ("無糖", "微冰"): "桂花青茶",
    ("無糖", "少冰"): "四季春茶",
    ("無糖", "正常冰"): "冷泡金萱",
    ("微糖", "去冰"): "鲜橙綠茶" if False else "鮮橙綠茶",
    ("微糖", "微冰"): "多多綠",
    ("微糖", "少冰"): "葡萄柚綠",
    ("微糖", "正常冰"): "荔枝烏龍",
    ("少糖", "去冰"): "金桔檸檬",
    ("少糖", "微冰"): "百香果綠",
    ("少糖", "少冰"): "蜂蜜檸檬",
    ("少糖", "正常冰"): "水蜜桃青茶",
    ("半糖", "去冰"): "芒果綠茶",
    ("半糖", "微冰"): "鳳梨青茶",
    ("半糖", "少冰"): "梅子綠茶",
    ("半糖", "正常冰"): "草莓果茶",
    ("全糖", "去冰"): "黑糖鮮奶",
    ("全糖", "微冰"): "焦糖奶茶",
    ("全糖", "少冰"): "芋頭鮮奶",
    ("全糖", "正常冰"): "珍珠奶茶"
}

# 資料庫模型：訂單
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(30), nullable=False)
    drink_name = db.Column(db.String(50), nullable=False)
    sugar = db.Column(db.String(20), nullable=False)
    ice = db.Column(db.String(20), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    topping = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='製作中') # 製作中, 已完成, 已取消
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html', drinks=DRINKS_MENU)

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    data = request.json or {}
    sugar = data.get('sugar', '微糖')
    ice = data.get('ice', '微冰')
    
    # 透過固定對應矩陣查詢
    recommended_drink = RECOMMENDATION_MATRIX.get((sugar, ice), "珍珠奶茶")
    price = next((d['price'] for d in DRINKS_MENU if d['name'] == recommended_drink), 50)
    
    return jsonify({
        'recommended_drink': recommended_drink,
        'price': price
    })

@app.route('/order', methods=['POST'])
def create_order():
    customer_name = request.form.get('customer_name', '').strip()
    drink_name = request.form.get('drink_name', '').strip()
    sugar = request.form.get('sugar', '微糖')
    ice = request.form.get('ice', '微冰')
    size = request.form.get('size', '中杯')
    topping = request.form.get('topping', '無')
    notes = request.form.get('notes', '').strip()
    
    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        quantity = 1

    # 驗證姓名：必填且只允許中英文、最多30字
    name_pattern = re.compile(r'^[\u4e00-\u9fa5a-zA-Z]{1,30}$')
    if not name_pattern.match(customer_name):
        return jsonify({'success': False, 'error': '姓名格式錯誤：僅允許中文或英文，且最多30個字。'}), 400

    # 驗證杯數：1至35杯，超過35杯拒絕線上送單
    if quantity < 1 or quantity > 35:
        return jsonify({'success': False, 'error': '每筆線上訂單最多35杯，超過35杯請電話訂購：0900-878787'}), 400

    # 驗證飲料是否在20款清單內
    drink_obj = next((d for d in DRINKS_MENU if d['name'] == drink_name), None)
    if not drink_obj:
        return jsonify({'success': False, 'error': '選擇的飲料不存在。'}), 400

    unit_price = drink_obj['price']
    total_price = unit_price * quantity
    
    # 產生高熵追蹤 Token
    token = secrets.token_urlsafe(32)

    new_order = Order(
        token=token,
        customer_name=customer_name,
        drink_name=drink_name,
        sugar=sugar,
        ice=ice,
        size=size,
        topping=topping,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        notes=notes,
        status='製作中'
    )
    db.session.add(new_order)
    db.session.commit()

    return jsonify({'success': True, 'token': token})

@app.route('/order/<token>')
def order_status(token):
    order = Order.query.filter_by(token=token).first_or_404()
    return render_template('status.html', order=order)

@app.route('/api/order/<token>')
def api_order_status(token):
    order = Order.query.filter_by(token=token).first_or_404()
    return jsonify({
        'status': order.status,
        'drink_name': order.drink_name,
        'quantity': order.quantity,
        'total_price': order.total_price,
        'updated_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        expected_email = os.environ.get('ADMIN_EMAIL', 'admin@drinkhelper.com')
        
        # 密碼檢查固定值 St970625
        if email == expected_email and password == 'St970625':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('登入失敗：帳號或密碼錯誤', 'danger')
            
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    date_filter = request.args.get('date', '')
    
    query = Order.query
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d')
            next_date = datetime(filter_date.year, filter_date.month, filter_date.day + 1) if filter_date.day < 28 else filter_date # simplified query bound
            query = query.filter(Order.created_at >= filter_date)
        except ValueError:
            pass

    orders = query.order_by(Order.created_at.desc()).all()
    
    # 計算今日統計（未取消訂單計入營業額）
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    today_orders = [o for o in orders if o.created_at.strftime('%Y-%m-%d') == today_str]
    today_count = len(today_orders)
    today_revenue = sum(o.total_price for o in today_orders if o.status != '已取消')
    preparing_count = sum(1 for o in orders if o.status == '製作中')

    return render_template('admin.html', 
                           orders=orders, 
                           today_count=today_count, 
                           today_revenue=today_revenue, 
                           preparing_count=preparing_count,
                           date_filter=date_filter)

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
def admin_update_status(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': '未授權'}), 401
    
    data = request.json or {}
    new_status = data.get('status')
    if new_status not in ['製作中', '已完成', '已取消']:
        return jsonify({'success': False, 'error': '無效狀態'}), 400
        
    order = Order.query.get_or_404(order_id)
    order.status = new_status
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
