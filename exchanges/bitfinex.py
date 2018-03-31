"""Bitfinex exchange."""
import base64
import hashlib
import hmac
import json

import requests

from coinlib.core import crypto
from coinlib.core import exchange

_BASE_URL = 'https://api.bitfinex.com/v1'


class AuthenticationError(Exception):
  """Exception raised on Authentication errors."""


class Bitfinex(exchange.Exchange):

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
    r.raise_for_status()
    return r.json()

  _SYMBOLS = None

  def _symbols(self):
    if self._SYMBOLS is None:
      self._SYMBOLS = self._get_request('/symbols')
    return self._SYMBOLS

  def assets(self):
    return sorted(set(x[:3].upper() for x in self._symbols()))

  def currencies(self):
    return sorted(
        set(x[3:].upper() for x in self._symbols()) - set(self.assets()))

  def pairs(self):
    return sorted((x[:3].upper(), x[3:].upper()) for x in self._symbols())

  def _make_symbol(self, primary, secondary):
    symbol = '{}{}'.format(primary.lower(), secondary.lower())
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
        if balance['type'] == 'exchange'
    }

  def _place_order(self, amount, asset, price, currency, side, order_type):
    symbol = self._make_symbol(asset, currency)
    payload = {
        'symbol': symbol,
        'amount': amount,
        'price': price,
        'side': side,
        'type': order_type,
        'exchange': 'bitfinex',
    }
    return self._post_request('/order/new', payload)

  def _cancel_order(self, order_id):
    return self._post_request('/order/cancel', {'order_id': order_id})

  def _order_status(self, order_id):
    # TODO: Return 'active', 'canceled' or 'executed'.
    return self._post_request('/order/status', {'order_id': order_id})

  def _active_orders(self):
    orders = self._post_request('/orders')
    return [order['id'] for order in orders]

  def _past_orders(self, include_canceled):
    orders = self._post_request('/orders/hist')
    return [order['id'] for order in orders]
