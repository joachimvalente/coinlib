"""A python interface for the Bitfinex API v1.

See https://docs.bitfinex.com/v1/docs

Usage:

  from coinlib import bitfinex

  # Print stats for bitcoin. Doesn't require authentication.
  with bitfinex.BitfinexClient() as client:
    print(client.symbols())
    print(client.stats('btcusd'))
    ...

  # Check balances.
  with bitfiex.BitfinexClient(API_KEY, API_SECRET) as client:
    print(client.balances())
    client.transfer(10.0, 'btc', wallet_from='exchange', wallet_to='trading')

    # Place a new buy order.
    order = bitfinex.Order(symbol='btcusd', amount=10, price=1000, side='buy',
                           order_type='exchange limit')
    order_id = client.new_order(order)['id']
    print('Placed order ID {}'.format(order_id))
    ...
"""
import collections
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib

import requests

logger = logging.getLogger(__name__)

Order = collections.namedtuple(
    'Order', ['symbol', 'amount', 'price', 'side', 'order_type'])


class NotAuthenticatedError(Exception):
  """
  Exception raised when invoking methods requiring authentication with
  unauthenticated clients.
  """


class BitfinexClient(object):

  BASE_URL = 'https://api.bitfinex.com/v1'

  def __init__(self, api_key=None, api_secret=None):
    """Constructs the client."""
    if api_key and not api_secret:
      raise ValueError('Must provide API secret')
    if api_secret and not api_key:
      raise ValueError('Must provide API key')
    self._session = requests.Session()
    self._authenticated = api_key is not None
    if self._authenticated:
      if isinstance(api_key, str):
        self._api_key = api_key.encode('utf8')
      else:
        self._api_key = api_key
      if isinstance(api_secret, str):
        self._api_secret = api_secret.encode('utf8')
      else:
        self._api_secret = api_secret

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self._session.close()

  def _nonce(self):
    """Returns a nonce."""
    return str(int(time.time() * 1000000))

  def _sign(self, payload):
    """Signs a payload and returns authenticated HTTP headers.

    Args:
      payload: JSON-encoded body of the payload.

    Returns:
      Authenticated HTTP headers.
    """
    if not self._authenticated:
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
    r = self._session.get(self.BASE_URL + path, params=params or {})
    logger.info('GET request ' + r.url)
    if r.status_code == requests.codes.bad_request:
      raise requests.HTTPError('400 Bad Request: ' + r.json()['message'])
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
    if not self._authenticated:
      raise NotAuthenticatedError(
          'Must be authenticated to send POST requests')
    payload = payload or {}
    payload.update(nonce=self._nonce(), request='/v1' + path)
    r = self._session.post(self.BASE_URL + path, headers=self._sign(payload),
                           verify=True)
    logger.info('POST request ' + r.url)
    r.raise_for_status()
    return r.json()

  ############################# PUBLIC ENDPOINTS #############################

  def symbols(self):
    """Gets list of available symbols."""
    return sorted(self._get_request('/symbols'))

  def symbols_details(self, symbol=None):
    """Gets list of available symbols along with details."""
    r = self._get_request('/symbols_details')
    if symbol:
      details = [x for x in r if x['pair'] == symbol]
      if not details:
        raise KeyError('Symbol {} not found'.format(symbol))
      return details[0]
    return r

  def ticker(self, symbol='btcusd'):
    """Gets ticker for the given symbol."""
    return self._get_request('/pubticker/' + symbol)

  def stats(self, symbol='btcusd'):
    """Gets stats about the given symbol."""
    return self._get_request('/stats/' + symbol)

  def funding_book(self, currency='usd', limit_bids=50, limit_asks=50):
    """Gets the full margin funding book."""
    return self._get_request(
        '/lendbook/' + currency,
        {'limit_bids': limit_bids, 'limit_asks': limit_asks})

  def order_book(self, symbol='btcusd', limit_bids=50, limit_asks=50,
                 group=False):
    """Gets the full order book."""
    return self._get_request(
        '/book/' + symbol,
        {'limit_bids': limit_bids, 'limit_asks': limit_asks, 'group': group})

  def trades(self, symbol='btcusd', timestamp=0, limit_trades=50):
    """Gets list of most recent trades for the symbol."""
    return self._get_request(
        '/trades/' + symbol,
        {'timestamp': timestamp, 'limit_trades': limit_trades})

  def lends(self, currency='usd', timestamp=0, limit_lends=50):
    """Gets a list of the most recent funding data for currency."""
    return self._get_request(
        '/lends/' + currency,
        {'timestamp': timestamp, 'limit_lends': limit_lends})

  ########################## AUTHENTICATED ENDPOINTS ##########################

  def trading_fees(self):
    """Gets trading fees."""
    return self._post_request('/account_infos')

  def account_fees(self):
    """Gets fees applied to withdrawals."""
    return self._post_request('/account_fees')

  def summary(self):
    """Gets a 30-day summary of trading volume and return on margin funding."""
    return self._post_request('/summary')

  def deposit_address(self, wallet_name, method='bitcoin', renew=False):
    """Shows deposit address."""
    return self._post_request(
        '/deposit/new',
        {'method': method, 'wallet_name': wallet_name, 'renew': int(renew)})

  def key_permissions(self):
    """Gets the API permissions associated with this client."""
    return self._post_request('/key_info')

  def margin_info(self):
    """Gets the trading wallet info for margin trading."""
    self._post_request('/margin_infos')

  def balances(self):
    """Gets the wallet balances."""
    return self._post_request('/balances')

  def transfer(self, amount, currency, wallet_from, wallet_to):
    """Transfers between wallets."""
    self._post_request(
        '/transfer',
        {'amount': amount, 'currency': currency, 'wallet_from': wallet_from,
         'wallet_to': wallet_to})

  def withdraw(self, withdraw_type, wallet, amount, **kwargs):
    """Withdraws from a wallet."""
    payload = {
        'withdraw_type': withdraw_type,
        'walletselected': wallet,
        'amount': amount,
    }
    payload.update(kwargs)
    self._post_request('/withdraw', payload)

  ############################## ORDER ENDPOINTS ##############################

  def new_order(self, order, is_hidden=False, is_postonly=False,
                use_all_available=False, oco_order=False, buy_price_oco=0.0,
                sell_price_oco=0.0):
    """Place a new order."""
    payload = {
        'symbol': order.symbol,
        'amount': order.amount,
        'price': order.price,
        'side': order.side,
        'type': order.order_type,
        'exchange': 'bitfinex',
    }
    if is_hidden:
      payload['is_hidden'] = 1
    if is_postonly:
      payload['is_postonly'] = 1
    if use_all_available:
      payload['use_all_available'] = 1
    if oco_order:
      payload.update(oco_order=1,
                     buy_price_oco=buy_price_oco,
                     sell_price_oco=sell_price_oco)
    return self._post_request('/order/new', payload)

  def new_orders(self, orders):
    """Place multiple new orders at once.

    Args:
      orders: A list of Order objects.
    """
    payload = {'orders': [{
        'symbol': order.symbol,
        'amount': order.amount,
        'price': order.price,
        'side': order.side,
        'type': order.order_type,
        'exchange': 'bitfinex',
    } for order in orders]}
    return self._post_request('/order/new/multi', payload)

  def cancel_order(self, order_id):
    """Cancel an order."""
    return self._post_request('/order/cancel', {'order_id': order_id})

  def cancel_orders(self, order_ids):
    """Cancel multiple orders."""
    return self._post_request('/order/cancel/multi', {'order_ids': order_ids})

  def cancel_all_orders(self):
    """Cancel all orders."""
    return self._post_request('/order/cancel/all')

  def replace_order(self, order_id, new_order, is_hidden=False,
                    is_postonly=False, use_all_available=False):
    """Replace an existing order with a new one."""
    payload = {
        'order_id': order_id,
        'symbol': new_order.symbol,
        'amount': new_order.amount,
        'price': new_order.price,
        'side': new_order.side,
        'type': new_order.order_type,
        'exchange': 'bitfinex',
    }
    if is_hidden:
      payload['is_hidden'] = 1
    if is_postonly:
      payload['is_postonly'] = 1
    if use_all_available:
      payload['use_all_available'] = 1
    return self._post_request('/order/cancel/replace', payload)

  def order_status(self, order_id):
    """Get status of an order."""
    return self._post_request('/order/status', {'order_id': order_id})

  def active_orders(self):
    """Get the order status of all active orders."""
    return self._post_request('/orders')

  def order_history(self):
    """Get the status of the latest inactive orders, limited to 3 days."""
    return self._post_request('/orders/hist')

  ...  # to be continued
