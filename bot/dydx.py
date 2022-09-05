from dydx3 import Client
from dydx3.constants import API_HOST_MAINNET
from dydx3.constants import NETWORK_ID_MAINNET
import json
from web3 import Web3


with open("dydx_keys.json", "r") as file:
    keys = json.load(file)

STARK_KEY_PAIRS = keys['STARK_KEY_PAIRS']

API_KEY_PAIRS = keys['API_KEY_PAIRS']

eth_private_key = keys['eth_private_key']
eth_address = keys['eth_address']
infura_key = keys['infura_key']

uri_ws = 'wss://api.dydx.exchange/v3/ws'
uri_api = 'https://api.dydx.exchange'

WEB_PROVIDER_URL = f'https://mainnet.infura.io/v3/{infura_key}'
w3 = Web3(Web3.WebsocketProvider(f'wss://mainnet.infura.io/ws/v3/{infura_key}'))

client = Client(
    network_id=NETWORK_ID_MAINNET,
    host=API_HOST_MAINNET,
    default_ethereum_address=eth_address,
    web3=w3, #Web3(Web3.HTTPProvider(WEB_PROVIDER_URL)),
    eth_private_key=eth_private_key,
    stark_private_key=STARK_KEY_PAIRS['privateKey'],
    stark_public_key=STARK_KEY_PAIRS['publicKey'],
    stark_public_key_y_coordinate=STARK_KEY_PAIRS['publicKeyYCoordinate'],
    web3_provider=WEB_PROVIDER_URL,
    api_key_credentials=API_KEY_PAIRS
)

public_client = Client(
    host=API_HOST_MAINNET,
)
