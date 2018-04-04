"""General cryptographic functions."""
import time


def nonce():
  """Returns a nonce."""
  return str(int(time.time() * 1000000))
