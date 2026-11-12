import os, re, secrets, hashlib, hmac
from datetime import datetime, date
from functools import wraps
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("請先在 Render 設定 SECRET_KEY（至少 32 字元隨機字串）")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "1") == "1"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 4

db_url = os.environ.get("DATABASE_URL", "")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
if db_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    db_path = os.environ.get("DB_PATH", "/var/data/drinkhelper.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["300 per hour"])

MENU = {
    "青檸烏龍":45, "桂花青茶":35, "四季春茶":30, "冷泡金萱":40,
    "鮮橙綠茶":55, "多多綠":50, "葡萄柚綠":55, "荔枝烏龍":50,
    "金桔檸檬":45, "百香果綠":50, "蜂蜜檸檬":45, "水蜜桃青茶":50,
    "芒果綠茶":55, "鳳梨青茶":50, "梅子綠茶":45, "草莓果茶":55,
    "黑糖鮮奶":60, "焦糖奶茶":55, "芋頭鮮奶":65, "珍珠奶茶":50
}
SUGARS = ["無糖","微糖","少糖","半糖","全糖"]
ICES = ["去冰","微冰","少冰","正常冰"]
MATRIX = {
    ("無糖","去冰"):"青檸烏龍", ("無糖","微冰"):"桂花青茶", ("無糖","少冰"):"四季春茶", ("無糖","正常冰"):"冷泡金萱",
    ("微糖","去冰"):"鮮橙綠茶", ("微糖","微冰"):"多多綠", ("微糖","少冰"):"葡萄柚綠", ("微糖","正常冰"):"荔枝烏龍",
    ("少糖","去冰"):"金桔檸檬", ("少糖","微冰"):"百香果綠", ("少糖","少冰"):"蜂蜜檸檬", ("少糖","正常冰"):"水蜜桃青茶",
    ("半糖","去冰"):"芒果綠茶", ("半糖","微冰"):"鳳梨青茶", ("半糖","少冰"):"梅子綠茶", ("半糖","正常冰"):"草莓果茶",
    ("全糖","去冰"):"黑糖鮮奶", ("全糖","微冰"):"焦糖奶茶", ("全糖","少冰"):"芋頭鮮奶", ("全糖","正常冰"):"珍珠奶茶"
}
MOODS = {
    "清爽解渴":"清爽", "酸甜開胃":"酸甜", "茶香回甘":"茶香",
    "濃郁香醇":"濃郁", "水果清新":"水果", "咀嚼口感":"咀嚼",
    "想喝點甜的":"甜感"
}
# 三個條件組合都會落到唯一且固定的推薦；甜度＋冰塊矩陣是權威規則。
# 咀嚼口感的指定組合獨立列出，兩組各只有一款。
MOOD_OVERRIDES = {
    ("咀嚼口感","少糖","少冰"):"珍珠奶茶",
    ("咀嚼口感","微糖","少冰"):"芋頭鮮奶",
}
MOOD_ALIASES = {
    "咀嚼":"咀嚼口感", "有料":"咀嚼口感", "珍珠":"咀嚼口感",
    "清爽":"清爽解渴", "解渴":"清爽解渴", "酸甜":"酸甜開胃",
    "開胃":"酸甜開胃", "茶香":"茶香回甘", "回甘":"茶香回甘",
    "濃郁":"濃郁香醇", "香醇":"濃郁香醇", "水果":"水果清新",
    "果香":"水果清新", "甜":"想喝點甜的"
}

def recommend(mood, sugar, ice):
    mood = mood if mood in MOODS else "清爽解渴"
    if (mood, sugar, ice) in MOOD_OVERRIDES:
        return MOOD_OVERRIDES[(mood, sugar, ice)]
    return MATRIX[(sugar, ice)]

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(24), unique=True, nullable=False)
    tracking_hash = db.Column(db.String(64), nullable=False)
    customer_name = db.Column(db.String(30), nullable=False)
    drink = db.Column(db.String(40), nullable=False)
    sugar = db.Column(db.String(10), nullable=False)
    ice = db.Column(db.String(10), nullable=False)
    mood = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    size = db.Column(db.String(10), nullable=False)
    topping = db.Column(db.String(10), nullable=False)
    note = db.Column(db.String(200), default="")
    unit_price = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), default="製作中", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    day_key = db.Column(db.String(10), nullable=False)

class DailyReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_key = db.Column(db.String(10), unique=True, nullable=False)
    order_count = db.Column(db.Integer, nullable=False)
    revenue = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    return resp

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def archive_previous_days():
    today = date.today().isoformat()
    days = db.session.query(Order.day_key).filter(Order.day_key < today).distinct().all()
    for (day_key,) in days:
        if not DailyReport.query.filter_by(day_key=day_key).first():
            rows = Order.query.filter_by(day_key=day_key).all()
            db.session.add(DailyReport(day_key=day_key,
                        order_count=len(rows),
                        revenue=sum(o.total for o in rows if o.status != "已取消")))
    db.session.commit()

@app.route("/")
def index():
    return render_template("index.html", menu=MENU, sugars=SUGARS, ices=ICES, csrf_token=generate_csrf())

