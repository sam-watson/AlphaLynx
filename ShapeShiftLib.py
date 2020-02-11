import requests as req
import uuid
import psycopg2
import os
import Utilities as utils


notif_email = "Andrew.hardy@bitlynx.io"

def GenTransactionID():
    return uuid.uuid4().hex[:16].upper()


def TXStatusAddress(deposit_address):
    url = "https://shapeshift.io/txStat/"+deposit_address
    x = req.get(url)
    x = x.json()
    print x


def GetRateAndLimit(currency_from,currency_to):
    pair = currency_from.lower() + "_" + currency_to.lower()
    url = "https://shapeshift.io/marketinfo/" + pair
    x = req.get(url)
    x = x.json()
    rate = x['rate']
    input_denom_price = 1 / rate
    minimum = x['minimum']
    limit = x['limit']
    max_limit = x['maxLimit']
    miner_fee = x['minerFee']
    return rate, input_denom_price, minimum, limit, max_limit, miner_fee


def GetCoinAvailabilityShapeShift():
    url = "https://shapeshift.io/getcoins"
    x = req.get(url)
    x = x.json()
    coin_list = []
    for coin in x:
        coin_list.append(coin)
    available_list = []
    for c in coin_list:
        data = x[c]
        if data['status'] == 'available':
            available_list.append(c)

    return available_list

def ValidateAddress(address, coin_symbol):
    url = "https://shapeshift.io/validateAddress/" + address + "/" + coin_symbol
    x = req.get(url)
    x = x.json()
    isvalid = x['isvalid']
    if str(isvalid).lower() == 'true':
        return True
    else:
        return False

def RequestEmailReceipt(email,txid):
    url = "https://shapeshift.io/mail"
    params = {"email":email,"txid":txid}
    x = req.post(url,data=params)
    x = x.json()
    response = x['email']
    if str(response['status']).lower() == 'success':
        return True
    else:
        return False

def ValidateTransactionStatus(shapeshift_txid, address):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "Select * from shapeshift_keys limit 1"
    cursor.execute(sql)
    x = cursor.fetchall()
    x = x[0]
    public = x[0]
    private = x[1]
    conn.close()

    url = "https://shapeshift.io/txbyaddress/"+address+"/"+private
    x = req.get(url)
    x = x.json()
    status = 'Not Found'
    for trans in x:
        if trans['inputTXID'] == shapeshift_txid:
            status = trans['status']
            break
    return status


def Transact(currency_from, currency_to, amount_to_buy):
    pair = currency_from.lower()+"_"+currency_to.lower()
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()

    sql = "select address from bitlynx_wallets where coin = '" + currency_from + "' limit 1"
    cursor.execute(sql)
    x = cursor.fetchall()
    from_address = x[0][0]
    return_address = from_address

    sql = "select host_exchange from bitlynx_wallets where coin = '" + currency_from + "' limit 1"
    cursor.execute(sql)
    x = cursor.fetchall()
    from_exchange = x[0][0]

    sql = "select address from bitlynx_wallets where coin = '" + currency_to + "' limit 1"
    cursor.execute(sql)
    x = cursor.fetchall()
    to_address = x[0][0]
    conn.close()

    if ValidateAddress(to_address,currency_to):

        url = "https://shapeshift.io/shift"
        params = {
                    "withdrawal":to_address, #address to send the coin we want to
                    "pair":pair,
                    "returnAddress":return_address

                 }
        x = req.post(url, data=params)
        response = x.json()
        deposit_address = response['deposit']
        txid_shapeshift = response['orderId']

        #Calculate amounts and prices
        rate, input_denom_price, minimum, limit, max_limit, miner_fee = GetRateAndLimit(currency_from,currency_to)

        #ex want to buy 6 LTC
        crypto_to_wthdraw = input_denom_price * amount_to_buy

        #get api info for exchange that we are withdrawing from to send to shapeshift
        api_key, api_secret, api_passphrase = utils.GetAPIKeyData(from_exchange)
        if from_exchange.lower() == 'gdax':
            from GDAXLib import AuthenticatedClient
            #GDAX Specifications
            crypto_to_wthdraw = round(crypto_to_wthdraw,8)
            my_auth = AuthenticatedClient(api_key, api_secret, api_passphrase)
            x = my_auth.crypto_withdraw(amount=str(crypto_to_wthdraw),
                                        currency=str(currency_from).upper(),
                                        crypto_address=deposit_address)
            transfer_id_host = x['id']

        return_message =  {"deposit_address":deposit_address,
               "shapeshift_txid":txid_shapeshift,
               "currency_from":currency_from,
               "currency_to":currency_to,
               "price_denom_currency_from":input_denom_price,
               "from_exchange":from_exchange,
               "from_address":from_address,
               "crypto_withdrawn":crypto_to_wthdraw,
               "withdraw_txid":transfer_id_host}

        return return_message

#############################################################################################################################
#testing

