
import os
import uuid

from flask import (
    Flask,
    jsonify,
    render_template,
    request
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    'SECRET_KEY',
    'drink-helper-secret-key'
)

# ==============================
# 20 款飲料菜單與價格
# ==============================

drinks = [
    {'name': '青檸烏龍', 'price': 45},
    {'name': '桂花青茶', 'price': 35},
    {'name': '四季春茶', 'price': 30},
    {'name': '冷泡金萱', 'price': 40},
    {'name': '珍珠奶茶', 'price': 50},
    {'name': '黑糖鮮奶', 'price': 65},
    {'name': '芋頭鮮奶', 'price': 70},
    {'name': '焦糖奶茶', 'price': 55},
    {'name': '金桔檸檬', 'price': 50},
    {'name': '百香果綠', 'price': 50},
    {'name': '梅子綠茶', 'price': 40},
    {'name': '鮮橙綠茶', 'price': 60},
    {'name': '葡萄柚綠', 'price': 60},
    {'name': '水蜜桃青茶', 'price': 55},
    {'name': '芒果綠茶', 'price': 55},
    {'name': '荔枝烏龍', 'price': 50},
    {'name': '草莓果茶', 'price': 65},
    {'name': '冬瓜檸檬', 'price': 45},
    {'name': '仙草凍奶茶', 'price': 55},
    {'name': '椰果百香綠', 'price': 55},
]

# ==============================
# 訂單資料
# ==============================

orders = {}

# ==============================
# 首頁
# ==============================

@app.route('/')
def index():
    return render_template(
        'index.html',
        drinks=drinks
    )


# ==============================
# AI 智慧口味推薦
# ==============================

@app.route('/api/recommend', methods=['POST'])
def recommend():

    data = request.get_json(silent=True) or {}

    feel = data.get('feel', '清爽解渴')

    recommendation_map = {
        '清爽解渴': '青檸烏龍',
        '酸甜開胃': '金桔檸檬',
        '茶香濃郁': '桂花青茶',
        '香醇奶味': '黑糖鮮奶',
        '咀嚼口感': '珍珠奶茶',
    }

    rec_name = recommendation_map.get(
        feel,
        '四季春茶'
    )

    price = next(
        (
            drink['price']
            for drink in drinks
            if drink['name'] == rec_name
        ),
        30
    )

    return jsonify({
        'recommended_drink': rec_name,
        'price': price
    })


# ==============================
# 顧客送出訂單
# ==============================

@app.route('/order', methods=['POST'])
def create_order():

    try:
        customer_name = request.form.get(
            'customer_name',
            ''
        ).strip()

        if not customer_name:
            return jsonify({
                'success': False,
                'error': '請輸入顧客姓名'
            })

        if len(customer_name) > 30:
            return jsonify({
                'success': False,
                'error': '姓名不可超過30個字'
            })

        drink_name = request.form.get('drink_name', '')
        sugar = request.form.get('sugar', '微糖')
        ice = request.form.get('ice', '微冰')
        size = request.form.get('size', '中杯')
        topping = request.form.get('topping', '無')

        try:
            quantity = int(
                request.form.get('quantity', 1)
            )
        except ValueError:
            return jsonify({
                'success': False,
                'error': '杯數格式錯誤'
            })

        if not (1 <= quantity <= 35):
            return jsonify({
                'success': False,
                'error': '杯數必須介於1到35杯'
            })

        # 確認飲料是否存在
        selected_drink = next(
            (
                drink
                for drink in drinks
                if drink['name'] == drink_name
            ),
            None
        )

        if selected_drink is None:
            return jsonify({
                'success': False,
                'error': '請選擇有效的飲料'
            })

        base_price = selected_drink['price']

        # 大杯加價10元
        extra = 10 if size == '大杯' else 0

        # 加料加價10元
        if topping != '無':
            extra += 10

        total_price = (
            base_price + extra
        ) * quantity

        token = str(uuid.uuid4())[:8]

        orders[token] = {
            'token': token,
            'customer_name': customer_name,
            'drink_name': drink_name,
            'sugar': sugar,
            'ice': ice,
            'size': size,
            'topping': topping,
            'quantity': quantity,
            'total_price': total_price,
            'status': '待處理'
        }

        return jsonify({
            'success': True,
            'token': token
        })

    except Exception as e:

        app.logger.exception('訂單建立失敗')

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==============================
# 訂單明細頁面
# ==============================

@app.route('/order/<token>')
def order_detail(token):

    if token not in orders:
        return '找不到此訂單', 404

    return render_template(
        'order.html',
        token=token
    )


# ==============================
# 顧客查詢訂單狀態
# ==============================

@app.route('/api/order_status/<token>')
def order_status_api(token):

    order = orders.get(token)

    if not order:
        return jsonify({
            'success': False,
            'error': '找不到訂單'
        }), 404

    return jsonify({
        'success': True,
        **order
    })


# ==============================
# 店家管理後台
# ==============================

@app.route('/admin')
def admin_panel():

    return render_template('admin.html')


# ==============================
# 管理後台訂單列表
# ==============================

@app.route('/api/admin/orders')
def admin_orders_api():

    return jsonify({
        'orders': list(orders.values())
    })


# ==============================
# 更新訂單狀態
# ==============================

@app.route(
    '/api/admin/update_status/<token>',
    methods=['POST']
)
def update_status(token):

    data = request.get_json(silent=True) or {}

    new_status = data.get('status')

    allowed_status = [
        '待處理',
        '已完成',
        '已取消'
    ]

    if token in orders and new_status in allowed_status:

        orders[token]['status'] = new_status

        return jsonify({
            'success': True,
            'message': '訂單狀態更新成功'
        })

    return jsonify({
        'success': False,
        'error': '更新失敗'
    }), 400


# ==============================
# 啟動 Flask
# ==============================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=False
    )
