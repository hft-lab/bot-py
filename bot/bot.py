# -*- coding: utf-8 -*-

from multiprocessing import Process, shared_memory
import re
import sys, os
from . import db as db_t
from . import common
from .ftx import bot_FTX_public
from .timex import *
from . import dydx

db = db_t.DB()

offset = datetime.timedelta(hours=3)
datetime.timezone(offset)

# with open('/home/ubuntu/keys_binance.txt', 'r', encoding = 'UTF-8') as db:
#     m = db.read().split('\n')
# api_key = m[0].split("'")[1]
# api_secret = m[1].split("'")[1]

# bot_binance_pro = ccxtpro.binanceusdm({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})


def return_string_price(price):
    if 'e' in str(price):
        price = str(price)
        try:
            parts = re.search(r'\.(\d+)e.(\d+)', price)
        except Exception as e:
            return float(price)
        res = len(parts.group(1))
        exp = int(parts.group(2)) + res
        return "{:.{exp}f}".format(float(price), exp=exp)
    else:
        return price


def create_balance_message(proc_data):
    start_summ = 0
    summ_TIMEX = 0
    total_summ = 0
    start_balance = proc_data['start_balance']
    main_coin = proc_data['coin']
    price_coin = proc_data['price_coin']
    changes = proc_data['changes']
    coins_amounts = proc_data['coins_amounts']
    PNL_profit = proc_data['pnl_changed_diff']['cumulative_profit'] - start_balance['pnl_start']
    for coin, amount in start_balance['balances'].items():
        if coin == 'USDC':
            continue
        if 'USD' in coin:
            start_summ += amount
            continue
        start_summ += amount * changes[coin]
    if start_balance['positions'].get(main_coin):
        position_profit = start_balance['positions'][main_coin]['position'] * (changes[main_coin] - start_balance['positions'][main_coin]['price'])
    else:
        position_profit = 0

    message = 'Balance TIMEX\n'
    message += 'Coin  Free   Total  USD\n\n'
    for coin in [price_coin, main_coin, 'TIME']:
        if coin in ['USDT', 'USDC', 'AUDT']:
            round_len = 0
        else:
            round_len = 3
        coin_len = 6 - len(coin)
        free_amount_len = 7 - len(str(round(coins_amounts['TIMEX'][coin]['free'], round_len)))
        total_amount_len = 7 - len(str(round(coins_amounts['TIMEX'][coin]['total'], round_len)))
        message += f"{coin}" + ' ' * coin_len + f"{round(coins_amounts['TIMEX'][coin]['free'], round_len)}" #FREE COINS AMOUNT
        message += ' ' * free_amount_len + f"{round(coins_amounts['TIMEX'][coin]['total'], round_len)}" #TOTAL COINS AMOUNT
        message += ' ' * total_amount_len + f"{round(coins_amounts['TIMEX'][coin]['total'] * changes[coin])}\n" #RECOUNTED IN USD
        summ_TIMEX += coins_amounts['TIMEX'][coin]['total'] * changes[coin]
    total_summ += summ_TIMEX
    message += '\nBalance DYDX\n'
    message += 'Coin  Free   Total  USD\n\n'
    for coin, amount in coins_amounts['DYDX'].items():
        if coin == 'positions':
            continue
        coin_len = 6 - len(coin)
        free_amount_len = 7 - len(str(round(amount['free'])))
        total_amount_len = 7 - len(str(round(amount['total'])))
        message += f"{coin}" + ' ' * coin_len + f"{round(amount['free'])}"
        message += ' ' * free_amount_len + f"{round(amount['total'])}" + ' ' * total_amount_len + f"{round(amount['total'])}\n"
        total_summ += amount['total']

    message += f'\n\nTotal: {round(total_summ, 2)} USD'
    message += f'\nProfit: {round(summ_TIMEX - start_summ - position_profit + PNL_profit, 2)} USD\n'
    message += f"\nInd price: {round(changes[main_coin], 4)}"
    if coins_amounts['DYDX']['positions'][main_coin]['position']:
        liq_koef = round(coins_amounts['DYDX']['USDC']['total'] / (coins_amounts['DYDX']['positions'][main_coin]['position'] * changes[main_coin]), 4)
        liq_price = round(changes[main_coin] - (changes[main_coin] * liq_koef * 0.9), 2)
    else:
        liq_price = 0
    # message += f"\nLiq. price DYDX: {round(coins_amounts['DYDX']['positions'][coin]['liq_price'], 2)}"
    message += f"\nLiq. price DYDX: {liq_price}"
    message += f"\n{main_coin} TIMEX pos.: {round(coins_amounts['TIMEX'][main_coin]['total'], 4)}"
    message += f"\n{main_coin} DYDX pos.: {round(coins_amounts['DYDX']['positions'][main_coin]['position'], 4)}"
    message += f"\n{main_coin} tot. pos.:"
    message += f"{round(coins_amounts['DYDX']['positions'][main_coin]['position'] + coins_amounts['TIMEX'][main_coin]['total'], 2)}"
    return message


