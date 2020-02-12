from RPCBitcoin import RPCHost
import psycopg2
import os
import Utilities as utils

# Default port for the bitcoin testnet is 18332
# The port number depends on the one writtein the bitcoin.conf file

# The RPC username and RPC password MUST match the one in your bitcoin.conf file
rpcUser = 'bitlynx'
rpcPassword = 'Bitlynx_Secret_Key'

#Accessing the RPC local server
ipaddress = "45.63.18.25"
port = "8332"
BitcoinServerURL = "http://{}:{}@{}:{}".format(rpcUser, rpcPassword, ipaddress, port)

def CreateBTCAddress(accountnum, currency):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    sql = """select address from user_wallets where accountnum = {} and currency = '{}'""".format(accountnum, currency)
    cursor.execute(sql)
    x = cursor.fetchall()
    conn.close()
    if len(x) > 0:
        address = x[0][0]
    else:
        host = RPCHost(BitcoinServerURL)
        address = host.call('getnewaddress')
        utils.LogAddress(accountnum, address, currency)
        return address



def GetAccounts():
    host = RPCHost(BitcoinServerURL)
    info = host.call('listreceivedbyaddress', 1, True)
    return info


def SendBTC(toaddress, amount):
    host = RPCHost(BitcoinServerURL)
    txid = host.call('sendtoaddress', toaddress, amount, "", "", True)
    return txid

