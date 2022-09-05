import json
import string
import random


def id_generator(size=12, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def creating_procData(dydx, bot_TIMEX):
    user = dydx.client.private.get_user().data
    pair_DYDX = 'ETH-USD'
    pair_TIMEX = 'ETH/AUDT'
    coin = 'ETH'
    price_coin = 'AUDT'
    markets_DYDX = None
    markets_TIMEX = None
    while not markets_DYDX or not markets_TIMEX:
        try:
            markets_DYDX = dydx.public_client.public.get_markets()
            markets_TIMEX = bot_TIMEX.load_markets()
        except:
            pass
    try:
        with open('/home/ubuntu/balance.json', 'r') as file:
            start_balance = json.load(file)
    except:
        with open('/home/ubuntu/balance.json', 'w') as file:
            json.dump('', file)
        start_balance = None
    procData = {'i': 0,
                'proc_name': None,
                'sh_rates_TIMEX': None,
                'sh_rates_DYDX': None,
                'sh_trades_TIMEX': None,
                'min_amount': None,
                'max_amount': None,
                'start_balance': start_balance,
                'coins_amounts': None,
                'last_date_report': 0,
                'changes': {},
                'TIMEX_fee': markets_TIMEX[pair_TIMEX]['maker'],
                'TIMEX_taker_fee': markets_TIMEX[pair_TIMEX]['taker'],
                'DYDX_fee': float(user['user']['makerFeeRate']),
                'DYDX_taker_fee': float(user['user']['takerFeeRate']),
                'report_sender': None,
                'takers_only': False,
                'ticksize_DYDX': float(markets_DYDX.data['markets'][pair_DYDX]['tickSize']),
                'stepsize_DYDX': float(markets_DYDX.data['markets'][pair_DYDX]['stepSize']),
                'ticksize_TIMEX': float(markets_TIMEX[pair_TIMEX]['precision']['price']),
                'stepsize_TIMEX': float(markets_TIMEX[pair_TIMEX]['precision']['amount']),
                'target_position': 0,
                'maker_positions': [],
                'disbalanses': [],
                'max_buy_DYDX': None,
                'max_sell_DYDX': None,
                'buy_profits': {'taker': 0, 'maker': 0},
                'sell_profits': {'taker': 0, 'maker': 0},
                'orderbook_TIMEX': None,
                'orderbook_DYDX': None,
                'min_profit': None,
                'buy_proc': None,
                'depth': 20,
                'depth_taker': 20,
                'order_TIMEX_info': None,
                'pair_DYDX': pair_DYDX,
                'pair_TIMEX': pair_TIMEX,
                'coin': coin,
                'price_coin': price_coin,
                'pnl_diff': None,
                'position_side': None, #!!! END IT!
                'pnl_changed_diff': {
                    'cumulative_profit': 0,
                    'times_changed_side': 0}  #DYDX SIDE
                }
    return procData


procData = creating_procData()
