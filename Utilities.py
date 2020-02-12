import requests as req
import os
import psycopg2
import datetime
import threading
import base64
import hashlib
import hmac
import uuid
import sendgrid
import RPCUtils as rpc

if 'Development' in os.environ['APP_SETTINGS']:
    baseURL = 'https://bitlynx-staging.herokuapp.com/'
elif 'Production' in os.environ['APP_SETTINGS']:
    baseURL = "https://bitlynx.herokuapp.com/"
elif 'Staging' in os.environ['APP_SETTINGS']:
    baseURL = 'https://bitlynx-staging.herokuapp.com/'

if 'Development' in os.environ['APP_SETTINGS']:
    db_url = """postgres://zbbkqlsfdaogoj:6c6b047fc1856aa4332a19dac73083af7a8d007c21f51ecaf324dcd085516e79@ec2-23-23-222-184.compute-1.amazonaws.com:5432/d9nsd1kp8hr78k"""


def GetBestPrice(exchlist, currrency, side, market_selection, customerid=None):

    def getprices(exchange, currency, side, market_selection, results,index):
        if exchange != 'ShapeShift':
            if exchange == 'GDAX':
                k = GDAXBidASk(currrency)

            elif exchange == 'Gemini':
                k = GeminiBidAsk(currrency)

            elif exchange == 'Bittrex':
                k = BittrexBidAsk(currency, market_selection)

            elif exchange == 'Kraken':
                k = KrakenBidAsk(currency, market_selection)

            if side == 'Buy':
                price = k['AskPrice']
            else:
                price = k['BidPrice']

        #Shapeshift
        else:
            #hardcoding at the moment to buy with bitcoin 4/21/18
            if side == 'Buy':
                currency_from = 'btc'
                currency_to = currency.lower()
                rate, input_denom_price, minimum, limit, max_limit, miner_fee = GetRateAndLimit(currency_from,
                                                                                                currency_to)

            else:
                currency_from = currency.lower()
                currency_to = 'btc'
                rate, input_denom_price, minimum, limit, max_limit, miner_fee = GetRateAndLimit(currency_from,
                                                                                                currency_to)



            #GET BTC Price
            url = baseURL + "api/info/priceinfo"
            params = {"CustomerID":customerid,"Currency":"BTC","Side":side}
            x = req.post(url, data=params)
            x = x.json()
            btc_price_usd = float(x['best_price'] )

            #accounting for fees in here
            if side == 'Buy':
                price = (input_denom_price  * btc_price_usd )
            else:
                price = (input_denom_price / btc_price_usd)

        results[index] = (exchange, price)


    threads = [None for i in range(len(exchlist))]
    results = [None for i in range(len(exchlist))]
    for i, exch in enumerate(exchlist):
        threads[i] = threading.Thread(target=getprices, args=(exch, currrency, side, market_selection, results, i))
        threads[i].start()

    for j in range(len(threads)):
        threads[j].join()

    return results

#ShapeShift
def GenTransactionID():
    return uuid.uuid4().hex[:16].upper()

#ShapeShift
def TXStatusAddress(deposit_address):
    url = "https://shapeshift.io/txStat/" + deposit_address
    x = req.get(url)
    x = x.json()
    print x

#ShapeShift
def GetRateAndLimit(currency_from, currency_to):
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

#ShapeShift
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

#ShapeShift
def ValidateAddress(address, coin_symbol):
    url = "https://shapeshift.io/validateAddress/" + address + "/" + coin_symbol
    x = req.get(url)
    x = x.json()
    isvalid = x['isvalid']
    if str(isvalid).lower() == 'true':
        return True
    else:
        return False

def ShapeShiftBidAsk(currency):
    #get BTC ask rate
    pair = 'btc' + "_" + currency.lower()
    url = "https://shapeshift.io/marketinfo/" + pair
    x = req.get(url)
    x = x.json()
    rate = float(x['rate'])
    ask_rate = 1 / rate
    ask_vol = float(x['limit'])

    #get bid rate
    pair = currency.lower() + "_btc"
    url = "https://shapeshift.io/marketinfo/" + pair
    x = req.get(url)
    x = x.json()
    bid_rate = float(x['rate'])
    bid_vol = float(x['limit'])


    url = baseURL + "api/info/priceinfo"
    params = {"CustomerID": customerid, "Currency": "BTC", "Side": side}
    x = req.post(url, data=params)
    x = x.json()
    btc_price_usd = float(x['best_price'])

    bid_price = round(bid_rate * btc_price_usd,2)
    ask_price = round(ask_rate * btc_price_usd,2)

    return_dict = {"BidPrice": bid_price,
                   "BidVol": bid_vol,
                   "AskPrice": ask_price,
                   "AskVol": ask_vol,
                   "ExchangeCode": "ShapeShift",
                   "CurrencyCode": currency.upper() + "-USD",
                   "TimeStamp": datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}

    return return_dict


#ShapeShift
def RequestEmailReceipt(email, txid):
    url = "https://shapeshift.io/mail"
    params = {"email": email, "txid": txid}
    x = req.post(url, data=params)
    x = x.json()
    response = x['email']
    if str(response['status']).lower() == 'success':
        return True
    else:
        return False


#ShapeShift
def Transact(currency_from, currency_to, amount_to_buy):
    pair = currency_from.lower() + "_" + currency_to.lower()
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

    if ValidateAddress(to_address, currency_to):

        url = "https://shapeshift.io/shift"
        params = {
            "withdrawal": to_address,  # address to send the coin we want to
            "pair": pair,
            "returnAddress": return_address

        }
        x = req.post(url, data=params)
        response = x.json()
        deposit_address = response['deposit']
        txid_shapeshift = response['orderId']

        # Calculate amounts and prices
        rate, input_denom_price, minimum, limit, max_limit, miner_fee = GetRateAndLimit(currency_from, currency_to)

        # ex want to buy 6 LTC
        crypto_to_wthdraw = input_denom_price * amount_to_buy

        # get api info for exchange that we are withdrawing from to send to shapeshift
        api_key, api_secret, api_passphrase = GetAPIKeyData(from_exchange)
        if from_exchange.lower() == 'gdax':
            from GDAXLib import AuthenticatedClient
            # GDAX Specifications
            crypto_to_wthdraw = round(crypto_to_wthdraw, 8)
            my_auth = AuthenticatedClient(api_key, api_secret, api_passphrase)
            x = my_auth.crypto_withdraw(amount=str(crypto_to_wthdraw),
                                        currency=str(currency_from).upper(),
                                        crypto_address=deposit_address)
            transfer_id_host = x['id']

        return_message = {"exchange":"ShapeShift",
                          "ss_deposit_address": deposit_address,
                          "shapeshift_txid": txid_shapeshift,
                          "currency_from": currency_from,
                          "currency_to": currency_to,
                          "price_denom_currency_from": input_denom_price,
                          "from_exchange": from_exchange,
                          "from_address": from_address,
                          "crypto_withdrawn": crypto_to_wthdraw,
                          "withdraw_txid": transfer_id_host}

        return return_message


