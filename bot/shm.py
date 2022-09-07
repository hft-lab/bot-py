import time
import json


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