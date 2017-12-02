import unittest
from unittest import mock

import requests

from coinlib import bitfinex


class ResponseMock(requests.Response):
  """Mock for requests.Response objects."""

  def __init__(self, status_code, response_body):
    super().__init__()
    self.status_code = status_code
    self._response_body = response_body

  def json(self):
    return self._response_body


class SessionMock(requests.Session):
  """Mock for requests.Session objects."""

  def __init__(self, status_code, response_body):
    super().__init__()
    self._status_code = status_code
    self._response_body = response_body

  def get(self, *args, **kwargs):
    return ResponseMock(self._status_code, self._response_body)

  def post(self, *args, **kwargs):
    return ResponseMock(self._status_code, self._response_body)


class BitfinexClientTests(unittest.TestCase):

  @mock.patch.object(requests, 'Session', return_value=SessionMock(200, '[1]'))
  def test_platform_status(self, session_mock):
    client = bitfinex.BitfinexClient()
    self.assertEqual('[1]', client.platform_status())

  @mock.patch.object(requests, 'Session', return_value=SessionMock(500, ''))
  def test_platform_status_fails(self, session_mock):
    client = bitfinex.BitfinexClient()
    self.assertRaisesRegexp(requests.exceptions.HTTPError, '500 Server Error',
                            client.platform_status)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(
      200,
      "[['exchange', 'ETH', 10.0, 0, None], "
      "['exchange', 'BTC', 20.0, 0, None]]"))
  def test_platform_status(self, session_mock):
    client = bitfinex.BitfinexClient(auth=('key', 'secret'))
    self.assertEqual(
        "[['exchange', 'ETH', 10.0, 0, None], "
        "['exchange', 'BTC', 20.0, 0, None]]", client.wallets())

  def test_wallets_unauthenticated_fails(self):
    client = bitfinex.BitfinexClient()
    self.assertRaises(bitfinex.NotAuthenticatedError, client.wallets)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(500, ''))
  def test_wallets_invalid_authentication(self, session_mock):
    client = bitfinex.BitfinexClient(auth=('key', 'wrong-secret'))
    self.assertRaisesRegexp(requests.exceptions.HTTPError, '500 Server Error',
                            client.wallets)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(200, '[1]'))
  def test_multiple_requests(self, session_mock):
    with bitfinex.BitfinexClient(auth=('key', 'secret')) as client:
      self.assertEqual('[1]', client.wallets())
      self.assertEqual('[1]', client.active_orders())


if __name__ == '__main__':
  unittest.main()
