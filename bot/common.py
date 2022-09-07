import json
import datetime

from .config import config

offset = datetime.timedelta(hours=3)
datetime.timezone(offset)


def save_balance(balance):
    with open(config["DB"]["balance_path"], "w") as f:
        json.dump(balance, f)
