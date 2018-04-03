"""Bittrex exchange."""
import dateutil.parser
import hashlib
import hmac
import json
import urllib.parse

import requests

from coinlib.core import crypto
from coinlib.core import exchange

_BASE_URL = 'https://bittrex.com/api/v1.1'


def _timestamp(date):
  return dateutil.parser.parse(date).timestamp()


class Bittrex(exchange.Exchange):

  def name(self):
    return 'Bittrex'

  def _sign(self, path):
    """Signs a payload and returns authenticated HTTP headers.

    Args:
      path: API path to sign (including nonce and API key).

    Returns:
      HMAC signature.
    """
    return hmac.new(self._api_secret, path.encode('utf-8'),
                    hashlib.sha512).hexdigest()

  def _public_request(self, path, params=None):
    """Sends an unauthenticated GET request to the API.

    Args:
      path: Path to the endpoint.
      params: Dictionary of URL params.

    Returns:
      JSON-encoded response.
    """
    uri = '{base}{path}{params}'.format(
        base=_BASE_URL, path=path,
        params=('?' + urllib.parse.urlencode(sorted(params.items())))
               if params else '')
    r = self._session.get(uri)
    r.raise_for_status()
    response = r.json()
    if not response['success']:
      raise exchange.RequestFailedError(response['message'])
    return response['result']

  def _signed_request(self, path, params=None):
    """Sends an authenticated GET request to the API.

    Args:
      path: Path to the endpoint.
      params: Dictionary of URL params.

    Returns:
      JSON-encoded response.
    """
    params = params or {}
    params.update(nonce=crypto.nonce(), apikey=self._api_key)
    uri = '{base}{path}{params}'.format(
        base=_BASE_URL, path=path,
        params=('?' + urllib.parse.urlencode(sorted(params.items())))
               if params else '')
    r = self._session.get(uri, headers={'apisign': self._sign(uri)})
    r.raise_for_status()
    response = r.json()
    if not response['success']:
      raise exchange.RequestFailedError(response['message'])
    return response['result']

  _MARKETS = None

  def _markets(self):
    if self._MARKETS is None:
      markets = self._public_request('/public/getmarkets')
      self._MARKETS = {x['MarketName']: x for x in markets}
    return self._MARKETS

  def _make_symbol(self, primary, secondary):
    symbol = '{}-{}'.format(primary.upper(), secondary.upper())
    if symbol not in self._markets():
      raise ValueError('Invalid pair {}/{}'.format(primary, secondary))
    return symbol

  def _symbol_details(self, primary, secondary):
    return self._markets()[self._make_symbol(primary, secondary)]

  def _min_order_size(self, primary, secondary):
    return float(self._symbol_details(primary, secondary)['MinTradeSize'])

  def pairs(self):
    return sorted(tuple(x.split('-')) for x in self._markets())

  def ticker(self, primary, secondary):
    symbol = self._make_symbol(primary, secondary)
    ticker = self._public_request(
        '/public/getmarketsummary', {'market': symbol})[0]
    return {
        'ask': float(ticker['Ask']),
        'bid': float(ticker['Bid']),
        'last': float(ticker['Last']),
        'high': float(ticker['High']),
        'low': float(ticker['Low']),
        'volume': float(ticker['Volume']),
        'timestamp': _timestamp(ticker['TimeStamp']),
    }

  def trades(self, primary, secondary):
    symbol = self._make_symbol(primary, secondary)
    trades = self._public_request(
        '/public/getmarkethistory', {'market': symbol})
    return sorted([{
        'quantity': float(trade['Quantity']),
        'price': float(trade['Price']),
        'side': trade['OrderType'].lower(),
        'timestamp': _timestamp(trade['TimeStamp']),
    } for trade in trades], key=lambda x: -x['timestamp'])

  def _balances(self):
    balances = self._signed_request('/account/getbalances')
    return {
        balance['Currency']: float(balance['Balance']) for balance in balances
    }

  def _place_order(self, primary, secondary, side, amount, price, order_type):
    symbol = self._make_symbol(primary, secondary)
    min_order_size = self._min_order_size(primary, secondary)
    if amount < min_order_size:
      raise ValueError('Minimum order size is {}'.format(min_order_size))
    if order_type != 'limit':
      raise ValueError('Only limit orders are allowed')
    params = {
        'market': self._make_symbol(primary, secondary),
        'quantity': amount,
        'rate': price,
    }
    endpoint = '/market/buylimit' if side == 'buy' else '/public/selllimit'
    return self._signed_request(endpoint, params)['uuid']

  def _cancel_order(self, order_id):
    self._signed_request('/market/cancel', {'uuid': order_id})

  def _order_details(self, order_id):
    details = self._signed_request('/account/getorder', {'uuid': order_id})
    primary, secondary = details['Exchange'].split('-')
    order_type, side = map(lambda x: x.lower(), details['Type'].split('_'))
    if details['IsOpen']:
      status = 'active'
    elif details['CancelInitiated']:
      status = 'canceled'
    else:
      status = 'executed'
    return {
        'primary': primary,
        'secondary': secondary,
        'order_type': order_type,
        'side': side,
        'quantity': details['Quantity'],
        'remaining': details['QuantityRemaining'],
        'price': details['Price'],
        'timestamp_opened': _timestamp(details['Opened']),
        'status': status,
    }

  def _active_orders(self):
    orders = self._signed_request('/market/getopenorders')
    return [order['OrderUuid'] for order in orders]

  def _past_orders(self):
    orders = self._signed_request('/account/getorderhistory')
    return [order['OrderUuid'] for order in orders]
