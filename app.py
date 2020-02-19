from flask import Flask, session, request, Response, render_template, redirect, url_for, send_from_directory
import os
import json
import datetime
import requests as req
import psycopg2 as pg
from flask import Flask
import random, string
import Utilities as utils
import feedparser
import RPCUtils as rpc

# app setup
app = Flask(__name__)
# config
app.config.from_object(os.environ['APP_SETTINGS'])

# DB
if 'Development' in os.environ['APP_SETTINGS']:
    db_url = """postgres://zbbkqlsfdaogoj:6c6b047fc1856aa4332a19dac73083af7a8d007c21f51ecaf324dcd085516e79@ec2-23-23-222-184.compute-1.amazonaws.com:5432/d9nsd1kp8hr78k"""
    baseURL = 'https://bitlynx-staging.herokuapp.com/'
else:
    db_url = os.environ['DATABASE_URL']
    if 'Production' in os.environ['APP_SETTINGS']:
        baseURL = "https://bitlynx.herokuapp.com/"
        # baseURL = "https://damp-brook-82840.herokuapp.com/"
    elif 'Staging' in os.environ['APP_SETTINGS']:
        baseURL = 'https://bitlynx-staging.herokuapp.com/'

# Define colors
colors_list = utils.GetColors()

#define timeout
timeout = 20


#session timeout
@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(minutes=timeout)
    session.modified = True

@app.route('/', methods=['GET', 'POST'])
def Home():

    session['logged_in'] = False
    session['customerid'] = None
    if request.method == 'POST':
        return redirect(url_for('LoginApp'))

    return render_template('Home.html')


########################################################################################################################

# LOGIN

########################################################################################################################

@app.route('/api/login', methods=['POST'])
def LoginAPI():
    if request.method == 'POST':
        data = request.form  # a multidict containing POST data
        #decryption
        username = utils.Hash(str(data['username']).lower())
        password = utils.Hash(str(data['password']))
        ip_address = str(data['IP_Address'])

        conn = pg.connect(db_url)
        # Perform query and return JSON data
        SQL = "select ID, first_name, email from Login where UserName = %s and Password = %s"
        data = (username, password)
        cursor = conn.cursor()
        cursor.execute(SQL, data)
        x = cursor.fetchall()
        conn.close()

        if len(x) > 0:
            acctnum = x[0][0]
            name = x[0][1]
            email = x[0][2]
            acctnum = str(acctnum)
            name = str(name)
            email = str(email)
            session['logged_in'] = True
            message = {'CustomerID': acctnum}
            utils.LogVisit(acctnum,ip_address)
            ip_address = str(ip_address)
            utils.SendEmail(email, 'Login', {'name':name, 'ip_address':ip_address})
        else:
            message = {'Message': 'User Name or Password Incorrect'}
        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp


########################################################################################################################
@app.route('/app/login', methods=['GET', 'POST'])
def LoginApp():
    if request.method == 'GET':
        return render_template('Login.html')
    if request.method == 'POST':
        data = request.form

        username = str(data['username'])
        password = str(data['password'])
        params = {'username': username,
                  'password': password,
                  'IP_Address':request.environ['REMOTE_ADDR']}
        url = baseURL + "api/login"
        x = req.post(url, data=params)
        x = x.json()

        if 'CustomerID' in x.keys():
            customerid = x['CustomerID']
            session['customerid'] = x['CustomerID']

            return redirect(url_for('DashboardApp'))
        else:
            return redirect(url_for('Error'))


########################################################################################################################

# REGISTATION

