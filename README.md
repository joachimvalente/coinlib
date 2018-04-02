# coinlib
Python3 API for crypto exchanges.

## Requirements

```shell
pip install -r requirements.txt
```

## Currently supported exchanges

* Bitfinex

## Usage

```
>>> from coinlib.exchanges import bitfinex

>>> b = bitfinex.Bitfinex()

>>> b.pairs()
[('AID', 'BTC'),
 ('AID', 'ETH'),
 ('AID', 'USD'),
 ...
 ('ZRX', 'USD')]

>>> b.ticker('BTC', 'USD')
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

>>> b.place_order('BTC', 'ETH', 'buy', 0.1)  # market buy order of .1 BTC
10151635975

>>> b.order_status(10151635975)
'executed'
```
