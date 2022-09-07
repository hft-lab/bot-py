import ccxt

bot_FTX_public = ccxt.ftx({'enableRateLimit': True})


def fetch_AUD_price():
    BTC_USD = bot_FTX_public.fetchOrderBook(symbol='BTC/USD', limit=20)
    BTC_AUD = bot_FTX_public.fetchOrderBook(symbol='BTC/AUD', limit=20)
    BTC_USD = (BTC_USD['asks'][0][0] + BTC_USD['bids'][0][0]) / 2
    BTC_AUD = (BTC_AUD['asks'][0][0] + BTC_AUD['bids'][0][0]) / 2
    change_AUDT = round(BTC_USD / BTC_AUD, 4)
    return change_AUDT
