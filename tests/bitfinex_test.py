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
    self.url = 'https://api.bitfinex.com/v1/endpoint'

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

  @mock.patch.object(requests, 'Session',
                     return_value=SessionMock(200, ["btcusd", "btcltc"]))
  def test_symbols(self, session_mock):
    client = bitfinex.BitfinexClient()
    self.assertListEqual(['btcltc', 'btcusd'], client.symbols())

  @mock.patch.object(requests, 'Session', return_value=SessionMock(500, {}))
  def test_symbols_fails(self, session_mock):
    client = bitfinex.BitfinexClient()
    self.assertRaisesRegex(requests.exceptions.HTTPError, '500 Server Error',
                           client.symbols)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(
      200, [{
          'type': 'deposit',
          'currency': 'btc',
          'amount': 0.0,
          'available': 0.0,
      }]))
  def test_balances(self, session_mock):
    client = bitfinex.BitfinexClient('key', 'secret')
    self.assertEqual([{
        'type': 'deposit',
        'currency': 'btc',
        'amount': 0.0,
        'available': 0.0,
    }], client.balances())

  def test_balances_unauthenticated_fails(self):
    client = bitfinex.BitfinexClient()
    self.assertRaises(bitfinex.NotAuthenticatedError, client.balances)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(500, {}))
  def test_balances_invalid_authentication(self, session_mock):
    client = bitfinex.BitfinexClient('key', 'wrong-secret')
    self.assertRaisesRegex(requests.exceptions.HTTPError, '500 Server Error',
                           client.balances)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(200, [1]))
  def test_multiple_requests(self, session_mock):
    with bitfinex.BitfinexClient('key', 'secret') as client:
      self.assertEqual([1], client.symbols())
      self.assertEqual([1], client.balances())

  @mock.patch.object(
      requests, 'Session',
      return_value=SessionMock(400, {'message': 'Unknown symbol'}))
  def test_bad_request(self, session_mock):
    client = bitfinex.BitfinexClient()
    self.assertRaisesRegex(requests.exceptions.HTTPError,
                           '400 Bad Request: Unknown symbol', client.ticker)

  @mock.patch.object(requests, 'Session', return_value=SessionMock(
      200, {
          'id': 448364249,
          'side': 'buy',
          'avg_execution_price': 0,
      }))
  def test_new_order(self, session_mock):
    client = bitfinex.BitfinexClient('key', 'secret')
    order = bitfinex.Order(symbol='btcusd', amount=100, price=0.5, side='buy',
                           order_type='exchange market')
    self.assertEqual(448364249, client.new_order(order)['id'])


if __name__ == '__main__':
  unittest.main()
