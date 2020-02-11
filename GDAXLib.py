import hmac
import hashlib
import time
import requests
import base64
import json
from requests.auth import AuthBase


class GdaxAuth(AuthBase):
    # Provided by gdax: https://docs.gdax.com/#signing-a-message
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        message = timestamp + request.method + request.path_url + (request.body or '')
        request.headers.update(get_auth_headers(timestamp, message, self.api_key, self.secret_key,
                                                self.passphrase))
        return request


def get_auth_headers(timestamp, message, api_key, secret_key, passphrase):
    message = message.encode('ascii')
    hmac_key = base64.b64decode(secret_key)
    signature = hmac.new(hmac_key, message, hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')
    return {
        'Content-Type': 'Application/JSON',
        'CB-ACCESS-SIGN': signature_b64,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-ACCESS-KEY': api_key,
        'CB-ACCESS-PASSPHRASE': passphrase
    }


class PublicClient(object):
    """GDAX public client API.
    All requests default to the `product_id` specified at object
    creation if not otherwise specified.
    Attributes:
        url (Optional[str]): API URL. Defaults to GDAX API.
    """

    def __init__(self, api_url='https://api.gdax.com', timeout=30):
        """Create GDAX API public client.
        Args:
            api_url (Optional[str]): API URL. Defaults to GDAX API.
        """
        self.url = api_url.rstrip('/')
        self.timeout = timeout

    def _get(self, path, params=None):
        """Perform get request"""

        r = requests.get(self.url + path, params=params, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_products(self):
        """Get a list of available currency pairs for trading.
        Returns:
            list: Info about all currency pairs. Example::
                [
                    {
                        "id": "BTC-USD",
                        "display_name": "BTC/USD",
                        "base_currency": "BTC",
                        "quote_currency": "USD",
                        "base_min_size": "0.01",
                        "base_max_size": "10000.00",
                        "quote_increment": "0.01"
                    }
                ]
        """
        return self._get('/products')

    def get_product_order_book(self, product_id, level=1):
        """Get a list of open orders for a product.
        The amount of detail shown can be customized with the `level`
        parameter:
        * 1: Only the best bid and ask
        * 2: Top 50 bids and asks (aggregated)
        * 3: Full order book (non aggregated)
        Level 1 and Level 2 are recommended for polling. For the most
        up-to-date data, consider using the websocket stream.
        **Caution**: Level 3 is only recommended for users wishing to
        maintain a full real-time order book using the websocket
        stream. Abuse of Level 3 via polling will cause your access to
        be limited or blocked.
        Args:
            product_id (str): Product
            level (Optional[int]): Order book level (1, 2, or 3).
                Default is 1.
        Returns:
            dict: Order book. Example for level 1::
                {
                    "sequence": "3",
                    "bids": [
                        [ price, size, num-orders ],
                    ],
                    "asks": [
                        [ price, size, num-orders ],
                    ]
                }
        """

        # Supported levels are 1, 2 or 3
        level = level if level in range(1, 4) else 1
        return self._get('/products/{}/book'.format(str(product_id)), params={'level': level})

    def get_product_ticker(self, product_id):
        """Snapshot about the last trade (tick), best bid/ask and 24h volume.
        **Caution**: Polling is discouraged in favor of connecting via
        the websocket stream and listening for match messages.
        Args:
            product_id (str): Product
        Returns:
            dict: Ticker info. Example::
                {
                  "trade_id": 4729088,
                  "price": "333.99",
                  "size": "0.193",
                  "bid": "333.98",
                  "ask": "333.99",
                  "volume": "5957.11914015",
                  "time": "2015-11-14T20:46:03.511254Z"
                }
        """
        return self._get('/products/{}/ticker'.format(str(product_id)))

    def get_product_trades(self, product_id):
        """List the latest trades for a product.
        Args:
            product_id (str): Product
        Returns:
            list: Latest trades. Example::
                [{
                    "time": "2014-11-07T22:19:28.578544Z",
                    "trade_id": 74,
                    "price": "10.00000000",
                    "size": "0.01000000",
                    "side": "buy"
                }, {
                    "time": "2014-11-07T01:08:43.642366Z",
                    "trade_id": 73,
                    "price": "100.00000000",
                    "size": "0.01000000",
                    "side": "sell"
                }]
        """
        return self._get('/products/{}/trades'.format(str(product_id)))

    def get_product_historic_rates(self, product_id, start=None, end=None,
                                   granularity=None):
        """Historic rates for a product.
        Rates are returned in grouped buckets based on requested
        `granularity`. If start, end, and granularity aren't provided,
        the exchange will assume some (currently unknown) default values.
        Historical rate data may be incomplete. No data is published for
        intervals where there are no ticks.
        **Caution**: Historical rates should not be polled frequently.
        If you need real-time information, use the trade and book
        endpoints along with the websocket feed.
        The maximum number of data points for a single request is 200
        candles. If your selection of start/end time and granularity
        will result in more than 200 data points, your request will be
        rejected. If you wish to retrieve fine granularity data over a
        larger time range, you will need to make multiple requests with
        new start/end ranges.
        Args:
            product_id (str): Product
            start (Optional[str]): Start time in ISO 8601
            end (Optional[str]): End time in ISO 8601
            granularity (Optional[str]): Desired time slice in seconds
        Returns:
            list: Historic candle data. Example::
                [
                    [ time, low, high, open, close, volume ],
                    [ 1415398768, 0.32, 4.2, 0.35, 4.2, 12.3 ],
                    ...
                ]
        """
        params = {}
        if start is not None:
            params['start'] = start
        if end is not None:
            params['end'] = end
        if granularity is not None:
            params['granularity'] = granularity

        return self._get('/products/{}/candles'.format(str(product_id)), params=params)

    def get_product_24hr_stats(self, product_id):
        """Get 24 hr stats for the product.
        Args:
            product_id (str): Product
        Returns:
            dict: 24 hour stats. Volume is in base currency units.
                Open, high, low are in quote currency units. Example::
                    {
                        "open": "34.19000000",
                        "high": "95.70000000",
                        "low": "7.06000000",
                        "volume": "2.41000000"
                    }
        """
        return self._get('/products/{}/stats'.format(str(product_id)))

    def get_currencies(self):
        """List known currencies.
        Returns:
            list: List of currencies. Example::
                [{
                    "id": "BTC",
                    "name": "Bitcoin",
                    "min_size": "0.00000001"
                }, {
                    "id": "USD",
                    "name": "United States Dollar",
                    "min_size": "0.01000000"
                }]
        """
        return self._get('/currencies')

    def get_time(self):
        """Get the API server time.
        Returns:
            dict: Server time in ISO and epoch format (decimal seconds
                since Unix epoch). Example::
                    {
                        "iso": "2015-01-07T23:47:25.201Z",
                        "epoch": 1420674445.201
                    }
        """
        return self._get('/time')


class AuthenticatedClient(PublicClient):
    def __init__(self, key, b64secret, passphrase, api_url="https://api.gdax.com", timeout=30):
        super(AuthenticatedClient, self).__init__(api_url)
        self.auth = GdaxAuth(key, b64secret, passphrase)
        self.timeout = timeout

    def get_account(self, account_id):
        r = requests.get(self.url + '/accounts/' + account_id, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_accounts(self):
        return self.get_account('')

    def get_account_history(self, account_id):
        result = []
        r = requests.get(self.url + '/accounts/{}/ledger'.format(account_id), auth=self.auth,
                         timeout=self.timeout)
        # r.raise_for_status()
        result.append(r.json())
        if "cb-after" in r.headers:
            self.history_pagination(account_id, result, r.headers["cb-after"])
        return result

    def history_pagination(self, account_id, result, after):
        r = requests.get(self.url + '/accounts/{}/ledger?after={}'.format(account_id, str(after)),
                         auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        if r.json():
            result.append(r.json())
        if "cb-after" in r.headers:
            self.history_pagination(account_id, result, r.headers["cb-after"])
        return result

    def get_account_holds(self, account_id):
        result = []
        r = requests.get(self.url + '/accounts/{}/holds'.format(account_id), auth=self.auth,
                         timeout=self.timeout)
        # r.raise_for_status()
        result.append(r.json())
        if "cb-after" in r.headers:
            self.holds_pagination(account_id, result, r.headers["cb-after"])
        return result

    def holds_pagination(self, account_id, result, after):
        r = requests.get(self.url + '/accounts/{}/holds?after={}'.format(account_id, str(after)),
                         auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        if r.json():
            result.append(r.json())
        if "cb-after" in r.headers:
            self.holds_pagination(account_id, result, r.headers["cb-after"])
        return result

    def order_buy_sell(self, kwargs):
        print kwargs

        r = requests.post(self.url + '/orders',
                          json=kwargs,
                          auth=self.auth,
                          timeout=self.timeout)
        return r.json()



    def cancel_order(self, order_id):
        r = requests.delete(self.url + '/orders/' + order_id, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def cancel_all(self, product_id=''):
        url = self.url + '/orders/'
        if product_id:
            url += "?product_id={}&".format(str(product_id))
        r = requests.delete(url, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_order(self, order_id):
        r = requests.get(self.url + '/orders/' + order_id, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_orders(self, product_id='', status=[]):
        result = []
        url = self.url + '/orders/'
        params = {}
        if product_id:
            params["product_id"] = product_id
        if status:
            params["status"] = status
        r = requests.get(url, auth=self.auth, params=params, timeout=self.timeout)
        # r.raise_for_status()
        result.append(r.json())
        if 'cb-after' in r.headers:
            self.paginate_orders(product_id, status, result, r.headers['cb-after'])
        return result

    def paginate_orders(self, product_id, status, result, after):
        url = self.url + '/orders'

        params = {
            "after": str(after),
        }
        if product_id:
            params["product_id"] = product_id
        if status:
            params["status"] = status
        r = requests.get(url, auth=self.auth, params=params, timeout=self.timeout)
        # r.raise_for_status()
        if r.json():
            result.append(r.json())
        if 'cb-after' in r.headers:
            self.paginate_orders(product_id, status, result, r.headers['cb-after'])
        return result

    def get_fills(self, order_id='', product_id='', before='', after='', limit=''):
        result = []
        url = self.url + '/fills?'
        if order_id:
            url += "order_id={}&".format(str(order_id))
        if product_id:
            url += "product_id={}&".format(product_id)
        if before:
            url += "before={}&".format(str(before))
        if after:
            url += "after={}&".format(str(after))
        if limit:
            url += "limit={}&".format(str(limit))
        r = requests.get(url, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        result.append(r.json())
        if 'cb-after' in r.headers and limit is not len(r.json()):
            return self.paginate_fills(result, r.headers['cb-after'], order_id=order_id, product_id=product_id)
        return result

    def paginate_fills(self, result, after, order_id='', product_id=''):
        url = self.url + '/fills?after={}&'.format(str(after))
        if order_id:
            url += "order_id={}&".format(str(order_id))
        if product_id:
            url += "product_id={}&".format(product_id)
        r = requests.get(url, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        if r.json():
            result.append(r.json())
        if 'cb-after' in r.headers:
            return self.paginate_fills(result, r.headers['cb-after'], order_id=order_id, product_id=product_id)
        return result

    def get_fundings(self, result='', status='', after=''):
        if not result:
            result = []
        url = self.url + '/funding?'
        if status:
            url += "status={}&".format(str(status))
        if after:
            url += 'after={}&'.format(str(after))
        r = requests.get(url, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        result.append(r.json())
        if 'cb-after' in r.headers:
            return self.get_fundings(result, status=status, after=r.headers['cb-after'])
        return result

    def repay_funding(self, amount='', currency=''):
        payload = {
            "amount": amount,
            "currency": currency  # example: USD
        }
        r = requests.post(self.url + "/funding/repay", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def margin_transfer(self, margin_profile_id="", transfer_type="", currency="", amount=""):
        payload = {
            "margin_profile_id": margin_profile_id,
            "type": transfer_type,
            "currency": currency,  # example: USD
            "amount": amount
        }
        r = requests.post(self.url + "/profiles/margin-transfer", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_position(self):
        r = requests.get(self.url + "/position", auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def close_position(self, repay_only=""):
        payload = {
            "repay_only": repay_only or False
        }
        r = requests.post(self.url + "/position/close", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def deposit(self, amount="", currency="", payment_method_id=""):
        payload = {
            "amount": amount,
            "currency": currency,
            "payment_method_id": payment_method_id
        }
        r = requests.post(self.url + "/deposits/payment-method", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def coinbase_deposit(self, amount="", currency="", coinbase_account_id=""):
        payload = {
            "amount": amount,
            "currency": currency,
            "coinbase_account_id": coinbase_account_id
        }
        r = requests.post(self.url + "/deposits/coinbase-account", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def withdraw(self, amount="", currency="", payment_method_id=""):
        payload = {
            "amount": amount,
            "currency": currency,
            "payment_method_id": payment_method_id
        }
        r = requests.post(self.url + "/withdrawals/payment-method", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def coinbase_withdraw(self, amount="", currency="", coinbase_account_id=""):
        payload = {
            "amount": amount,
            "currency": currency,
            "coinbase_account_id": coinbase_account_id
        }
        r = requests.post(self.url + "/withdrawals/coinbase", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def crypto_withdraw(self, amount="", currency="", crypto_address=""):
        payload = {
            "amount": amount,
            "currency": currency,
            "crypto_address": crypto_address
        }
        r = requests.post(self.url + "/withdrawals/crypto", data=json.dumps(payload), auth=self.auth,
                          timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_payment_methods(self):
        r = requests.get(self.url + "/payment-methods", auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_coinbase_accounts(self):
        r = requests.get(self.url + "/coinbase-accounts", auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def create_report(self, report_type="", start_date="", end_date="", product_id="", account_id="",
                      report_format="",
                      email=""):
        payload = {
            "type": report_type,
            "start_date": start_date,
            "end_date": end_date,
            "product_id": product_id,
            "account_id": account_id,
            "format": report_format,
            "email": email
        }
        r = requests.post(self.url + "/reports", data=json.dumps(payload), auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_report(self, report_id=""):
        r = requests.get(self.url + "/reports/" + report_id, auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()

    def get_trailing_volume(self):
        r = requests.get(self.url + "/users/self/trailing-volume", auth=self.auth, timeout=self.timeout)
        # r.raise_for_status()
        return r.json()