########################################################################################################################
@app.route('/api/registration', methods=['POST'])
def RegisterAccountAPI():
    if request.method == 'POST':
        data = request.form  # a multidict containing POST data
        username = str(data['username']).lower()
        password = str(data['password'])
        first_name = str(data['firstname'])
        last_name = str(data['lastname'])
        email = str(data['email'])
        address1 = str(data['address1'])

        city = str(data['city'])
        state = str(data['state'])
        zipcode = str(data['zipcode'])
        country = str(data['country'])
        company = str(data['company'])
        occupation = str(data['occupation'])
        est_ann_income = str(data['est_ann_income'])
        source_of_funds = str(data['source_of_funds'])

        #lock their account by default
        is_locked = str(1)

        conn = pg.connect(db_url)
        mySQL = "Select * from Login where UserName = %s"
        cursor = conn.cursor()
        data = (username,)
        cursor.execute(mySQL, data)
        x = cursor.fetchall()
        conn.close()
        if len(x) > 0:
            message = {'Message': 'User Already Exists'}
        else:
            conn = pg.connect(db_url)
            cursor = conn.cursor()

            # insert record into login table
            mySQL = "Insert into Login (" \
                    "UserName,Password,first_name,last_name,address1," \
                    "city,state,zip,country,company," \
                    "occupation,est_ann_income,source_of_funds,is_locked,email) " \
                    "values(%s,%s,%s,%s,%s," \
                    "%s,%s,%s,%s,%s," \
                    "%s,%s,%s,%s,%s)"

            #encryption of sensitive data
            h_username = utils.Hash(username)
            h_password = utils.Hash(password)

            data = (h_username, h_password, str(first_name), str(last_name), str(address1),
                    str(city), str(state), int(zipcode), str(country),str(company),
                    str(occupation), str(est_ann_income), str(source_of_funds), int(is_locked),str(email))

            cursor.execute(mySQL, data)
            conn.commit()

            # get account number
            mySQL = "select id from Login order by id desc limit 1"
            cursor.execute(mySQL)
            x = cursor.fetchall()
            acctnum = x[0][0]

            # initialize an acct balance of 0
            mySQL = "Insert into Holdings(accountnum ,exchangecode,currency,amount,dollarvalue) values( %s,'BitLynx','USD',0,0)"
            data = (str(acctnum),)
            cursor.execute(mySQL, data)
            conn.commit()

            mySQL = "Insert into holdingshistory(accountnum, dollarvalue, timestamp) values( %s,0,current_timestamp)"
            data = (str(acctnum),)
            cursor.execute(mySQL, data)
            conn.commit()

            #initialize a holdings history of 0

            conn.close()
            message = {'Message': 'User Added'}
        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp


########################################################################################################################
@app.route('/app/registration', methods=['GET', 'POST'])
def RegistrationApp():
    if request.method == 'GET':
        return render_template('Registration.html')
    if request.method == 'POST':
        error = None
        success = None
        data = request.form
        #required fields
        username = data['username']
        password = data['password']
        rpassword = data['rpassword']
        first_name = data['firstname']
        email = data['email']
        #optional fields
        try:
            last_name = data['lastname']
        except KeyError:
            last_name = "NULL"

        try:
            address1 = data['address1']
        except KeyError:
            address1 = "NULL"

        try:
            city = data['city']
        except KeyError:
            city = "NULL"

        try:
            state = data['state']
        except KeyError:
            state = "NULL"

        try:
            zipcode = data['zipcode']
        except KeyError:
            zipcode = "NULL"

        try:
            country = data['country']
        except KeyError:
            country = "NULL"

        try:
            company = data['company']
        except KeyError:
            company = "NULL"

        try:
            occupation = data['occupation']
        except KeyError:
            occupation = "NULL"

        try:
            est_ann_income = data['est_ann_income']
        except KeyError:
            est_ann_income = "NULL"

        try:
            source_of_funds = data['source_of_funds']
        except KeyError:
            source_of_funds = "NULL"

        required_items = [username, password, rpassword, first_name, email]
        optional_items = [last_name, address1, city, state, zipcode, country, company, occupation, est_ann_income, source_of_funds]
        #check for required items
        for t in required_items:
            if t == '' or t == None:
                return render_template("Registration.html", error = "Required fields must be filled out: Username, Password, First Name, and Email Address")
        #check for password match
        if password != rpassword:
            error = "Passwords must match"
            return render_template('Registration.html', error=error)

        else:
            params = {
                "username": username,
                "password": password,
                "firstname": first_name,
                "lastname": last_name,
                "address1": address1,
                "city": city,
                "state": state,
                "zipcode": zipcode,
                "country": country,
                "company": company,
                "occupation": occupation,
                "est_ann_income": est_ann_income,
                "source_of_funds": source_of_funds,
                "email":email
            }
            url = baseURL + "api/registration"
            x = req.post(url, data=params)
            x = x.json()
            if x['Message'] == 'User Added':
                success = "Account Added, Please Return to Login Page For Entry"
                return render_template('Registration.html', success=success)

            else:
                error = x['Message']
                return render_template('Registration.html', error=error)



########################################################################################################################

# DASHBOARD


