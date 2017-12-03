import base64
import hashlib
import hmac
import json
import logging
import time
import urllib

import requests

logger = logging.getLogger(__name__)


class NotAuthenticatedError(Exception):
  """
  Exception raised when invoking methods requiring authentication with
  unauthenticated clients.
  """


def authenticated(func):
  """Decorator for methods that require authentication."""

  def wrapper(self, *args, **kwargs):
    if not self._authenticated:
      raise NotAuthenticatedError
    return func(self, *args, **kwargs)

  return wrapper


class BitfinexV2Client(object):

  BASE_URL = 'https://api.bitfinex.com/'

  def __init__(self, api_key=None, api_secret=None):
    """Constructs the client.

    Args:
      auth: A str or bytes tuple containing API key and API secret.
    """
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

  def platform_status(self):
    """Gets the exchange platform status."""
    return self._get_request('v2/platform/status')

  def tickers(self, symbols):
    """Gets tickers for the given symbols.

    Args:
      symbols: List of symbols such as tBTCUSD or fUSD.

    Returns:
      Tickers response.
    """
    return self._get_request('v2/tickers', {'symbols': ','.join(symbols)})

  def ticker(self, symbol):
    """Gets ticker for the given symbol."""
    return self._get_request('v2/ticker/' + symbol)

  def trades(self, symbol, limit=120, start=0, end=0, sort=False):
    """Get trades info such as price, size and time.

    Args:
      symbol: Symbol such as tBTCUSD or fUSD.
      limit: Number of records.
      start: Start time in ms.
      end: End time in ms.
      sort: Sort by timestamp.

    Returns:
      Trades info.
    """
    params = {
        'limit': limit,
        'start': start,
        'end': end,
        'sort': 1 if sort else -1,
    }
    return self._get_request('v2/trades/{}/hist'.format(symbol), arams)

  def book(self, symbol, precision='P0', length=25):
    """Get the Order Books for the given symbol.

    Args:
      symbol: Symbol such as tBTCUSD or fUSD.
      precision: Level of price aggregation. One of P0, P1, P2, P3, R0.
      length: Number of price points.

    Returns:
      Order book for the given symbol.
    """
    if precision not in ('P0', 'P1', 'P2', 'P3', 'R0'):
      raise ValueError('Precision must be one of P0, P1, P2, P3, R0')
    return self._get_request('v2/book/{}/{}'.format(symbol, precision),
                             {'len': length})

  def stats(self, key, size, symbol, side, section, sort=False):
    """Get stats about the given symbol.

    Args:
      key: One of funding.size, credits.size, credits.size.sym, pos.size.
      size: Size, e.g. 1m.
      symbol: Symbol such as tBTCUSD.
      side: Either long or short.
      section: Either last or hist.
      sort: Sort by timestamp.

    Returns:
      Stats for the given symbol.
    """
    return self._get_request(
        'v2/stats1/{}:{}:{}:{}/{}'.format(key, size, symbol, side, section),
        {'sort': 1 if sort else -1})

  def candles(self, time_frame, symbol, section, limit=100, start=None,
              end=None, sort=False):
    """Get candles for the given symbol.

    Args:
      time_frame: Time frame, one of 1m, 5m, 15m, 30m, 1h, 3h, 6h, 12h, 1D, 7D,
        14D, 1M.
      symbol: Symbol such as tBTCUSD or fUSD.
      section: Either last or hist.
      limit: Number of candles requested.
      start: Filter start (ms).
      end: Filter end (ms).
      sort: Sort by timestamp.

    Returns:
      Candles for the given symbol and time frame.
    """
    params = {'limit': limit, 'sort': 1 if sort else -1}
    if start:
      params.update(start=start)
    if end:
      params.update(end=end)
    return self._get_request(
        'v2/candles/trade:{}:{}/{}'.format(time_frame, symbol, section),
        params)

  def market_average_price(self, symbol, amount, period=0, rate_limit=None):
    """Calculate market average price.

    Args:
      symbol: Symbol such as tBTCUSD or fUSD.
      amount: Amount. Positive for buy, negative for sell.
      period: Maximum period for margin funding.
      rate_limit: Limit rate/price.

    Returns:
      The computed market average price.
    """
    params = {'symbol': symbol, 'amount': amount, 'period': period}
    if rate_limit:
      params.update(rate_limit=rate_limit)
    return self._post_request('v2/calc/trade/avg', params)

  @authenticated
  def wallets(self):
    """Fetches wallets."""
    return self._post_request('v2/auth/r/wallets')

  @authenticated
  def orders(self):
    """Fetches active orders."""
    return self._post_request('v2/auth/r/orders')

  @authenticated
  def order_history(self, symbol=None, start=0, end=0, limit=25):
    """Fetches active orders.

    Args:
      symbol: Symbol.
      start: Start time in ms.
      end: End time in ms.
      limit: Number of records.
    """
    if symbol:
      path = 'v2/auth/r/orders/{}/hist'.format(symbol)
    else:
      path = 'v2/auth/r/orders/hist'
    params = {'start': start, 'end': end, 'limit': limit}
    return self._post_request(path, params)

  @authenticated
  def order_trades(self, symbol, order_id):
    """Get trades generated by an order."""
    return self._post_request(
        'v2/auth/r/order/{}:{}/trades'.format(symbol, order_id))

  @authenticated
  def trades(self, symbol=None, start=0, end=0, limit=25):
    """Get trades."""
    if symbol:
      path = 'v2/auth/r/trades/{}/hist'.format(symbol)
    else:
      path = 'v2/auth/r/trades/hist'
    params = {'start': start, 'end': end, 'limit': limit}
    return self._post_request(path, params)

  @authenticated
  def positions(self):
    """Get active positions."""
    return self._post_request('v2/auth/r/positions')

  @authenticated
  def funding_offers(self, symbol):
    """Get funding offers."""
    return self._post_request('v2/auth/r/funding/offers/' + symbol)

  @authenticated
  def funding_offers_history(self, symbol, start=0, end=0, limit=25):
    """Get past inactive funding offers (limited to last 3 days)."""
    params = {'start': start, 'end': end, 'limit': limit}
    return self._post_request('v2/auth/r/funding/offers/{}/hist'.format(symbol),
                              params)

  @authenticated
  def funding_loans(self, symbol):
    """Funds not used in active positions."""
    return self._post_request('v2/auth/r/funding/loans/' + symbol)

  @authenticated
  def funding_loans_history(self, symbol, start=0, end=0, limit=25):
    """Inactive funds not used in positions (limited to last 3 days)."""
    params = {'start': start, 'end': end, 'limit': limit}
    return self._post_request('v2/auth/r/funding/loans/{}/hist'.format(symbol),
                              params)

  @authenticated
  def funding_credits(self, symbol):
    """Funds used in active positions."""
    return self._post_request('v2/auth/r/funding/credits/' + symbol)

  @authenticated
  def funding_credits_history(self, symbol, start=0, end=0, limit=25):
    """Inactive funds used in positions (limited to last 3 days)."""
    params = {'start': start, 'end': end, 'limit': limit}
    return self._post_request(
        'v2/auth/r/funding/credits/{}/hist'.format(symbol), params)

  @authenticated
  def funding_trades(self, symbol, start=0, end=0, limit=25):
    """Get funding trades."""
    params = {'start': start, 'end': end, 'limit': limit}
    return self._post_request('v2/auth/r/funding/trades/{}/hist'.format(symbol),
                              params)

  @authenticated
  def margin_info(self, key):
    """Get account margin info.

    Args:
      key: "base" or symbol.

    Returns:
      Account margin info.
    """
    return self._post_request('v2/auth/r/info/margin/' + key)

  @authenticated
  def funding_info(self, key):
    """Get account funding info.

    Args:
      key: "base" or symbol.

    Returns:
      Account funding info.
    """
    return self._post_request('v2/auth/r/info/funding/' + key)

  @authenticated
  def movements(self, currency):
    """Get movements."""
    return self._post_request('v2/auth/r/movements/{}/hist'.format(currency))

  @authenticated
  def performance(self):
    """Get account historical daily performance."""
    return self._post_request('v2/auth/r/stats/perf:1D/hist')

  @authenticated
  def alerts(self, alert_type='price'):
    """Return the alert list."""
    return self._post_request('v2/auth/r/alerts', body={'type': alert_type})

  @authenticated
  def set_alert(self, symbol, price, alert_type='price'):
    """Set a new alert."""
    body = {
        'type': alert_type,
        'symbol': symbol,
        'price': price
    }
    return self._post_request('v2/auth/w/alert/set', body=body)

  @authenticated
  def delete_alert(self, symbol, price):
    """Delete an alert."""
    self._post_request(
        'v2/auth/w/alert/price:{}:{}/del'.format(symbol, price))

  @authenticated
  def available_balance(self, symbol, direction, rate, order_type):
    """Calculate available balance.

    Args:
      symbol: Symbol.
      direction: Direction of the order/offer. Orders: 1=buy -1=sell. Offers:
        1=sell -1=buy.
      rate: Rate of the order/offer.
      order_type: Type of the order/offer EXCHANGE or MARGIN.

    Returns:
      Available balance.
    """
    body = {
        'symbol': symbol,
        'dir': direction,
        'rate': rate,
        'type': order_type,
    }
    self._post_request('v2/auth/calc/order/avail', body=body)

  def _nonce(self):
    """Returns a nonce."""
    return str(int(time.time() * 1000000))

  def _headers(self, path, body):
    """Generates headers from path, body, API key & secret and nonce.

    Returns an empty dictionary for unauthenticated clients.

    Args:
      path: Path to the endpoint.
      body: JSON-encoded body of the request.

    Returns:
      Headers formatted as a dictionary.
    """
    if not self._authenticated:
      return {}
    nonce = self._nonce()
    raw_body = json.dumps(body)
    signature = ('/api/' + path + nonce + raw_body).encode('utf-8')
    h = hmac.new(self._api_secret, signature, hashlib.sha384)
    signature = h.hexdigest()
    return {
        'bfx-apikey': self._api_key,
        'bfx-nonce': nonce,
        'bfx-signature': signature,
        'content-type': 'application/json',
    }

  def _get_request(self, path, params=None):
    """Sends a GET request.

    Args:
      path: Path to the endpoint.
      body: JSON-encoded body of the request.
      params: Dictionary of URL params.

    Returns:
      JSON-encoded response.
    """
    headers = self._headers(path, {})
    r = self._session.get(self.BASE_URL + path, headers=headers, verify=True,
                          params=params or {})
    logger.info('GET request ' + r.url)
    r.raise_for_status()
    return r.json()

  def _post_request(self, path, params=None, body=None):
    """Sends a POST request.

    Args:
      path: Path to the endpoint.
      body: JSON-encoded body of the request.
      params: Dictionary of URL params.

    Returns:
      JSON-encoded response.
    """
    headers = self._headers(path, body or {})
    r = self._session.post(self.BASE_URL + path, headers=headers,
                           json=body or {}, verify=True, params=params or {})
    r.raise_for_status()
    return r.json()