def everyday_check(proc_data, coins_amounts, changes, start_balance, coin):
    # try:
    disbalanses = proc_data['disbalanses']
    last = db.get_orders_res()
    now_total_balance = 0
    now_time_stamp = time.time()
    price_coin = proc_data['price_coin']
    TIMEX_taker_fee = proc_data['TIMEX_taker_fee']
    TIMEX_fee = proc_data['TIMEX_fee']
    last_day = str(datetime.datetime.utcfromtimestamp(now_time_stamp - 86400).strftime('%Y-%m-%d %H:%M')).split('-')[2].split(' ')[0]
    now_total_balance += coins_amounts['DYDX']['USDC']['total']
    now_total_balance += coins_amounts['TIMEX'][price_coin]['total'] * changes[price_coin]
    now_total_balance += coins_amounts['TIMEX'][coin]['total'] * changes[coin]
    now_total_balance += coins_amounts['TIMEX']['TIME']['total'] * changes['TIME']
    position_profit = start_balance['positions'][coin]['position'] * (changes[coin] - start_balance['positions'][coin]['price'])
    count_deals = 0
    total_cashflow = 0
    max_deal = 0
    theor_profit = 0
    tick_count = 0
    last_tick = 0
    takers = 0
    makers = 0
    total_cashin_cashout = 0
    total_fee_TIMEX_paid = 0
    for record in last[::-1]:
        start_price = record[2]        
        last_total_balance = record[16]
        total_cashin_cashout += record[17]
        if record[1] == 'Daily report':
            break
        if int(record[7].split(' ')[1].split(':')[0]) < 9 and record[7].split(' ')[0].split('-')[2] == last_day:
            break
        if 'TAKER' == record[11]:
            takers += 1
            total_fee_TIMEX_paid += record[6] * TIMEX_taker_fee
        else:
            makers += 1
            total_fee_TIMEX_paid += record[6] * TIMEX_fee
        if record[6] > max_deal:
            max_deal = record[6]
        theor_profit += record[10]
        count_deals += 1
        total_cashflow += record[6] * 2
    main_coin_profit = round((coins_amounts['TIMEX'][coin]['total'] - start_balance['balances'][coin]) * changes[coin])
    USD_profit = round((coins_amounts['TIMEX'][price_coin]['total'] - start_balance['balances'][price_coin]) * changes[price_coin])
    TIME_profit = round((coins_amounts['TIMEX']['TIME']['total'] - start_balance['balances']['TIME']) * changes['TIME'])
    PNL_profit = proc_data['pnl_changed_diff']['cumulative_profit'] - start_balance['pnl_start']

    funding_payments = dydx.get_funding_payments(market=proc_data['pair_DYDX'], limit=24)
    total_payments_DYDX = 0
    for payment in funding_payments.data['fundingPayments']:
        total_payments_DYDX += float(payment['payment'])

    # TIMEX_cashback = 0.000109

    trade_profit = USD_profit - position_profit + main_coin_profit + PNL_profit + TIME_profit
    # trade_profit = SNX_profit * changes[coin] + USD_profit + USDN_profit / changes['USDN'] + TIMEX_cashback * total_cashflow / 2

    message = f'#TIMEX\n'
    message += f"Daily report {coin}/{price_coin} for:\n{str(datetime.datetime.now(datetime.timezone(offset))).split('.')[0]}\n"
    message += '---------------------------\n'
    message += f"Trade profits:\n"
    message += f"Total, USD: {round(trade_profit, 2)}\n"
    message += f"Total, %: {round(trade_profit / last_total_balance * 100, 4)}\n"
    message += f"Theory profit, USD: {round(theor_profit, 2)}\n"
    message += f"Last 24h payments DYDX, USD: {round(total_payments_DYDX, 2)}\n"
    message += f"Total payments for last 24h, USD: {round(total_payments_DYDX, 2)}\n"
    message += f"TIME fee refund: {TIME_profit} USD\n"
    message += f"TIMEX fee paid: {total_fee_TIMEX_paid} USD\n"
    message += '---------------------------\n'
    message += f"Balances:\nUSD, start: {last_total_balance}\n"
    message += f"Cashin/cashout: {total_cashin_cashout}\n"
    message += f"USD, end: {now_total_balance}\n"
    message += f"{coin}, start: {start_balance['positions'][coin]['position']}\n"
    message += f"{coin}, end: {coins_amounts['DYDX']['positions'][coin]['position'] + coins_amounts['TIMEX'][coin]['total']}\n"
    # message += '---------------------------\n'
    # message += f"Real crypto balance, SNX: {(coins_amounts['DYDX']['USDN']['total'] / changes['USDN'] + coins_amounts['DYDX']['USD']['total']) / changes[coin] + coins_amounts['DYDX'][coin]['total']}\n"
    message += '---------------------------\n'
    message += f"Prices:\n{coin} start, USD: {start_price}\n"
    message += f"{coin} end, USD: {changes[coin]}\n"
    message += f"Day CF, USD: {round(total_cashflow, 2)}\n"
    message += f"Day deals: {count_deals}\n"
    message += f"Taker deals: {takers}\n"
    message += f"Maker deals: {makers}\n"
    message += f"Biggest deal, USD: {round(max_deal, 2)}\n"
    message += '---------------------------\n' 
    message += f"Average deal values:\n"
    message += f"Amount, USD: {round(total_cashflow / count_deals / 2, 2)}\n"
    message += f"Profit, %: {round(trade_profit / total_cashflow * 2 * 100, 4)}\n"
    message += f"Profit, USD: {round(trade_profit / count_deals, 4)}\n" 
    message += '---------------------------\n' 
    message += f"CF / balance: {round(total_cashflow / now_total_balance, 4)}\n"
    # message += '---------------------------\n'
    # message += f'Av. makers positions:\n'
    # message += f"SNX/USDN: {round(sum(maker_positions) / len(maker_positions), 2)}\n"
    total_deals = 0
    total_cashflow = 0
    loss_deals = 0
    deals_loss = []
    deals_theor_loss = []
    loss_deals_cashflow = 0
    total_theor_profit = 0

    for record in last[::-1]:  
        if record[1] == 'Daily report':
            break
        if int(record[7].split(' ')[1].split(':')[0]) < 9 and record[7].split(' ')[0].split('-')[2] == last_day:
            break
        deal_profit = record[10]
        total_theor_profit += record[10]
        total_deals += 1
        total_cashflow += record[6]
        if deal_profit < 0:
            deals_theor_loss.append(record[8])
            deals_loss.append(record[10])
            loss_deals += 1
            loss_deals_cashflow += record[6]

    start_date = last[0][7]
    end_date = last[-1][7]
    total_cashin_cashout = 0
    end_balance = last[-1][16]
    start_USD_balance = last[0][16]
    for record in last[::-1]:  
        total_cashin_cashout += record[17]
    max_deal_theor = 0
    for deal in deals_theor_loss:
        if max_deal_theor > deal:
            max_deal_theor = deal
    max_deal = 0
    for deal in deals_loss:
        if max_deal > deal:
            max_deal = deal
    message += '---------------------------\n' 
    message += f"Start date: {start_date}\n"
    message += f"End date: {end_date}\n"
    message += f"Total profit: {round(end_balance - start_USD_balance - total_cashin_cashout, 2)}\n"
    message += '---------------------------\n' 
    message += f"Negative deals statistic:\nTotal loss deals: {loss_deals}\nTotal deals: {total_deals}\n"
    message += f"Max loss, USD: {max_deal}\n"
    try:
        message += f"Av. loss, %: {round(sum(deals_theor_loss) / len(deals_theor_loss), 4)}\n"
    except:
        message += f"Av. loss, %: 0\n"
    message += f"Max loss, %: {round(max_deal_theor, 2)}\n"
    try:
        message += f"Loss/profit deals, %: {round(loss_deals / total_deals * 100, 2)}\n"
        message += f"Loss/profit cashflow, %: {round(loss_deals_cashflow / total_cashflow * 100, 2) }\n"
    except:
        message += f"Loss/profit deals, %: 0\n"
        message += f"Loss/profit cashflow, %: 0\n"        
    message += f"Total cashflow, USD: {round(total_cashflow, 2)}\n"
    message += f"Loss deals cashflow, USD: {round(loss_deals_cashflow, 2)}\n"
    try:
        message += f"Av. loss deal amount, USD: {round(loss_deals_cashflow / loss_deals)}\n"
    except:
        message += f"Av. loss deal amount, USD: 0\n"
    message += f"Total loss, USD: {round(sum(deals_loss), 2)}\n"
    message += f"Total theor profit, USD: {round(total_theor_profit, 2)}\n"
    dis_sum = 0
    dis_loss = 0
    dis_max_loss = 0
    for dis in disbalanses:
        dis_sum += dis[0]
        dis_loss += abs(dis[0] * dis[1])
        if dis_max_loss < dis[0] * dis[1]:
            dis_max_loss = dis[0] * dis[1]
    message += f"Disbalanses: {len(disbalanses)}\n"
    message += f"Disbalanse sum, USD: {round(dis_sum * changes[coin], 2)}\n"
    message += f"Disbalanses total loss, USD: {round(dis_loss, 2)}\n"
    message += f"Disblance max loss, USD: {round(dis_max_loss, 2)}\n"
    message += f"Position side changes: {proc_data['pnl_changed_diff']['times_changed_side']}\n"
    total_profit = total_payments_DYDX + theor_profit - dis_loss
    message += '---------------------------\n'
    message += f"Total real profit, USD: {total_profit}\n"
    message += f"PNL profit, USD: {proc_data['pnl_changed_diff']['cumulative_profit'] - start_balance['pnl_start']}"
    try:
        telegram.send_second_chat('<pre>' + message + '</pre>', parse_mode='HTML')
    except:
        try:
            time.sleep(1)
            telegram.send_second_chat('<pre>' + message + '</pre>', parse_mode='HTML')
        except:
            pass
    to_base = {'TIMEX_USD': 0,
                'DYDX_USD': 0,
                'buy_exchange': 'Daily report',
                'buy_price': changes[coin],
                'sell_exchange': 'Daily report',
                'sell_price': changes[coin],
                'deal_amount': 0,
                'deal_amount_USD': 0,
                'deal_datetime': 'Daily report',
                'profit_perc': 0,
                f'profit_abs_{coin}': 0,
                'profit_abs_USD': 0,
                'deal_type': 'Daily report',
                'total_profit': 0,
                'total_balance_real': now_total_balance,
                'cashin_cashout': 0}
    db.sql_add_new_order_buy(to_base)
    # except Exception as e:
    #     exc_type, exc_obj, exc_tb = sys.exc_info()
    #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #     try:
    #         telegram_bot.send_message(chat_id, f"#TIMEX\nBot {procData['pair_DYDX']} crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
    #         # print(f"Bot {procData['proc_name']} crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
    #     except:
    #         pass
     

async def total_balance(proc_data):
    # try:
    start_summ = 0
    summ = 0
    cashin_cashout = 0 
    main_coin = proc_data['coin']
    price_coin = proc_data['price_coin']
    changes = proc_data['changes']
    change_TIME = await fetch_change_price('TIMEUSDT')
    changes.update({'TIME': round(change_TIME, 2)})   
    proc_data = coins_amounts_calc(proc_data)
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
    # except Exception as e:
    #     exc_type, exc_obj, exc_tb = sys.exc_info()
    #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #     try:
    #         # telegram_bot.send_message(chat_id, f"#TIMEX\nBot crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
    #     except:
    #         pass


