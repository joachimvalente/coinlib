# coinlib
Python3 API for crypto exchanges.

## Requirements

```shell
pip install -r requirements.txt
```

## Currently supported exchanges

* Bitfinex
* Bittrex

## Usage

```
>>> import coinlib

>>> b = coinlib.Bitfinex()  # or coinlib.Bittrex()

>>> b.pairs()
[('BTC', 'AID'),
 ('BTC', 'AVT'),
 ('BTC', 'BAT'),
 ...
 ('USD', 'ZRX')]

>>> b.ticker('USD', 'BTC')
{'ask': 6833.0,
 'bid': 6832.9,
 'high': 7208.1,
 'last': 6833.0,
 'low': 6533.0,
 'timestamp': 1522484090.4236696,
 'volume': 72466.42337525}

>>> b.authenticate(API_KEY, API_SECRET)

>>> b.balances()
{'BTC': 3.0, 'ETH': 10.0}

>>> b.place_order('USD', 'BTC', 'buy', 0.1)  # market buy order of .1 BTC
10151635975

>>> b.order_details(10151635975)['status']
'executed'
```
