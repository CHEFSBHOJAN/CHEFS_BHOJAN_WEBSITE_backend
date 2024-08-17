import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO
import requests
from pymongo import MongoClient
from flask_cors import CORS
import os
from bson import ObjectId
import json
from twilio.rest import Client


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
    
app = Flask(__name__)

os.environ['PASSWORD'] = 'ChefsKuku@28'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secure_default_key')
password = os.environ.get('PASSWORD')

CORS(app, supports_credentials=True, allow_headers="*", origins="*", methods=["OPTIONS", "POST"])
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', engineio_logger=True)

client = MongoClient(
    'mongodb+srv://ChefsBhojan:usX7ZS8kPz4Pv@cluster0.eikei2d.mongodb.net/',
    connectTimeoutMS=30000, 
    socketTimeoutMS=None)
db = client['ORDERS']
CB_PONDA = db['CB_PONDA']
CB_MARGAO = db['CB_MARGAO']
MARGAO_STATUS = db['CB_MARGOA_STATUS']
PONDA_STATUS = db['CB_PONDA_STATUS']

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
    entered_password = request.form['password']
    selected_outlet = request.form['outlet']
    if entered_password == password:
        if selected_outlet == 'Ponda':
            return redirect(url_for('ponda_orders'))
        elif selected_outlet == 'Margao':
            return redirect(url_for('margao_orders'))
    else :
        return redirect(url_for('index'))

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
        order['total_amount'] = round(total_amount / 1.2, 2)
        
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
            order['items_list'] = items_list
            order['total_amount'] = round(total_amount / 1.2, 2)
        
    return render_template('margao_orders.html', orders=orders)

@app.route('/api/orders', methods=['POST', 'OPTIONS'])
def save_form_data():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'success', 'message': 'CORS preflight request handled successfully'}), 200
    
    data = request.json
    print("Received form data:", data)
    status_margao = MARGAO_STATUS.find_one({}, {'_id': 0, 'status': 1})['status']
    status_ponda = PONDA_STATUS.find_one({}, {'_id': 0, 'status': 1})['status']
    
    print(status_margao)
    print(status_ponda)
    
    pincode = data.get('pincode')
    outlet_selected = data.get('selectedOutlet')

    if outlet_selected == 'Ponda':
        if status_ponda:
            if pincode in ALLOWED_PINCODES_PONDA:
                new_order = {
                    'orderId': data['orderId'],
                    'name' : data['name'],
                    'phone': data['phone'],
                    'address': data['address'],
                    'pincode': data['pincode'],
                    'items' : data['items'],
                    'date_created': data['date'],
                    'status': "accept"
                }
                result = CB_PONDA.insert_one(new_order)
                new_order['_id'] = result.inserted_id
                socketio.emit('new_order', {'outlet': 'Ponda', 'order':  json.loads(json.dumps(new_order, cls=JSONEncoder))})

                send_whatsapp_message(new_order)
                
                return jsonify({'status': 'success', 'message': 'Form data saved successfully'}), 200
            else:
                return jsonify({'status': 'error', 'message': 'Delivery not available for the entered pincode'}), 400
        else:
            return jsonify({'status': 'error', 'message': 'Currently not accepting orders'}), 400
    
    elif outlet_selected == 'Margao':
        if status_margao:
            if pincode in ALLOWED_PINCODES_MARGAO:
                new_order = {
                    'orderId': data['orderId'],
                    'name' : data['name'],
                    'phone': data['phone'],
                    'address': data['address'],
                    'pincode': data['pincode'],
                    'items' : data['items'],
                    'date_created': data['date'],
                    'status': "accept"
                }
                result = CB_MARGAO.insert_one(new_order)
                new_order['_id'] = result.inserted_id
                socketio.emit('new_order', {'outlet': 'Margao', 'order':  json.loads(json.dumps(new_order, cls=JSONEncoder))})

                send_whatsapp_message(new_order)
                
                return jsonify({'status': 'success', 'message': 'Form data saved successfully'}), 200
            else:
                return jsonify({'status': 'error', 'message': 'Delivery not available for the entered pincode'}), 400
        else:
            return jsonify({'status': 'error', 'message': 'Currently not accepting orders'}), 400
        
    else:
        return jsonify({'status': 'error', 'message': 'Invalid outlet selected'}), 400

