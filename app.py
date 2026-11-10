from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "drinkhelper-demo-secret"
DB_PATH = Path(__file__).with_name("drinkhelper.db")

DRINKS = [
    ("珍珠奶茶", 55, "奶茶", "紅茶、牛奶、珍珠", "牛奶", "含咖啡因"),
    ("四季春茶", 35, "純茶", "四季春茶葉、水", "無", "含咖啡因"),
    ("百香果綠茶", 50, "水果茶", "綠茶、百香果、糖", "可能含水果過敏原", "含咖啡因"),
    ("鮮奶茶", 60, "鮮奶茶", "紅茶、鮮乳", "牛奶", "含咖啡因"),
    ("冬瓜檸檬", 45, "水果茶", "冬瓜、檸檬、水", "柑橘類", "通常不含茶葉咖啡因"),
    ("蜂蜜青茶", 45, "純茶", "青茶、蜂蜜", "蜂蜜", "含咖啡因"),
]

FAQS = [
    ("如何調整甜度？", "點餐時可選擇無糖、微糖、半糖或全糖；實際甜度仍依門市配方為準。"),
    ("可以做去冰嗎？", "可以在客製化點餐時選擇去冰、微冰、少冰或正常冰。"),
    ("飲料含有乳製品嗎？", "部分奶茶與鮮奶茶含牛奶。請查看飲品成分，若有嚴重過敏，點餐前務必向店員再次確認。"),
    ("訂單多久會完成？", "本展示系統會顯示門市更新的訂單狀態，實際等待時間依現場狀況而定。"),
    ("可以取消訂單嗎？", "此課堂展示版尚未提供線上取消功能，請直接聯絡門市人員。"),
]

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            phone TEXT NOT NULL,
            drink TEXT NOT NULL,
            sugar TEXT NOT NULL,
            ice TEXT NOT NULL,
            toppings TEXT,
            quantity INTEGER NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT '已收到訂單'
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT,
            rating INTEGER NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS drinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER,
            category TEXT,
            ingredients TEXT,
            allergens TEXT,
            caffeine TEXT
        )""")
        count = conn.execute("SELECT COUNT(*) FROM drinks").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO drinks(name,price,category,ingredients,allergens,caffeine) VALUES(?,?,?,?,?,?)",
                DRINKS
            )

@app.route("/")
def home():
    with connect_db() as conn:
        drinks = conn.execute("SELECT * FROM drinks ORDER BY id").fetchall()
    return render_template("index.html", drinks=drinks)

@app.route("/order", methods=["POST"])
def order():
    fields = ["customer", "phone", "drink", "sugar", "ice"]
    if any(not request.form.get(field, "").strip() for field in fields):
        flash("請完整填寫姓名、聯絡電話及飲料選項。", "error")
        return redirect(url_for("home") + "#order")
    quantity = max(1, min(20, int(request.form.get("quantity", 1))))
    toppings = ", ".join(request.form.getlist("toppings"))
    with connect_db() as conn:
        cur = conn.execute("""INSERT INTO orders
            (customer,phone,drink,sugar,ice,toppings,quantity,note)
            VALUES(?,?,?,?,?,?,?,?)""",
            (request.form["customer"].strip(), request.form["phone"].strip(),
             request.form["drink"], request.form["sugar"], request.form["ice"],
             toppings, quantity, request.form.get("note", "").strip()))
        order_id = cur.lastrowid
    return render_template("success.html", order_id=order_id)

@app.route("/track", methods=["GET", "POST"])
def track():
    order = None
    if request.method == "POST":
        try:
            order_id = int(request.form.get("order_id", "0"))
        except ValueError:
            order_id = 0
        with connect_db() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            flash("查無此訂單，請確認訂單編號。", "error")
    return render_template("track.html", order=order)

@app.route("/feedback", methods=["POST"])
def feedback():
    message = request.form.get("message", "").strip()
    if not message:
        flash("請填寫回饋內容。", "error")
        return redirect(url_for("home") + "#feedback")
    rating = max(1, min(5, int(request.form.get("rating", 5))))
    with connect_db() as conn:
        conn.execute("INSERT INTO feedback(customer,rating,category,message) VALUES(?,?,?,?)",
                     (request.form.get("customer", "").strip(), rating,
                      request.form.get("category", "其他"), message))
    flash("感謝你的回饋！我們會持續改善服務。", "success")
    return redirect(url_for("home") + "#feedback")

@app.route("/admin")
def admin():
    with connect_db() as conn:
        orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50").fetchall()
        feedbacks = conn.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT 30").fetchall()
    return render_template("admin.html", orders=orders, feedbacks=feedbacks)

@app.route("/admin/status/<int:order_id>", methods=["POST"])
def update_status(order_id):
    status = request.form.get("status", "製作中")
    allowed = ["已收到訂單", "製作中", "可取餐", "已完成"]
    if status in allowed:
        with connect_db() as conn:
            conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        flash(f"訂單 #{order_id} 狀態已更新。", "success")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
