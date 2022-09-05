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


telegram = Telegram(config["bot_token"],
                    config["emergency_token"],
                    config["chat_id"],
                    config["second_chat_id"],
                    config["third_chat_id"],
                    )