def send_whatsapp_message(order):
    access_token = 'EAAFNtF4tqZA0BOZBQPQKhre2onFphjV6tKARnKIzGKkgftbDk7aWEjvx8WrhuTXX3TlkW6eUfi7WHLTbbaaYIHJxJ5nPdxR98xXsbIbhvXfvsQ4KWiLDvZB6wSpBeIUm039y0ZCvzDcle8HxdwZBFBm7sIpsJp5ecrs9kzsJh9JgsGOQS0kwVVAN2QhYPSvrVH3TguZB7UvyXJ8rRmsPQZD'
    phone_number_id = '323798344160879'
    recipient_phone_number = '919923388852'
    
    items_summary = "".join([f"{item['name']}: {item['quantity']}" for item in order['items']])
    
    url = f'https://graph.facebook.com/v20.0/{phone_number_id}/messages'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone_number,
        "type": "template",
        "template": {
            "name": "neworder",
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "text",
                            "text": order["name"]
                        }
                    ]
                },
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": order["phone"]
                        },
                        {
                            "type": "text",
                            "text": items_summary
                        }
                    ]
                }
            ]
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print("Message sent successfully!")
        print(response.json())
    else:
        print(f"Failed to send message: {response.status_code}")
        print(response.json())

        
        
def send_whatsapp_message_to_customer(order ,status):
    access_token = 'EAAFNtF4tqZA0BOZBQPQKhre2onFphjV6tKARnKIzGKkgftbDk7aWEjvx8WrhuTXX3TlkW6eUfi7WHLTbbaaYIHJxJ5nPdxR98xXsbIbhvXfvsQ4KWiLDvZB6wSpBeIUm039y0ZCvzDcle8HxdwZBFBm7sIpsJp5ecrs9kzsJh9JgsGOQS0kwVVAN2QhYPSvrVH3TguZB7UvyXJ8rRmsPQZD'
    phone_number_id = '323798344160879'
    recipient_phone_number = f'91{order["phone"]}'
    items_summary = "\n".join([f"{item['name']}: {item['quantity']}" for item in order['items']])
    
    url = f'https://graph.facebook.com/v20.0/{phone_number_id}/messages'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    if status == 'accept':
        template_name = "order_accepted"
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": "en"
                },
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "text",
                                "text": order["name"]  
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": items_summary
                            }
                        ]
                    }
                ]
            }
        }
    elif status == 'deliver':
        template_name = "outfor_delivery"
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": "en"
                }
            }
        }
    elif status == 'fulfill':
        template_name = "fulfilled_order"
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": "en"
                }
            }
        }
    else:
        print("Invalid status")
        return
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print("Message sent successfully!")
        print(response.json())
    else:
        print(f"Failed to send message: {response.status_code}")
        print(response.json())


@app.route('/api/status_order_Ponda', methods=['POST'])
def fulfill_order_Ponda():
    
    data = request.json
    order_id = data.get('orderId')
    status = data.get('status')
    order_id = int(order_id)
    order = CB_PONDA.find_one({'orderId': order_id})

    if(status == 'accept'):
        newStatus = 'deliver'
    elif(status == 'deliver'):
        newStatus = 'fulfill'
    elif(status == 'fulfill'):
        newStatus = 'fulfilled'
    else:
        return
        
    if order_id:
        CB_PONDA.update_one({'orderId': order_id}, {'$set': {'status':newStatus}})
        send_whatsapp_message_to_customer(order , status)
        return jsonify({'status': 'success', 'message': f'Order {order_id} marked as fulfilled'}), 200

    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/api/status_order_Margao', methods=['POST'])
