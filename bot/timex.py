import ccxt
import time
import datetime
import websockets
import json
import asyncio
import string
import random

from . import shm
from .db import db
from .telegram import telegram
from .config import config
from .ftx import fetch_AUD_price

offset = datetime.timedelta(hours=3)

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
            orderbook = {'bids': [], 'asks': [], 'timestamp': 0}
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


async def fetch_TIMEX_trades(proc_data, buffer_trades_TIMEX):
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


async def total_balance(proc_data):
    from . import dydx
    # try:
    start_summ = 0
    summ = 0
    cashin_cashout = 0
    main_coin = proc_data['coin']
    price_coin = proc_data['price_coin']
    changes = proc_data['changes']
    change_TIME = await fetch_change_price('TIMEUSDT')
    changes.update({'TIME': round(change_TIME, 2)})
    proc_data = dydx.coins_amounts_calc(proc_data)
    start_balance = proc_data['start_balance']
    coins_amounts = proc_data['coins_amounts']
    for coin, amount in start_balance['balances'].items():
        start_summ += amount * changes[coin]
    position_profit = start_balance['positions'][main_coin]['position'] * (changes[main_coin] - start_balance['positions'][main_coin]['price'])
    summ += coins_amounts['DYDX']['USDC']['total']
    summ += coins_amounts['TIMEX'][price_coin]['total'] * changes[price_coin]
    summ += coins_amounts['TIMEX'][main_coin]['total'] * changes[main_coin]
    total_balance_real = round(summ, 2)
    total_profit = round(summ - start_summ - position_profit, 2)
    # if abs(total_profit) / total_balance_real * 100 > 3:
    #     start_balance = start_balance_rewrite(coins_amounts, changes)
    #     cashin_cashout = total_profit
    DYDX_USD = coins_amounts['DYDX']['USDC']['total']
    TIMEX_USD = coins_amounts['TIMEX'][price_coin]['total'] * changes[price_coin] + coins_amounts['TIMEX'][main_coin]['total'] * changes[main_coin]
    return total_balance_real, total_profit, DYDX_USD, TIMEX_USD, cashin_cashout


async def execute_order(proc_data, order_type, amount, price, side, fee_amount, fee_coin):
    ticksize_DYDX = proc_data['ticksize_DYDX']
    DYDX_fee = proc_data['DYDX_fee']
    if order_type == 'MAKER':
        TIMEX_fee = proc_data['TIMEX_fee']
    else:
        TIMEX_fee = proc_data['TIMEX_taker_fee']
    TIMEX_taker_fee = proc_data['TIMEX_taker_fee']
    pair_DYDX = proc_data['pair_DYDX']
    coin = proc_data['coin']
    if proc_data['price_coin'] == 'AUDT':
        price_AUDT = price
        change_AUDT = fetch_AUD_price()
        price *= change_AUDT
    sh_rates_DYDX = proc_data['sh_rates_DYDX']
    orderbook_DYDX = shm.fetch_shared_memory(proc_data['sh_rates_DYDX'], 'DEAL')
    if side == 'BUY':
        sell_dydx_price = orderbook_DYDX['bids'][0][0] + ticksize_DYDX
        profit = (sell_dydx_price - price) / price - (TIMEX_fee + DYDX_fee)
    else:
        buy_dydx_price = orderbook_DYDX['asks'][0][0] - ticksize_DYDX
        profit = (price - buy_dydx_price) / buy_dydx_price - (DYDX_fee + TIMEX_fee)

    changes = {coin: (orderbook_DYDX['asks'][0][0] + orderbook_DYDX['bids'][0][0]) / 2, 'USDC': 1, 'USDT': 1}
    USD_amount = amount * changes[coin]
    if fee_coin == 'AUDT':
        fee_amount = fee_amount * change_AUDT
        changes.update({'AUDT': change_AUDT})
    TG_message = f"{order_type} ORDER EXECUTED\n"
    TG_message += f"Profit: {round(profit * 100, 3)}% ({round(USD_amount * profit, 2)} USD)\n"
    if side == 'BUY':
        buy_stock = 'TIMEX'
        sell_stock = 'DYDX'
        buy_price = price
        sell_price = sell_dydx_price
        TG_message += f"Buy stock: {buy_stock}\n"
        TG_message += f"Buy price: {price}\n"
        if proc_data['price_coin'] == 'AUDT':
            TG_message += f"Buy price, AUDT: {price_AUDT}\n"
        TG_message += f"Sell stock: {sell_stock}\n"
        TG_message += f"Sell price: {sell_price}\n"
    else:
        buy_stock = 'DYDX'
        sell_stock = 'TIMEX'
        sell_price = price
        buy_price = buy_dydx_price
        TG_message += f"Buy stock: {buy_stock}\n"
        TG_message += f"Buy price: {buy_price}\n"
        TG_message += f"Sell stock: {sell_stock}\n"
        TG_message += f"Sell price: {sell_price}\n"
        if proc_data['price_coin'] == 'AUDT':
            TG_message += f"Sell price, AUDT: {price_AUDT}\n"
    TG_message += f"Deal amount:\n{amount} {coin}\n"
    TG_message += f"({USD_amount} USD)\n"
    TG_message += f"Fee: {fee_amount} USD\n"
    if proc_data['price_coin'] == 'AUDT':
        TG_message += f"Change price AUDT/USDT: {changes['AUDT']}\n"
    try:
        telegram.send_first_chat('<pre>' + TG_message + '</pre>', parse_mode='HTML')
    except:
        pass
    proc_data['changes'] = changes
    total_balance_real, total_profit, DYDX_USD, TIMEX_USD, cashin_cashout = await total_balance(proc_data)
    to_base = {'TIMEX_USD': TIMEX_USD,
               'DYDX_USD': DYDX_USD,
               'buy_exchange': buy_stock,
               'buy_price': buy_price,
               'sell_exchange': sell_stock,
               'sell_price': sell_price,
               'deal_amount': round(amount, 8),
               'deal_amount_USD': USD_amount,
               'deal_datetime': str(datetime.datetime.now(datetime.timezone(offset))).split('.')[0],
               'profit_perc': round(profit * 100, 3),
               f'profit_abs_{coin}': round(amount * profit, 6),
               'profit_abs_USD': round(USD_amount * profit, 2),
               'deal_type': order_type,
               'total_profit': total_profit,
               'total_balance_real': total_balance_real,
               'cashin_cashout': cashin_cashout}
    db.sql_add_new_order_buy(to_base)


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


