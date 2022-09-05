import ccxt
import time
import datetime
import websockets
import json
from .common import id_generator
from .telegram import telegram

uri_ws = 'wss://plasma-relay-backend.timex.io/socket/relay'

with open('/home/ubuntu/timex_keys.txt', 'r', encoding='UTF-8') as db:
    m = db.read().split('\n')
_api_key = m[1].split("'")[1]
_api_secret = m[0].split("'")[1]

bot_TIMEX = ccxt.timex({'apiKey': _api_key, 'secret': _api_secret,
                        'enableRateLimit': True})

bot_TIMEX_public = ccxt.timex({'enableRateLimit': True})


def msg_for_create_order(data):
    timestamp = time.time() + 86400
    datetime_expire = datetime.datetime.fromtimestamp(timestamp)
    expire_time = 'T'.join(str(datetime_expire)[:-3].split(' ')) + 'Z'
    data['pair'] = ''.join(data['pair'].split('/'))
    msg = {
        "type": "REST",
        "requestId": id_generator(size=6),
        "stream": "/post/trading/orders/json",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "body": [
                {
                    "price": str(data['price']),
                    "quantity": str(data['amount']),
                    "side": data['side'],
                    'type': 'LIMIT',
                    "symbol": data['pair'],
                    "clientOrderId": id_generator(size=12),
                    'expireTime': expire_time
                }
            ]
        }
    }
    return msg


def update_order(data):
    timestamp = time.time() + 86400
    datetime_expire = datetime.datetime.fromtimestamp(timestamp)
    expire_time = 'T'.join(str(datetime_expire)[:-3].split(' ')) + 'Z'
    msg = {
        "type": "REST",
        "requestId": id_generator(size=6),
        "stream": "/put/trading/orders/json",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "body": [
                {
                    "id": data['order_id'],
                    "price": str(data['price']),
                    "quantity": str(data['amount']),
                    "expireTime": expire_time
                }
            ]
        }
    }
    return msg


def msg_for_cancel(order_id):
    msg = {
        "type": "REST",
        "requestId": id_generator(size=6),
        "stream": "/delete/trading/orders/json",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "body": [
                {
                    "id": order_id
                }
            ]
        }
    }
    return msg


def fetch_historical_orders(amount=10):
    msg = {
        "type": "REST",
        "requestId": id_generator(size=6),
        "stream": "/get/history/orders",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "pageable": {
                "page": 0,
                "size": amount
            }
        }
    }
    return msg


def get_trades():
    msg = {
        "type": "REST",
        "requestId": id_generator(size=6),
        "stream": "/get/history/trades",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "pageable": {
                "page": 0,
                "size": 10
            }
        }
    }
    return msg


def fetch_open_orders():
    msg = {
        "type": "REST",
        "requestId": id_generator(size=6),
        "stream": "/get/trading/orders",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "pageable": {
                "size": 10
            }
        }
    }
    return msg


def cancel_all_orders_TIMEX():
    response_fetch = bot_TIMEX.fetchOpenOrders()
    ids = [x['id'] for x in response_fetch]
    response_cancel = bot_TIMEX.cancelOrders(ids)
# def rewrite_last_pnl():
#     TIMEX_pnl = None
#     while not TIMEX_pnl:
#         try:
#             TIMEX_pnl = bot_TIMEX.private_get_pnl_historical_changes()
#         except:
#             pass
#     total_profit_TIMEX = round(float(TIMEX_pnl['result']['totalPnl'][procData['pair_TIMEX']]))
#     today_date = datetime.datetime.utcfromtimestamp(int(float(TIMEX_pnl['result']['today']))).strftime('%Y-%m-%d %H:%M:%S')
#     to_file = f"{today_date}\n{total_profit_TIMEX}"
#     with open('last_date_pnl.txt', 'w') as file:
#         file.write(to_file)


def hist_orders_check(res, order_id):
    for order in res['responseBody']['orders']:
        if order['id'] == order_id:
            return order
    return None


async def fetch_ws_order(order_id):
    async with websockets.connect(uri_ws) as websocket:
        msg = fetch_open_orders()
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res = json.loads(res)
        if res.get('responseBody'):
            order = hist_orders_check(res, order_id)
        orders_len = 0
        if not order:
            for i in range(4):
                if order:
                    break
                orders_len += 10
                msg = fetch_historical_orders(orders_len)
                await websocket.send(json.dumps(msg))
                res = await websocket.recv()
                res = json.loads(res)
                if res['requestId'] == msg['requestId']:
                    if res.get('responseBody'):
                        order = hist_orders_check(res, order_id)
        return order


