import base64
import hashlib
import hmac
import json
import urllib
import time

import requests

class NotAuthenticatedError(Exception):
  """
  Exception raised when invoking methods requiring authentication with
  unauthenticated clients.
  """


class BitfinexClient(object):

  BASE_URL = 'https://api.bitfinex.com/'

  def __init__(self, auth=None):
    """Constructs the client.

    Args:
      auth: A str or bytes tuple containing API key and API secret.
    """
    self._session = requests.Session()
    self._authenticated = auth is not None
    if self._authenticated:
      api_key, api_secret = auth
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

  def __close__(self, *args):
    self._session.close()

  def platform_status(self):
    """Gets the exchange platform status."""
    path = 'v2/platform/status'
    body = {}
    return self._get_request(path, body)

  def active_orders(self):
    """Fetches active orders."""
    if not self._authenticated:
      raise NotAuthenticatedError
    path = 'v2/auth/r/orders'
    body = {}
    return self._post_request(path, body)

  def wallets(self):
    """Fetches wallets."""
    if not self._authenticated:
      raise NotAuthenticatedError
    path = 'v2/auth/r/wallets'
    body = {}
    return self._post_request(path, body)

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

  def _get_request(self, path, body):
    """Sends a GET request.

    Args:
      path: Path to the endpoint.
      body: JSON-encoded body of the request.

    Returns:
      JSON-encoded response.
    """
    headers = self._headers(path, body)
    r = self._session.get(self.BASE_URL + path,
                          headers=headers, json=body, verify=True)
    r.raise_for_status()
    return r.json()

  def _post_request(self, path, body):
    """Sends a POST request.

    Args:
      path: Path to the endpoint.
      body: JSON-encoded body of the request.

    Returns:
      JSON-encoded response.
    """
    headers = self._headers(path, body)
    r = self._session.post(self.BASE_URL + path,
                           headers=headers, json=body, verify=True)
    r.raise_for_status()
    return r.json()
