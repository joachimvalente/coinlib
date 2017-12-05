"""A python interface for the Bitfinex API v1.

See https://docs.bitfinex.com/v1/docs
"""
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


class BitfinexClient(object):

  BASE_URL = 'https://api.bitfinex.com/v1'

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

  def _nonce(self):
    """Returns a nonce."""
    return str(int(time.time() * 1000000))

  def _sign(self, payload):
    """Generates headers from path, body, API key & secret and nonce.

    Returns an empty dictionary for unauthenticated clients.

    Args:
      payload: JSON-encoded body of the payload.

    Returns:
      Headers formatted as a dictionary.
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
    """Gets list of available symbols.

    Example:
      [
        "btcusd",
        "ltcbtc",
        "ltcusd",
        ...
      ]

    Ratelimit:
      5 req/min.

    Returns:
       Sorted list of symbols.
    """
    return sorted(self._get_request('/symbols'))

  def symbols_details(self, symbol=None):
    """Gets list of available symbols along with details.

    Example:
      [{
        "pair":"btcusd",
        "price_precision":5,
        "initial_margin":"30.0",
        "minimum_margin":"15.0",
        "maximum_order_size":"2000.0",
        "minimum_order_size":"0.01",
        "expiration":"NA"
      },
      ...]

    Args:
      symbol: If provided, will return details only for that symbol instead of
        the list.

    Ratelimit:
      5 req/min.

    Returns:
      List of
        pair: The pair code.
        price_precision: Maximum number of significant digits for price in this
          pair.
        initial_margin: Initial margin required to open a position in this pair.
        minimum_margin: Minimal margin to maintain (in %).
        maximum_order_size: Maximum order size of the pair.
        minimum_order_size: Minimum order size of the pair.
        expiration: Expiration date for limited contracts/pairs.
    """
    r = self._get_request('/symbols_details')
    if symbol:
      details = [x for x in r if x['pair'] == symbol]
      if not details:
        raise KeyError('Symbol {} not found'.format(symbol))
      return details[0]
    return r

  def ticker(self, symbol='btcusd'):
    """Gets ticker for the given symbol.

    Example:
      {
        "mid":"244.755",
        "bid":"244.75",
        "ask":"244.76",
        "last_price":"244.82",
        "low":"244.2",
        "high":"248.19",
        "volume":"7842.11542563",
        "timestamp":"1444253422.348340958"
      }

    Ratelimit:
      60 req/min.

    Args:
       symbol: Symbol.

    Returns:
      mid: (bid + ask) / 2.
      bid: Innermost bid.
      ask: Innermost ask.
      last_price: The price at which the last order executed.
      low: Lowest trade price of the last 24 hours.
      high: Highest trade price of the last 24 hours.
      volume: Trading volume of the last 24 hours.
      timestamp: The timestamp at which this information was valid.
    """
    return self._get_request('/pubticker/' + symbol)

  def stats(self, symbol='btcusd'):
    """Gets stats about the given symbol.

    Example:
      [{
        "period":1,
        "volume":"7967.96766158"
      },{
        "period":7,
        "volume":"55938.67260266"
      },{
        "period":30,
        "volume":"275148.09653645"
      }]

    Ratelimit:
      10 req/min.

    Args:
       symbol: Symbol.

    Returns:
      List of
        period: Period covered in days.
        volume: Volume.
    """
    return self._get_request('/stats/' + symbol)

  def funding_book(self, currency='usd', limit_bids=50, limit_asks=50):
    """Gets the full margin funding book.

    Example:
      {
        "bids":[{
          "rate":"9.1287",
          "amount":"5000.0",
          "period":30,
          "timestamp":"1444257541.0",
          "frr":"No"
        }],
        "asks":[{
          "rate":"8.3695",
          "amount":"407.5",
          "period":2,
          "timestamp":"1444260343.0",
          "frr":"No"
        }]
      }

    Ratelimit:
      45 req/min.

    Args:
      currency: Currency.
      limit_bids: Limit the number of funding bids returned. May be 0 in which
        case the array of bids is empty.
      limit_asks: Limit the number of funding offers returned. May be 0 in which
        case the array of asks is empty.

    Returns:
      List of funding bids and offers, which are made of
        rate: Rate in %/365 days.
        amount: Amount.
        period: Minimum period in days for the margin funding contract.
        timestamp: Timestamp.
        frr: "Yes" if the offer is at Flash Return Rate, "No" if the offer is at
          fixed rate.
    """
    return self._get_request(
        '/lendbook/' + currency,
        {'limit_bids': limit_bids, 'limit_asks': limit_asks})

  def order_book(self, symbol='btcusd', limit_bids=50, limit_asks=50,
                 group=False):
    """Gets the full order book.

    Example:
      {
        "bids":[{
          "price":"574.61",
          "amount":"0.1439327",
          "timestamp":"1472506127.0"
        }],
        "asks":[{
          "price":"574.62",
          "amount":"19.1334",
          "timestamp":"1472506126.0"
        }]
      }

    Ratelimit:
      60 req/min.

    Args:
      symbol: Symbol.
      limit_bids: Limit the number of bids returned. May be 0 in which case the
        array of bids is empty.
      limit_asks: Limit the number of asks returned. May be 0 in which case the
        array of asks is empty.
      group: If true, orders are grouped by price in the orderbook. If false,
        orders are not grouped and sorted individually.

    Returns:
      List of bids and asks, which are made of
        price: Price.
        amount: Amount.
        timestamp: Timestamp.
    """
    return self._get_request(
        '/book/' + symbol,
        {'limit_bids': limit_bids, 'limit_asks': limit_asks, 'group': group})

  def trades(self, symbol='btcusd', timestamp=0, limit_trades=50):
    """Gets list of most recent trades for the symbol.

    Ratelimit:
      45 req/min.

    Example:
      [{
        "timestamp":1444266681,
        "tid":11988919,
        "price":"244.8",
        "amount":"0.03297384",
        "exchange":"bitfinex",
        "type":"sell"
      }]

    Args:
      symbol: Symbol.
      timestamp: Only show trades at or after this timestamp.
      limit_trades: Limit the number of trades returned. Must be >= 1.

    Returns:
      List of
        tid: Trade ID.
        timestamp: Timestamp.
        price: Price.
        amount: Amount.
        exchange: "bitfinex".
        type: "sell" or "buy" or "" if undetermined.
    """
    return self._get_request(
        '/trades/' + symbol,
        {'timestamp': timestamp, 'limit_trades': limit_trades})

  def lends(self, currency='usd', timestamp=0, limit_lends=50):
    """Gets a list of the most recent funding data for currency.

    Example:
      [{
        "rate":"9.8998",
        "amount_lent":"22528933.77950878",
        "amount_used":"0.0",
        "timestamp":1444264307
      }]

    Ratelimit:
      60 req/min.

    Args:
      currency: Currency.
      timestamp: Only show data at or after this timestamp.
      limit_lends: Limit the amount of funding data returned. Must be >= 1.

    Returns:
      List of
        rate: Average rate (in %/365 days) of total funding received at fixed
          rates, i.e. past Flash Return Rate annualized.
        amount_lent: Total amount of open margin funding in the given currency.
        amount_used: Total amount of open margin funding used  in a margin
          position in the given currency.
        timestamp: Timestamp.
    """
    return self._get_request(
        '/lends/' + currency,
        {'timestamp': timestamp, 'limit_lends': limit_lends})

  ########################## AUTHENTICATED ENDPOINTS ##########################

  def trading_fees(self):
    """Gets trading fees.

    Example:
      [{
        "maker_fees":"0.1",
        "taker_fees":"0.2",
        "fees":[{
          "pairs":"BTC",
          "maker_fees":"0.1",
          "taker_fees":"0.2"
         },{
          "pairs":"LTC",
          "maker_fees":"0.1",
          "taker_fees":"0.2"
         },
         {
          "pairs":"ETH",
          "maker_fees":"0.1",
          "taker_fees":"0.2"
        }]
      }]
    """
    return self._post_request('/account_infos')

  def account_fees(self):
    """Gets fees applied to withdrawals.

    Example:
      {
        "withdraw":{
          "BTC": "0.0005",
          "LTC": 0,
          "ETH": 0,
          ...
        }
      }
    """
    return self._post_request('/account_fees')

  def summary(self):
    """Gets a 30-day summary of trading volume and return on margin funding.

    Example:
      {
        "trade_vol_30d":[
          {"curr":"BTC","vol":11.88696022},
          {"curr":"LTC","vol":0.0},
          {"curr":"ETH","vol":0.1},
          {"curr":"Total (USD)","vol":5027.63}
        ],
        "funding_profit_30d":[
          {"curr":"USD","amount":0.0},
          {"curr":"BTC","amount":0.0},
          {"curr":"LTC","amount":0.0},
          {"curr":"ETH","amount":0.0}
        ],
        "maker_fee":0.001,
        "taker_fee":0.002
      }
    """
    return self._post_request('/summary')

  def deposit_address(self, wallet_name, method='bitcoin', renew=False):
    """Shows deposit address.

    Example:
      {
        "result":"success",
        "method":"bitcoin",
        "currency":"BTC",
        "address":"1A2wyHKJ4KWEoahDHVxwQy3kdd6g1qiSYV"
      }

    Args:
      wallet_name: Wallet to deposit in ("trading", "exchange" or "deposit").
        The wallet must already exist.
      method: One of "bitcoin", "litecoin", "ethereum", "tetheruso",
        "ethereumc", "zcash", "monero", "iota", "bcash".
      renew: If true, use a new unused deposit address.
    """
    return self._post_request(
        '/deposit/new',
        {'method': method, 'wallet_name': wallet_name, 'renew': int(renew)})

  def key_permissions(self):
    """Gets the API permissions associated with this client.

    Example:
      {
        "account":{
          "read":true,
          "write":false
        },
        "history":{
          "read":true,
          "write":false
        },
        "orders":{
          "read":true,
          "write":true
        },
        "positions":{
          "read":true,
          "write":true
        },
        "funding":{
          "read":true,
          "write":true
        },
        "wallets":{
          "read":true,
          "write":true
        },
        "withdraw":{
          "read":null,
          "write":null
        }
      }
    """
    return self._post_request('/key_info')

  def margin_info(self):
    """Gets the trading wallet info for margin trading.

    Example:
      [{
        "margin_balance":"14.80039951",
        "tradable_balance":"-12.50620089",
        "unrealized_pl":"-0.18392",
        "unrealized_swap":"-0.00038653",
        "net_value":"14.61609298",
        "required_margin":"7.3569",
        "leverage":"2.5",
        "margin_requirement":"13.0",
        "margin_limits":[{
          "on_pair":"BTCUSD",
          "initial_margin":"30.0",
          "margin_requirement":"15.0",
          "tradable_balance":"-0.329243259666666667"
        }],
        "message": "Margin requirement, leverage and tradable balance ..."
      }]

    Returns:
      margin_balance: The USD value of all your trading assets (based on last
        prices).
      unrealized_pl: The unrealized profit/loss of all your open positions.
      unrealized_swap: The margin funding used by all your open positions.
      net_value: Your net value (the USD value of your trading wallet, including
        your margin balance, your unrealized P/L and margin funding).
      required_margin: The minimum net value to maintain in your trading wallet,
        under which all of your positions are fully liquidated.
      margin_limits: The list of margin limits for each pair. The array gives
        you the following information, for each pair.
      on_pair: The pair for which these limits are valid.
      initial_margin: The minimum margin (in %) to maintain to open or increase
        a position.
      tradable_balance: Your tradable balance in USD (the maximum size you can
        open on leverage for this pair).
      margin_requirements: The maintenance margin %/of the USD value of all of
        your open positions in the current pair to maintain).
    """
    self._post_request('/margin_infos')

  def balances(self):
    """Gets the wallet balances.

    Example:
      [{
        "type":"deposit",
        "currency":"btc",
        "amount":"0.0",
        "available":"0.0"
      },{
        "type":"exchange",
        "currency":"btc",
        "amount":"1",
        "available":"1"
      },{
        "type":"trading",
        "currency":"usd",
        "amount":"1",
        "available":"1"
      },
      ...]

    Returns:
      type: "trading", "deposit" or "exchange".
      currency: Currency.
      amount: How much balance of this currency in this wallet.
      available: How much there is in this wallet available to trade.
    """
    return self._post_request('/balances')

  def transfer(self, amount, currency, wallet_from, wallet_to):
    """Transfer between wallets.

    Example:
      [{
        "status":"success",
        "message":"1.0 USD transfered from Exchange to Deposit"
      }]

    Args:
      amount: Amount to transfer.
      currency: Currency or funds to transfer.
      wallet_from: Wallet to transfer from ("trading", "deposit" or "exchange").
      wallet_to: Wallet to transfer to ("trading", "deposit" or "exchange").

    Returns:
      status: "success" or "error".
      message: Success or error message.
    """
    self._post_request(
        '/transfer',
        {'amount': amount, 'currency': currency, 'wallet_from': wallet_from,
         'wallet_to': wallet_to})

  def withdraw(self, withdraw_type, wallet, amount, **kwargs):
    """Withdraw from a wallet.

    Example:
      [{
        "status":"success",
        "message":"Your withdrawal request has been successfully submitted.",
        "withdrawal_id":586829
      }]

    Args:
      withdraw_type: one of 'bitcoin', 'litecoin', 'ethereum', 'ethereumc',
        'mastercoin', 'zcash', 'monero', 'wire', 'dash', 'ripple', 'eos', 'neo',
        'aventus', 'qtum', 'eidoo'.
      wallet: The wallet to withdraw from ("trading", "exchange", or "deposit").
      amount: Amount to withdraw.
      address: Destination address for withdrawal.
      payment_id: Optional hex string to identify a Monero transaction.
      account_name: Account name.
      account_number: Account number.
      swift: The SWIFT code for your bank.
      bank_name: Bank name.
      bank_address: Bank address.
      bank_city: Bank city.
      bank_country: Bank country.
      detail_payment: Message to beneficiary.
      expressWire: 1 to submit an express wire withdrawal, 0 or omit for a
        normal withdrawal.
      intermediary_bank_name: Intermediary bank name.
      intermediary_bank_address: Intermediary bank address.
      intermediary_bank_city: Intermediary bank city.
      intermediary_bank_country: Intermediary bank country.
      intermediary_bank_account: Intermediary bank account.
      intermediary_bank_swift: Intermediary bank SWIFT.

    Notes:
      * For ALL withdrawals, you must supply the Withdrawal Type, the Wallet and
        the Amount.
      * For CRYPTOCURRENCY withdrawals, you will also supply the Address where
        the funds should be sent. If it is a monero transaction, you can also
        include a Payment ID.
      * For WIRE WITHDRAWALS, you will need to fill in the beneficiary bank
        information.
      * In some cases your bank will require the use of an intermediary bank, if
        this is the case, please supply those fields as well.
      * When submitting a Ripple Withdrawal via API, you should include tag in
        the payment_id field.

    Returns:
      status: "success" or "error".
      message: Success or error message.
      withdrawal_id: ID of the withdrawal (or 0 if unsuccessful).
    """
    payload = {
        'withdraw_type': withdraw_type,
        'walletselected': wallet,
        'amount': amount,
    }
    payload.update(kwargs)
    self._post_request('/withdraw', payload)

  ...  # to be continued