########################################################################################################################
@app.route('/api/dashboard', methods=['POST'])
def DashboardAPI():
    if request.method == 'POST':
        data = request.form  # a multidict containing POST data

        cid = str(data['CustomerID'])
        conn = pg.connect(db_url)
        cursor = conn.cursor()

        # GET HOLDINGS VALUE
        mySQL = "Select sum(DollarValue) from Holdings where " \
                "AccountNum = %s"
        data = (str(cid),)
        cursor.execute(mySQL, data)
        x = cursor.fetchall()
        dollarvalue = x[0][0]
        dollarvalue = str(float(dollarvalue))

        # GET ACTUAL HOLDINGS
        mySQL = "Select currency,cast(amount as real), cast(dollarvalue as real) from Holdings where amount > 0 and "
        mySQL += "AccountNum = %s"
        data = (str(cid),)
        cursor.execute(mySQL, data)
        holdings = cursor.fetchall()

        # GET HOLDINGS HISTORY
        mySQL = "Select to_char(timestamp, 'FMHHam Mon FMDD'), cast(dollarvalue as real) from holdingshistory where "
        mySQL += "AccountNum = %s order by timestamp desc limit 72"
        data = (str(cid),)
        cursor.execute(mySQL, data)
        holdingstemp = []
        holdingshistory = []
        for d in cursor.fetchall():
            holdingstemp.append([str(d[0]), int(d[1])])
        for i,h in enumerate(reversed(holdingstemp)):
            if i % 6 == 0:
                holdingshistory.append(h)
        conn.close()
        message = {"AcctValUSD": dollarvalue,
                   "Holdings": holdings,
                   "HoldingsHistory": holdingshistory}

        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp


########################################################################################################################
@app.route('/app/dashboard', methods=['GET'])
def DashboardApp():
    if request.method == 'GET':

        # dynamically define links

        params = {'CustomerID': session['customerid']}
        url = baseURL + "api/dashboard"
        x = req.post(url, data=params)
        x = x.json()
        dollar_value = x['AcctValUSD']
        holdings = x['Holdings']


        holdingshistory = x['HoldingsHistory']
        labels_pie = [h[0] for h in holdings]
        values_pie = [h[2] for h in holdings]

        line_labels = [hh[0] for hh in holdingshistory]
        line_values = [hh[1] for hh in holdingshistory]

        colors_pie = []
        for i in range(len(holdings)):
            colors_pie.append(colors_list[i])
        return render_template('Dashboard.html',
                               customerId=session['customerid'],
                               dollar_value=dollar_value,
                               holdings=holdings,
                               set=zip(values_pie, labels_pie, colors_pie),
                               labels=line_labels,
                               values=line_values,
                               min_line=min(line_values) - (.25 * min(line_values)),
                               max_line=max(line_values))



########################################################################################################################

# TRADING

