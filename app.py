
from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

DATABASE = os.path.join(app.instance_path, "drinkhelper.db")
os.makedirs(app.instance_path, exist_ok=True)

TAIWAN = ZoneInfo("Asia/Taipei")

PRICES = {
    "青檸烏龍": 45,
    "桂花青茶": 35,
    "四季春茶": 30,
    "冷泡金萱": 40,
    "鮮橙綠茶": 55,
    "多多綠": 50,
    "葡萄柚綠": 55,
    "荔枝烏龍": 50,
    "金桔檸檬": 45,
    "百香果綠": 50,
    "蜂蜜檸檬": 45,
    "水蜜桃青茶": 50,
    "芒果綠茶": 55,
    "鳳梨青茶": 50,
    "梅子綠茶": 45,
    "草莓果茶": 55,
    "黑糖鮮奶": 60,
    "焦糖奶茶": 55,
    "芋頭鮮奶": 65,
    "珍珠奶茶": 50
}


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
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
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            report_date TEXT PRIMARY KEY,
            total_orders INTEGER,
            revenue INTEGER
        )
    """)

    conn.commit()
    conn.close()


def settle_old_orders():
    """午夜後第一次收到網站請求時，結算並清除昨天以前的訂單。"""

    today = datetime.now(TAIWAN).date().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    # 找出今天以前尚未結算的訂單日期
    cursor.execute("""
        SELECT DISTINCT substr(created_at, 1, 10)
        FROM orders
        WHERE substr(created_at, 1, 10) < ?
    """, (today,))

    old_dates = [row[0] for row in cursor.fetchall() if row[0]]

    for old_date in old_dates:
        cursor.execute("""
            SELECT drink, quantity, status
            FROM orders
            WHERE substr(created_at, 1, 10) = ?
        """, (old_date,))

        old_orders = cursor.fetchall()

        total_orders = len(old_orders)

        revenue = sum(
            PRICES.get(row["drink"], 0) * (row["quantity"] or 0)
            for row in old_orders
            if row["status"] != "已取消"
        )

        # 保存每日營業額，避免重複結算
        cursor.execute("""
            INSERT OR IGNORE INTO daily_reports
            (report_date, total_orders, revenue)
            VALUES (?, ?, ?)
        """, (old_date, total_orders, revenue))

    # 清除已結算的舊訂單
    cursor.execute("""
        DELETE FROM orders
        WHERE substr(created_at, 1, 10) < ?
    """, (today,))

    conn.commit()
    conn.close()


@app.before_request
def daily_cleanup():
    settle_old_orders()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}

    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "數量格式錯誤"}), 400

    if quantity < 1 or quantity > 20:
        return jsonify({"success": False, "message": "數量必須介於 1 到 20"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO orders
        (customer, drink, sugar, ice, size, topping,
         quantity, note, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("customer", ""),
        data.get("drink", ""),
        data.get("orderSugar", data.get("sugar", "")),
        data.get("orderIce", data.get("ice", "")),
        data.get("size", ""),
        data.get("topping", ""),
        quantity,
        data.get("note", ""),
        "製作中",
        datetime.now(TAIWAN).strftime("%Y-%m-%d %H:%M:%S")
    ))

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "訂單送出成功",
        "order_id": order_id
    })


@app.route("/api/orders", methods=["GET"])
def get_orders():
    conn = get_connection()

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")

    orders = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify(orders)


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

    conn = get_connection()
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


@app.route("/api/daily-reports", methods=["GET"])
def get_daily_reports():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT report_date, total_orders, revenue
        FROM daily_reports
        ORDER BY report_date DESC
    """)

    reports = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify(reports)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