def LogResponse(response, exchange, amount, accountnum, price, currencypair, side, market_selection):
    if exchange != "ShapeShift":
        if exchange == 'GDAX':
            exchangecode = exchange
            accountnum = accountnum
            transid = response['id']
            status = response['status']
            currencypair = response['product_id']
            side = response['side']
            ordertype = response['type']


        elif exchange == 'Gemini':
            exchangecode = exchange
            accountnum = accountnum
            transid = response['order_id']
            if float(response['remaining_amount']) > 0:
                status = 'pending'
            else:
                status = 'completed'

            currencypair = response['symbol']
            side = response['side']
            ordertype = response['type']

        elif exchange == 'Kraken':
            exchangecode = exchange
            accountnum = accountnum
            ordertype = 'market'
            status = 'pending'

            x = response['result']
            transid = x['txid']
            transid = transid[0]

            x = response['result']
            x = x['descr']
            data = str(x['order']).split()
            side = data[0]
            currencypair = data[2]

        elif exchange == 'Bittrex':
            x = response['result']
            exchangecode = exchange
            transid = x['uuid']
            status = 'pending'
            currencypair = str(currencypair).replace("BTC","USD")
            ordertype = 'Limit'

        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cursor = conn.cursor()
        SQL = """Insert into orderhistory(exchangecode,timestamp,amount,accountnum,transid,status,currencypair,side,ordertype,
        price,market_selection) values ('{}',current_timestamp,{},{},'{}','{}','{}','{}','{}',{},'{}') RETURNING tradeid""".format(exchangecode,amount,
                                                            accountnum,transid,status,currencypair,side,ordertype,price,market_selection)
        cursor.execute(SQL)
        id_of_new_row = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        # tradeid | exchangecode | timestamp | amount | accountnum | transid | status | currencypair | side |
        # | ordertype | price
        #Sample GDAX Response:
        # {
        #     "id": "d0c5340b-6d6c-49d9-b567-48c4bfca13d2",
        #     "price": "0.10000000",
        #     "size": "0.01000000",
        #     "product_id": "BTC-USD",
        #     "side": "buy",
        #     "stp": "dc",
        #     "type": "limit",
        #     "time_in_force": "GTC",
        #     "post_only": false,
        #     "created_at": "2016-12-08T20:02:28.53864Z",
        #     "fill_fees": "0.0000000000000000",
        #     "filled_size": "0.00000000",
        #     "executed_value": "0.0000000000000000",
        #     "status": "pending",
        #     "settled": false
        # }


        #Sample gemini response
        # {
        #     "order_id": "22333",
        #     "client_order_id": "20150102-4738721",
        #     "symbol": "btcusd",
        #     "price": "34.23",
        #     "avg_execution_price": "34.24",
        #     "side": "buy",
        #     "type": "exchange limit",
        #     "timestamp": "128938491",
        #     "timestampms": 128938491234,
        #     "is_live": true,
        #     "is_cancelled": false,
        #     "options": ["maker-or-cancel"],
        #     "executed_amount": "12.11",
        #     "remaining_amount": "16.22",
        #     "original_amount": "28.33"
        # }
    #Exchange is shapeshift
    else:
        exchangecode = response['exchange']
        transid = response['shapeshift_txid']
        status = 'pending'
        ordertype = 'market'
        currency_from = response['currency_from']
        currency_to = response['currency_to']
        currencypair = str(currency_to).upper() + "-USD"
        ss_deposit_address = response['deposit_address']
        price_denom_currency_from = response['price_denom_currency_from']
        from_exchange = response['from_exchange']
        from_address = response['from_address'],
        crypto_withdrawn = response['crypto_withdrawn']
        withdraw_txid = response['withdraw_txid']


        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cursor = conn.cursor()
        SQL = """Insert into orderhistory(
        exchangecode,
        timestamp,
        amount,
        accountnum,
        currencypair,
        transid,
        status,
        side,
        ordertype,
        price,  
        ss_deposit_address,
        currency_from,
        currency_to,
        price_denom_currency_from,
        from_exchange,
        from_address,
        crypto_withdrawn,
        withdraw_txid) values('"""
        SQL += str(exchangecode) +"',current_timestamp," + str(amount) +"," +str(accountnum) +",'"+str(currencypair) +"','"
        SQL += str(transid) +"','" + str(status) +"','" +str(side) + "','" + str(ordertype) + "'," + str(price) + ",'"
        SQL += str(ss_deposit_address) + "','" + str(currency_from) + "','" + str(currency_to) +"'," +str(price_denom_currency_from)
        SQL += ",'" +str(from_exchange) +"','" +str(from_address) + "'," +str(crypto_withdrawn) + ",'" +str(withdraw_txid) +"')"
        cursor.execute(SQL)
        id_of_new_row = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        # {"exchange": "ShapeShift",
        #  "deposit_address": deposit_address,
        #  "shapeshift_txid": txid_shapeshift,
        #  "currency_from": currency_from,
        #  "currency_to": currency_to,
        #  "price_denom_currency_from": input_denom_price,
        #  "from_exchange": from_exchange,
        #  "from_address": from_address,
        #  "crypto_withdrawn": crypto_to_wthdraw,
        #  "withdraw_txid": transfer_id_host}
    return id_of_new_row, transid