def check_target_profits(max_sell_DYDX, max_buy_DYDX):
    # total balance:
    # leverage = x3
    # for_takers = x0.5
    # coins_in_list = x1
    # buy_ : TIMEX buy -> DYDX sell
    # sell_ : DYDX buy -> TIMEX sell
    # sell_TIMEX_profits = {'taker': 0.001, 'maker': 0.001}
    # buy_TIMEX_profits = {'taker': 0.001, 'maker': 0.001}    
    stake_side_koef = max_buy_DYDX / max_sell_DYDX
    if stake_side_koef > 10:
        sell_TIMEX_profits = {'taker': 0.001, 'maker': 0.001}
        buy_TIMEX_profits = {'taker': 0, 'maker': 0}
    elif 10 > stake_side_koef > 5:
        sell_TIMEX_profits = {'taker': 0.0008, 'maker': 0.0008}
        buy_TIMEX_profits = {'taker': 0, 'maker': 0}
    elif 5 > stake_side_koef > 2:
        sell_TIMEX_profits = {'taker': 0.0005, 'maker': 0.0005}
        buy_TIMEX_profits = {'taker': 0.0001, 'maker': 0.0001}
    elif 2 > stake_side_koef > 0.5:
        sell_TIMEX_profits = {'taker': 0.0005, 'maker': 0.0005}
        buy_TIMEX_profits = {'taker': 0.0005, 'maker': 0.0005}
    elif 0.5 > stake_side_koef > 0.2:
        sell_TIMEX_profits = {'taker': 0.0001, 'maker': 0.0001}
        buy_TIMEX_profits = {'taker': 0.0005, 'maker': 0.0005}
    elif 0.2 > stake_side_koef > 0.1:
        sell_TIMEX_profits = {'taker': 0, 'maker': 0}
        buy_TIMEX_profits = {'taker': 0.0008, 'maker': 0.0008}
    elif stake_side_koef < 0.1:
        sell_TIMEX_profits = {'taker': 0, 'maker': 0}
        buy_TIMEX_profits = {'taker': 0.001, 'maker': 0.001}
    return buy_TIMEX_profits, sell_TIMEX_profits


def fetch_error_coins_calc(procData):
    try:
        procData = coins_amounts_calc(procData)
    except:
        fetch_error_coins_calc(procData)
        pass
    return procData


def check_max_amounts(proc_data, daily_report=False, pos_balancing=False, line=0):
    # try:
    coin = proc_data['coin']
    price_coin = proc_data['price_coin']
    start_balance = proc_data['start_balance']
    changes = proc_data['changes']
    max_amount = proc_data['max_amount']
    report_sender = proc_data['report_sender']
    proc_name = proc_data['proc_name']
    sh_rates_TIMEX = proc_data['sh_rates_TIMEX']
    fetch_error_coins_calc(proc_data)
    coins_amounts = proc_data['coins_amounts']
    if pos_balancing:
        balancing_TIMEX(proc_data)
        fetch_error_coins_calc(proc_data)
    coins_amounts = proc_data['coins_amounts']
    max_buy_DYDX = coins_amounts['TIMEX'][coin]['total'] * changes[coin] / 2
    max_sell_DYDX = coins_amounts['TIMEX'][price_coin]['total'] * changes[price_coin] / 2
    
    inlimited_max_sell = max_sell_DYDX if max_sell_DYDX > 0 else 1
    unlimited_max_buy = max_buy_DYDX if max_buy_DYDX > 0 else 1
    
    max_buy_DYDX = unlimited_max_buy if unlimited_max_buy < max_amount * changes[coin] else max_amount * changes[coin]
    max_sell_DYDX = inlimited_max_sell if inlimited_max_sell < max_amount * changes[coin] else max_amount * changes[coin]
    proc_data['max_sell_DYDX'] = max_sell_DYDX
    proc_data['max_buy_DYDX'] = max_buy_DYDX
    # buy_profits, sell_profits = check_target_profits(inlimited_max_sell_TIMEX, unlimited_max_buy_TIMEX)
    if not start_balance:
        start_balance = start_balance_rewrite(proc_data, coin, coins_amounts, changes)
        proc_data['start_balance'] = start_balance
    if report_sender:
        message = create_balance_message(proc_data)
        message += f"\nProcess sender: {proc_name}"
        if line:
            message += f"\nLine: {line}"
        try:
            open_orders = asyncio.get_event_loop().run_until_complete(fetchOpenOrders())
            orderbook = fetch_shared_memory(sh_rates_TIMEX, 'DEAL')
        except:
            open_orders = None
        buyOrders = 0
        sellOrders = 0
        if open_orders:
            for order in open_orders['responseBody']['orders']:
                if order['side'] == 'BUY':
                    buyOrders += 1
                    message += f"\nBuy.P: {order['price']} BB: {orderbook['bids'][0][0]}"
                else:
                    sellOrders += 1
                    message += f"\nSell.P: {order['price']} BA: {orderbook['asks'][0][0]}"
        if sellOrders > 1 or buyOrders > 1:
            for order in open_orders['responseBody']['orders']:
                asyncio.get_event_loop().run_until_complete(cancel_ws_order(order['id'])) 
        if daily_report:
            everyday_check(proc_data, coins_amounts, changes, start_balance, coin)
            time.sleep(5)
            proc_data['start_balance'] = start_balance_rewrite(proc_data, coin, coins_amounts, changes)
        else:
            try:
                telegram.send_first_chat('<pre>' + message + '</pre>', parse_mode='HTML')
            except:
                telegram.send_emergency('<pre>' + message + '</pre>', parse_mode='HTML')
    return proc_data
    # except Exception as e:
    #     exc_type, exc_obj, exc_tb = sys.exc_info()
    #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #     try:
    #         telegram_bot.send_message(chat_id, f"Trace {e}. Error on line {exc_tb.tb_lineno}")
    #     except:
    #         pass


def pnl_diff_fetch(proc_data, balance_DYDX=None):
    pair_DYDX = proc_data['pair_DYDX']
    if not balance_DYDX:
        balance_DYDX = dydx.get_account_data()
    try:
        unrealized_position_pnl = float(balance_DYDX['account']['openPositions'][pair_DYDX]['unrealizedPnl'])
    except:
        return proc_data
    realized_position_pnl = float(balance_DYDX['account']['openPositions'][pair_DYDX]['realizedPnl'])
    DYDX_position_pnl = unrealized_position_pnl + realized_position_pnl
    DYDX_position_side = balance_DYDX['account']['openPositions'][pair_DYDX]['side']
    if proc_data['position_side'] and proc_data['position_side'] != DYDX_position_side:
        proc_data['pnl_changed_diff']['cumulative_profit'] += proc_data['pnl_diff']
        proc_data['pnl_changed_diff']['times_changed_side'] += 1
        proc_data['position_side'] = DYDX_position_side
    proc_data['pnl_diff'] = DYDX_position_pnl
    if not proc_data['position_side']:
        proc_data['position_side'] = DYDX_position_side
        proc_data['pnl_changed_diff']['cumulative_profit'] = DYDX_position_pnl
    return proc_data

                # 'pnl_diff': None,
                # 'position_side': None, #!!! END IT!
                # 'pnl_changed_diff': {
                #                 'cumulative_profit': 0,
                #                 'times_changed_side': 0}  #DYDX SIDE


def start_balance_rewrite(proc_data, coin, coins_amounts, changes):
    proc_data = pnl_diff_fetch(proc_data)
    price_coin = proc_data['price_coin']
    pnl_diff_start = proc_data['pnl_diff']
    start_balance = {'balances': {'USDC': coins_amounts['DYDX']['USDC']['total'],
                                  price_coin: coins_amounts['TIMEX'][price_coin]['total'],
                                  coin: coins_amounts['TIMEX'][coin]['total'],
                                  'TIME': coins_amounts['TIMEX']['TIME']['total']},
                     'positions': {proc_data['coin']: {
                         'position': coins_amounts['DYDX']['positions'][coin]['position'] + coins_amounts['TIMEX'][coin]['total'],
                         'price': changes[coin]}},
                     'pnl_start': pnl_diff_start}
    with open('/home/ubuntu/balance.json', 'w') as file:
        json.dump(start_balance, file)
    return start_balance


def coins_amounts_calc(proc_data):
    # try:
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
    proc_data = pnl_diff_fetch(proc_data, balance_DYDX=balance_DYDX)
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
    # except Exception as e:
    #     exc_type, exc_obj, exc_tb = sys.exc_info()
    #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #     try:
    #         # telegram_bot.send_message(chat_id, f"#TIMEX\nBot crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
    #     except:
    #         pass


