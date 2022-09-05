from setuptools import setup


setup(
    name='bot-py',
    version='1.4',
    packages=['bot'],
    install_requires=[
        'ccxt==1.92.30',
        'pyTelegramBotAPI==4.7.0',
        'websockets==9.1',
        'web3',
        #'dydx-v3-python',  # has conflicting version of setuptools with ccxt
    ],
    entry_points={
        'console_scripts': [
            'bot = bot.bot:main',
        ],
    }
)