def UpdateHoldings(currency,amount,side,customerid,exchange, price, cashbalance, total_trade_cost, bitlynx_fee, market_selection):
    #calculate trade cost

    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()

    #check to see if they have the coin in their holdings already
    SQL = "select amount,dollarvalue from holdings where currency = '" + str(currency) +"' and accountnum = " +str(customerid)
    SQL += " and exchangecode = '" + str(exchange) + "'"
    cursor.execute(SQL)
    x = cursor.fetchall()
    if len(x) > 0:
        #they have the coin in holdings already
        #get current amount of coin
        current_amount = float(x[0][0])
        #current dollar value of coin holdings (amt*price) at time of purchase
        current_dollar_value = float(x[0][1])
        if market_selection == "USD":
            if str(side).lower() == 'buy':
                #if they are buying
                #add in new amount they are getting
                new_amount = current_amount + float(amount)

                #subtract the money they spent on it
                new_cash_balance = round(cashbalance - total_trade_cost, 2)

                #new dollar value = old dollar value - price of trade in dollars
                new_dollar_value = round(new_amount * price, 2)
            else:
                #they are selling
                #subtract amount they are selling from current amount
                new_amount = current_amount - float(amount)

                #add in the money they gained from the trade
                new_cash_balance = round(cashbalance + total_trade_cost, 2)

                #new coin dollar value
                new_dollar_value = round(new_amount * price, 2)

            #update bitlynx cash balance
            SQL = "update holdings set amount  = " + str(new_cash_balance) + " where exchangecode ='BitLynx' and "
            SQL += "accountnum = "+str(customerid)
            cursor.execute(SQL)
            conn.commit()


            #update bitlynx cash balance
            SQL = "update holdings set dollarvalue  = " + str(new_cash_balance) + " where exchangecode ='BitLynx' and "
            SQL += "accountnum = " + str(customerid)
            cursor.execute(SQL)
            conn.commit()

            #update coin balances
            SQL = "Update holdings set amount = " + str(new_amount) + " where accountnum = " + str(customerid) + " and "
            SQL += "currency = '" + str(currency) +"' and exchangecode = '" + str(exchange) +"'"
            cursor.execute(SQL)
            conn.commit()

            #update coin balances
            SQL = "Update holdings set dollarvalue = " + str(new_dollar_value) + " where accountnum = " + str(customerid) + " and "
            SQL += "currency = '" + str(currency) + "' and exchangecode = '" + str(exchange) + "'"
            cursor.execute(SQL)
            conn.commit()

        elif market_selection == 'BTC':
            btc_balance = cashbalance
            btc_price_usd = GetBestPrice([exchange], 'BTC', side, "USD", customerid)
            btc_price_usd = btc_price_usd[0][1]
            if str(side).lower() == 'buy':
                # if they are buying
                # add in new amount they are getting
                new_amount = current_amount + float(amount)
                # new dollar value = old dollar value - price of trade in dollars
                new_dollar_value = round(new_amount * price * btc_price_usd, 2)

                # subtract the money they spent on it
                new_btc_balance = round(btc_balance - total_trade_cost, 2)
                new_btc_dollar_value = round(new_btc_balance * btc_price_usd, 2)
            else:
                # they are selling
                # subtract amount they are selling from current amount
                new_amount = current_amount - float(amount)
                new_dollar_value = round(new_amount * price * btc_price_usd, 2)

                # add in the money they gained from the trade
                new_btc_balance = btc_balance + total_trade_cost

                # new coin dollar value
                new__btc_dollar_value = round(new_btc_balance * btc_price_usd, 2)

            # update their exchange level btc balance
            SQL = """update holdings set amount = {} , dollarvalue = {} where exchangecode = '{}' 
                    and accountnum = {} and currency = '{}'""".format(new_btc_balance, new__btc_dollar_value,
                                                            exchange, customerid, market_selection)
            cursor.execute(SQL)
            conn.commit()

            # update coin balances
            SQL = """update holdings set amount = {}, dollarvalue = {} where exchangecode = '{}'
                    and accountnum = {} and currency = '{}'""".format(new_amount, new_dollar_value, exchange,
                                                                      customerid, currency)
            cursor.execute(SQL)
            conn.commit()

    else:
        #they don't already have the coin so make a new entry
        #this should only be hit when they are buying because if they are selling that means that they have bought
        #--with us before ( as of 3/29/18 )

        #calculate new cash balance

        if market_selection == "USD":
            new_amount = float(amount)
            # subtract the money they spent on it
            new_cash_balance = round(cashbalance - total_trade_cost, 2)
            # new dollar value = old dollar value - price of trade in dollars
            new_dollar_value = round(new_amount * price, 2)
            # insert coin record
            SQL = """insert into holdings(accountnum, exchangecode,currency,amount,dollarvalue)
                              values('{}','{}','{}','{}','{}')""".format(customerid, exchange, currency, new_amount,
                                                                        new_dollar_value)

            cursor.execute(SQL)
            conn.commit()

            #update cash balance
            SQL = """Update holdings set amount = {}, dollarvalue = {} where accountnum = {} and 
                exchangecode = 'BitLynx' and currency = 'USD'""".format(new_cash_balance,new_cash_balance,customerid)
            cursor.execute(SQL)
            conn.commit()

        elif market_selection == 'BTC':

            btc_balance = cashbalance
            btc_price_usd = GetBestPrice([exchange], 'BTC', side, "USD", customerid)
            btc_price_usd = btc_price_usd[0][1]

            new_amount = float(amount)
            new_dollar_value = round(new_amount * price * btc_price_usd, 2)

            # add in the money they gained from the trade
            new_btc_balance = round(btc_balance - total_trade_cost, 5)
            # new coin dollar value
            new_btc_dollar_value = round(new_btc_balance * btc_price_usd, 2)

            SQL = """insert into holdings(accountnum, exchangecode,currency,amount,dollarvalue)
                                          values('{}','{}','{}','{}','{}')""".format(customerid, exchange, currency,
                                                                                    new_amount,
                                                                                    new_dollar_value)

            cursor.execute(SQL)
            conn.commit()

            # update cash balance
            SQL = """Update holdings set amount = {}, dollarvalue = {} where accountnum = {} and 
                            exchangecode = 'BitLynx' and currency = 'BTC'""".format(new_btc_balance, new_btc_dollar_value,customerid)
            cursor.execute(SQL)
            conn.commit()



    conn.close()

def GDAXBidASk(currency):
    cur_pair = str(currency).upper() + "-" + "USD"
    endpoint = "/products/"+str(cur_pair)+"/book"
    url = "https://api.gdax.com"+endpoint
    y = req.get(url).json()
    bid_price = y['bids'][0][0]
    bid_vol = y['bids'][0][1]
    ask_price = y['asks'][0][0]
    ask_vol = y['asks'][0][1]
    return_dict = {"BidPrice": float(bid_price),
                   "BidVol": float(bid_vol),
                   "AskPrice": float(ask_price),
                   "AskVol": float(ask_vol),
                   "ExchangeCode":"GDAX",
                   "CurrencyCode":cur_pair,
                   "TimeStamp":datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}
    return return_dict

def KrakenBidAsk(currency, market_selection):
    if market_selection == 'USD':
        from KrakenLib import GetBidAsk
        if currency == 'BTC':
            currency = "XBT"
        cur_pair = "X" + str(currency).upper() + "ZUSD"
        bid_ask = GetBidAsk(cur_pair)
    else:
        cur_pair = "X" + str(currency).upper() + "XXBT"
        bid_ask = GetBidAsk(cur_pair)
    return bid_ask

def KrakenOrderBook(currency, side, depth, market_selection):
    if market_selection == "USD":
        from KrakenLib import GetOrderBook
        if currency == 'BTC':
            currency = "XBT"
        cur_pair = "X" + str(currency).upper() + "ZUSD"
    else:
        from KrakenLib import GetOrderBook
        cur_pair = "X" + str(currency).upper() + "XXBT"
    return GetOrderBook(cur_pair,side,depth, market_selection)

def BittrexOrderBook(currency, side, depth, market_selection):
    #return price in USD
    results_list = []
    cur_pair = "BTC-" + str(currency).upper()
    if currency not in ('BTC', 'LTC'):
        url = "https://bittrex.com/api/v1.1/public/getorderbook?market={}&type={}".format(cur_pair,side)
        y = req.get(url).json()
        y = y['result']

        #GetBTCprice
        if market_selection == 'USD':
            url = "https://bittrex.com/api/v1.1/public/getorderbook?market={}&type={}".format("USDT-BTC", side)
            x = req.get(url)
            x = x.json()
            x = x['result']
            x = x[0]['Rate']
            btc_price_usd = float(x)

            for i,item in enumerate(y,1):
                rate = round(float(item['Rate']) * btc_price_usd , 8)
                quantity = item['Quantity']
                results_list.append({'rate':rate,'quantity':quantity,'exchange':'Bittrex'})
                if i >= depth:
                    break
        else:
            for i,item in enumerate(y,1):
                rate = round(float(item['Rate']), 8)
                quantity = item['Quantity']
                results_list.append({'rate':rate,'quantity':quantity,'exchange':'Bittrex'})
                if i >= depth:
                    break
    else:
        if currency == 'BTC':
            cur_pair = "USDT-BTC"
        if currency == 'LTC':
            cur_pair = 'USDT-LTC'
        url = "https://bittrex.com/api/v1.1/public/getorderbook?market={}&type={}".format(cur_pair, side)
        y = req.get(url).json()
        y = y['result']
        for i, item in enumerate(y, 1):
            rate = round(float(item['Rate']), 2)
            quantity = item['Quantity']
            results_list.append({'rate': rate, 'quantity': quantity, 'exchange': 'Bittrex'})
            if i >= depth:
                break
    return results_list