# def fetch_positions_TIMEX():
#     positions_TIMEX = None
#     while not positions_TIMEX:
#         try:
#             positions_TIMEX = bot_TIMEX.fetchPositions()
#             return positions_TIMEX
#         except:
#             continue    


def balancing_TIMEX(proc_data):
    # try:
    balance_DYDX = dydx.get_account_data()
    # positions_TIMEX = fetch_positions_TIMEX()
    coin = proc_data['coin']
    pair_TIMEX = proc_data['pair_TIMEX']
    pair_DYDX = proc_data['pair_DYDX']
    sh_rates_TIMEX = proc_data['sh_rates_TIMEX']
    target_position = proc_data['target_position']
    min_amount = proc_data['min_amount']
    ticksize_TIMEX = proc_data['ticksize_TIMEX']
    sh_rates_DYDX = proc_data['sh_rates_DYDX']
    coins_amounts = proc_data['coins_amounts']
    changes = proc_data['changes']
    OB_DYDX = fetch_shared_memory(sh_rates_DYDX, 'DEAL')
    if balance_DYDX['account']['openPositions'].get(pair_DYDX):
        position_DYDX = float(balance_DYDX['account']['openPositions'][pair_DYDX]['size'])
    else:
        position_DYDX = 0
    position_TIMEX = coins_amounts['TIMEX'][coin]['total']
    # # LONG
    # if position_DYDX_USD - position_TIMEX > min_amount:
    #     bot_TIMEX.create_order(pair_TIMEX, 'limit', 'buy', position_DYDX_USD - position_TIMEX, OB_TIMEX['asks'][0][0] - 0.03)
    # elif position_DYDX_USD - position_TIMEX < - min_amount:
    #     bot_TIMEX.create_order(pair_TIMEX, 'limit', 'sell', abs(position_DYDX_USD - position_TIMEX), OB_TIMEX['bids'][0][0] + 0.03)
    # ZERO POSITION
    position_total = position_DYDX + position_TIMEX
    if position_total > target_position:
        if target_position <= 0:
            if position_total >= 0:
                disbalanse_amount = position_total + abs(target_position)
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['bids'][0][0] + ticksize_TIMEX, disbalanse_amount, 'SELL', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
            elif position_total <= 0:
                disbalanse_amount = abs(target_position) - abs(position_total)
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['bids'][0][0] + ticksize_TIMEX, disbalanse_amount, 'SELL', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
        elif target_position >= 0:
            if position_total >= 0:
                disbalanse_amount = target_position - position_total
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['bids'][0][0] + ticksize_TIMEX, disbalanse_amount, 'SELL', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
            elif position_total <= 0:
                disbalanse_amount = target_position + abs(position_total)
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['bids'][0][0] + ticksize_TIMEX, disbalanse_amount, 'SELL', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)

    elif position_total < target_position:
        if target_position <= 0:
            if position_total >= 0:
                disbalanse_amount = abs(target_position) + position_total
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['asks'][0][0] - ticksize_TIMEX, disbalanse_amount, 'BUY', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
            elif position_total <= 0:
                disbalanse_amount = abs(position_total) - abs(target_position)
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['asks'][0][0] - ticksize_TIMEX, disbalanse_amount, 'BUY', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
        elif target_position >= 0:
            if position_total >= 0:
                disbalanse_amount = target_position - position_total
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['asks'][0][0] - ticksize_TIMEX, disbalanse_amount, 'BUY', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
            elif position_total <= 0:
                disbalanse_amount = target_position + abs(position_total)
                if disbalanse_amount > min_amount:
                    response = dydx.create_order(proc_data, OB_DYDX['asks'][0][0] - ticksize_TIMEX, disbalanse_amount, 'BUY', order_type ='MARKET')
                    db.disbalanses_append(disbalanse_amount)
    # except Exception as e:
    #     exc_type, exc_obj, exc_tb = sys.exc_info()
    #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #     try:
    #         telegram_bot.send_message(chat_id, f"#TIMEX\nBalancer error. Trace {e}. Error on line {exc_tb.tb_lineno}")
    #     except:
    #         pass

#EXECUTED ORDER RESPONSE
# {'info': 
#     {'id': '0x064633b0926dba804dc1207956bff331836d6b7dd796922f13bee3e4ceccc129', 'cursorId': '1753066938', 'clientOrderId': None, 
#     'symbol': 'ETHAUDT', 'side': 'BUY', 'type': 'LIMIT', 'quantity': '0.03', 'filledQuantity': '0.03', 'cancelledQuantity': '0', 
#     'price': '1525.94', 'avgPrice': '1525.94', 'createdAt': '2022-07-02T10:06:13.429Z', 'updatedAt': '2022-07-02T10:06:13.489Z', 
#     'expireTime': '2023-07-02T10:06:13.416Z', 'trades': 
#         [{'id': '28183587', 'makerOrderId': '0xf867fa487f68a6ff6464dfaa8b3373f6f00c8a5c6e863524dfd1e7179d784220', 
#         'takerOrderId': '0x064633b0926dba804dc1207956bff331836d6b7dd796922f13bee3e4ceccc129', 'symbol': 'ETHAUDT','side': 'BUY', 'quantity': '0.03', 
#         'fee': '0.228891', 'feeToken': 'AUDT', 'price': '1525.94', 'makerOrTaker': 'TAKER', 'timestamp': '2022-07-02T10:06:13.489Z'
#         }]
#     },
# 'id': '0x064633b0926dba804dc1207956bff331836d6b7dd796922f13bee3e4ceccc129', 'clientOrderId': None, 'timestamp': 1656756373429, 
# 'datetime': '2022-07-02T10:06:13.429Z', 'lastTradeTimestamp': 1656756373489, 'symbol': 'ETH/AUDT', 'type': 'limit', 'timeInForce': None, 
# 'postOnly': None, 'side': 'buy', 'price': 1525.94, 'stopPrice': None, 'amount': 0.03, 'cost': 45.7782, 'average': 1525.94, 'filledQuantity': 0.03, 
# 'remaining': 0.0, 'status': 'closed', 'fee': 
#     {'currency': 'AUDT', 'cost': 0.228891
#     }, 
# 'trades': 
#     [{'info': 
#         {
#         'id': '28183587', 'makerOrderId': '0xf867fa487f68a6ff6464dfaa8b3373f6f00c8a5c6e863524dfd1e7179d784220', 
#         'takerOrderId': '0x064633b0926dba804dc1207956bff331836d6b7dd796922f13bee3e4ceccc129', 'symbol': 'ETHAUDT', 'side': 'BUY', 
#         'quantity': '0.03', 'fee': '0.228891', 'feeToken': 'AUDT', 'price': '1525.94', 'makerOrTaker': 'TAKER', 
#         'timestamp': '2022-07-02T10:06:13.489Z'
#         }, 
#     'id': '28183587', 'timestamp': 1656756373489, 'datetime': '2022-07-02T10:06:13.489Z','symbol': 'ETH/AUDT', 
#     'order': '0x064633b0926dba804dc1207956bff331836d6b7dd796922f13bee3e4ceccc129', 'type': 'limit', 'side': 'buy', 'price': 1525.94, 
#     'amount': 0.03, 'cost': 45.7782, 'takerOrMaker': 'taker', 'fee': 
#         {'cost': 0.228891, 'currency': 'AUDT'
#         }
#     }], 
# 'fees': 
#     [{'currency': 'AUDT', 'cost': 0.228891
#     }]
# }


