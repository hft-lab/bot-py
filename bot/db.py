import sqlite3
from . import common
from .telegram import telegram
from .config import config


class DB:
    def __init__(self):
        self.sql_create_table()
        self.connect = sqlite3.connect(config["DB"]["db_path"])

    def sql_create_table(self):
        cursor = self.connect.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS orders_res (
        deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        buy_stock TEXT,
        buy_price REAL,
        sell_stock TEXT,
        sell_price REAL,
        deal_amount REAL,
        deal_amount_USD REAL,
        deal_time TEXT,
        deal_profit REAL,
        deal_profit_abs REAL,
        deal_profit_abs_USD REAL,
        taker_maker TEXT,
        DYDX_USD REAL,
        TIMEX_USD REAL,
        total_profit REAL,
        total_profit_real REAL,
        total_balance REAL,
        cashin_cashout REAL
        );""")
        self.connect.commit()
        cursor.close()

    def sql_add_new_order_buy(self, to_base):
        coin = common.PROC_DATA["coin"]
        cursor = self.connect.cursor()
        last = cursor.execute("SELECT * FROM orders_res;").fetchall()
        if len(last):
            total_profit = last[-1][-3] + to_base['profit_abs_USD']
        else:
            total_profit = to_base['profit_abs_USD']

        sql = f"""INSERT INTO orders_res( 
            buy_stock, 
            buy_price, 
            sell_stock, 
            sell_price, 
            deal_amount, 
            deal_amount_USD, 
            deal_time, 
            deal_profit, 
            deal_profit_abs, 
            deal_profit_abs_USD, 
            taker_maker, 
            DYDX_USD,
            TIMEX_USD,
            total_profit, 
            total_profit_real, 
            total_balance,
            cashin_cashout)
            VALUES ("{to_base['buy_exchange']}", 
            {to_base['buy_price']}, 
            "{to_base['sell_exchange']}", 
            {to_base['sell_price']}, 
            {to_base['deal_amount']}, 
            {to_base['deal_amount_USD']}, 
            "{to_base['deal_datetime']}", 
            {to_base['profit_perc']}, 
            {to_base[f'profit_abs_{coin}']}, 
            {to_base['profit_abs_USD']}, 
            "{to_base['deal_type']}", 
            {to_base['DYDX_USD']},
            {to_base['TIMEX_USD']},
            {total_profit}, 
            {to_base['total_profit']}, 
            {to_base['total_balance_real']},
            {to_base['cashin_cashout']})"""
        cursor.execute(sql)
        self.connect.commit()
        cursor.close()

    def disbalanses_append(self, dis_amount):
        orderbook_TIMEX = common.PROC_DATA['orderbook_TIMEX']
        ticksize_TIMEX = common.PROC_DATA['ticksize_TIMEX']
        changes = common.PROC_DATA['changes']
        coin = common.PROC_DATA['coin']
        cursor = self.connect.cursor()
        last = cursor.execute("SELECT * FROM orders_res;").fetchall()
        cursor.close()
        if len(last) > 10:
            if last[-1][1] == 'TIMEX':
                if common.PROC_DATA['price_coin'] == 'AUDT':
                    timex_price = (orderbook_TIMEX['asks'][0][0] - ticksize_TIMEX) * changes['AUDT']
                else:
                    timex_price = (orderbook_TIMEX['asks'][0][0] - ticksize_TIMEX)
                price_diff = timex_price - last[-1][2]
            else:
                if common.PROC_DATA['price_coin'] == 'AUDT':
                    timex_price = (orderbook_TIMEX['bids'][0][0] + ticksize_TIMEX) * changes['AUDT']
                else:
                    timex_price = (orderbook_TIMEX['bids'][0][0] + ticksize_TIMEX)
                price_diff = last[-1][4] - timex_price
        else:
            price_diff = 0
        common.PROC_DATA['disbalanses'].append([abs(dis_amount), price_diff])
        message = f"Disbalanse found:\n"
        message += f"Amount, {coin}: {round(abs(dis_amount), 2)}\n"
        message += f"Disbalanse loss, USD: {round(abs(dis_amount) * price_diff, 2)}\n"
        message += f"Process: {common.PROC_DATA['proc_name']}"
        try:
            telegram.send_first_chat(message)
        except:
            telegram.send_emergency(message)
            pass

    def get_orders_res(self):
        cursor = self.connect.cursor()
        last = cursor.execute("SELECT * FROM orders_res;").fetchall()
        cursor.close()
        return last