def BittrexBidAsk(currency, market_selection):
    if currency <> 'BTC':
        #get currency bid ask
        cur_pair = "BTC-" + str(currency).upper()
        url = "https://bittrex.com/api/v1.1/public/getorderbook?market="+str(cur_pair)+"&type=both"
        y = req.get(url).json()
        y = y['result']
        bid_price = y['buy'][0]['Rate']
        bid_vol = y['buy'][0]['Quantity']
        ask_price = y['sell'][0]['Rate']
        ask_vol = y['sell'][0]['Quantity']

        #get bitcoin price dollars
        if market_selection == "USD":
            cur_pair = "USDT-BTC"
            url = "https://bittrex.com/api/v1.1/public/getorderbook?market=" + str(cur_pair) + "&type=both"
            y = req.get(url).json()
            y = y['result']
            bid_price_btc = y['buy'][0]['Rate']
            ask_price_btc = y['sell'][0]['Rate']


            return_dict = {"BidPrice": round(float(bid_price) * float(bid_price_btc) ,3),
                           "BidVol": float(bid_vol),
                           "AskPrice": round(float(ask_price) * float(ask_price_btc),3),
                           "AskVol": float(ask_vol),
                           "ExchangeCode":"Bittrex",
                           "CurrencyCode":cur_pair,
                           "TimeStamp":datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}
        else:
            return_dict = {"BidPrice":float(bid_price),
                           "BidVol": float(bid_vol),
                           "AskPrice": float(ask_price),
                           "AskVol": float(ask_vol),
                           "ExchangeCode":"Bittrex",
                           "CurrencyCode":cur_pair,
                           "TimeStamp":datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}
    else:
        cur_pair = "USDT-BTC"
        url = "https://bittrex.com/api/v1.1/public/getorderbook?market=" + str(cur_pair) + "&type=both"
        y = req.get(url).json()
        y = y['result']
        bid_price= y['buy'][0]['Rate']
        bid_vol = y['buy'][0]['Quantity']
        ask_price = y['sell'][0]['Rate']
        ask_vol = y['sell'][0]['Quantity']
        return_dict = {"BidPrice": float(bid_price),
                       "BidVol": float(bid_vol),
                       "AskPrice": float(ask_price),
                       "AskVol": float(ask_vol),
                       "ExchangeCode": "Bittrex",
                       "CurrencyCode": cur_pair,
                       "TimeStamp": datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}


    return return_dict


def GeminiBidAsk(currency):
    cur_pair = str(currency).lower() + "usd"
    url = "https://api.gemini.com/v1/book/"+str(cur_pair)
    y = req.get(url).json()
    bid_price = y['bids'][0]['price']
    bid_vol = y['bids'][0]['amount']
    ask_price = y['asks'][0]['price']
    ask_vol = y['asks'][0]['amount']
    return_dict = {"BidPrice": float(bid_price),
                   "BidVol": float(bid_vol),
                   "AskPrice": float(ask_price),
                   "AskVol": float(ask_vol),
                   "ExchangeCode":"Gemini",
                   "CurrencyCode":cur_pair,
                   "TimeStamp":datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}
    return return_dict

def GetExchanges():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    SQL = "select distinct Exchange from currency_availability"
    cursor.execute(SQL)
    x = cursor.fetchall()
    conn.close()
    exchanges = []
    for t in x:
        exchanges.append(t[0])
    return exchanges

def GetColors():
    return ["#F7464A", "#46BFBD", "#FDB45C", "#FEDCBA",
    "#ABCDEF", "#DDDDDD", "#ABCABC", "#4169E1",
    "#C71585", "#FF4500", "#FEDCBA", "#46BFBD"]


def GetCurrencies():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    SQL = "select distinct currency,name from currency_availability"
    cursor.execute(SQL)
    x = cursor.fetchall()
    conn.close()
    currencies = []

    for t in x:
        if t[0] != 'DOGE':
            currencies.append(t)
    # ss_currencies = GetCoinAvailabilityShapeShift()
    # currencies += ss_currencies
    currencies = set(currencies)
    currencies = sorted(list(currencies))
    #currencies = currencies.remove("DOGE")
    return currencies




def GetAPIKeyData(exchange):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    SQL = "select api_key, api_secret, api_passphrase from exchange_keys where exchange ='" + str(exchange) + "'"
    cursor.execute(SQL)
    api_data = cursor.fetchall()
    api_key = api_data[0][0]
    api_secret = api_data[0][1]
    api_passphrase = api_data[0][2]
    conn.close()
    return api_key,api_secret,api_passphrase

def GetAvailableCurrencies(market_selection):
    return_list = []
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    #conn = psycopg2.connect()
    cursor = conn.cursor()
    SQL = """select currency, name from currency_availability where market_availability = %s"""
    cursor.execute(SQL, (market_selection,))
    x = cursor.fetchall()
    for item in x:
        return_list.append((item[0],item[1]))
    conn.close()
    return sorted(return_list)

def GetCurrencyAvailabilty(currency, market_selection):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    SQL = """select distinct Exchange from currency_availability where currency = '{}' 
            and market_availability ='{}'""".format(currency, market_selection)
    cursor.execute(SQL)
    sup_exchs = []
    for exch in cursor.fetchall():
        sup_exchs.append(exch[0])
    conn.close()
    return sup_exchs

def CheckForError(response, exchange):
    if exchange == 'GDAX':
        if 'type' in response.keys():
            if response['type'] == 'error':
                error = True
                error_message = response['message']
            else:
                error = False
                error_message = None
        else:
            error = False
            error_message = None


    elif exchange == 'Gemini':
        if 'result' in response.keys():
            if response['result'] == 'error':
                error = True
                error_message = response['message']
            else:
                error = False
                error_message = None
        else:
            error = False
            error_message = None


    elif exchange == 'Kraken':
        if 'error' in response.keys():
            if response['error'] != []:
                error = True
                error_message = response['error']
                error_message = error_message[0]
            else:
                error = False
                error_message = None
        else:
            error = False
            error_message = None


    elif exchange == 'Bittrex':
        x = response['success']
        if x:
            error = False
            error_message = None
        else:
            error = True
            error_message = response['message']

    else:
        error = False
        error_message = None

    return error, error_message

def GetFeeFactor(exchange,side):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    mySQL = "select fee_factor from exchangefees where exchangecode = '" +str(exchange) + "' and side = '" +str(side).lower() +"'"
    cursor.execute(mySQL)
    results = cursor.fetchall()
    fee_factor = results[0][0]
    conn.close()
    return float(fee_factor)

def AddNotification(customerid,notification):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    mySQL = "Insert into notifications values(" +str(customerid) +",'" + notification +"',current_timestamp)"
    cursor.execute(mySQL)
    conn.commit()
    conn.close()

def BittrexCheckOrderStatus(transid):
    from BittrexLib import Bittrex
    api_key, api_secret, api_passphrase = GetAPIKeyData('Bittrex')
    my_auth = Bittrex(api_key,api_secret)
    r = my_auth.get_order(transid)
    r = r['result']
    s = r['IsOpen']
    if s:
        status = 'pending'
    else:
        status = 'complete'
    return status