########################################################################################################################
@app.route('/api/info/<option>', methods=['POST'])
def InfoAPI(option):
    if request.method == 'POST':
        if option == "balanceinfo":
            data = request.form  # a multidict containing POST data
            cid = str(data['CustomerID'])
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            mySQL = "select cast(sum(dollarvalue) as real) from Holdings where accountnum = %s and exchangecode = 'BitLynx'"
            data = (str(cid),)
            cursor.execute(mySQL, data)
            x = cursor.fetchall()
            bitlynxbal = x[0][0]
            message = {'BitLynx_Balance': bitlynxbal}
            conn.close()

        elif option == 'holdingshistorychartdata':
            data = request.form
            cid = str(data['CustomerID'])
            timescale = str(data['Timescale'])
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            #day
            if timescale.lower() == 'day':
                mySQL = "Select to_char(timestamp, 'FMHHam Mon FMDD'), cast(dollarvalue as real) from holdingshistory where "
                mySQL += """AccountNum = %s  and date_part('year',timestamp) = date_part('year',current_date)
                         and date_part('day',timestamp) = date_part('day',current_date)
                         order by timestamp desc limit 24"""
                data = (str(cid),)
                cursor.execute(mySQL, data)
                holdingstemp = []
                holdingshistory = []
                for d in cursor.fetchall():
                    holdingstemp.append([str(d[0]), int(d[1])])
                for i, h in enumerate(reversed(holdingstemp)):
                    if i % 2 == 0:
                        holdingshistory.append(h)
            #month
            elif timescale.lower() == 'month':
                mySQL = "Select to_char(timestamp, 'FMHHam Mon FMDD'), cast(dollarvalue as real) from holdingshistory where "
                mySQL += """AccountNum = %s
                         and date_part('year',timestamp) = date_part('year',current_date)
                         and date_part('month',timestamp) = date_part('month',current_date)
                         order by timestamp desc limit 730"""
                data = (str(cid),)
                cursor.execute(mySQL, data)
                holdingstemp = []
                holdingshistory = []
                for d in cursor.fetchall():
                    holdingstemp.append([str(d[0]), int(d[1])])
                for i, h in enumerate(reversed(holdingstemp)):
                    if 0 <= len(cursor.fetchall()) <= 24:
                        if i % 2 == 0:
                            holdingshistory.append(h)
                    elif 24 < len(cursor.fetchall()) <= 72:
                        if i % 6 == 0:
                            holdingshistory.append(h)
                    elif 72 < len(cursor.fetchall()) <=730:
                        if i % 24 == 0:
                            holdingshistory.append(h)

            # 3 months
            elif timescale.lower() == 'three months':
                mySQL = "Select to_char(timestamp, 'FMHHam Mon FMDD'), cast(dollarvalue as real) from holdingshistory where "
                mySQL += """AccountNum = %s and timestamp >= date_trunc('day', NOW() - interval '3 months')
                order by timestamp desc limit 2130"""
                data = (str(cid),)
                cursor.execute(mySQL, data)
                holdingstemp = []
                holdingshistory = []
                for d in cursor.fetchall():
                    holdingstemp.append([str(d[0]), int(d[1])])
                for i, h in enumerate(reversed(holdingstemp)):
                    if 0 <= len(cursor.fetchall()) <= 24:
                        if i % 2 == 0:
                            holdingshistory.append(h)
                    elif 24 < len(cursor.fetchall()) <= 72:
                        if i % 6 == 0:
                            holdingshistory.append(h)
                    elif 72 < len(cursor.fetchall()) <=730:
                        if i % 24 == 0:
                            holdingshistory.append(h)
                    elif 730 < len(cursor.fetchall()) <= 2130:
                        if i % 72 == 0:
                            holdingshistory.append(h)

            elif timescale.lower() == 'year':
                mySQL = "Select to_char(timestamp, 'FMHHam Mon FMDD'), cast(dollarvalue as real) from holdingshistory where "
                mySQL += """AccountNum = %s and timestamp >= date_trunc('day', NOW() - interval '1 year')
                                order by timestamp desc limit 8760"""
                data = (str(cid),)
                cursor.execute(mySQL, data)
                holdingstemp = []
                holdingshistory = []
                for d in cursor.fetchall():
                    holdingstemp.append([str(d[0]), int(d[1])])
                for i, h in enumerate(reversed(holdingstemp)):
                    if 0 <= len(cursor.fetchall()) <= 24:
                        if i % 2 == 0:
                            holdingshistory.append(h)
                    elif 24 < len(cursor.fetchall()) <= 72:
                        if i % 6 == 0:
                            holdingshistory.append(h)
                    elif 72 < len(cursor.fetchall()) <=730:
                        if i % 24 == 0:
                            holdingshistory.append(h)
                    elif 730 < len(cursor.fetchall()) <= 2130:
                        if i % 72 == 0:
                            holdingshistory.append(h)
                    elif 2130 < len(cursor.fetchall()) <= 8640:
                        if i % 288 == 0:
                            holdingshistory.append(h)
                    else:
                        if i % 500 == 0:
                            holdingshistory.append(h)

            elif timescale.lower() == 'all time':
                mySQL = "Select to_char(timestamp, 'FMHHam Mon FMDD'), cast(dollarvalue as real) from holdingshistory where "
                mySQL += """AccountNum = %s
                                order by timestamp desc"""
                data = (str(cid),)
                cursor.execute(mySQL, data)
                holdingstemp = []
                holdingshistory = []
                for d in cursor.fetchall():
                    holdingstemp.append([str(d[0]), int(d[1])])
                for i, h in enumerate(reversed(holdingstemp)):
                    if 0 <= len(cursor.fetchall()) <= 24:
                        if i % 2 == 0:
                            holdingshistory.append(h)
                    elif 24 < len(cursor.fetchall()) <= 72:
                        if i % 6 == 0:
                            holdingshistory.append(h)
                    elif 72 < len(cursor.fetchall()) <=730:
                        if i % 24 == 0:
                            holdingshistory.append(h)
                    elif 730 < len(cursor.fetchall()) <= 2130:
                        if i % 72 == 0:
                            holdingshistory.append(h)
                    elif 2130 < len(cursor.fetchall()) <= 8640:
                        if i % 288 == 0:
                            holdingshistory.append(h)
                    else:
                        if i % 500 == 0:
                            holdingshistory.append(h)
            conn.close()
            message = {'ChartData': holdingshistory}



        elif option == 'orderhistory':
            data = request.form  # a multidict containing POST data
            cid = str(data['CustomerID'])
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            mySQL = """select o.currencypair,
            cast(o.amount as real),
            o.side,
            o.transid,
            '$'||cast(o.price as varchar),
            o.status,
            o.ordertype,
            to_char(o.timestamp, 'MM-DD-YYYY HH24:MI:SS'),
            cast(round(cast(b.bitlynx_fee_pcnt * 100 as numeric), 1) as varchar)||'%%',
            '$' || cast(round(cast(b.bitlynx_fee_amt as numeric),2) as varchar)

            from orderhistory o
            left join bitlynxfees b on o.tradeid = b.tradeid

            where o.accountnum = %s  order by o.timestamp desc"""
            data = (str(cid),)
            cursor.execute(mySQL, data)
            orderhistory = cursor.fetchall()
            message = {'OrderHistory':orderhistory}
            conn.close()


        elif option == 'getavailablecurrencies':
            cid = str(request.form['CustomerID'])
            market_selection = str(request.form['market_selection'])

            avail_currencies = utils.GetAvailableCurrencies(market_selection)
            message = {'AvailableCurrencies':avail_currencies}

        elif option == 'holdingsinfo':
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            # GET ACTUAL HOLDINGS
            #cid = session['customerid']
            cid = str(request.form['CustomerID'])
            mySQL = "Select currency,cast(sum(amount) as real),cast(sum(dollarvalue) as real) from Holdings where "
            mySQL += "AccountNum = %s group by currency"
            data = (str(cid),)
            cursor.execute(mySQL, data)
            holdings_bulk = cursor.fetchall()
            holdings = []
            for h in holdings_bulk:
                holdings.append({'currency':h[0],'amount':h[1],'dollar_value':'${:,.2f}'.format(h[2])})
            message = {'Holdings':holdings}
            conn.close()

        elif option == 'priceinfo':
            # GET ACTUAL HOLDINGS
            # cid = session['customerid']
            cid = str(request.form['CustomerID'])
            currency = str(request.form['Currency'])
            side = str(request.form['Side'])
            market_selection = str(request.form['market_selection'])
            ############################################
            sup_exchs = utils.GetCurrencyAvailabilty(currency, market_selection)

            # Get the best price of the currency across the supported exchanges,
            if 'ShapeShift' in sup_exchs:
                price_results = utils.GetBestPrice(sup_exchs, currency, side,market_selection, customerid=cid)
            else:
                price_results = utils.GetBestPrice(sup_exchs, currency, side, market_selection)

            tdata = []

            for pdata in price_results:
                tdata.append(float(pdata[1]))

            # if buy find lowest price and exchange
            if side.lower() == 'buy':
                winning_price = min(tdata)
                winning_index = tdata.index(winning_price)
                winning_exchange = price_results[winning_index][0]

            # if sell find highest price and exchange
            elif side.lower() == 'sell':
                winning_price = max(tdata)
                winning_index = tdata.index(winning_price)
                winning_exchange = price_results[winning_index][0]

            ###########################################

            message = {'best_price':winning_price,'exchange':winning_exchange}

        elif option == 'accountinfo':
            cid = str(request.form['CustomerID'])
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            SQL = """select first_name,
            last_name,
            address1,
            city,
            state,
            zip,
            country,
            occupation,
            est_ann_income,
            source_of_funds,
            is_locked,
            is_verified
            from login where id = %s"""
            data = (str(cid),)
            cursor.execute(SQL, data)
            x = cursor.fetchall()
            results = x[0]
            fn = results[0]
            ln = results[1]
            adr = results[2]
            city = results[3]
            state = results[4]
            zip_code = results[5]
            country = results[6]
            occupation = results[7]
            est_income = results[8]
            source_of_funds = results[9]
            is_locked = results[10]
            is_verified = results[11]
            if int(is_locked) == 0:
                is_locked = 'False'
            elif int(is_locked) == 1:
                is_locked = 'True'
            else:
                is_locked = 'True'

            if int(is_verified) == 1:
                is_verified = 'True'
            else:
                is_verified = 'False'
            conn.close()
            message = {
                "AccountInfo": {'first':fn,
                       'last':ln,
                       'address':adr,
                       'city':city,
                       'state':state,
                       'zipcode':zip_code,
                       'country':country,
                       'occupation':occupation,
                       'est_income':est_income,
                       'source_of_funds':source_of_funds,
                       'is_locked':is_locked,
                        'is_verified':is_verified}
                }

        elif option == 'notifications':
            cid = str(request.form['CustomerID'])
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            SQL = "select message from notifications where accountnum = %s order by timestamp desc limit 20"
            data = (str(cid),)
            cursor.execute(SQL, data)
            notifications = []
            x = cursor.fetchall()
            for item in x:
                notifications.append(item[0])
            message = {'notifications':notifications}
            conn.close()

        elif option == 'getorderbook':
            return_list_temp = []
            cid = int(request.form['CustomerID'])
            currency = str(request.form['Currency'])
            side = str(request.form['Side'])
            market_selection = str(request.form['market_selection'])

            all_accts = utils.GetAccountNums()
            if cid in all_accts:
                x = utils.GetAggOrderBook(currency, side, market_selection)
                for item in x:
                    for sub in item:
                        return_list_temp.append(sub)
                orderbook = sorted(return_list_temp,key=lambda sub: sub['rate'])
                message = {'orderbook':orderbook}
            else:
                message = {'message':'Invalid token'}

        elif option == 'getchartexchange':
            currency = str(request.form['Currency'])
            exchange = utils.GetChartExchange(currency)
            message = {'exchange':exchange}

        elif option == 'getwalletaddress':
            currency = str(request.form['Currency'])
            accountnum = request.form['CustomerID']
            address = utils.GetWalletAddress(accountnum,currency)
            print "test"
            message = {"address":address}

        elif option == 'gettransferhistory':
            cid = str(request.form['CustomerID'])
            conn = pg.connect(db_url)
            cursor = conn.cursor()
            SQL = """select to_char(timestamp, 'MM-DD-YYYY HH12:MI:SS'), 'Deposit' AS deposit, cast(amount as varchar), currency from deposit_history where accountnum = {}
                      UNION
                      select to_char(timestamp, 'MM-DD-YYYY HH12:MI:SS'), 'Withdrawal' AS withdrawal, cast(amount as varchar), currency from withdrawal_history where accountnum = {}""".format(cid,cid)

            cursor.execute(SQL)
            x = cursor.fetchall()
            transferhistorytemp = []
            for item in x:
                transferhistorytemp.append(item)
            transferhistory = sorted(transferhistorytemp,key=lambda tup:tup[0])
            conn.close()
            message = {'TransferHistory':transferhistory}
        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

