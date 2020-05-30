import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, Markup
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd
import logging 

logging.basicConfig(level=logging.DEBUG)

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # Get current balance from users
    user_balance = db.execute("SELECT cash FROM users where id=:user_id", user_id=session["user_id"])
    global cash 
    cash = float(user_balance[0]["cash"])

    # Get current balance of stocks 
    global stock_balance 
    stock_balance = db.execute("""
    SELECT 
    symbol
    , name
    , SUM(CASE WHEN is_bought then quantity else -1*quantity end) shares
    FROM transactions
    where username=:username
    GROUP BY 
    symbol
    , name 
    HAVING 
    SUM(CASE WHEN is_bought then quantity else -1*quantity end) > 0
    ORDER BY timestamp
    """, username=username)

    total_balance = cash

    for i in range(0, len(stock_balance)):
        stock_balance[i]["price"] = lookup(stock_balance[i]["symbol"])["price"]
        stock_balance[i]["TOTAL"] = round(float(stock_balance[i]["price"]) * int(stock_balance[i]["shares"]),2)
        total_balance += stock_balance[i]["TOTAL"] 
    
    print(stock_balance)
    # Pass arguments in index.html
    return render_template("index.html", cash=cash, stocks=stock_balance, total_balance=total_balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        try:
            stock = lookup(request.form.get("symbol"))
            if len(stock) == 0:
                return apology("not found")
        except:
            return apology("please provide symbol")
        
        try:
            quantity = int(request.form.get("quantity"))
            if quantity <= 0:
                return apology("please provide valid quantity")
        except:
            return apology("please provide quantity")

        # Check current balance 
        
        if cash > float(stock["price"]) * quantity:
            # create table to track purchases
            db.execute(""" 
            INSERT INTO transactions (username, is_bought, symbol, name, price, quantity, total_price, date, timestamp)
            values (:username, :is_bought, :symbol, :name, :price, :quantity, :total_price, :date, :timestamp)
            """
            , username=username
            , is_bought=True
            , symbol=stock["symbol"]
            , name=stock["name"]
            , price=stock["price"]
            , quantity=quantity
            , total_price=float(stock["price"])*quantity
            , date=datetime.now().strftime("%Y-%m-%d")
            , timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            db.execute("UPDATE users SET cash = :updated_cash where id=:user_id",
            updated_cash=cash - float(stock["price"]) * quantity
            , user_id=session["user_id"]
            )
        else: 
            return apology("you're broke")
        
        return redirect('/')

@app.route("/history")
@login_required
def history():
    # Get all user transaction
    history = db.execute("""
    SELECT 
    symbol
    , name
    , case when is_bought then 'Bought' else 'Sold' end is_bought
    , quantity
    , price
    , round(total_price,2) total_price
    , timestamp
    from transactions
    where username=:username
    order by timestamp"""
    , username=username)

    return render_template("history.html", history=history)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            # return apology("must provide username", 403)
            # return render_template('apology.html', message="Please provide username!")
            return render_template('login.html', message='Please provide username!')

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template('login.html', message='Please provide password!')

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            # return apology("invalid username and/or password", 403)
            return render_template('login.html', message='Invalid credentials!')

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        global username
        username = request.form.get("username")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quotes.html")
    else: 
        if not request.form.get("symbol"):
            # return apology("must provide symbol")
            return render_template('quotes.html', message='Please provide symbol!')

        if not lookup(request.form.get("symbol")):
            # return apology("error")
            return render_template('quotes.html', message='Error!')
        
        stocks = lookup(request.form.get("symbol"))
        if len(stocks) == 0:
            # return apology("stock not found")
            return render_template('quotes.html', message='Stock not found!')

        return render_template("quoted.html", stocks=stocks)
    


@app.route("/register", methods=["GET", "POST"])
def register():
    # If GET, displays Form 
    if request.method == "GET":
        return render_template("register.html")
    else: 
        print(request.form.get("username"))
        # Check if user has filled up user name
        if not request.form.get('username'):
            # return apology("must provide username", 403)
            return render_template('register.html', message="Please provide username!")

        else:
            # Check if username exists in users 
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
            if len(rows) != 0:
                # return apology("username taken!", 403)
                return render_template('register.html', message="Username taken!")
        
        if not request.form.get('password'):
            # return apology("must provide password", 403)
            return render_template('register.html', message="Please provide password!")
        
        if not request.form.get('confirm_password'):
            # return apology("must confirm password", 403)
            return render_template('register.html', message="Please confirm password!")

        if request.form.get('password') != request.form.get('confirm_password'):
            # return apology("passwords doesn't match", 403)
            return render_template('register.html', message="Passwords don't match!")

        # Update users table 
        db.execute("INSERT INTO users (username, hash) values (:username,:hash_password);",
                        username=request.form.get("username"), hash_password= generate_password_hash(request.form.get("password")))
        return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    symbols = []
    for i in range(0, len(stock_balance)):
        symbols.append(stock_balance[i]["symbol"])
        print(symbols)

    if request.method == "GET":
        return render_template('sell.html', symbols=symbols)
    else:
        if not request.form.get("symbol"):
            # return apology("please select symbol")
            return render_template('sell.html', message="Please select a symbol!",symbols=symbols)
        
        try:
            shares_balance = int(list(filter(lambda to_sell: to_sell["symbol"] == request.form.get("symbol"), stock_balance))[0]['shares'])
            if not request.form.get("quantity"):
                # return apology("please provide sell quantity")
                return render_template('sell.html', message="Please provide a quantity!",symbols=symbols)

            elif int(request.form.get("quantity") ) <= 0:
                # return apology("please provide valid quantity")
                return render_template('sell.html', message="Please provide a valid quantity!",symbols=symbols)

            elif shares_balance < int(request.form.get("quantity") ):
                # return apology("you don't own this many shares")
                return render_template('sell.html', message="Not enough shares!",symbols=symbols)

            to_sell = int(request.form.get("quantity"))

        except:
            return apology("error")
        
        # Insert transaction 
        sell = lookup(request.form.get("symbol"))
        db.execute("""
        INSERT INTO TRANSACTIONS (username, is_bought, symbol, name, price, quantity, total_price, date, timestamp)
        values (:username, :is_bought, :symbol, :name, :price, :quantity, :total_price, :date, :timestamp)
        """
        , username=username
        , is_bought = False
        , symbol = sell["symbol"]
        , name = sell["name"]
        , price = sell["price"]
        , quantity = to_sell
        , total_price = to_sell * float(sell["price"])
        , date = datetime.now().strftime("Y-%m-%d")
        , timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        # Update cash balance
        updated_cash = cash + to_sell * float(sell["price"])
        db.execute("UPDATE users SET cash = :updated_cash WHERE id=:id", updated_cash=updated_cash, id=session["user_id"])
        
    return redirect('/')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)