def LogFees(trade_id, trans_id, customerid, side, amount, currency, bitlynx_fee_factor, bitlynx_fee, exchange,
            exchange_fee_factor,exchange_fee,bitlynx_fee_denom, exchange_fee_denom):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    mySQL = """Insert into bitlynxfees values
            ('{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')""".format(trade_id,trans_id,customerid,side,
            amount,currency,bitlynx_fee_factor,bitlynx_fee,exchange,exchange_fee_factor,exchange_fee,
            bitlynx_fee_denom, exchange_fee_denom)
    cursor.execute(mySQL)
    conn.commit()
    conn.close()

def ExecuteTrade(currency, amount, side, market_selection, customerid):

    #find what exchanges the coin they want to transact is supported on
    sup_exchs = GetCurrencyAvailabilty(currency, market_selection)

    #Get the best price of the currency across the supported exchanges
    price_results = GetBestPrice(sup_exchs,currency,side, market_selection, customerid)

    tdata = []

    for pdata in price_results:
        tdata.append(float(pdata[1]))

    #if buy find lowest price and exchange
    if side == 'Buy':
        winning_price = min(tdata)
        winning_index = tdata.index(winning_price)
        winning_exchange = price_results[winning_index][0]

    #if sell find highest price and exchange
    elif side == 'Sell':
        winning_price = max(tdata)
        winning_index = tdata.index(winning_price)
        winning_exchange = price_results[winning_index][0]

    order_tup = (winning_exchange,winning_price)

    #see how much cash they have
    if market_selection == "USD":
        url = baseURL + "api/info/balanceinfo"
        params = {'CustomerID':customerid}
        x = req.post(url,data=params)
        x = x.json()
        cash_bal = float(x['BitLynx_Balance'])
    elif market_selection == 'BTC':
        url = baseURL + "api/info/holdingsinfo"
        params = {'CustomerID': customerid}
        x = req.post(url, data=params)
        x = x.json()
        holdings = x['Holdings']
        cash_bal = 0
        for h in holdings:
            if h['currency'] == 'BTC':
                cash_bal =  float(h['amount'])
                break


    #see how much of the coin they want to transact they own
    ###
    url = baseURL + "api/info/holdingsinfo"
    params = {'CustomerID': customerid}
    x = req.post(url, data=params)
    x = x.json()
    holdings = x['Holdings']

    amount_owned = None
    for h in holdings:
        if h['currency'] == currency:
            amount_owned = h['amount']
            break
    if amount_owned == None:
        amount_owned = 0

    #calculate trade cost
    trade_cost = float(amount) * float(winning_price)

    #Calculate our fees
    bitlynx_fee_factor = GetFeeFactor('BitLynx',side)
    bitlynx_fee = bitlynx_fee_factor * trade_cost
    bitlynx_fee_denomination = market_selection

    #calculate what the exchange is getting
    if winning_exchange != "ShapeShift":
        exchange_fee_factor = GetFeeFactor(winning_exchange,side)
        exchange_fee = exchange_fee_factor * trade_cost
        exchange_fee_denomination = market_selection
    else:
        exchange_fee_factor = 0
        exchange_fee = 0


    #make sure they have enough money to pay our fee
    if side.lower() == 'buy':
        trade_cost = trade_cost + bitlynx_fee # + exchange_fee
    else:
        trade_cost = trade_cost - bitlynx_fee # - exchange_fee

    #4/14 added <= >= to logic, may need to change later
    if (trade_cost <= cash_bal and side == 'Buy') or (side == "Sell" and amount_owned >= float(amount)):
        if winning_exchange != "ShapeShift":
            api_key,api_secret,api_passphrase = GetAPIKeyData(order_tup[0])

            #implement bittrex 5-25-18

            if winning_exchange == 'Bittrex':
                from BittrexLib import Bittrex
                my_auth = Bittrex(api_key,api_secret)
                symbol = "BTC-" + currency.upper()

                ##Change for BTC 7-29-2018
                if currency == 'BTC':
                    symbol = "USDT-BTC"
                if currency == "LTC":
                    symbol = "USDT-LTC"
                if side.lower() == 'buy':
                    f = BittrexBidAsk(currency, market_selection)
                    rate = f['AskPrice']
                    response = my_auth.buy_limit(symbol,amount,rate)
                elif side.lower() == 'sell':
                    f = BittrexBidAsk(currency, market_selection)
                    rate = f['BidPrice']
                    response = my_auth.sell_limit(symbol,amount,rate)

            if winning_exchange == 'GDAX':
                from GDAXLib import AuthenticatedClient
                my_auth = AuthenticatedClient(api_key, api_secret, api_passphrase)
                symbol = str(currency).upper() + "-" + "USD"
                myargs = {"type": "market", "side": str(side).lower(), "product_id": symbol, "size": amount}
                response = my_auth.order_buy_sell(kwargs=myargs)


            elif winning_exchange == 'Gemini':
                from GeminiLib import Gemini
                # create authenticated client
                my_auth = Gemini(PUBLIC_API_KEY=api_key, PRIVATE_API_KEY=api_secret)
                # define symbol
                symbol = str(currency).lower() + "usd"
                # make new order
                response = my_auth.new_order(symbol, amount, order_tup[1], side,'exchange limit')

            elif winning_exchange == 'Kraken':
                if market_selection == "USD":
                    from KrakenLib import Buy, Sell
                    if currency == 'BTC':
                        currency = 'XBT'
                    symbol = "X" + currency.upper() + "ZUSD"
                    if side == 'Buy':
                        response = Buy(apikey=api_key, apisecret=api_secret,cur_pair = symbol,amount=amount)
                        if 'error' in response.keys():
                            if response['error'] != []:
                                symbol = symbol[1:]
                                symbol = str(symbol).replace("ZUSD", "USD", 1)
                                response = Buy(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)

                    elif side == 'Sell':
                        response = Sell(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)
                        if 'error' in response.keys():
                            if response['error'] != []:
                                symbol = symbol[1:]
                                symbol = str(symbol).replace("ZUSD", "USD", 1)
                                response = Sell(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)

                elif market_selection == 'BTC':
                    from KrakenLib import Buy, Sell
                    symbol = "X" + currency.upper() + "XXBT"
                    if side == 'Buy':
                        response = Buy(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)
                        if 'error' in response.keys():
                            if response['error'] != []:
                                symbol = symbol[1:]
                                symbol = str(symbol).replace("XXBT", "XBT", 1)
                                response = Buy(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)

                    elif side == 'Sell':
                        response = Sell(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)
                        if 'error' in response.keys():
                            if response['error'] != []:
                                symbol = symbol[1:]
                                symbol = str(cur_pair).replace("XXBT", "XBT", 1)
                                response = Sell(apikey=api_key, apisecret=api_secret, cur_pair=symbol, amount=amount)

        #Exchange is shapeshift
        #hardcoding bitcoin as the base currency for alt transactions 4/21/18
        else:
            symbol = None
            if side == "Buy":
                currency_from = 'btc'
                currency_to = str(currency).lower()
            else:
                currency_from = str(currency).lower()
                currency_to = 'btc'
            response = Transact(currency_from,currency_to,amount)


        error, error_message = CheckForError(response, winning_exchange)

        if not error:
            trade_id, trans_id = LogResponse(response, winning_exchange,amount, customerid, winning_price,symbol,side, market_selection)

            LogFees(trade_id,
                    trans_id,
                    customerid,
                    side,
                    amount,
                    currency,
                    bitlynx_fee_factor,
                    bitlynx_fee,
                    winning_exchange,
                    exchange_fee_factor,
                    exchange_fee,
                    bitlynx_fee_denomination,
                    exchange_fee_denomination)

            ############################################
            #ad hoc fix for kraken XBT
            ###########################################
            if winning_exchange == 'Kraken' and currency.lower() == 'xbt':
                currency = 'BTC'
            #############################################################
            UpdateHoldings(currency,amount,side,customerid,winning_exchange, winning_price, cash_bal, trade_cost,bitlynx_fee,market_selection)

            notification = "Trade Successfully Processed: You"
            if str(side).lower() == 'buy':
                notification += " bought "
                factor = -1
            else:
                notification += " sold "
                factor = 1
            notification += """{} {} for a total trade cost of {} {} on {} at {} EST""".format(amount, currency, (factor * trade_cost),
                    market_selection,datetime.datetime.now().strftime("%m-%d-%Y"),datetime.datetime.now().strftime("%H:%M"))
            AddNotification(customerid,notification)

            return "Trade Successful"
        else:
            return "Error during trade: " + error_message
    else:
        return "Trade Failed: Insufficient funds"