########################################################################################################################
@app.route('/api/generateaddress',methods=['POST'])
def GenerateAddress():
    if request.method == 'POST':
        customerid = request.form['CustomerID']
        currency = request.form['Currency']
        address = rpc.CreateBTCAddress(customerid, currency)
        message = {'WalletAddress': address, "Currency":currency, "CustomerID":customerid}
        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp


########################################################################################################################
@app.route('/app/documents', methods=['GET'])
def DocumentsApp():
    return render_template("Construction.html")

#####################################################################################################################3
@app.route('/app/transfers', methods=['GET','POST'])
def TransfersApp():
    currencies_deposit = [('BTC', 'BitCoin')]
    currencies_withdraw = utils.GetWithdrawableCurrencies()
    with open('./static/webfont/cryptocoins-map.json') as json_data:
        currencyChars = json.load(json_data)

    if request.method == 'GET':
        #Get holdings
        url = baseURL + "/api/info/holdingsinfo"
        #params = {"CustomerID": 2}
        params = {"CustomerID": session['customerid']}
        x = req.post(url, data=params)
        x = x.json()
        holdings = []
        x = x['Holdings']
        for item in x:
            currency = item['currency']
            if currency == "USD":
                amount = "$" + str(item['amount'])
            else:
                amount = item['amount']
            if amount > 0:
                holdings.append([currency, amount])

        url = baseURL + "/api/info/gettransferhistory"
        params = {"CustomerID": session['customerid']}
        #params = {"CustomerID": 2}
        x = req.post(url, data=params)
        x = x.json()
        transferhist = x['TransferHistory']
        return render_template('Transfers.html',
                               info_url=baseURL,
                               currencyChars=currencyChars,
                               currencies_deposit=currencies_deposit,
                               currencies_withdraw = currencies_withdraw,
                               transferhist=transferhist,
                               holdings=holdings)

    elif request.method == 'POST':
        customerid = request.form['CustomerID']
        currency = request.form['Currency']
        button_name = request.form['button']
        if button_name == 'Generate':
            address = utils.GenerateWalletAddress(customerid, currency)
            resp = Response(json.dumps({'address':address}))
        else:
            withdrawal_address = request.form['withdrawal_address']
            withdrawal_amount = request.form['withdrawal_amount']
            withdrawal_response = utils.WithdrawCurrency(withdrawal_address, withdrawal_amount, currency, customerid)
            resp = Response(json.dumps({'message':withdrawal_response}))

        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp



