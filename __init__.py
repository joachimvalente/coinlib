class Bitfinex(object):
  """Importing exchange to coinlib namespace."""

  def __new__(cls):
    from coinlib.exchanges import bitfinex
    return bitfinex.Bitfinex()


class Bittrex(object):
  """Importing exchange to coinlib namespace."""

  def __new__(cls):
    from coinlib.exchanges import bittrex
    return bittrex.Bittrex()
