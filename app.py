import os
import uuid
from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'drink-helper-secret-key')

# 20 款預設飲料清單
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

# 記憶體訂單資料庫
orders = {}


@app.route('/')
def index():
  return render_template('index.html', drinks=drinks)


@app.route('/api/recommend', methods=['POST'])
def recommend():
  data = request.get_json() or {}
  feel = data.get('feel', '清爽解渴')
  recommendation_map = {
      '清爽解渴': '青檸烏龍',
      '酸甜開胃': '金桔檸檬',
      '茶香回甘': '桂花青茶',
      '濃郁香醇': '黑糖鮮奶',
      '水果清新': '鮮橙綠茶',
      '咀嚼口感': '珍珠奶茶',
      '想喝甜的': '焦糖奶茶',
  }
  rec_name = recommendation_map.get(feel, '四季春茶')
  price = next((d['price'] for d in drinks if d['name'] == rec_name), 30)
  return jsonify({'recommended_drink': rec_name, 'price': price})


@app.route('/order', methods=['POST'])
def create_order():
  try:
    customer_name = request.form.get('customer_name', '').strip()
    if not customer_name or len(customer_name) > 30:
      return jsonify({'success': False, 'error': '姓名無效或超過30字'})

    drink_name = request.form.get('drink_name')
    sugar = request.form.get('sugar', '微糖')
    ice = request.form.get('ice', '微冰')
    size = request.form.get('size', '中杯')
    topping = request.form.get('topping', '無')
    quantity = int(request.form.get('quantity', 1))

    if not (1 <= quantity <= 35):
      return jsonify({'success': False, 'error': '杯數須介於 1 到 35 杯之間'})

    base_price = next(
        (d['price'] for d in drinks if d['name'] == drink_name), 30
    )
    extra = 10 if size == '大杯' else 0
    if topping != '無':
      extra += 10
    total_price = (base_price + extra) * quantity

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
        'status': '待處理',
    }
    return jsonify({'success': True, 'token': token})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)})


@app.route('/order/<token>')
def order_detail(token):
  return render_template('order.html', token=token)


@app.route('/api/order_status/<token>')
def order_status_api(token):
  order = orders.get(token)
  if not order:
    return jsonify({'success': False, 'error': '找不到訂單'})
  return jsonify({'success': True, **order})


@app.route('/admin')
def admin_panel():
  return render_template('admin.html', orders=list(orders.values()))


@app.route('/api/admin/update_status/<token>', methods=['POST'])
def update_status(token):
  data = request.get_json() or {}
  new_status = data.get('status')
  if token in orders and new_status in ['待處理', '已完成', '已取消']:
    orders[token]['status'] = new_status
    return jsonify({'success': True})
  return jsonify({'success': False, 'error': '更新失敗'})


if __name__ == '__main__':
  app.run(debug=True)