########################################################################################################################
@app.route('/app/positions', methods=['GET'])
def PositionsApp():
    url = baseURL + "/api/info/holdingsinfo"
    params = {"CustomerID":session['customerid']}
    x = req.post(url,data=params)
    x = x.json()
    holdings = []
    x = x['Holdings']
    for item in x:
        amount = item['amount']
        dollarvalue = item['dollar_value']
        currency = item['currency']
        if amount > 0:
            holdings.append([currency,amount,dollarvalue])
    return render_template("Positions.html", holdings=holdings)
#########################################################################################################################
@app.route('/app/trade', methods=['GET','POST'])
def TradeApp():
    # api url
    bestprice = str(0)
    currencies = utils.GetCurrencies()
    with open('./static/webfont/cryptocoins-map.json') as json_data:
        currencyChars = json.load(json_data)
    if 'customerid' in session:
        cid = session['customerid']
    else:
        cid = str(request.form['CustomerID'])

    if request.method == 'GET':
        return render_template('Trade.html',
                               currencies=currencies,
                               currencyChars=currencyChars,
                               bestprice=bestprice,
                               info_url=baseURL,
                               #customerId=2)
                               customerId=cid)

    elif request.method == 'POST':

        currency = str(request.form['currency'])
        amount = request.form.get('amount')
        market_selection = request.form['market_selection']

        if amount == '':
            amount = 0
        side = str(request.form['side'])
        if float(amount) > 0:
            response = utils.ExecuteTrade(currency=currency,
                                         amount=amount,
                                         side=side,
                                         market_selection=market_selection,
                                         #customerid=2)
                                         customerid=cid)
            message = {'message':response}

        else:
            message = {'message':"Please enter an amount greater than zero"}

        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp
