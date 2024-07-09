import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from datetime import datetime
from flask_cors import CORS
import os
from bson import ObjectId
import json

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
    
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secure_default_key')

CORS(app, supports_credentials=True, allow_headers="*", origins="*", methods=["OPTIONS", "POST"])
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', engineio_logger=True)

client = MongoClient(
    'mongodb+srv://crob0008:GYfLnhxdJgeiOTPO@chefsbhojan.oxsu9gm.mongodb.net/',
    connectTimeoutMS=30000, 
    socketTimeoutMS=None)
db = client['ORDERS']
CB_PONDA = db['CB_PONDA']
CB_MARGAO = db['CB_MARGAO']

ALLOWED_PINCODES_PONDA = [
    "403401",  # Ponda
    "403102",  # Agapur Adpoi
    "403401",  # Bandora
    "403103",  # Shiroda
    "403404",  # Mardol
    "403706",  # Usgao
    "403406"   # Borim
]

ALLOWED_PINCODES_MARGAO = [
    "403707",  # Margao
    "403708",  # Aquem
    "403709",  # Navelim
    "403710",  # Fatorda
    "403711",  # Borda
    "403712",  # Colva
    "403713"   # Benaulim
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select_outlet', methods=['POST'])
def select_outlet():
    selected_outlet = request.form['outlet']
    if selected_outlet == 'Ponda':
        return redirect(url_for('ponda_orders'))
    elif selected_outlet == 'Margao':
        return redirect(url_for('margao_orders'))

@app.route('/ponda_orders')
def ponda_orders():
    orders_cursor = CB_PONDA.find().sort('date_created', -1)
    orders = list(orders_cursor)
    
    for order in orders:
        order['_id'] = str(order['_id']) 
        items_list = []
        total_amount = 0
        
        for item in order['items']:
            item_total = item['price'] * item['quantity']
            items_list.append({
                'name': item['name'],
                'quantity': item['quantity'],
                'price': item['price'],
                'item_total': item_total
            })
            total_amount += item_total
        order['items_list'] = items_list
        order['total_amount'] = total_amount
        
    return render_template('ponda_orders.html', orders=orders)

@app.route('/margao_orders')
def margao_orders():
    orders_cursor = CB_MARGAO.find().sort('date_created', -1)
    orders = list(orders_cursor)
    
    for order in orders:
        order['_id'] = str(order['_id'])
        items_list = []
        total_amount = 0
        
        for item in order['items']:
            item_total = item['price'] * item['quantity']
            items_list.append({
                'name': item['name'],
                'quantity': item['quantity'],
                'price': item['price'],
                'item_total': item_total
            })
            total_amount += item_total
        order['total_amount'] = round(total_amount / 1.2, 2)
        
    return render_template('margao_orders.html', orders=orders)

@app.route('/api/orders', methods=['POST', 'OPTIONS'])
def save_form_data():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'success', 'message': 'CORS preflight request handled successfully'}), 200
    
    data = request.json
    print("Received form data:", data)
    
    pincode = data.get('pincode')
    outlet_selected = data.get('selectedOutlet')

    if outlet_selected == 'Ponda':
        if pincode in ALLOWED_PINCODES_PONDA:
            new_order = {
                'orderId': data['orderId'],
                'name' : data['name'],
                'phone': data['phone'],
                'address': data['address'],
                'pincode': data['pincode'],
                'items' : data['items'],
                'date_created': data['date'],
                'fulfilled': False
            }
            result = CB_PONDA.insert_one(new_order)
            new_order['_id'] = result.inserted_id
            socketio.emit('new_order', {'outlet': 'Ponda', 'order':  json.loads(json.dumps(new_order, cls=JSONEncoder))})
            return jsonify({'status': 'success', 'message': 'Form data saved successfully'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Delivery not available for the entered pincode'}), 400
    
    elif outlet_selected == 'Margao':
        if pincode in ALLOWED_PINCODES_MARGAO:
            new_order = {
                'orderId': data['orderId'],
                'name' : data['name'],
                'phone': data['phone'],
                'address': data['address'],
                'pincode': data['pincode'],
                'items' : data['items'],
                'date_created': data['date'],
                'fulfilled': False
            }
            result = CB_MARGAO.insert_one(new_order)
            new_order['_id'] = result.inserted_id
            socketio.emit('new_order', {'outlet': 'Margao', 'order':  json.loads(json.dumps(new_order, cls=JSONEncoder))})
            return jsonify({'status': 'success', 'message': 'Form data saved successfully'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Delivery not available for the entered pincode'}), 400
    
    else:
        return jsonify({'status': 'error', 'message': 'Invalid outlet selected'}), 400


@app.route('/api/fulfill_order_Ponda', methods=['POST'])
def fulfill_order_Ponda():
    data = request.json
    order_id = data.get('orderId')
    print(order_id)
    if order_id:
        order_id = int(order_id)
        CB_PONDA.update_one({'orderId': order_id}, {'$set': {'fulfilled': True}})
        return jsonify({'status': 'success', 'message': f'Order {order_id} marked as fulfilled'}), 200

    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/api/fulfill_order_Margao', methods=['POST'])
def fulfill_order_Margao():
    data = request.json
    order_id = data.get('orderId')
    print(order_id)
    if order_id:
        order_id = int(order_id)
        CB_MARGAO.update_one({'orderId': order_id}, {'$set': {'fulfilled': True}})
        return jsonify({'status': 'success', 'message': f'Order {order_id} marked as fulfilled'}), 200

    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=8080)