def GetAccountNums():
    return_list = []
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "select distinct id from login"
    cursor.execute(sql)
    x = cursor.fetchall()
    for id in x:
        return_list.append(id[0])
    conn.close()
    return return_list


def AddSupportTicket(accountnum,date,description):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "Insert into support_tickets(date_opened,ticket_desc,status,accountnum) values('"+str(date)+"','"+str(description)+"','Open',"
    sql += str(accountnum)+")"
    cursor.execute(sql)
    conn.commit()

    sql = "select ticket_id from support_tickets where accountnum = "+ str(accountnum)+" order by ticket_id desc limit 1"
    cursor.execute(sql)
    x = cursor.fetchall()
    return_id = x[0][0]
    conn.close()
    return return_id

def GDAXCheckOrderStatus(transid):
    api_key, api_secret, api_passphrase = GetAPIKeyData('GDAX')
    from GDAXLib import AuthenticatedClient
    my_auth = AuthenticatedClient(api_key, api_secret, api_passphrase)
    response = my_auth.get_order(transid)
    if response['status'] != 'done':
        status = 'pending'
    else:
        status='complete'
    return status

def ShapeShiftCheckOrderStatus(shapeshift_txid, address):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "Select * from shapeshift_keys limit 1"
    cursor.execute(sql)
    x = cursor.fetchall()
    x = x[0]
    public = x[0]
    private = x[1]
    conn.close()

    url = "https://shapeshift.io/txbyaddress/" + address + "/" + private
    x = req.get(url)
    x = x.json()
    status = ''
    for trans in x:
        if trans['inputTXID'] == shapeshift_txid:
            status = trans['status']
            break
    if str(status).lower() != 'complete':
        status = 'pending'
    return status

def GeminiCheckOrderStatus(transid):
    api_key, api_secret, api_passphrase = GetAPIKeyData('Gemini')
    from GeminiLib import Gemini
    # create authenticated client
    my_auth = Gemini(PUBLIC_API_KEY=api_key, PRIVATE_API_KEY=api_secret)
    response = my_auth.status_of_order(transid)
    if float(response['remaining_amount']) != 0:
        status = 'pending'
    else:
        status = 'complete'
    return status

def KrakenCheckOrderStatus(transid):
    api_key, api_secret, api_passphrase = GetAPIKeyData('Kraken')
    from KrakenLib import OrderStatus
    response = OrderStatus(apikey=api_key,apisecret=api_secret,transid=transid)
    if response == {}:
        return 'complete'
    else:
        found = False
        for r in response:
            if r['ordertxid'] == transid:
                found = True
                break
        if found:
            return 'pending'
        else:
            return 'pending'

def UpdateOrderStatus():
    # get all accounts
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    mySQL = "select distinct accountnum from orderhistory where status <> 'complete'"
    cursor.execute(mySQL)
    accountnums = cursor.fetchall()
    for a in accountnums:
        mySQL = "select exchangecode,transid,tradeid from orderhistory where accountnum = " + str(a[0])
        cursor.execute(mySQL)
        open_orders = cursor.fetchall()
        for o in open_orders:
            exchange = str(o[0]).rstrip()
            transid = o[1]
            tradeid = o[2]
            if exchange == 'GDAX':
                response = GDAXCheckOrderStatus(transid)

            elif exchange == 'Gemini':
                response = GeminiCheckOrderStatus(transid)

            elif exchange == 'Kraken':

                response = KrakenCheckOrderStatus(transid)

            elif exchange == 'ShapeShift':
                mySQL = "select ss_deposit_address where transid = '"+transid+"'"
                cursor.execute(mySQL)
                x = cursor.fetchall()
                address = x[0][0]
                response = ShapeShiftCheckOrderStatus(transid,address)

            elif exchange == 'Bittrex':
                response = BittrexCheckOrderStatus(transid)
            else:
                response = None

            if response == 'complete':
                mySQL = "update orderhistory set status = '" + str(response) + "' where tradeid = " +str(tradeid)
                cursor.execute(mySQL)
                conn.commit()
    conn.close()

def UpdateHistory():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    mySQL = "select distinct accountnum from holdings"
    cursor.execute(mySQL)
    accountnums = cursor.fetchall()
    for a in accountnums:
        acct_num = a[0]
        # update all the holdings to current dollar value
        mySQL = "select exchangecode,currency,amount from holdings where exchangecode <> 'BitLynx' and accountnum = " + str(
            acct_num)
        cursor.execute(mySQL)
        hdata = cursor.fetchall()

        if len(hdata) > 0:
            for d in hdata:
                exch = str(d[0]).rstrip()
                cur = d[1]
                amt = float(d[2])

                if exch == 'GDAX':
                    rdata = GDAXBidASk(cur)


                elif exch == 'Gemini':
                    rdata = GeminiBidAsk(cur)


                elif exch == 'Bittrex':
                    rdata = BittrexBidAsk(cur,'BTC')

                elif exch == 'Kraken':
                    rdata = KrakenBidAsk(cur,'USD')

                elif exch == 'ShapeShift':
                    rdata = ShapeShiftBidAsk(cur)

                price = (float(rdata['BidPrice']) + float(rdata['AskPrice'])) / 2
                dollar_val = round(price * amt, 2)

                mySQL = "Update holdings set dollarvalue = " + str(dollar_val) + " where accountnum = " + str(
                    acct_num) + " and exchangecode = '"
                mySQL += exch + "' and currency = '" + str(cur) + "'"
                cursor.execute(mySQL)
                conn.commit()

        # get the updated dollar value for each account (sum of all dollar values across coins)
        mySQL = "Select sum(DollarValue) from holdings where accountnum = " + str(acct_num)
        cursor.execute(mySQL)
        x = cursor.fetchall()
        value = x[0][0]

        # update the holdings history
        mySQL = "Insert into holdingshistory(accountnum,dollarvalue,timestamp) values (" + str(acct_num) + "," \
                + str(value) + ",current_timestamp)"
        cursor.execute(mySQL)
        conn.commit()

    # close connection
    conn.close()



