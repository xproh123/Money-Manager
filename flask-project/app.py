from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3


app = Flask(__name__)


app.config["SESSION_PERMANENT"] = False # No permanent session
app.config["SESSION_TYPE"] = 'filesystem' # Use the files in the same project
Session(app)


conn = sqlite3.connect('transactions.db', check_same_thread=False) 
cursor = conn.cursor()


@app.template_filter("vnd")
def currencyFormat(value, suffix="₫"):
    formatted = f"{value:,}".replace(",",".")
    return f"{formatted}{suffix}"


@app.route('/apology')
def apology():
    return render_template('apology.html')


@app.route('/history', methods=['GET', 'POST'])
def history():
    if "user" not in session:
        return redirect("/signin")
    if request.method == 'POST':
        current_user = session.get('user')
        transaction = request.form['transaction']
        keywords = request.form['keywords']
        start = request.form['start']
        end = request.form['end']
        sort = request.form['sort']

        transaction_type = {
            "all": "",
            "earning": "AND transaction_type = 'earning'",
            "expense": "AND transaction_type = 'expense'"
        }

        sorting_type = {
            "oldest": "time ASC",
            "newest": "time DESC",
            "largest": "amount DESC",
            "smallest": "amount ASC" 
        }

        select_type = {
            "all" : "*",
            "sum_amount": "SUM(amount)"
        }

        query_for_all = f"SELECT * FROM transactions WHERE (time >= ? AND time <= ?) {transaction_type[transaction]} AND user = ? AND details LIKE ? ORDER BY {sorting_type[sort]}"
        query_for_sum_of_expenses = f"SELECT SUM(amount) FROM transactions WHERE (time >= ? AND time <= ?) {transaction_type["expense"]} AND user = ? AND details LIKE ? ORDER BY {sorting_type[sort]}"
        query_for_sum_of_earnings = f"SELECT SUM(amount) FROM transactions WHERE (time >= ? AND time <= ?) {transaction_type["earning"]} AND user = ? AND details LIKE ? ORDER BY {sorting_type[sort]}"

        rows = cursor.execute(query_for_all, (start, end, current_user, f"%{keywords}%")).fetchall()
        total_expenses = cursor.execute(query_for_sum_of_expenses, (start, end, current_user, f"%{keywords}%")).fetchone()[0]
        if total_expenses is None:
            total_expenses = 0
        total_earnings = cursor.execute(query_for_sum_of_earnings, (start, end, current_user, f"%{keywords}%")).fetchone()[0]
        if total_earnings is None:
            total_earnings = 0
        return render_template('history.html', rows=rows, start=start, end=end, total_expenses=total_expenses, total_earnings=total_earnings)
    
    return render_template('history.html')


@app.route('/')
def home_page():
    current_user = session.get('user')
    if current_user is None:
        return render_template('homepage.html', welcome_message=f"Welcome to Money Manager.")
    this_month_expenses = cursor.execute("""SELECT SUM(amount) FROM transactions WHERE user = ? AND transaction_type = ? AND strftime('%Y-%m', time) = strftime('%Y-%m', 'now')""", (current_user, 'expense')).fetchone()[0]
    if this_month_expenses is None:
        this_month_expenses = 0
    this_month_earnings = cursor.execute("""SELECT SUM(amount) FROM transactions WHERE user = ? AND transaction_type = ? AND strftime('%Y-%m', time) = strftime('%Y-%m', 'now')""", (current_user, 'earning')).fetchone()[0]
    if this_month_earnings is None:
        this_month_earnings = 0
    return render_template('homepage.html', welcome_message=f"Hello, {current_user}.", this_month_expenses=this_month_expenses, this_month_earnings=this_month_earnings)


@app.route('/new', methods=['GET', 'POST'])
def new_transactions():
    if "user" not in session:
        return redirect("/signin")
    if request.method == 'POST':
        current_user = session.get('user') # get the name of current user
        transaction = request.form['transaction']
        amount = request.form['amount']
        if amount == "":
            return render_template('apology.html', text="must have an amount")
        elif not amount.isnumeric():
            return render_template('apology.html', text="amount must be a number")
        elif int(amount) < 0: # If user typed a negative number
            return render_template('apology.html', text="amount can not be negative")
        details = request.form['details']
        time = request.form['time']
        if time == "":
            return render_template('apology.html', text="time can not be blanked")
        if transaction == 'earning':
            cursor.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)", (current_user, "earning", amount, details, time))
            conn.commit()
            return render_template('new_transactions.html', message="Added successfully.")
        elif transaction == 'expense':
            cursor.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)", (current_user, "expense", amount, details, time))
            conn.commit()
            return render_template('new_transactions.html', message="Added successfully.")  
    return render_template('new_transactions.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    
    # This returns a list of tuples
    list_of_username_tuples = cursor.execute("SELECT username from users").fetchall()

    # Create a list only takes the first value of each tuple
    # In this case there's only 1 value in each tuple so it will get the full username
    username_list = [row[0] for row in list_of_username_tuples]

    if request.method == 'POST':
        username = request.form["username"]
        if username == "":
            return render_template('apology.html', text='must include username')
        password = request.form["password"]
        if password == "":
            return render_template('apology.html', text='must include password')
        if username not in username_list:
            password_hash = generate_password_hash(password)
            cursor.execute("INSERT INTO users VALUES (?, ?)", (username, password_hash))
            conn.commit()
            return redirect('/signin')
        else:
            return render_template('apology.html', text="username already existed.")
    else:
        return render_template('register.html')


@app.route('/signin', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        username = request.form["username"]
        if username == "": # If blank username
            return render_template('apology.html', text='must include username')
        password = request.form["password"]
        if password == "": # If blank password
            return render_template('apology.html', text='must include password')
        user = cursor.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
        if user: # If user exist
            password_hash_tuple = cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
            password_hash = password_hash_tuple[0]
            if check_password_hash(password_hash, password):
                session['user'] = username # assign the username for this session
                return redirect('/')
            else:
                return render_template('apology.html', text="wrong username or password.")
        else:
            return render_template('apology.html', text="wrong username or password.")
    else:
        return render_template('sign_in.html')


@app.route('/signout', methods=['GET'])
def sign_out():
    if request.method == 'GET':
        session.clear() # clear current user' session
        return redirect('/')