########################################################################################################################
# ORDER HISTORY PAGE

########################################################################################################################
@app.route('/app/orderhistory', methods=['GET'])
def OrderHistApp():
    url = baseURL + "/api/info/orderhistory"
    params = {"CustomerID":session['customerid']}
    x = req.post(url,data=params)
    try:
        x = x.json()
        orderhistory = x['OrderHistory']
    except:
        orderhistory=[]
    return render_template('OrderHistory.html',orderhistory=orderhistory)

@app.route('/app/notifications',methods=['GET'])
def NotificationsApp():
    url = baseURL + "/api/info/notifications"
    params = {"CustomerID": session['customerid']}
    x = req.post(url, data=params)
    try:
        x = x.json()
        notifications = x['notifications']
    except:
        notifications = []
    return render_template('Notifications.html',notifications=notifications)
########################################################################################################################
# ERROR REDIRECT

########################################################################################################################
@app.route('/app/error', methods=['GET'])
def Error():
    if request.method == 'GET':
        return render_template('Error.html')


########################################################################################################################

# Update history endpoint
@app.route('/api/updatehistory', methods=['POST'])
def UpdateHistory():
    if request.method == 'POST':
        data = request.form
        secret_key = data['Secret_Key']
        if secret_key == 'BitLynxSecretKey':
            # get all accounts
            utils.UpdateHistory()
            message = {'Message': 'Script Started'}
            message = json.dumps(message)
            resp = Response(message)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp

@app.route('/api/updateorderstatus', methods=['POST'])
def UpdateOrderStatus():
    if request.method == 'POST':
        data = request.form
        secret_key = data['Secret_Key']
        if secret_key == 'BitLynxSecretKey':
            utils.UpdateOrderStatus()

            message = {'Message': 'Script Started'}
            message = json.dumps(message)
            resp = Response(message)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp
        else:
            message = {'Message': 'Wrong Key'}
            message = json.dumps(message)
            resp = Response(message)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Content-Type'] = 'application/json; charset=utf-8'
            return resp

