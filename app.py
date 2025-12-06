import sqlite3
import os
import json
from flask import Flask, request
import hashlib
import base64
import hmac

app = Flask(__name__)
db_name = "payments.db"
sql_file = "payments.sql"
db_flag = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sql_file = os.path.join(BASE_DIR, "payments.sql")
db_name = os.path.join(BASE_DIR, "payments.db")
key_file = os.path.join(BASE_DIR, "key.txt")


#from my project 1 and 2 user management
@app.route('/clear', methods = (['GET']))
def clear():
	global db_flag
	
	try:
		os.remove(db_name)

	except FileNotFoundError:
		pass
	db_flag = False
	create_db()
	return "cleared"

def create_db():
    conn = sqlite3.connect(db_name)
    
    with open(sql_file, 'r') as sql_startup:
    	init_db = sql_startup.read()
    cursor = conn.cursor()
    cursor.executescript(init_db)
    conn.commit()
    conn.close()
    global db_flag
    db_flag = True
    return conn

def get_db():
	if not db_flag:
		create_db()
	conn = sqlite3.connect(db_name)
	return conn

@app.route('/', methods=(['GET']))
def index():
	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("SELECT * FROM payments;")
	result = cursor.fetchall()
	conn.close()

	return result

@app.route('/add_initial', methods = (['POST']))
def add_initial():
	username = request.form.get('username')
	amount = float(request.form.get('amount'))
	cents = amount*100

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()
	cursor.execute("INSERT INTO balances(username, balanceCents) VALUES (?, ?)", (username, cents))
	conn.commit()
	conn.close()
	return json.dumps({"status": 1})

@app.route('/get_balance', methods = (['GET']))
def get_balance():
	username = request.args.get('username')

	if username is None:
		return json.dumps({"status": 2, "balance": "NULL"})

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	cursor.execute("SELECT balanceCents FROM balances WHERE username = ?", (username,))
	row = cursor.fetchone()
	conn.close()
	
	if row is None:
		return json.dumps({"status": 2, "balance": "NULL"})
	
	balance_cents = row[0]                      
	balance_str = "{:.2f}".format(float(balance_cents))

	conn.close()
	return json.dumps({"balance_inCents": balance_cents})

@app.route('/transfer', methods = (['POST']))
def transfer():
	passenger = request.form.get('passenger')
	driver = request.form.get('driver')
	amount = request.form.get('amount')
	amountCents = int(float(amount)*100)

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()
	cursor.execute("UPDATE balances SET balanceCents = balanceCents - ? WHERE username = ?", (amountCents, passenger))
	conn.commit()
	cursor.execute("UPDATE balances SET balanceCents = balanceCents + ? WHERE username = ?", (amountCents, driver))
	conn.commit()
	conn.close()
	return json.dumps({"status": 1})


@app.route('/add', methods=(['POST']))
def add_money():
	token = request.headers.get('Authorization') 
	amount_str = request.form.get('amount') 
	amount = float(amount_str) 
	cents = int(amount *100)

	if amount_str is None:
		return json.dumps({"status": 2})

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()
	
	if token is None: 
		conn.close()
		return json.dumps({"status": 2})
	
	header_b64, payload_b64, signature = token.split('.')

	#verify JWT
	with open('key.txt', 'r') as k:
		key = k.read()
	header_and_payload = header_b64 + "." + payload_b64
	expectedSig = hmac.new(key.encode('utf-8'), header_and_payload.encode('utf-8'), hashlib.sha256).hexdigest()

	if expectedSig != signature:
		conn.close()
		return json.dumps({"status": 2})
	
	#pull username from payload
	payloadJSON = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
	payload_2 = json.loads(payloadJSON)
	userFromPayload = payload_2.get('username')

	#does user exist in balance?
	cursor.execute("SELECT balanceCents FROM balances WHERE username = ?", (userFromPayload,))
	if cursor.fetchone() is None:
		conn.close()
		return json.dumps({"status": 2})

	cursor.execute("UPDATE balances SET balanceCents = balanceCents + ? WHERE username = ?", (cents, userFromPayload))
	conn.commit()
	conn.close()
	return json.dumps({"status": 1})

@app.route('/view', methods=(['GET']))
def view_balance():
	token = request.headers.get('Authorization')

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	if token is None: 
		conn.close()
		return json.dumps({"status": 2})
	
	header_b64, payload_b64, signature = token.split('.')

	#verify JWT
	with open('key.txt', 'r') as k:
		key = k.read()
	header_and_payload = header_b64 + "." + payload_b64
	expectedSig = hmac.new(key.encode('utf-8'), header_and_payload.encode('utf-8'), hashlib.sha256).hexdigest()

	if expectedSig != signature:
		conn.close()
		return json.dumps({"status": 2})
	
	#pull username from payload
	payloadJSON = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
	payload_2 = json.loads(payloadJSON)
	userFromPayload = payload_2.get('username')
	
	cursor.execute("SELECT balanceCents FROM balances WHERE username = ?", (userFromPayload,)) 
	row = cursor.fetchone() 
	conn.close()

	if row is None:
		return json.dumps({"status": 2, "balance": "NULL"})
	
	cents = row[0]
	dollars = f"{cents/100:.2f}"
	return json.dumps({"status": 1, "balance": dollars})