def takers_count(proc_data):
    orderbook_DYDX = proc_data['orderbook_DYDX']
    orderbook_TIMEX = proc_data['orderbook_TIMEX']
    max_buy_DYDX = proc_data['max_buy_DYDX']
    max_sell_DYDX = proc_data['max_sell_DYDX']
    coin = proc_data['coin']
    ticksize_TIMEX = proc_data['ticksize_TIMEX']
    ticksize_DYDX = proc_data['ticksize_DYDX']
    TIMEX_fee = proc_data['TIMEX_taker_fee']
    DYDX_fee = proc_data['DYDX_fee']
    min_profit_buy = proc_data['buy_profits']['taker']
    min_profit_sell = proc_data['sell_profits']['taker']
    changes = proc_data['changes']

    buy_amount_DYDX = orderbook_TIMEX['bids'][0][1] if orderbook_TIMEX['bids'][0][1] * changes[coin] < max_buy_DYDX else round(max_buy_DYDX / changes[coin], 1)

    sell_amount_DYDX = orderbook_TIMEX['asks'][0][1] if orderbook_TIMEX['asks'][0][1] * changes[coin] < max_sell_DYDX else round(max_sell_DYDX / changes[coin], 1)

    buy_DYDX_deals = [{'price': orderbook_TIMEX['bids'][0][0], 'amount': buy_amount_DYDX, 'position': 0}]
    sell_DYDX_deals = [{'price': orderbook_TIMEX['asks'][0][0], 'amount': sell_amount_DYDX, 'position': 0}]
    #FOR REAL TAKERS ON TIMEX SIDE
    # for lot in range(depth_taker):
    #     if lot == 0:
    #         continue
    #     try:
    #         buy_amount_DYDX = orderbook_DYDX['bids'][lot - 1][1] + orderbook_DYDX['bids'][lot][1] if (orderbook_DYDX['bids'][lot - 1][1] + orderbook_DYDX['bids'][lot][1]) * changes[coin] < max_buy_DYDX else round(max_buy_DYDX / changes[coin], 6)
            
    #         buy_DYDX_deals.append({'price': round(orderbook_DYDX['bids'][lot][0], 2), 'amount': buy_amount_DYDX, 'position': lot})
    #     except:
    #         pass
        
    #     try:           
    #         sell_amount_DYDX = orderbook_DYDX['asks'][lot - 1][1] + orderbook_DYDX['asks'][lot][1] if (orderbook_DYDX['asks'][lot - 1][1] + orderbook_DYDX['asks'][lot][1]) * changes[coin] < max_sell_DYDX else round(max_sell_DYDX / changes[coin], 6)
            
    #         sell_DYDX_deals.append({'price': round(orderbook_DYDX['asks'][lot][0], 2), 'amount': sell_amount_DYDX, 'position': lot})
    #     except:
    #         pass
    for deal in buy_DYDX_deals:
        amount = deal['amount']
        if amount <= 0:
            continue
        buy_price_DYDX = orderbook_DYDX['asks'][0][0] - ticksize_DYDX
        if proc_data['price_coin'] == 'AUDT':
            deal['price'] = deal['price'] * changes['AUDT']
        profit = (deal['price'] - buy_price_DYDX) / buy_price_DYDX - (TIMEX_fee + DYDX_fee)
        profit_abs = profit * amount
        if profit > min_profit_buy:
                
            profit_deal = {'deal_buy': 'DYDX', 
                           'deal_sell': 'TIMEX',
                           'amount': amount,
                           'buy_price': buy_price_DYDX,
                           'sell_price': deal["price"],# - ticksize_DYDX
                           'profit_abs': profit_abs,
                           'profit': profit,
                           'taker_depth': deal["position"],
                           'time': datetime.datetime.now(),
                           'AUDT/USDT': changes['AUDT']}
            
            profit_deal = timex_order_data_precision(proc_data, profit_deal)
            return profit_deal

    for deal in sell_DYDX_deals:
        amount = deal['amount']
        if amount <= 0:
            continue
        sell_price_DYDX = orderbook_DYDX['bids'][0][0] + ticksize_DYDX
        if proc_data['price_coin'] == 'AUDT':
            deal['price'] = deal['price'] * changes['AUDT']
        profit = (sell_price_DYDX - deal['price']) / deal['price'] - (TIMEX_fee + DYDX_fee)
        profit_abs = profit * amount
        if profit > min_profit_sell:

            profit_deal = {'deal_buy': 'TIMEX', 
                           'deal_sell': 'DYDX',
                           'amount': amount,
                           'buy_price': deal["price"],# + ticksize,
                           'sell_price': sell_price_DYDX,
                           'profit_abs': profit_abs,
                           'profit': profit,
                           'taker_depth': deal["position"],
                           'time': datetime.datetime.now(),
                           'AUDT/USDT': changes['AUDT']}
            profit_deal = timex_order_data_precision(proc_data, profit_deal)
            return profit_deal

    return None


def timex_order_data_precision(proc_data, deal):
    tickSize = proc_data['ticksize_TIMEX']
    stepSize = proc_data['stepsize_TIMEX']
    if proc_data['price_coin'] == 'AUDT':
        if deal['deal_buy'] == 'TIMEX':
            deal['buy_price'] = deal['buy_price'] / proc_data['changes']['AUDT']
        else:
            deal['sell_price'] = deal['sell_price'] / proc_data['changes']['AUDT']
    if '.' in str(stepSize):
        round_amount_len = len(str(stepSize).split('.')[1])
    else:
        round_amount_len = 0
    deal['amount'] = str(round(deal['amount'] - (deal['amount'] % stepSize), round_amount_len))
    if '.' in str(tickSize):
        round_price_len = len(str(tickSize).split('.')[1])
    else:
        round_price_len = 0
    if deal['deal_buy'] == 'TIMEX':
        deal['buy_price'] = round(deal['buy_price'] - (deal['buy_price'] % tickSize), round_price_len)
    else:
        deal['sell_price'] = round(deal['sell_price'] - (deal['sell_price'] % tickSize), round_price_len)
    return deal


