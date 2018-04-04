"""Bitfinex exchange."""
import base64
import hashlib
import hmac
import json

import requests

from coinlib.base import crypto
from coinlib.base import exchange

_BASE_URL = 'https://api.bitfinex.com/v1'


class Bitfinex(exchange.Exchange):

  def name(self):
    return 'Bitfinex'

  def _sign(self, payload):
    """Signs a payload and returns authenticated HTTP headers.

    Args:
      payload: JSON-encoded body of the payload.

    Returns:
      Authenticated HTTP headers.
    """
    if not self._api_key or not self._api_secret:
      return {}
    json_payload = json.dumps(payload)
    data = base64.standard_b64encode(json_payload.encode('utf8'))
    h = hmac.new(self._api_secret, data, hashlib.sha384)
    signature = h.hexdigest()
    return {
        'x-bfx-apikey': self._api_key,
        'x-bfx-payload': data,
        'x-bfx-signature': signature,
    }

  def _get_request(self, path, params=None):
    """Sends a GET request.

    Args:
      path: Path to the endpoint.
      params: Dictionary of URL params.

    Returns:
      JSON-encoded response.
    """
    r = self._session.get(_BASE_URL + path, params=params or {})
    if r.status_code == 400:
      raise exchange.RequestFailedError(r.json()['message'])
    r.raise_for_status()
    return r.json()

  def _post_request(self, path, payload=None):
    """Sends an authenticated POST request.

    Args:
      path: Path to the endpoint.
      payload: JSON-encoded payload. Nonce and request are automatically added.

    Returns:
      JSON-encoded response.
    """
    payload = payload or {}
    payload.update(nonce=crypto.nonce(), request='/v1' + path)
    r = self._session.post(_BASE_URL + path, headers=self._sign(payload),
                           verify=True)
    if r.status_code == 400:
      raise ValueError(r.json()['message'])
    r.raise_for_status()
    return r.json()

  _SYMBOLS = None
  _SYMBOL_DETAILS = None

  def _symbols(self):
    if self._SYMBOLS is None:
      self._SYMBOLS = self._get_request('/symbols')
    return self._SYMBOLS

  def _symbol_details(self, primary, secondary):
    if self._SYMBOL_DETAILS is None:
      self._SYMBOL_DETAILS = {x['pair']: x
                              for x in self._get_request('/symbols_details')}
    return self._SYMBOL_DETAILS[self._make_symbol(primary, secondary)]

  def _min_order_size(self, primary, secondary):
    return float(self._symbol_details(primary, secondary)['minimum_order_size'])

  def _max_order_size(self, primary, secondary):
    return float(self._symbol_details(primary, secondary)['maximum_order_size'])

  def pairs(self):
    return sorted((x[3:].upper(), x[:3].upper()) for x in self._symbols())

  def _make_symbol(self, primary, secondary):
    symbol = '{}{}'.format(secondary.lower(), primary.lower())
    if symbol not in self._symbols():
      raise ValueError('Invalid pair {}/{}'.format(primary, secondary))
    return symbol

  def ticker(self, primary, secondary):
    symbol = self._make_symbol(primary, secondary)
    ticker = self._get_request('/pubticker/' + symbol)
    return {
        'ask': float(ticker['ask']),
        'bid': float(ticker['bid']),
        'last': float(ticker['last_price']),
        'high': float(ticker['high']),
        'low': float(ticker['low']),
        'volume': float(ticker['volume']),
        'timestamp': float(ticker['timestamp']),
    }

  def trades(self, primary, secondary):
    symbol = self._make_symbol(primary, secondary)
    trades = self._get_request(
        '/trades/' + symbol, {'timestamp': 0, 'limit_trades': 50})
    return sorted([{
        'quantity': float(trade['amount']),
        'price': float(trade['price']),
        'side': trade['type'],
        'timestamp': float(trade['timestamp']),
    } for trade in trades], key=lambda x: -x['timestamp'])

  def _balances(self):
    balances = self._post_request('/balances')

    # Margin and trading wallets are not supported, only exchange wallets are.
    return {
        balance['currency'].upper(): float(balance['amount'])
        for balance in balances
        if balance['type'] == 'exchange' and float(balance['amount']) > 0
    }

  def _place_order(self, primary, secondary, side, amount, price, order_type):
    symbol = self._make_symbol(primary, secondary)
    min_order_size = self._min_order_size(primary, secondary)
    max_order_size = self._max_order_size(primary, secondary)
    if amount < min_order_size:
      raise ValueError('Minimum order size is {}'.format(min_order_size))
    if amount > max_order_size:
      raise ValueError('Maximum order size is {}'.format(max_order_size))
    payload = {
        'symbol': symbol,
        'amount': str(amount),
        'price': str(price) if order_type != 'market' else '1.0',
        'side': side,
        'type': 'exchange {}'.format(order_type),
        'exchange': 'bitfinex',
    }
    return self._post_request('/order/new', payload)['id']

  def _cancel_order(self, order_id):
    self._post_request('/order/cancel', {'order_id': order_id})

  def _order_details(self, order_id):
    details = self._post_request('/order/status', {'order_id': order_id})
    primary = details['symbol'][3:].upper()
    secondary = details['symbol'][:3].upper()
    if details['is_live']:
      status = 'active'
    elif details['is_cancelled']:
      status = 'canceled'
    else:
      status = 'executed'
    return {
        'primary': primary,
        'secondary': secondary,
        'order_type': details['type'].replace('exchange ', ''),
        'side': details['side'],
        'quantity': float(details['original_amount']),
        'remaining': float(details['remaining_amount']),
        'price': float(details['price']),
        'timestamp_opened': float(details['timestamp']),
        'status': status,
    }

  def _active_orders(self):
    orders = self._post_request('/orders')
    return [order['id'] for order in orders]

  def _past_orders(self):
    orders = self._post_request('/orders/hist')
    return [order['id'] for order in orders]
