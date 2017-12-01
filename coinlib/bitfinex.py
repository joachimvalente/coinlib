import base64
import hashlib
import hmac
import json
import requests
import urllib
import time


class BitfinexClient(object):

  BASE_URL = 'https://api.bitfinex.com/'

  def __init__(self, api_key, api_secret):
    self._api_key = api_key.encode('utf8')
    self._api_secret = api_secret.encode('utf8')

  def active_orders(self):
    """Fetches active orders."""
    path = 'v2/auth/r/orders'
    body = {}
    return self._post_request(path, body)

  def wallets(self):
    """Fetches wallets."""
    path = 'v2/auth/r/wallets'
    body = {}
    return self._post_request(path, body)

  def _nonce(self):
    """Returns a nonce."""
    return str(int(time.time() * 1000000))

  def _headers(self, path, body):
    """Generates headers from path, body, API key & secret and nonce."""
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

  def _post_request(self, path, body):
    """Sends a POST request."""
    headers = self._headers(path, body)
    r = requests.post(self.BASE_URL + path,
                      headers=headers, json=body, verify=True)
    r.raise_for_status()
    return r.json()
