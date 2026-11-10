
from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)

# 資料庫位置
DATABASE = os.path.join(app.instance_path, "drinkhelper.db")
os.makedirs(app.instance_path, exist_ok=True)


# 建立資料庫
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT,
            drink TEXT,
            sugar TEXT,
            ice TEXT,
            size TEXT,
            topping TEXT,
            quantity INTEGER,
            note TEXT,
            status TEXT DEFAULT '製作中',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# 首頁：顧客點餐
@app.route("/")
def index():
    return render_template("index.html")


# 店家管理後台
@app.route("/admin")
def admin():
    return render_template("admin.html")


# 顧客送出訂單
@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO orders
        (customer, drink, sugar, ice, size, topping, quantity, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("customer", ""),
        data.get("drink", ""),
        data.get("orderSugar", data.get("sugar", "")),
        data.get("orderIce", data.get("ice", "")),
        data.get("size", ""),
        data.get("topping", ""),
        data.get("quantity", 1),
        data.get("note", "")
    ))

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "訂單送出成功",
        "order_id": order_id
    })


# 取得所有訂單
@app.route("/api/orders", methods=["GET"])
def get_orders():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()

    orders = [dict(row) for row in rows]

    conn.close()

    return jsonify(orders)


# 修改訂單狀態
@app.route("/api/orders/<int:order_id>", methods=["PATCH"])
def update_order(order_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    allowed_status = ["製作中", "已完成", "已取消"]

    if status not in allowed_status:
        return jsonify({
            "success": False,
            "message": "無效的訂單狀態"
        }), 400

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status, order_id)
    )

    updated = cursor.rowcount

    conn.commit()
    conn.close()

    if updated == 0:
        return jsonify({
            "success": False,
            "message": "找不到這筆訂單"
        }), 404

    return jsonify({
        "success": True,
        "message": "訂單狀態更新成功"
    })


# 初始化資料庫
init_db()


if __name__ == "__main__":
    app.run(debug=True)
