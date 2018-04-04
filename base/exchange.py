"""Generic API for an exchange."""
from abc import ABC, abstractmethod

import requests


class AuthenticationError(Exception):
  """Exception raised on authentication errors."""


class RequestFailedError(Exception):
  """Exception raised when API calls fail."""


class Exchange(ABC):

  def __init__(self):
    self._authenticated = False
    self._session = requests.Session()

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self._session.close()

  ### Authentication.

  def authenticate(self, api_key, api_secret):
    """Authenticates with given API key and secret."""
    if self._authenticated:
      raise AuthenticationError('Already authenticated')
    self._api_key = (
        api_key.encode('utf-8') if isinstance(api_key, str) else api_key)
    self._api_secret = (
        api_secret.encode('utf-8') if isinstance(api_secret, str)
        else api_secret)
    try:
      # Try checking balances to validate authentication.
      self._balances()
    except RequestFailedError:
      raise AuthenticationError('Invalid credentials')
    self._authenticated = True

  def unauthenticate(self):
    self._authenticated = False

  def is_authenticated(self):
    return self._authenticated

  @abstractmethod
  def name(self):
    """Returns the name of this exchange."""

  ### Supported assets.

  @abstractmethod
  def pairs(self):
    """Returns list of supported pairs, e.g. [('BTC', 'USD')]."""

  ### Market data.

  @abstractmethod
  def ticker(self, primary, secondary):
    """Gets last ticker for given trading pair.

    Returns:
      Dictionary with keys 'ask', 'bid', 'last', 'high', 'low', 'volume'
        (expressed in secondary unit) and 'timestamp'.
    """

  @abstractmethod
  def trades(self, primary, secondary):
    """Gets last trades for given trading pair.

    Returns:
      List of dictionaries with keys 'quantity', 'price', 'side' (buy or sell)
        and 'timestamp'. Sorted with most recent first.
    """

  ### Balance.

  def balances(self):
    """Returns dictionary currency/asset -> amount."""
    if not self._authenticated:
      raise AuthenticationError('Client not authenticated')
    return self._balances()

  @abstractmethod
  def _balances(self):
    ...

  ### Orders.

  def place_order(self, primary, secondary, side, amount, price=None,
                  order_type='market'):
    """Places a new order.

    Args:
      primary: Primary, e.g. 'USD'.
      secondary: Secondary, e.g. 'BTC'.
      side: 'buy' or 'sell'.
      amount: Amount to buy or sell.
      price: Price for one secondary. Leave None for market orders.
      order_type: 'market', 'limit' or 'stop'.

    Returns:
      Order ID.
    """
    if not self._authenticated:
      raise AuthenticationError('Client not authenticated')
    if side not in ('buy', 'sell'):
      raise ValueError('`side` param must be "buy" or "sell"')
    if order_type == 'market' and price is not None:
      raise ValueError('Do not provide price for market orders')
    return self._place_order(
        primary, secondary, side, amount, price, order_type)

  @abstractmethod
  def _place_order(self, primary, secondary, side, amount, price, order_type):
    ...

  def cancel_order(self, order_id):
    """Cancels an active order."""
    if not self._authenticated:
      raise AuthenticationError('Client not authenticated')
    return self._cancel_order(order_id)

  @abstractmethod
  def _cancel_order(self, order_id):
    ...

  def order_details(self, order_id):
    """Checks order details.

    Returns:
      Dictionary with keys 'primary', 'secondary', 'order_type', 'side',
        'quantity', 'remaining', 'price', 'timestamp_opened' and 'status' where
        status is one of 'active', 'canceled' or 'executed'.
    """
    if not self._authenticated:
      raise AuthenticationError('Client not authenticated')
    return self._order_details(order_id)

  @abstractmethod
  def _order_details(self, order_id):
    ...

  def active_orders(self):
    """Gets the list of active order IDs."""
    if not self._authenticated:
      raise AuthenticationError('Client not authenticated')
    return self._active_orders()

  @abstractmethod
  def _active_orders(self):
    ...

  def past_orders(self):
    """Gets the list of executed and optionally canceled order IDs."""
    if not self._authenticated:
      raise AuthenticationError('Client not authenticated')
    return self._past_orders()

  @abstractmethod
  def _past_orders(self):
    ...