def fulfill_order_Margao():
    
    data = request.json
    order_id = data.get('orderId')
    status = data.get('status')
    order_id = int(order_id)
    order = CB_MARGAO.find_one({'orderId': order_id})
    
    if(status == 'accept'):
        newStatus = 'deliver'
    elif(status == 'deliver'):
        newStatus = 'fulfill'
    elif(status == 'fullfill'):
        newStatus = 'fulfilled'

    if order_id:
        CB_MARGAO.update_one({'orderId': order_id}, {'$set': {'status':newStatus}})
        send_whatsapp_message_to_customer(order , status)
        return jsonify({'status': 'success', 'message': f'Order {order_id} marked as fulfilled'}), 200
    

    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/api/Get_Margao_Status', methods=['GET'])
def Get_Margao_Status():
    status = MARGAO_STATUS.find_one({}, {'_id': 0, 'status': 1})
    if status:
        return jsonify({'status': status['status']})
    return jsonify({'status': False})

@app.route('/api/Update_Margao_Status', methods=['POST'])
def Update_Margao_Status():
    data = request.json
    status = data.get('status')
    if status == 'on':
        MARGAO_STATUS.update_one({}, {'$set': {'status': True}})
        return jsonify({'status': 'success', 'message': 'Margao marked as On'}), 200
    elif status == 'off':
        MARGAO_STATUS.update_one({}, {'$set': {'status': False}})
        return jsonify({'status': 'success', 'message': 'Margao marked as Off'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/api/Get_Ponda_Status', methods=['GET'])
def Get_Ponda_Status():
    status = PONDA_STATUS.find_one({}, {'_id': 0, 'status': 1})
    if status:
        return jsonify({'status': status['status']})
    return jsonify({'status': False})

@app.route('/api/Update_Ponda_Status', methods=['POST'])
def Update_Ponda_Status():
    data = request.json
    status = data.get('status')
    if status == 'on':
        PONDA_STATUS.update_one({}, {'$set': {'status': True}})
        return jsonify({'status': 'success', 'message': 'Margao marked as On'}), 200
    elif status == 'off':
        PONDA_STATUS.update_one({}, {'$set': {'status': False}})
        return jsonify({'status': 'success', 'message': 'Margao marked as Off'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

# digital menu backend

@app.route('/api/getmenumargao', methods=['GET'])
def MargaoMenu():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'success', 'message': 'CORS preflight request handled successfully'}), 200
    
    try:
        menu_file_path = os.path.join(os.path.dirname(__file__), 'margaomenu.json')
        with open(menu_file_path, 'r') as file:
            dishes = json.load(file)
        return jsonify({'dishes': dishes}), 200
    except FileNotFoundError:
        error_message = "menu.json file not found"
        print(error_message)
        return jsonify({'error': error_message}), 500
    except json.JSONDecodeError:
        error_message = "Error decoding JSON from menu.json"
        print(error_message)
        return jsonify({'error': error_message}), 500
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        return jsonify({'error': error_message}), 500
    
@app.route('/api/getmenuponda', methods=['GET'])
def PondaMenu():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'success', 'message': 'CORS preflight request handled successfully'}), 200
    
    try:
        menu_file_path = os.path.join(os.path.dirname(__file__), 'pondamenu.json')
        with open(menu_file_path, 'r') as file:
            dishes = json.load(file)
        return jsonify({'dishes': dishes}), 200
    except FileNotFoundError:
        error_message = "menu.json file not found"
        print(error_message)
        return jsonify({'error': error_message}), 500
    except json.JSONDecodeError:
        error_message = "Error decoding JSON from menu.json"
        print(error_message)
        return jsonify({'error': error_message}), 500
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        return jsonify({'error': error_message}), 500

if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=8080)
