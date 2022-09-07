from .config import config
import telebot


class Telegram:
    def __init__(self, bot_token, emergency_token, chat_id, second_chat_id, third_chat_id):
        self.bot = telebot.TeleBot(bot_token)
        self.emergency_bot = telebot.TeleBot(emergency_token)
        self.chat_id = chat_id
        self.second_chat_id = second_chat_id
        self.third_chat_id = third_chat_id

    def send_first_chat(self, *args, **kwargs):
        return self.bot.send_message(self.chat_id, *args, **kwargs)

    def send_second_chat(self, *args, **kwargs):
        return self.bot.send_message(self.second_chat_id, *args, **kwargs)

    def send_third_chat(self, *args, **kwargs):
        return self.bot.send_message(self.third_chat_id, *args, **kwargs)

    def send_emergency(self, *args, **kwargs):
        return self.emergency_bot.send_message(self.chat_id, *args, **kwargs)

    def send_document(self, doc):
        return self.bot.send_document(doc)


conf = config["TELEGRAM"]
telegram = Telegram(conf["bot_token"],
                    conf["emergency_bot_token"],
                    int(conf["first_chat_id"]),
                    int(conf["second_chat_id"]),
                    int(conf["third_chat_id"]),
                    )
