# crypto-ticker-discord-bot

A Discord bot that elegantly displays the price of any cryptocurrency in its nickname

## About

This Discord bot is more of a template to implement bots suited to any cryptocurrency [CoinGecko](https://www.coingecko.com/) supports. It's set to [Nano](https://nano.org/) by default.

This bot is supposed to be on as few servers as possible, since it needs privileged intents and Discord's API doesn't like updating nicknames too often.

## Requirements

- Python >= 3.8
- discord.py >= 1.7.2
- requests >= 2.23.0
- python-dateutil >= 2.8.1
- parsedatetime >= 2.6
- pycoingecko >= 2.0.0

The Python modules are listed in ``requirements.txt``, so you only need to do ``pip install -r requirements.txt``.

## Configuration
Go into ``config.json`` and change the following variables to suit your needs:

- ``token``: Your Discord bot token.
- ``cryptocurrency_id``: CoinGecko's ID of your cryptocurrency. You can look them up on their website, but it's usually something like ``nano``, ``bitcoin``, ``ethereum`` etc.
- ``cryptocurrency_name``: Can be anything you want, it's used in the name to neatly show the name of the cryptocurrency used.
- ``fiat_id``: CoinGecko's ID of the fiat currency your cryptocurrency's price is compared against. You can look them up on their website, but it's usually something like ``eur``, ``usd``, ``gbp`` etc.
- ``fiat_name``: Can be anything you want, it's used in the name to neatly show the name of the fiat currency used.

---

### Donation :)

If you like this bot, why not consider making a small donation using [Nano](https://whynano.cc/)? :)

``nano_1manic1d9i4mh5gijuma8dmo8xccwny54nw87n18iu5ikdpat7yeozm64h6t``

![Nano Address](https://256.sh/i/4dp94bgr.png)
