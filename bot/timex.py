import ccxt
import time
import datetime
import websockets
import json
import asyncio
import string
import random

from .telegram import telegram
from .config import config

URI_WS = 'wss://plasma-relay-backend.timex.io/socket/relay'

_api_key = config["TIMEX"]["api_key"]
_api_secret = config["TIMEX"]["api_secret"]

bot_TIMEX = ccxt.timex({
    'apiKey': _api_key,
    'secret': _api_secret,
    'enableRateLimit': True})

bot_TIMEX_public = ccxt.timex({'enableRateLimit': True})


def id_generator(size=12, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


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
    async with websockets.connect(URI_WS) as websocket:
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
    async with websockets.connect(URI_WS) as websocket:
        msg = msg_for_cancel(order_id)
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res_cancel = json.loads(res)
        return res_cancel


async def update_ws_order(data):
    async with websockets.connect(URI_WS) as websocket:
        msg = update_order(data)
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res_update = json.loads(res)
        return res_update


async def create_ws_order(data):
    async with websockets.connect(URI_WS) as websocket:
        msg = msg_for_create_order(data)
        await websocket.send(json.dumps(msg))
        res = await websocket.recv()
        res_create = json.loads(res)
        return res_create


async def fetchOpenOrders():
    async with websockets.connect(URI_WS) as websocket:
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
    async with websockets.connect(URI_WS) as websocket:
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
    async with websockets.connect(URI_WS) as websocket:
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


async def fetch_TIMEX_trades(proc_data, execute_order, buffer_trades_TIMEX):
    pair_TIMEX = ''.join(proc_data['pair_TIMEX'].split('/'))
    last_len = 400
    flag = True
    async with websockets.connect(URI_WS) as websocket:
        while True:
            msg = get_trades()
            await websocket.send(json.dumps(msg))
            res_trades = await websocket.recv()
            res_trades = json.loads(res_trades)
            if flag:
                last_trade = res_trades['responseBody']['trades'][0]
                encoded_data = json.dumps(last_trade).encode('utf-8')
                buffer_trades_TIMEX[:len(encoded_data)] = encoded_data
                flag = False
            for trade in res_trades['responseBody']['trades']:
                if trade == last_trade:
                    break
                if trade['symbol'] == pair_TIMEX:
                    price = float(trade['price'])
                    side = trade['side']
                    amount = float(trade['quantity'])
                    fee_amount = float(trade['fee'])
                    order_type = trade['makerOrTaker']
                    fee_coin = trade['feeToken']
                    await execute_order(proc_data, order_type, amount, price, side, fee_amount, fee_coin)
                    encoded_data = json.dumps(last_trade).encode('utf-8')
                    if len(encoded_data) < last_len:
                        buffer_trades_TIMEX[:400] = bytearray([0 for x in range(400)])
                    buffer_trades_TIMEX[:len(encoded_data)] = encoded_data
                    last_len = len(encoded_data)
            last_trade = res_trades['responseBody']['trades'][0]


def start_proc_hack_TIMEX(proc_data, buffer_rates_TIMEX):
    name = f'WS_orderbook_TIMEX_{proc_data["coin"]}'
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(fetch_TIMEX_data(proc_data, buffer_rates_TIMEX))
        except Exception as e:
            try:
                telegram.send_third_chat(f"Process: {name}\nTrace:\n {e}")
            except:
                pass
