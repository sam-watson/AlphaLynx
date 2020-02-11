import KrakenAPI as api
import KrakenConnection as connection
import datetime


def GetOrderBook(cur_pair,side,depth, market_selection):
    results_list = []
    client = api.API()
    params = {'pair': cur_pair, 'count': depth}
    x = client.query_public('Depth', params)

    if 'error' in x.keys():
        if x['error'] != []:
            cur_pair = cur_pair[1:]
            if market_selection == "USD":
                cur_pair = str(cur_pair).replace("ZUSD", "USD", 1)
            elif market_selection == "BTC":
                cur_pair = str(cur_pair).replace("XXBT", "XBT", 1)
            params = {'pair': cur_pair, 'count': depth}
            x = client.query_public('Depth', params)

    x = x['result']
    x = x[cur_pair]
    if side.lower() == 'buy':
        x = x['asks']
    elif side.lower() == 'sell':
        x = x['bids']
    for item in x:
        rate = float(item[0])
        quantity = float(item[1])
        results_list.append({'rate':rate,'quantity':quantity,'exchange':'Kraken'})
    return results_list


def GetBidAsk(cur_pair):
    client = api.API()
    params = {'pair': cur_pair,'count':1}
    x = client.query_public('Depth',params)

    if 'error' in x.keys():
        if x['error'] != []:
            cur_pair = cur_pair[1:]
            cur_pair = str(cur_pair).replace("ZUSD","USD",1)
            params = {'pair': cur_pair, 'count': 1}
            x = client.query_public('Depth', params)

    x = x['result']
    x = x[cur_pair]
    bid_price = x['bids'][0][0]
    bid_vol = x['bids'][0][1]
    ask_price = x['asks'][0][0]
    ask_vol =  x['asks'][0][1]
    return_dict = {"BidPrice": float(bid_price),
                   "BidVol": float(bid_vol),
                   "AskPrice": float(ask_price),
                   "AskVol": float(ask_vol),
                   "ExchangeCode": "Kraken",
                   "CurrencyCode": cur_pair,
                   "TimeStamp": datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")}
    return return_dict

def Buy(apikey,apisecret,cur_pair,amount):
    client = api.API(key=apikey,secret=apisecret)
    params = {'pair': cur_pair,
              'type': 'buy',
              'ordertype':'market',
              'volume':float(amount)}
    x = client.query_private('AddOrder',req=params)
    return x

def Sell(apikey,apisecret,cur_pair,amount):
    client = api.API(key=apikey, secret=apisecret)
    params = {'pair': cur_pair, 'type': 'sell', 'ordertype': 'market', 'volume':float(amount)}
    x = client.query_private('AddOrder',req=params)
    return x

def OrderStatus(apikey, apisecret, transid):
    client = api.API(key=apikey, secret=apisecret)
    params = {'docalcs': 'true'}
    x = client.query_private('OpenPositions',req=params)
    return x['result']

def GetDepositMethods(apikey, apisecret, currency):
    client = api.API(key=apikey, secret=apisecret)
    params = {'asset':currency}
    x = client.query_private('DepositMethods',req=params)
    if 'error' in x.keys():
        if x['error'] == []:
            data = x['result']
            if 'fee' in data[0].keys():
                fee = float(data[0]['fee'])
            else:
                fee = 0
            method = data[0]['method']
        else:
            method = 'unavailable'
            fee = 0

    return {'method':method, 'fee':fee}

def GenerateDepositAddress(apikey,apisecret,currency):
    x = GetDepositMethods(apikey, apisecret,currency)
    method = x['method']
    client = api.API(key=apikey, secret=apisecret)
    params = {'asset': currency,'method':method,'new':'true'}
    x = client.query_private('DepositMethods', req=params)
    deposit_address = x['address']
    return deposit_address

def GetDepositStatus(apikey, apisecret, currency):
    client = api.API(key=apikey, secret=apisecret)
    x = GetDepositMethods(apikey,apisecret,currency)
    method = x['method']
    if method != 'unavailable':
        params = {'asset':currency, 'method':method}
        x = client.query_private('DepositStatus',req=params)
        if 'error' in x.keys():
            if x['error'] == []:
                x = x['result']
                status = x['status']
                message = {'status':status}
            else:
                message = {'status':'Unknown'}
    else:
        message = {'status':'Unknown'}
    return message

def Withdrawal(apikey, apisecret, currency, amount_to_withdraw, withdraw_address):
    client = api.API(key=apikey, secret=apisecret)
    params = {'asset': currency, 'method': method}
    x = client.query_private('DepositStatus', req=params)

##################TEST#####################################