def Hash(message):
    h = hmac.new(os.environ['FERNET'],message,hashlib.sha256)
    return base64.b64encode(h.digest())


def LogVisit(accountnum,ip_address):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    SQL = """insert into login_tracker values({},'{}',current_timestamp)""".format(accountnum,ip_address)
    cursor.execute(SQL)
    conn.commit()
    conn.close()


def GetAggOrderBook(currency, side, market_selection):
    exchlist = GetCurrencyAvailabilty(currency, market_selection)
    def getorderbook(exchange, currency, side, market_selection, results, index):
        count = 10
        if exchange == 'GDAX':
            print "Not supported"

        elif exchange == 'Gemini':
            print "Not supported"

        elif exchange == 'Bittrex':
            k = BittrexOrderBook(currency,side,count, market_selection)

        elif exchange == 'Kraken':
            k = KrakenOrderBook(currency, side, count, market_selection)

        results[index] = (k)

    threads = [None for i in range(len(exchlist))]
    results = [None for i in range(len(exchlist))]
    for i, exch in enumerate(exchlist):
        threads[i] = threading.Thread(target=getorderbook, args=(exch, currency, side, market_selection, results, i))
        threads[i].start()

    for j in range(len(threads)):
        threads[j].join()
    return results

def GetName(accountnum):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "select first_name from login where id = {}".format(accountnum)
    cursor.execute(sql)
    x = cursor.fetchall()
    name = x[0][0]
    conn.close()
    return name

