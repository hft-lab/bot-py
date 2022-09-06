from dydx3 import Client
from dydx3.constants import API_HOST_MAINNET
from dydx3.constants import NETWORK_ID_MAINNET
import json
import time
from web3 import Web3
from .config import config


conf = config["DYDX"]

api_key_credentials = {
    "secret": conf["api_key_secret"],
    "key": conf["api_key"],
    "passphrase": conf["api_passphrase"],
}

eth_private_key = conf['eth_private_key']

uri_ws = 'wss://api.dydx.exchange/v3/ws'
uri_api = 'https://api.dydx.exchange'

WEB_PROVIDER_URL = f'https://mainnet.infura.io/v3/{conf["infura_key"]}'
w3 = Web3(Web3.WebsocketProvider(f'wss://mainnet.infura.io/ws/v3/{conf["infura_key"]}'))

client = Client(
    network_id=NETWORK_ID_MAINNET,
    host=API_HOST_MAINNET,
    default_ethereum_address=conf['default_ethereum_address'],
    web3=w3,  # Web3(Web3.HTTPProvider(WEB_PROVIDER_URL)),
    eth_private_key=eth_private_key,
    stark_private_key=conf['stark_private_key'],
    stark_public_key=conf['stark_public_key'],
    stark_public_key_y_coordinate=conf['stark_public_key_y_coordinate'],
    web3_provider=WEB_PROVIDER_URL,
    api_key_credentials=api_key_credentials,
)

public_client = Client(
    host=API_HOST_MAINNET,
)


def create_order(procData, price, amount, side, order_type ='LIMIT'):
    ticksize_DYDX = procData['ticksize_DYDX']
    stepsize_DYDX = procData['stepsize_DYDX']
    pair_DYDX = procData['pair_DYDX']
    if '.' in str(stepsize_DYDX):
        round_amount_len = len(str(stepsize_DYDX).split('.')[1])
    else:
        round_amount_len = 0
    amount = str(round(amount - (amount % stepsize_DYDX), round_amount_len))
    if '.' in str(ticksize_DYDX):
        round_price_len = len(str(ticksize_DYDX).split('.')[1])
    else:
        round_price_len = 0
    price = round(price, round_price_len)
    price = str(round(price - (price % ticksize_DYDX), round_price_len))
    position_id = '208054'
    cancelId = None
    # if order_type == 'LIMIT':
    #     orderbook_DYDX = fetch_shared_memory(procData['sh_rates_DYDX'], 'DEAL')
    #     if side == 'SELL' and orderbook_DYDX['bids'][0][0] >= float(price):
    #         return None
    #     elif side == 'BUY' and orderbook_DYDX['asks'][0][0] <= float(price):
    #         return None
    expire_date = int(time.time() + 86000)
    placed_order = client.private.create_order(
        position_id=position_id,  # required for creating the order signature
        market=pair_DYDX,
        side=side,
        order_type='LIMIT',
        post_only=False,
        size=amount,
        price=price,
        limit_fee='0.0008',
        expiration_epoch_seconds=expire_date,
        time_in_force='GTT',
    )
    # PLACED ORDER RESPONSE
    # {'order': {'id': '2d1bea98cc71d28a122151851ea5d1c63dc3c5696bc7461ba9ca9ce4d30d47e', 'clientId': '25203841864648536',
    # 'accountId': 'b288bad8-0216-5c44-8b30-f4699387c7dd', 'market': 'BTC-USD', 'side': 'SELL', 'price': '150000', 'triggerPrice': None,
    # 'trailingPercent': None, 'size': '0.001', 'remainingSize': '0.001', 'type': 'LIMIT', 'createdAt': '2021-12-23T15:33:12.413Z',
    # 'unfillableAt': None, 'expiresAt': '2021-12-24T15:26:32.000Z', 'status': 'PENDING', 'timeInForce': 'GTT', 'postOnly': False,
    # 'cancelReason': None}}
    return placed_order.data


def get_account_data():
    return client.private.get_account().data


def cancel_all_orders(**kwargs):
    return client.private.cancel_all_orders(**kwargs)


def get_orderbook(**kwargs):
    return public_client.public.get_orderbook(**kwargs).data


def get_funding_payments(**kwargs):
    return client.private.get_funding_payments(**kwargs)