@app.route('/app/account', methods=['GET'])
def AccountApp():
    url = baseURL + "api/info/accountinfo"
    params = {'CustomerID':session['customerid']}
    x = req.post(url,data=params)
    x = x.json()
    accountinfo = x['AccountInfo']
    fn = str(accountinfo['first'])
    ln = str(accountinfo['last'])
    name = fn + " " + ln
    adr = str(accountinfo['address'])
    city = str(accountinfo['city'])
    state = str(accountinfo['state'])
    zip_code = str(accountinfo['zipcode'])
    country = str(accountinfo['country'])
    occupation = str(accountinfo['occupation'])
    est_income = str(accountinfo['est_income'])
    source_of_funds = str(accountinfo['source_of_funds'])
    is_locked = str(accountinfo['is_locked'])
    is_verified = str(accountinfo['is_verified'])

    return render_template('Account.html',
                           name=name,
                           address=adr,
                           city=city,
                           state=state,
                           zipcode=zip_code,
                           country=country,
                           occupation=occupation,
                           est_income=est_income,
                           source_of_funds=source_of_funds,
                           is_locked=is_locked,
                           kyc_complete=is_verified)

@app.route('/app/accountverification', methods=['GET'])
def AccountVerApp():
    return render_template('AccountVerification.html')

@app.route('/app/accountsupport', methods=['GET','POST'])
def AccountSupportApp():
    if request.method == 'GET':
        return render_template('Support.html')
    elif request.method == 'POST':
        description = request.form['ticket_description']
        date_str = str(request.form['ticket_date'])
        formatter_string = "%Y-%m-%d"
        datetime_object = datetime.datetime.strptime(date_str, formatter_string)
        date_object = str(datetime_object.date())
        ref_num = utils.AddSupportTicket(session['customerid'],date_object,description)


        return render_template('Support.html',success = True, ref_number=str(ref_num))

@app.route('/app/trending', methods=['GET'])
def TrendingApp():
    return render_template('Trending.html')

@app.route('/app/payments', methods=['GET'])
def PaymentsApp():
    return render_template('Construction.html')

@app.route('/app/research', methods=['GET'])
def ResearchApp():
    return render_template('Research.html')

@app.route('/app/marketcap',methods=['GET'])
def MarketCapApp():
    return render_template('Construction.html')

@app.route('/app/termsconditions',methods=['GET'])
def TermsAndConditions():
    return render_template('TermsAndConditions.html')

@app.route('/app/news',methods=['GET'])
def NewsApp():
    rss_addrs = {
        'CoinTelegraph': 'https://cointelegraph.com/editors_pick_rss',
        'CoinDesk': 'https://feeds.feedburner.com/CoinDesk',
        'NewsBTC': 'https://www.newsbtc.com/feed/'
    }
    feeds = []
    newsfeed = []
    for rss in rss_addrs:
        feeds.append(feedparser.parse(rss_addrs[rss]))

    n = 0
    i = 0
    f = len(feeds)
    while n < 25:
        if len(feeds[i].entries) > 0:
            newsfeed.append(feeds[i].entries[0])
            newsfeed[n].feed = feeds[i].feed
            feeds[i].entries.remove(newsfeed[n])
            n += 1
        i = (i + 1) % f

    newsfeed = sorted(newsfeed, key=lambda article: article.published_parsed, reverse=True)

    return render_template('News.html', feed=newsfeed)

@app.route('/app/kyc_completion',methods=['GET','POST'])
def KYCApp():
    if request.method == 'GET':
        return render_template('KYC.html')
    elif request.method == 'POST':

        response = utils.KYCSubmit()
        if response == 'Error':
            return render_template('KYC.html', error=response)
        else:
            return render_template('KYC.html', success=response)

@app.route('/api/checkfortrans',methods=['POST'])
def TransUpdatesApi():
    if request.method == 'POST':
        token = request.form['token']
        token_correct = 'BitLynx_Secret_Key'
        if token == token_correct:
            info = rpc.GetAccounts()
            wallets = utils.GetAllWalletAddresses()
            message = {'message':'No Deposits Processed'}
            for item in info:
                address = item['address']
                amount = item['amount']
                confirmations = item['confirmations']
                if len(item['txids']) > 0:
                    txid = item['txids'][0]
                else:
                    txid = None
                if address in wallets and confirmations >= 3:
                    utils.ProcessDeposit(address, 'BTC', amount, True, txid)
                    message = {'message':'Deposits were processed'}
        message = json.dumps(message)
        resp = Response(message)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp


@app.errorhandler(500)
def page_not_found(e):
    return render_template('Error.html'), 500

if __name__ == "__main__":
    # app.run()
    app.run(debug=True, threaded=True, port=5000)