def GetWalletAPIInfo(currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "Select api_key from wallet_api_keys where currency = '{}'".format(currency)
    cursor.execute(sql)
    x = cursor.fetchall()
    api_key = x[0][0]
    conn.close()
    return api_key

def GetChartExchange(currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "select exchange from currency_availability where currency = '{}'".format(currency)
    cursor.execute(sql)
    x = cursor.fetchall()
    exchange = x[0][0]
    conn.close()
    return exchange

def GetCorporateAddress(currency, exchange):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select address from bitlynx_wallets where coin = '{}' and host_exchange = '{}'""".format(str(currency).lower(), exchange)
    cursor.execute(sql)
    x = cursor.fetchall()
    address = x[0][0]
    conn.close()
    return address

def LogAddress(accountnum, address, currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """insert into user_wallets values({},'{}','Bitlynx BTC Wallet','{}','complete')""".format(accountnum,address,currency)
    cursor.execute(sql)
    conn.commit()
    conn.close()

def GetWalletAddress(customerid, currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select address from user_wallets where accountnum = {} and currency = '{}' 
    and wallet_status = 'complete'""".format(customerid, currency)
    cursor.execute(sql)
    x = cursor.fetchall()
    if len(x) > 0:
        wallet_address = x[0][0]
    else:
        wallet_address = "None"
    conn.close()
    return wallet_address

def GenerateWalletAddress(accountnum, currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select address from user_wallets where accountnum = {} and currency = '{}'""".format(accountnum, currency)
    cursor.execute(sql)
    x = cursor.fetchall()
    conn.close()
    if len(x) > 0:
        address = x[0][0]
    else:
        address = rpc.CreateBTCAddress(accountnum, currency)
    return address

def GetAllWalletAddresses():
    addresses = []
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select distinct address from user_wallets"""
    cursor.execute(sql)
    x = cursor.fetchall()
    for item in x:
        addresses.append(item[0])
    conn.close()
    return addresses

def GetAcctNumFromAddress(address):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select distinct accountnum from user_wallets where address = '{}'""".format(address)
    cursor.execute(sql)
    x = cursor.fetchall()
    accountnum = x[0][0]
    conn.close()
    return accountnum


def ProcessDeposit(address,currency,balance_change,funds_available,txid):
    #hardcoding forwarding exchange

    forwarding_exchange = 'Bittrex'

    #forwarding exchange
    addresses = GetAllWalletAddresses()
    if address in addresses:
        if funds_available:
            currency = str(currency)
            #set currency abbreviations
            if 'btc' in currency.lower():
                currency_abb = 'BTC'
            elif 'ltc' in currency.lower():
                currency_abb = 'LTC'
            elif 'doge' in currency.lower():
                currency_abb = 'DOGE'
            accountnum = GetAcctNumFromAddress(address)



            #get price for estimated value update
            p = {'CustomerID':accountnum,'Currency':currency_abb,'Side':"Sell","market_selection":"USD"}
            url = baseURL + "api/info/priceinfo"
            x = req.post(url,data=p)
            x = x.json()
            price = x['best_price']
            estimated_value = round(float(price) * float(balance_change) , 2)

            #start db connection
            conn = psycopg2.connect(os.environ['DATABASE_URL'])
            cursor = conn.cursor()

            #get a forwarding address
            sql = """select address from bitlynx_wallets where coin = '{}' and host_exchange = '{}'""".format(currency_abb.lower(),forwarding_exchange)
            cursor.execute(sql)
            x = cursor.fetchall()
            forwarding_address = str(x[0][0]).rstrip(" ")

            #update deposit history
            # when the funds are available we write into the db. We can now forward our funds from this wallet into the bittrex main wallet

            amt_to_withdraw = float(balance_change)

            sql = "select * from deposit_history where txid = '{}'".format(txid)
            cursor.execute(sql)
            x = cursor.fetchall()
            if len(x) == 0:
                sql = """Insert into deposit_history(accountnum,amount,txid,currency,wallet_address,deposit_status,funds_available,
                timestamp,estimated_value,forwarding_address) values({},{},'{}','{}',
                '{}','{}','{}',current_timestamp,{},'{}')""".format(accountnum,float(amt_to_withdraw),txid,currency_abb, address,'Complete','True',estimated_value,forwarding_address)

                cursor.execute(sql)
                conn.commit()

                #update holdings
                sql = """select amount from holdings where accountnum = {} 
                    and currency = '{}' and exchangecode = '{}'""".format(accountnum,currency_abb,forwarding_exchange)
                cursor.execute(sql)
                x = cursor.fetchall()
                if len(x) > 0:
                    sql = """update holdings set amount = amount + {}, dollarvalue = dollarvalue + {} 
                              where accountnum = {} and currency = '{}' and exchangecode = '{}'""".format(balance_change, estimated_value,
                                                                                                accountnum,currency_abb,forwarding_exchange)
                else:
                    sql = """insert into holdings values({},'{}','{}',{},{})""".format(accountnum, forwarding_exchange, currency_abb,

                                                                                                       amt_to_withdraw, estimated_value)
                cursor.execute(sql)
                conn.commit()

                #finally, check to see if they have a holdings history entry and update that for chart glitch
                sql = "Select * from holdingshistory where accountnum = {}".format(accountnum)
                cursor.execute(sql)
                x = cursor.fetchall()

                if len(x) == 0:
                    sql = "insert into holdingshistory values({},{},current_timestamp)".format(accountnum, amt_to_withdraw)
                    cursor.execute(sql)
                    conn.commit()

                #Send an email notification
                email = GetEmailAddress(accountnum)
                name = GetName(accountnum)
                email_params = {'amount':amt_to_withdraw, 'currency':currency_abb, 'name':name}
                SendEmail(email, 'Deposit', email_params)

                #when the funds are available we write into the db. We can now forward our funds from this wallet into the bittrex main wallet
                out_txid = rpc.SendBTC(forwarding_address, amt_to_withdraw)
                message = 'Deposit Processed'

                #Add a notification
                notification = "Your deposit of {} {} was successfully processed and is now available".format(currency_abb,amt_to_withdraw)
                AddNotification(accountnum,notification)

            else:
                message = 'Deposit Already Processed'
            conn.close()

        else:
            message = "Unconfirmed Transaction"
    else:
        message = "Address Not In System"

    return message

def GetWithdrawFee(currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select fee_amount from withdraw_fee_schedule where currency = '{}'""".format(currency)
    cursor.execute(sql)
    x = cursor.fetchall()
    fee_amount = float([0][0])
    conn.close()
    return fee_amount

def CheckLock(accountnum):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select is_locked from login where id = {}""".format(accountnum)
    cursor.execute(sql)
    x = cursor.fetchall()
    islocked = int([0][0])
    conn.close()
    if islocked == 0:
        islocked = False
    else:
        islocked = True
    return islocked

def WithdrawCurrency(withdrawal_address, withdrawal_amount, currency, accountnum):
    if not CheckLock(accountnum):
        exchange = 'Bittrex'
        api_key, api_secret, api_passphrase = GetAPIKeyData(exchange)
        url = baseURL + "api/info/holdingsinfo"

        #get how much of the coin they have
        params = {'CustomerID':accountnum}
        x = req.post(url, data=params)
        x = x.json()
        holdings = x['Holdings']
        available_amount_to_withdraw = 0
        for h in holdings:
            if h['currency'] == currency:
                available_amount_to_withdraw = h['amount']
                break

        #Get our withdrawal fee
        fee_amount = GetWithdrawFee(currency)
        #assess the fee
        withdrawal_amount = withdrawal_amount - fee_amount
        if available_amount_to_withdraw >= withdrawal_amount:

            #get wallet address we will withdraw from
            from_address = GetCorporateAddress(currency, exchange)

            #get an estimated value of withdrawal
            price = GetBestPrice([exchange], currency, 'Sell', 'USD', customerid=accountnum)
            estimated_value = round(withdrawal_amount * price , 2)
            if exchange == 'Bittrex':
                from BittrexLib import Bittrex
                my_auth = Bittrex(api_key, api_secret)
                response = my_auth.withdraw(currency, withdrawal_amount, withdrawal_address)
                txid = response['result']['uuid']


            elif exchange == 'Kraken':
                print "TEST"
                #log the withdrawal
                #update the holdings

            #Log withdrawal
            conn = psycopg2.connect(os.environ['DATABASE_URL'])
            cursor = conn.cursor()
            sql = """insert into withdawal_history values('{}','{}','{}','{}','{}',
            'Processed','{}',current_timestamp,'{}','{}'""".format(accountnum, withdrawal_amount, txid, currency,
                                                    withdrawal_address, from_address, estimated_value, fee_amount)
            cursor.execute(sql)
            conn.commit()

            #Update holdings
            sql = """update holdings
                    set amount = amount - {}, dollarvalue = dollarvalue - {} 
                    where accountnum = {} and currency = '{}' and exchange = '{}'""".format(withdrawal_amount,
                                                            estimated_value, accountnum, currency, exchange)
            cursor.execute(sql)
            conn.commit()
            conn.close()

            #send email
            name = GetName(accountnum)
            email = GetEmailAddress(accountnum)
            params = {'currency':currency,
                      'amount':withdrawal_amount,
                      'fee': fee_amount,
                      'name':name,
                      'email':email,
                      'toaddress':withdrawal_address}

            SendEmail(GetEmail(accountnum), 'Withdraw', params)
            result = "Success, Funds Withdrawn"
    else:
        result = "Account Is Locked, Withdrawal Disabled"
    return result


def SendEmail(to_email, email_type, params):
    username = os.environ['SENDGRID_USERNAME']
    password = os.environ['SENDGRID_PASSWORD']
    from_email = 'bitlynx_notifications@bitlynx.io'
    sg = sendgrid.SendGridClient(username, password)

    message = sendgrid.Mail()
    message.add_to(to_email)
    message.from_email = from_email
    message.set_html(' ')
    message.set_text(' ')

    if email_type == 'Login':
        message.set_subject('Bitlynx Login Notification')
        message.add_filter('templates', 'enable', '1')
        message.add_filter('templates', 'template_id', 'bac40bc7-bb9e-4b87-9061-2fcb24c6792d')
        ipaddress = params['ip_address']
        name = params['name']
        timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        message.add_substitution('-name-', name)
        message.add_substitution('-timestamp-', timestamp)
        message.add_substitution('-ipaddress-', ipaddress)

    elif email_type == 'Deposit':
        message.set_subject('Bitlynx Deposit Notification')
        message.add_filter('templates', 'enable', '1')
        message.add_filter('templates', 'template_id', '8a82d2d2-98e7-439d-9d33-969997687bc5')
        amount = params['amount']
        currency = params['currency']
        #get name
        name = params['name']

        timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        message.add_substitution('-amount-', amount)
        message.add_substitution('-timestamp-', timestamp)
        message.add_substitution('-currency-', currency)
        message.add_substitution('-name-', name)

    elif email_type == 'Withdraw':
        message.set_subject('Bitlynx Withdraw Notification')
        message.add_filter('templates', 'enable', '1')
        message.add_filter('templates', 'template_id', 'e4695ba0-b6c5-4837-8d6d-699c0561ed84')
        amount = params['amount']
        currency = params['currency']
        fee = params['fee']
        name = params['name']
        toaddress = params['toaddress']

        timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        message.add_substitution('-amount-', amount)
        message.add_substitution('-timestamp-', timestamp)
        message.add_substitution('-currency-', currency)
        message.add_substitution('-fee-', fee)
        message.add_substitution('-name-', name)
        message.add_substitution('-toaddress-', toaddress)

    status, msg = sg.send(message)

def GetEmailAddress(accountnum):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "select email from login where id = {}".format(accountnum)
    cursor.execute(sql)
    x = cursor.fetchall()
    email = x[0][0]
    conn.close()
    return email

def GetWithdrawableCurrencies():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = "select currency, name from currency_availability where exchange = 'Bittrex'"
    cursor.execute(sql)
    x = cursor.fetchall()
    return_list = []
    for item in x:
        y = (item[0], item[1])
        return_list.append(y)
    conn.close()
    return return_list


def OnfidoCreateContact(data, key):
    headers = {'Authorization': 'Token token=%s' % key,
                'Content-Type': 'application/json'}
    url = 'https://api.onfido.com/v2/applicants'
    x = req.post(url,data=data,headers=headers)
    x = x.json()
    return x['id']

def OnfidoCreateCheck(applicant_id, key, check_type='express'):

    url = 'https://api.onfido.com/v2/applicants/%s/checks' % applicant_id
    headers = {'Authorization': 'Token token=%s' % key,
               'Content-Type': 'application/json'}
    data = {
        "type": check_type,
        "reports": [{"name": "identity"}]
    }
    x = req.post(url, data=data, headers=headers)
    x = x.json()
    report_status = x['status']
    return report_status


def KYCSubmit(data):
    key, secret, passphrase = GetAPIKeyData('Onfido')
    applicant_id = OnfidoCreateContact(data,key)
    result = OnfidoCreateCheck(applicant_id,key,check_type='express')