@app.route("/api/ai-chat", methods=["POST"])
@limiter.limit("30 per minute")
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message",""))[:500]
    history = data.get("history", [])[-8:]
    # OpenAI 只負責理解自然語言/對話；飲料推薦由伺服器固定規則決定。
    mood = data.get("mood")
    sugar = data.get("sugar")
    ice = data.get("ice")
    if not mood:
        lower = message.lower()
        mood = next((canonical for key, canonical in MOOD_ALIASES.items() if key in lower), None)
        if mood is None:
            return jsonify(reply="今天想要什麼樣的感受呢？例如清爽解渴、酸甜開胃、茶香回甘、濃郁香醇、水果清新、咀嚼口感，或直接描述你想喝的感覺。", mood=None)
    if not sugar:
        sugar = next((s for s in SUGARS if s in message), None)
        if not sugar:
            return jsonify(reply="了解！你想要幾分甜呢？可選無糖、微糖、少糖、半糖或全糖。", mood=mood)
    if not ice:
        ice = next((i for i in ICES if i in message), None)
        if not ice:
            return jsonify(reply="那冰塊呢？可選去冰、微冰、少冰或正常冰。", mood=mood, sugar=sugar)
    if sugar not in SUGARS or ice not in ICES:
        return jsonify(reply="甜度或冰塊選項不正確，請重新選擇。", error=True), 400
    drink = recommend(mood, sugar, ice)
    reply = f"依照你想要的「{mood}」、{sugar}、{ice}，我只推薦一款：{drink}。你可以直接採用，也可以改選其他菜單飲料。"
    return jsonify(reply=reply, mood=mood, sugar=sugar, ice=ice, recommendation=drink)

@app.route("/api/orders", methods=["POST"])
@limiter.limit("10 per minute")
def create_order():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name","")).strip()
    drink = str(data.get("drink",""))
    sugar, ice = str(data.get("sugar","")), str(data.get("ice",""))
    mood = str(data.get("mood","清爽解渴"))
    try:
        qty = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify(error="杯數格式錯誤"), 400
    if not re.fullmatch(r"[A-Za-z\u4e00-\u9fff]{1,30}", name):
        return jsonify(error="姓名必填，只能輸入中英文，最多30字，不可有空格或符號。"), 400
    if qty < 1 or qty > 35:
        return jsonify(error="每筆線上訂單最多35杯，超過35杯請電話訂購：0900-878787"), 400
    if drink not in MENU or sugar not in SUGARS or ice not in ICES:
        return jsonify(error="飲料、甜度或冰塊資料無效"), 400
    size = data.get("size","中杯")
    topping = data.get("topping","無")
    if size not in ["中杯","大杯"] or topping not in ["無","珍珠","椰果","仙草"]:
        return jsonify(error="尺寸或配料選項無效"), 400
    note = str(data.get("note",""))[:200]
    price = MENU[drink] # 未定義尺寸/配料加價，因此不自行加價
    token = secrets.token_urlsafe(32)
    order_no = "DH" + secrets.token_hex(5).upper()
    order = Order(order_no=order_no, tracking_hash=hashlib.sha256(token.encode()).hexdigest(),
        customer_name=name, drink=drink, sugar=sugar, ice=ice, mood=mood,
        quantity=qty, size=size, topping=topping, note=note,
        unit_price=price, total=price*qty, status="製作中", day_key=date.today().isoformat())
    db.session.add(order)
    db.session.commit()
    return jsonify(order_no=order_no, token=token, total=order.total), 201

@app.route("/api/status", methods=["POST"])
@limiter.limit("20 per minute")
def order_status():
    data = request.get_json(silent=True) or {}
    order_no = str(data.get("order_no",""))
    token = str(data.get("token",""))
    order = Order.query.filter_by(order_no=order_no).first()
    if not order or not hmac.compare_digest(order.tracking_hash, hashlib.sha256(token.encode()).hexdigest()):
        return jsonify(error="查無訂單，請確認訂單編號與查詢碼。"), 404
    return jsonify(order_no=order.order_no, status=order.status, drink=order.drink, quantity=order.quantity)

@app.route("/admin/login", methods=["GET","POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        username = os.environ.get("ADMIN_USERNAME","")
        password = os.environ.get("ADMIN_PASSWORD","")
        given_user = request.form.get("username","")
        given_pass = request.form.get("password","")
        if username and password and hmac.compare_digest(given_user, username) and hmac.compare_digest(given_pass, password):
            session.clear()
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin"))
        flash("帳號或密碼錯誤")
    return render_template("login.html", csrf_token=generate_csrf())

@app.route("/admin/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def admin():
    archive_previous_days()
    today = date.today().isoformat()
    orders = Order.query.filter_by(day_key=today).order_by(Order.created_at.desc()).all()
    revenue = sum(o.total for o in orders if o.status != "已取消")
    making = sum(1 for o in orders if o.status == "製作中")
    reports = DailyReport.query.order_by(DailyReport.day_key.desc()).limit(30).all()
    return render_template("admin.html", orders=orders, revenue=revenue, making=making,
                           reports=reports, today=today, csrf_token=generate_csrf())

@app.route("/admin/api/orders")
@admin_required
def admin_orders_api():
    today = date.today().isoformat()
    orders = Order.query.filter_by(day_key=today).order_by(Order.created_at.desc()).all()
    return jsonify([{"order_no":o.order_no,"name":o.customer_name,"drink":o.drink,
        "quantity":o.quantity,"total":o.total,"status":o.status,
        "created_at":o.created_at.strftime("%H:%M:%S")} for o in orders])

@app.route("/admin/status/<order_no>", methods=["POST"])
@admin_required
def update_status(order_no):
    order = Order.query.filter_by(order_no=order_no).first_or_404()
    status = request.form.get("status")
    if status not in ["製作中","已完成","已取消"]:
        abort(400)
    order.status = status
    db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/history")
@admin_required
def history():
    day_key = request.args.get("date", date.today().isoformat())
    orders = Order.query.filter_by(day_key=day_key).order_by(Order.created_at.desc()).all()
    return render_template("admin.html", orders=orders,
        revenue=sum(o.total for o in orders if o.status != "已取消"),
        making=sum(1 for o in orders if o.status=="製作中"),
        reports=DailyReport.query.order_by(DailyReport.day_key.desc()).limit(30).all(),
        today=day_key, csrf_token=generate_csrf())

@app.route("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