async def cancel_ws_order(order_id):
    async with websockets.connect(uri_ws) as websocket:
        msg = msg_for_cancel(order_id)
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res_cancel = json.loads(res)
        return res_cancel


async def update_ws_order(data):
    async with websockets.connect(uri_ws) as websocket:
        msg = update_order(data)
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res_update = json.loads(res)
        return res_update


async def create_ws_order(data):
    async with websockets.connect(uri_ws) as websocket:
        msg = msg_for_create_order(data)
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res_create = json.loads(res)
        return res_create


async def fetchOpenOrders():
    async with websockets.connect(uri_ws) as websocket:
        msg = fetch_open_orders()
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res = json.loads(res)
        return res

async def fetch_change_price(pair):
    msg = {
        "type": "REST",
        "requestId": 'uniqueID',
        "stream": "/get/public/orderbook/raw",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "market": pair,
            "limit": 20
        }
    }
    uri_ws = 'wss://plasma-relay-backend.timex.io/socket/relay'
    async with websockets.connect(uri_ws) as websocket:
        try:
            orderbook = {'bids':[], 'asks': [], 'timestamp': 0}
            await websocket.send(json.dumps(msg))
            res = await websocket.recv()
            res = json.loads(res)
            for bid in res['responseBody']['bid']:
                orderbook['bids'].append([float(bid['price']), float(bid['quantity'])])
            for ask in res['responseBody']['ask']:
                orderbook['asks'].append([float(ask['price']), float(ask['quantity'])])
            if len(orderbook['bids']) and len(orderbook['asks']):
                if 'AUDT' in pair:
                    change = 1 / ((orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2)
                else:
                    change = ((orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2)
            elif len(orderbook['bids']) and not len(orderbook['asks']):
                if 'AUDT' in pair:
                    change = 1 / (orderbook['bids'][0][0])
                else:
                    change = orderbook['bids'][0][0]
            elif not len(orderbook['bids']) and len(orderbook['asks']):
                if 'AUDT' in pair:
                    change = 1 / (orderbook['asks'][0][0])
                else:
                    change = orderbook['asks'][0][0]
            elif not len(orderbook['bids']) and not len(orderbook['asks']):
                return await fetch_change_price(pair)
        except Exception as e:
            try:
                telegram.send_first_chat(f"Error: {e}\nOrderbook: {orderbook}")
            except:
                telegram.send_emergency(f"Error: {e}\nOrderbook: {orderbook}")
            return None
        return change


async def fetch_TIMEX_data(procData, buffer_rates_TIMEX):
    i = 0
    last_len = 15000
    last_data = {'asks': None, 'bids': None}
    pair_TIMEX = procData['pair_TIMEX'].split('/')[0] + procData['pair_TIMEX'].split('/')[1]
    msg = {
        "type": "REST",
        "requestId": 'uniqueID',
        "stream": "/get/public/orderbook/raw",
        "auth": {
            "id": _api_key,
            "secret": _api_secret
        },
        "payload": {
            "market": pair_TIMEX,
            "limit": 20
        }
    }
    uri_ws = 'wss://plasma-relay-backend.timex.io/socket/relay'
    async with websockets.connect(uri_ws) as websocket:
        while True:
            orderbook = {'bids':[], 'asks': [], 'timestamp': 0}
            await websocket.send(json.dumps(msg))
            res = await websocket.recv()
            res = json.loads(res)
            for bid in res['responseBody']['bid']:
                orderbook['bids'].append([float(bid['price']), float(bid['quantity'])])
            for ask in res['responseBody']['ask']:
                orderbook['asks'].append([float(ask['price']), float(ask['quantity'])])
            orderbook['timestamp'] = res['responseBody']['timestamp']
            encoded_data = json.dumps(orderbook).encode('utf-8')
            if len(encoded_data) < last_len:
                buffer_rates_TIMEX[:15000] = bytearray([0 for x in range(15000)])
            buffer_rates_TIMEX[:len(encoded_data)] = encoded_data
            last_len = len(encoded_data)
