INSTALL
=======

```shell
git clone git@github.com:hft-lab/dydx-v3-python.git
git clone git@github.com:hft-lab/bot-py.git
python3 -m virtualenv venv
./venv/bin/pip install -e dydx-v3-python
./venv/bin/pip install -e bot-py
```

CONFIG
======

```ini
[DYDX]
default_ethereum_address = ...
eth_private_key = ...
stark_public_key = ...
stark_private_key = ...
stark_public_key_y_coordinate = ...
api_key = ...
api_key_secret = ...
api_passphrase = ...
infura_key = ...

[TIMEX]
api_key = ...
api_secret = ...

[TELEGRAM]
bot_token = ...
emergency_bot_token = ...
first_chat_id = ...
second_chat_id = ...
third_chat_id = ...

[DB]
db_path = /home/ubuntu/new_orders_ETH.db
```

RUN
===

```sh
./venv/bin/bot --config config.ini
```
