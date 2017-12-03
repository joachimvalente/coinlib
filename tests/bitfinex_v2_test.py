import unittest
from unittest import mock

import requests

from coinlib import bitfinex_v2 as bitfinex


class ResponseMock(requests.Response):
  """Mock for requests.Response objects."""

  def __init__(self, status_code, response_body):
    super().__init__()
    self.status_code = status_code
    self._response_body = response_body
    self.url = 'https://api.bitfinex.com/v2/endpoint'

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


class BitfinexV2ClientTests(unittest.TestCase):

  @mock.patch.object(requests, 'Session', return_value=SessionMock(200, '[1]'))
  def test_platform_status(self, session_mock):
    client = bitfinex.BitfinexV2Client()
    self.assertEqual('[1]', client.platform_status())

  @mock.patch.object(requests, 'Session', return_value=SessionMock(500, ''))
  def test_platform_status_fails(self, session_mock):
    client = bitfinex.BitfinexV2Client()
    self.assertRaisesRegex(requests.exceptions.HTTPError, '500 Server Error',
                           client.platform_status)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(
      200,
      "[['exchange', 'ETH', 10.0, 0, None], "
      "['exchange', 'BTC', 20.0, 0, None]]"))
  def test_wallets(self, session_mock):
    client = bitfinex.BitfinexV2Client('key', 'secret')
    self.assertEqual(
        "[['exchange', 'ETH', 10.0, 0, None], "
        "['exchange', 'BTC', 20.0, 0, None]]", client.wallets())

  def test_wallets_unauthenticated_fails(self):
    client = bitfinex.BitfinexV2Client()
    self.assertRaises(bitfinex.NotAuthenticatedError, client.wallets)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(500, ''))
  def test_wallets_invalid_authentication(self, session_mock):
    client = bitfinex.BitfinexV2Client('key', 'wrong-secret')
    self.assertRaisesRegex(requests.exceptions.HTTPError, '500 Server Error',
                           client.wallets)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(200, '[1]'))
  def test_multiple_requests(self, session_mock):
    with bitfinex.BitfinexV2Client('key', 'secret') as client:
      self.assertEqual('[1]', client.wallets())
      self.assertEqual('[1]', client.orders())


if __name__ == '__main__':
  unittest.main()