def coins_amounts_calc(proc_data):
    from . import dydx
    coin = proc_data['coin']
    price_coin = proc_data['price_coin']

    changes = proc_data['changes']
    coins_amounts = {'DYDX': {'positions': {}}, 'TIMEX': {}}
    balance_TIMEX = None
    balance_DYDX = None
    while not balance_TIMEX:
        try:
            balance_TIMEX = bot_TIMEX.fetchBalance()
        except:
            pass
    while not balance_DYDX:
        try:
            balance_DYDX = dydx.get_account_data()
        except:
            pass
    proc_data = dydx.pnl_diff_fetch(proc_data, balance_DYDX=balance_DYDX)
    # TIMEX COINS UPDATE
    coins_amounts['TIMEX'].update({price_coin: {'free': round(float(balance_TIMEX[price_coin]['free'])), 'total': round(float(balance_TIMEX[price_coin]['total']))}})
    coins_amounts['TIMEX'].update({coin: {'free': float(balance_TIMEX[coin]['free']), 'total': float(balance_TIMEX[coin]['total'])}})
    coins_amounts['TIMEX'].update({'TIME': {'free': float(balance_TIMEX['TIME']['free']), 'total': float(balance_TIMEX['TIME']['total'])}})
    # DYDX COINS UPDATE
    #BALANCE DYDX:
    # {'account': {'starkKey': '0121fec581fb1851ccca9a412cf0df7afa99a989062bcf89f5494cf669567ebf', 'positionId': '150947',
    # 'equity': '1678.323904', 'freeCollateral': '1676.375642', 'pendingDeposits': '0.000000', 'pendingWithdrawals': '0.000000',
    #     'openPositions':
    #         {'BTC-USD': {'market': 'BTC-USD', 'status': 'OPEN', 'side': 'SHORT', 'size': '-0.001', 'maxSize': '-0.001',
    #         'entryPrice': '48749.000000', 'exitPrice': '0.000000', 'unrealizedPnl': '0.002840', 'realizedPnl': '0.000000',
    #         'createdAt': '2021-12-22T23:25:53.199Z', 'closedAt': None, 'sumOpen': '0.001', 'sumClose': '0', 'netFunding': '0'}},
    # 'accountNumber': '0', 'id': 'b288bad8-0216-5c44-8b30-f4699387c7dd', 'quoteBalance': '1727.030454', 'createdAt': '2021-12-01T09:29:38.279Z'}}
    coins_amounts['DYDX'].update({'USDC': {'free': float(balance_DYDX['account']['freeCollateral']), 'total': float(balance_DYDX['account']['equity'])}})
    if balance_DYDX['account']['openPositions'].get(proc_data['pair_DYDX']):
        DYDX_position = float(balance_DYDX['account']['openPositions'][proc_data['pair_DYDX']]['size'])
    else:
        DYDX_position = 0
    coins_amounts['DYDX']['positions'].update({proc_data['coin']: {'position': DYDX_position, 'liq_price': 0}})
    proc_data['coins_amounts'] = coins_amounts
    proc_data['changes'] = changes
    return proc_data