def makers_count(proc_data, orderbook_TIMEX, orderbook_DYDX, excluded_price=None):
    try:
        max_buy_DYDX = proc_data['max_buy_DYDX']
        max_sell_DYDX = proc_data['max_sell_DYDX']
        changes = proc_data['changes']
        coin = proc_data['coin']
        ticksize_TIMEX = proc_data['ticksize_TIMEX']
        ticksize_DYDX = proc_data['ticksize_DYDX']
        min_amount = proc_data['min_amount']
        min_profit_buy = proc_data['buy_profits']['maker']
        min_profit_sell = proc_data['sell_profits']['maker']
        buy_proc = proc_data['buy_proc']
        depth = proc_data['depth']
        TIMEX_fee = proc_data['TIMEX_fee']
        DYDX_fee = proc_data['DYDX_fee']
        for position in range(depth):
            if buy_proc:
                if excluded_price:
                    if orderbook_TIMEX['asks'][position][0] == excluded_price:
                        continue
                amount = max_buy_DYDX / changes[coin]
                buy_price_DYDX = orderbook_DYDX['asks'][0][0] - ticksize_DYDX
                sell_price_TIMEX = orderbook_TIMEX['asks'][position][0] - ticksize_TIMEX
                if sell_price_TIMEX != orderbook_TIMEX['bids'][0][0]:
                    sell_price = sell_price_TIMEX
                else:
                    sell_price = orderbook_TIMEX['asks'][position][0]
                if proc_data['price_coin'] == 'AUDT':
                    sell_price = sell_price * changes['AUDT']
                if amount > min_amount:
                    profit = (sell_price - buy_price_DYDX) / buy_price_DYDX - (TIMEX_fee + DYDX_fee)
                    profit_abs = profit * amount
                    if profit > min_profit_buy:
                        if position:
                            position -= 1
                        profit_deal = {'deal_buy': 'DYDX', 
                                       'deal_sell': 'TIMEX',
                                       'amount': amount,
                                       'buy_price': buy_price_DYDX,
                                       'sell_price': sell_price,
                                       'profit_abs': profit_abs,
                                       'profit': profit,
                                       'maker_position': position,
                                       'target_profit': min_profit_buy}
                        profit_deal = timex_order_data_precision(proc_data, profit_deal)
                        return profit_deal
            else:
                if excluded_price:
                    if orderbook_TIMEX['bids'][position][0] == excluded_price:
                        continue
                sell_price_DYDX = orderbook_DYDX['bids'][0][0] + ticksize_DYDX
                buy_price_TIMEX = orderbook_TIMEX['bids'][position][0] + ticksize_TIMEX
                if buy_price_TIMEX != orderbook_TIMEX['asks'][0][0]:
                    buy_price = buy_price_TIMEX
                else:
                    buy_price = orderbook_TIMEX['bids'][position][0]
                if proc_data['price_coin'] == 'AUDT':
                    buy_price = buy_price * changes['AUDT']

                amount = max_sell_DYDX / changes[proc_data['coin']]
                if amount > min_amount:
                    profit = (sell_price_DYDX - buy_price) / buy_price - (TIMEX_fee + DYDX_fee)
                    profit_abs = profit * amount
                    if profit > min_profit_sell:
                        
                        if position:
                            position -= 1
                        profit_deal = {'deal_buy': 'TIMEX', 
                                       'deal_sell': 'DYDX',
                                       'amount': amount,
                                       'buy_price': buy_price,
                                       'sell_price': sell_price_DYDX,
                                       'profit_abs': profit_abs,
                                       'profit': profit,
                                       'maker_position': position,
                                       'target_profit': min_profit_sell}
                        profit_deal = timex_order_data_precision(proc_data, profit_deal)
                        return profit_deal
        return None
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        i = 0
        try:
            telegram.send_first_chat(f"Bot {proc_data['proc_name']} crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
        except:
            pass


def check_order_status(proc_data):
    # def write_to_log(text):
    #     with open(f"{proc_name}.txt", "a") as myfile:
            # myfile.write(text + '\n\n')
    # try:
    sh_rates_TIMEX = proc_data['sh_rates_TIMEX']
    sh_rates_DYDX = proc_data['sh_rates_DYDX']
    sh_trades_TIMEX = proc_data['sh_trades_TIMEX']
    ticksize_TIMEX = proc_data['ticksize_TIMEX']
    order_TIMEX_info = proc_data['order_TIMEX_info']
    changes = proc_data['changes']
    cycles_counter = 0
    last_trade = None
    if order_TIMEX_info[1]['deal_buy'] == 'TIMEX':
        order_price = order_TIMEX_info[1]['buy_price']
    else: 
        order_price = order_TIMEX_info[1]['sell_price']
    order_amount = order_TIMEX_info[1]['amount']
    start_trade = fetch_shared_memory(sh_trades_TIMEX)
    while True:
        last_trade = fetch_shared_memory(sh_trades_TIMEX)
        if last_trade != start_trade:
            if last_trade['makerOrderId'] == order_TIMEX_info[0] or last_trade['takerOrderId'] == order_TIMEX_info[0]:
                response_cancel = asyncio.get_event_loop().run_until_complete(cancel_ws_order(order_TIMEX_info[0]))
                return
        orderbook_TIMEX = fetch_shared_memory(sh_rates_TIMEX, 'COUNT')
        orderbook_DYDX = fetch_shared_memory(sh_rates_DYDX, 'COUNT')
        if not orderbook_DYDX or not len(orderbook_DYDX['bids']) or not len(orderbook_DYDX['asks']) or not orderbook_TIMEX:
            continue   
        maker_deal = makers_count(proc_data, orderbook_TIMEX, orderbook_DYDX, order_price)
        if not maker_deal:
            response_cancel = asyncio.get_event_loop().run_until_complete(cancel_ws_order(order_TIMEX_info[0]))
            return
        if order_TIMEX_info[1]['deal_buy'] == 'TIMEX':
            if not maker_deal['buy_price'] - 2 * ticksize_TIMEX <= order_price <= maker_deal['buy_price'] + 2 * ticksize_TIMEX:
                response_cancel = asyncio.get_event_loop().run_until_complete(cancel_ws_order(order_TIMEX_info[0]))
                return
        else:
            if not maker_deal['sell_price'] - 2 * ticksize_TIMEX <= order_price <= maker_deal['sell_price'] + 2 * ticksize_TIMEX:
                response_cancel = asyncio.get_event_loop().run_until_complete(cancel_ws_order(order_TIMEX_info[0]))
                return
    # except Exception as e:
    #     exc_type, exc_obj, exc_tb = sys.exc_info()
    #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #     i = 0
    #     try:
    #         telegram_bot.send_message(chat_id, f"Bot {procData['proc_name']} crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
    #     except:
    #         pass


def fetch_shared_memory(shared, request_type=None):
    decoded_fetched_data = None
    while not decoded_fetched_data:
        fetched = bytes(shared.buf)
        fetched_str_data = str(fetched).split('}')[0].split("b'")[1] + '}'
        try:
            decoded_fetched_data = json.loads(fetched_str_data)
        except Exception as e:
            pass
        if decoded_fetched_data:
            if decoded_fetched_data.get('time'):
                if time.time() - decoded_fetched_data['time'] > 0.6:
                    # try:
                    #     telegram_bot.send_message(chat_id, f"Old orderbook data:\nTime gap: {time.time() - decoded_fetched_data['time']}\nData: {decoded_fetched_data}")
                    # except:
                    #     pass
                    if request_type == 'COUNT':
                        return None
                    decoded_fetched_data = None
            # elif decoded_fetched_data.get('timestamp'):
            #     if time.time() - (decoded_fetched_data['timestamp'] / 1000) > 0.6:
            #         # try:
            #         #     telegram_bot.send_message(chat_id, f"Old orderbook data:\nTime gap: {time.time() - (decoded_fetched_data['timestamp'] / 1000)}\nData: {decoded_fetched_data}")
            #         # except:
            #         #     pass
            #         if request_type == 'COUNT':
            #             return None
            #         decoded_fetched_data = None
    return decoded_fetched_data


def fetch_AUD_price():
    BTC_USD = bot_FTX_public.fetchOrderBook(symbol='BTC/USD', limit=20)
    BTC_AUD = bot_FTX_public.fetchOrderBook(symbol='BTC/AUD', limit=20)
    BTC_USD = (BTC_USD['asks'][0][0] + BTC_USD['bids'][0][0]) / 2
    BTC_AUD = (BTC_AUD['asks'][0][0] + BTC_AUD['bids'][0][0]) / 2
    change_AUDT = round(BTC_USD / BTC_AUD, 4)
    return change_AUDT


def find_arbitrage(proc_data, sh_rates_DYDX, sh_rates_TIMEX, sh_trades_TIMEX, buy_proc, report_sender=False, takers_only=False, proc_name=None):
    # def write_to_log(text):
    #     with open(f"{proc_name}.txt", "a") as myfile:
    #         myfile.write(text + '\n\n')  
    # write_to_log(f"Started process {datetime.datetime.now()}\n\n")
    # rewrite_last_pnl()
    proc_data['sh_rates_DYDX'] = sh_rates_DYDX
    proc_data['sh_rates_TIMEX'] = sh_rates_TIMEX
    proc_data['sh_trades_TIMEX'] = sh_trades_TIMEX
    orderbook_TIMEX = fetch_shared_memory(sh_rates_TIMEX, 'DEAL')
    orderbook_DYDX = fetch_shared_memory(sh_rates_DYDX, 'DEAL')
    proc_data['report_sender'] = report_sender
    proc_data['proc_name'] = proc_name
    proc_data['orderbook_TIMEX'] = orderbook_TIMEX
    changes = {'USDC': 1}
    proc_data['changes'] = changes
    proc_data['changes'].update({proc_data['coin']: float(orderbook_DYDX['bids'][0][0] + float(orderbook_DYDX['asks'][0][0])) / 2})
    proc_data['min_amount'] = round(50 / orderbook_DYDX['bids'][0][0], 6)
    proc_data['max_amount'] = round(2000 / orderbook_DYDX['bids'][0][0], 6)
    proc_data['buy_proc'] = buy_proc
    if proc_data['price_coin'] == 'AUDT':
        change_AUDT = fetch_AUD_price()
        proc_data['changes'].update({'AUDT': round(change_AUDT, 4)})
    change_TIME = asyncio.get_event_loop().run_until_complete(fetch_change_price('TIMEUSDT'))
    proc_data['changes'].update({'TIME': round(change_TIME, 2)})
    ticksize_TIMEX = proc_data['ticksize_TIMEX']
    min_amount = proc_data['min_amount']
    if takers_only:
        try:
            cancel_all_orders_TIMEX()
        except:
            pass
        proc_data = check_max_amounts(proc_data, pos_balancing = True)
    deal_made = False
    start_timestamp = time.time()
    maker_order = False
    last_taker_deal = None
    last_date_report = 0
    maker_counter = 0
    while True:
        try:
            if maker_order:
                if maker_counter == 5:
                    if proc_data['price_coin'] == 'AUDT':
                        change_AUDT = fetch_AUD_price()
                        proc_data['changes'].update({'AUDT': round(change_AUDT, 4)})
                    maker_counter = 0
                maker_counter += 1
                time_start = time.time()
                order = asyncio.get_event_loop().run_until_complete(fetch_ws_order(proc_data['order_TIMEX_info'][0]))
                if order:
                    filled_amount = float(order['filledQuantity'])
                    if filled_amount > min_amount:
                        proc_data = check_max_amounts(proc_data)
                    proc_data['order_TIMEX_info'] = []
                    maker_order = False
            if deal_made:
                proc_data = check_max_amounts(proc_data, line = 1504)
                deal_made = False
            if proc_data['proc_name'] == 'taker':
                if '03' == str(datetime.datetime.now(datetime.timezone(offset))).split('.')[0].split(':')[0].split(' ')[1] and '31' == str(datetime.datetime.now(datetime.timezone(offset))).split('.')[0].split(':')[1] and str(datetime.datetime.now(datetime.timezone(offset))).split(' ')[0].split('-')[2] != last_date_report:
                    last_date_report = str(datetime.datetime.now(datetime.timezone(offset))).split(' ')[0].split('-')[2]
                    proc_data = check_max_amounts(proc_data, daily_report = True)
                    doc = open(f"new_orders_{proc_data['coin']}.db", 'rb')
                    telegram.send_document(doc)
                    doc.close()
                    maker_positions = []
            if int(time.time() - start_timestamp) % 180 == 0:
                try:
                    dydx.cancel_all_orders(market=proc_data['pair_DYDX'])
                except:
                    pass
                proc_data = check_max_amounts(proc_data, pos_balancing = True, line = 1520)
                if proc_data['price_coin'] == 'AUDT':
                    change_AUDT = fetch_AUD_price()
                    proc_data['changes'].update({'AUDT': round(change_AUDT, 4)})
                change_TIME = asyncio.get_event_loop().run_until_complete(fetch_change_price('TIMEUSDT'))
                proc_data['changes'].update({'TIME': round(change_TIME, 2)})
            start_time = time.time()
            orderbook_TIMEX = fetch_shared_memory(sh_rates_TIMEX, 'COUNT')
            proc_data['orderbook_TIMEX'] = orderbook_TIMEX
            if not orderbook_TIMEX:
                continue
            orderbook_DYDX = fetch_shared_memory(sh_rates_DYDX, 'COUNT')
            proc_data['orderbook_DYDX'] = orderbook_DYDX
            if not orderbook_DYDX or not len(orderbook_DYDX['bids']) or not len(orderbook_DYDX['asks']):
                continue
            proc_data['changes'].update({proc_data['coin']: float(orderbook_DYDX['bids'][0][0] + float(orderbook_DYDX['asks'][0][0])) / 2})

            if takers_only:
                best_deal = takers_count(proc_data)
                if not best_deal:
                    continue
            else:
                if buy_proc:
                    if proc_data['max_buy_DYDX'] / proc_data['changes'][proc_data['coin']] < min_amount:
                        time.sleep(30)
                        proc_data = check_max_amounts(proc_data)
                        continue
                else:
                    if proc_data['max_sell_DYDX'] / proc_data['changes'][proc_data['coin']] < min_amount:
                        time.sleep(30)
                        proc_data = check_max_amounts(proc_data)
                        continue
                maker_deal = makers_count(proc_data, orderbook_TIMEX, orderbook_DYDX)
                if not maker_deal:
                    continue
                
                if maker_deal['deal_sell'] == 'TIMEX':
                    order_data = {'price': maker_deal['sell_price'], 'amount': maker_deal['amount'], 'side': 'SELL', 'pair': proc_data['pair_TIMEX']}
                    resp_create_TIMEX_order = asyncio.get_event_loop().run_until_complete(create_ws_order(order_data))
                elif maker_deal['deal_buy'] == 'TIMEX':
                    order_data = {'price': maker_deal['buy_price'], 'amount': maker_deal['amount'], 'side': 'BUY', 'pair': proc_data['pair_TIMEX']}
                    resp_create_TIMEX_order = asyncio.get_event_loop().run_until_complete(create_ws_order(order_data))
                try:
                    if not resp_create_TIMEX_order:
                        proc_data = check_max_amounts(proc_data)
                        maker_order = False
                        continue
                    proc_data['order_TIMEX_info'] = [resp_create_TIMEX_order['responseBody']['orders'][0]['id'], maker_deal, datetime.datetime.now()]
                    maker_order = True
                except Exception as e:
                    proc_data = check_max_amounts(proc_data)
                    continue
                if len(proc_data['order_TIMEX_info']):
                    check_order_status(proc_data)
                continue
            if last_taker_deal:
                if best_deal['buy_price'] == last_taker_deal['buy_price'] and best_deal['sell_price'] == last_taker_deal['sell_price']:
                    if best_deal['amount'] == last_taker_deal['amount']:
                        continue
            if best_deal['deal_buy'] == 'TIMEX':
                order_data = {'price': best_deal['buy_price'], 'amount': best_deal['amount'], 'side': 'BUY', 'pair': proc_data['pair_TIMEX']}
                resp_create_TIMEX_order = asyncio.get_event_loop().run_until_complete(create_ws_order(order_data))
                try:
                    response_cancel = asyncio.get_event_loop().run_until_complete(cancel_ws_order(resp_create_TIMEX_order['responseBody']['orders'][0]['id']))
                    if response_cancel['responseBody'].get('unchangedOrders'):
                        deal_made = True
                    if response_cancel['responseBody'].get('changedOrders'):
                        if response_cancel['responseBody']['changedOrders'][0]['filledQuantity'] != '0':
                           deal_made = True 
                except:
                    pass
                
            else:
                order_data = {'price': best_deal['sell_price'], 'amount': best_deal['amount'], 'side': 'SELL', 'pair': proc_data['pair_TIMEX']}
                resp_create_TIMEX_order = asyncio.get_event_loop().run_until_complete(create_ws_order(order_data))
                try:
                    response_cancel = asyncio.get_event_loop().run_until_complete(cancel_ws_order(resp_create_TIMEX_order['responseBody']['orders'][0]['id']))
                    if response_cancel['responseBody'].get('unchangedOrders'):
                        deal_made = True
                    if response_cancel['responseBody'].get('changedOrders'):
                        if response_cancel['responseBody']['changedOrders'][0]['filledQuantity'] != '0':
                           deal_made = True 
                except:
                    pass
            last_taker_deal = best_deal
            message = f"Taker deal found:\n"
            message += f"Buy/Sell: {best_deal['deal_buy']}/{best_deal['deal_sell']}\n"
            message += f"Buy/Sell price: {round(best_deal['buy_price'],2)}/{round(best_deal['sell_price'], 2)}\n"
            message += f"Profit: {round(best_deal['profit'] * 100, 3)}%\n"
            message += f"AUDT/USDT; {best_deal['AUDT/USDT']}\n"
            message += f"Amount: {best_deal['amount']}\n"
            message += f""
            message += f"Time counted: {best_deal['time']}\n"
            message += f"\nCircle time: {time.time() - start_time}"
            try:
                telegram.send_first_chat(message)
            except:
                telegram.send_emergency(message)
                pass
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            i = 0
            try:
                cancel_all_orders_TIMEX()
            except:
                pass
            try:
                telegram.send_first_chat(f"#TIMEX\nBot {proc_data['pair_DYDX']} crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
            except:
                telegram.send_emergency(f"#TIMEX\nBot {proc_data['pair_DYDX']} crushed. Trace {e}. Error on line {exc_tb.tb_lineno}")
                pass


def fetch_DYDX_api_rates(proc_data, buffer_rates_DYDX):
    last_len = 15000
    while True:
        time.sleep(0.15)
        orderbook = dydx.get_orderbook(market=proc_data['pair_DYDX'])
        orderbook['asks'] = [[float(x['price']), float(x['size'])] for x in orderbook['asks']]
        orderbook['bids'] = [[float(x['price']), float(x['size'])] for x in orderbook['bids']]
        orderbook.update({'time': time.time()})
        orderbook['asks'] = orderbook['asks'][:3]
        orderbook['bids'] = orderbook['bids'][:3]
        encoded_data = json.dumps(orderbook).encode('utf-8')
        if len(encoded_data) < last_len:
            buffer_rates_DYDX[:15000] = bytearray([0 for x in range(15000)])
        buffer_rates_DYDX[:len(encoded_data)] = encoded_data
        last_len = len(encoded_data)


async def fetch_DYDX_ws_rates(proc_data, buffer_rates_DYDX, sh_rates_DYDX):
    req_orderbook = {
        'type': 'subscribe',
        'channel': 'v3_orderbook',
        'id': proc_data['pair_DYDX'],
        'includeOffsets': True,
    }
    last_len = 15000
    async with websockets.connect(URI_WS) as websocket:
        await websocket.send(json.dumps(req_orderbook))       
        while True:
            res_OB = await websocket.recv()
            res_OB = json.loads(res_OB)
            orderbook = fetch_shared_memory(sh_rates_DYDX, 'DEAL')
            try:
                res_OB['contents']
            except:
                continue
            if res_OB['type'] == 'subscribed':
                orderbook = {'asks': [[float(ask['price']), float(ask['size'])] for ask in res_OB['contents']['asks'] if float(ask['size']) > 0],
                'bids': [[float(bid['price']), float(bid['size'])] for bid in res_OB['contents']['bids'] if float(bid['size']) > 0]
                }
                orderbook['asks'], orderbook['bids'] = sorted(orderbook['asks']), sorted(orderbook['bids'])[::-1]
                continue
            if res_OB.get('contents'):
                if len(res_OB['contents']['bids']):
                    for new_bid in res_OB['contents']['bids']:
                        found = False
                        for bid in orderbook['bids']:
                            if float(new_bid[0]) == bid[0]:
                                found = True
                                if float(new_bid[1]) > 0:
                                    bid[1] = float(new_bid[1])
                                else:
                                    orderbook['bids'].remove(bid)
                        if not found:
                            new_bid = [float(new_bid[0]), float(new_bid[1])]
                            orderbook['bids'].append(new_bid)
                            orderbook['bids'] = sorted(orderbook['bids'])[::-1]
                if len(res_OB['contents']['asks']):
                    for new_ask in res_OB['contents']['asks']:
                        found = False
                        for ask in orderbook['asks']:
                            if float(new_ask[0]) == ask[0]:
                                found = True
                                if float(new_ask[1]) > 0:
                                    ask[1] = float(new_ask[1])
                                else:
                                    orderbook['asks'].remove(ask)
                        if not found:
                            new_ask = [float(new_ask[0]), float(new_ask[1])]
                            orderbook['asks'].append(new_ask)
                            orderbook['asks'] = sorted(orderbook['asks'])
                orderbook['asks'] = orderbook['asks'][:3]
                orderbook['bids'] = orderbook['bids'][:3]
                orderbook.update({'time': time.time()})
                encoded_data = json.dumps(orderbook).encode('utf-8')
                if len(encoded_data) < last_len:
                    buffer_rates_DYDX[:15000] = bytearray([0 for x in range(15000)])
                buffer_rates_DYDX[:len(encoded_data)] = encoded_data
                last_len = len(encoded_data)


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
    orderbook_DYDX = fetch_shared_memory(proc_data['sh_rates_DYDX'], 'DEAL')
    if side == 'BUY':
        sell_dydx_price = orderbook_DYDX['bids'][0][0] + ticksize_DYDX
        resp_create_dydx = dydx.create_order(proc_data, sell_dydx_price, amount, 'SELL', order_type='LIMIT')
        profit = (sell_dydx_price - price) / price - (TIMEX_fee + DYDX_fee)
    else:
        buy_dydx_price = orderbook_DYDX['asks'][0][0] - ticksize_DYDX
        resp_create_dydx = dydx.create_order(proc_data, buy_dydx_price, amount, 'BUY', order_type='LIMIT')
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


def start_proc_hack_api_DYDX(proc_data, buffer_rates_DYDX):
    name = f'HTTP_orderbook_DYDX_{proc_data["coin"]}'
    while True:
        try:
            fetch_DYDX_api_rates(proc_data, buffer_rates_DYDX)
        except Exception as e:
            try:
                telegram.send_third_chat(f"Process: {name}\nTrace:\n {e}")
            except:
                pass
        time.sleep(1)


def start_proc_hack_ws_DYDX(proc_data, buffer_rates_DYDX, sh_rates_DYDX_ws):
    name = f'WS_orderbook_DYDX_{proc_data["coin"]}'
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(fetch_DYDX_ws_rates(proc_data, buffer_rates_DYDX, sh_rates_DYDX_ws))
        except Exception as e:
            try:
                telegram.send_third_chat(f"Process: {name}\nTrace:\n {e}")
            except:
                pass
        time.sleep(1)


def start_proc_hack_trades_TIMEX(proc_data, buffer_trades_TIMEX, sh_rates_DYDX_check):
    name = f'trades_DYDX_{proc_data["coin"]}'
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(fetch_TIMEX_trades(execute_order, buffer_trades_TIMEX, sh_rates_DYDX_check))
        except Exception as e:
            try:
                telegram.send_third_chat(f"Process: {name}\nTrace:\n {e}")
            except:
                pass
        time.sleep(1)


shm_rates_DYDX = shared_memory.SharedMemory(create=True, size=15000)
shm_rates_TIMEX = shared_memory.SharedMemory(create=True, size=15000)
shm_trades_TIMEX = shared_memory.SharedMemory(create=True, size=400)

buffer_rates_DYDX = shm_rates_DYDX.buf
buffer_rates_TIMEX = shm_rates_TIMEX.buf
buffer_trades_TIMEX = shm_trades_TIMEX.buf

sh_rates_DYDX_maker_buy = shared_memory.SharedMemory(shm_rates_DYDX.name)
sh_rates_DYDX_maker_sell = shared_memory.SharedMemory(shm_rates_DYDX.name)
sh_rates_DYDX_taker = shared_memory.SharedMemory(shm_rates_DYDX.name)
sh_rates_DYDX_ws = shared_memory.SharedMemory(shm_rates_DYDX.name)
sh_rates_DYDX_check = shared_memory.SharedMemory(shm_rates_DYDX.name)

sh_rates_TIMEX_maker_buy = shared_memory.SharedMemory(shm_rates_TIMEX.name)
sh_rates_TIMEX_maker_sell = shared_memory.SharedMemory(shm_rates_TIMEX.name)
sh_rates_TIMEX_taker = shared_memory.SharedMemory(shm_rates_TIMEX.name)

sh_trades_TIMEX_maker_buy = shared_memory.SharedMemory(shm_trades_TIMEX.name)
sh_trades_TIMEX_maker_sell = shared_memory.SharedMemory(shm_trades_TIMEX.name)


def main():
    common.creating_procData(dydx, bot_TIMEX)
    common.procData['sh_rates_DYDX'] = sh_rates_DYDX_check
    db.sql_create_table()
    procs = []
    proc = Process(target=start_proc_hack_TIMEX, args=(common.procData, buffer_rates_TIMEX, )) #TIMEX FETCHER LAUNCH
    procs.append(proc)

    proc = Process(target=start_proc_hack_api_DYDX, args=(common.procData, buffer_rates_DYDX, )) #TIMEX FETCHER LAUNCH
    procs.append(proc)

    proc = Process(target=start_proc_hack_ws_DYDX, args=(common.procData, buffer_rates_DYDX, sh_rates_DYDX_ws)) #TIMEX FETCHER LAUNCH
    procs.append(proc)

    proc = Process(target=start_proc_hack_trades_TIMEX, args=(common.procData, buffer_trades_TIMEX, sh_rates_DYDX_check, )) #FTX FETCHER LAUNCH
    procs.append(proc)

    proc = Process(target=find_arbitrage, args=(common.procData, sh_rates_DYDX_maker_sell, sh_rates_TIMEX_maker_sell, sh_trades_TIMEX_maker_sell, False, False, False, 'maker_sell'))
    procs.append(proc) #SNX-USD SELL MAKERS PROCS LAUNCH

    proc = Process(target=find_arbitrage, args=(common.procData, sh_rates_DYDX_maker_buy, sh_rates_TIMEX_maker_buy, sh_trades_TIMEX_maker_buy, True, False, False, 'maker_buy'))
    procs.append(proc)  # SNX-USD BUY MAKERS PROCS LAUNCH

    for proc in procs:
        time.sleep(1)
        proc.start()

    time.sleep(1)

    #LAUNCH MAIN PROC TAKER SNX/USDN
    find_arbitrage(common.procData, sh_rates_DYDX_taker, sh_rates_TIMEX_taker, None, buy_proc=True, report_sender=True, takers_only=True, proc_name='taker')
