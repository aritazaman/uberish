import sqlite3
import os
import json
from flask import Flask, request
import hashlib
import base64
import hmac
import requests

app = Flask(__name__)
db_name = "user.db"
sql_file = "user.sql"
db_flag = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sql_file = os.path.join(BASE_DIR, "user.sql")
db_name = os.path.join(BASE_DIR, "user.db")
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
	cursor.execute("SELECT * FROM user;")
	result = cursor.fetchall()
	conn.close()

	return result

@app.route('/create_user', methods=(['POST']))
def create_user():
	global db_name
	firstName = request.form['first_name']
	lastName = request.form['last_name']
	username = request.form['username']
	email = request.form['email_address']
	password = request.form['password']
	salt = request.form['salt']
	isDriver = request.form['driver']
	deposit = request.form['deposit']
	##PUT DEPOSIT INTO PAYMENT DB

	hashPass = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
	row = (username, email, firstName, lastName, hashPass, salt, isDriver)
	row2 = (email, hashPass)

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()
 
	cursor.execute("SELECT * FROM user WHERE username = ?",(username,))

	userExists = cursor.fetchall()
	if len(userExists) > 0:
		conn.close()
		return json.dumps({"status": 2, "pass_hash": "NULL"})

	cursor.execute("SELECT * FROM user WHERE email = ?",(email,))
	emailExists = cursor.fetchall()
	if len(emailExists) > 0:
		conn.close()
		return json.dumps({"status": 3, "pass_hash": "NULL"})
	
	#status 4, invalid password 
	check1 = passwordCheck(firstName, lastName, username, password)
	if (check1 == False):
		conn.close()
		return json.dumps({"status": 4, "pass_hash": "NULL"})
	
	#putting deposit into payments.sql
	requests.post("http://payments:5000/add_initial", data={"username": username, "amount": deposit})
	
	cursor.execute("INSERT INTO user VALUES(?, ?, ?, ?, ?, ?, ?);", row)
	conn.commit()
	conn.close()
	return json.dumps({"status": 1, "pass_hash": hashPass})


def passwordCheck(firstName, lastName, username, password):
	hasUpper = False
	hasLower = False
	hasNum = False
	noFirst = False
	noLast = False
	noUser = False
	if len(password) < 8: 
		return False
	for i in password:
		if 'A' <= i <= 'Z':
			hasUpper = True
	for i in password: 
		if 'a' <= i <= 'z':
			hasLower = True
	for i in password: 
		if i in "0123456789": 
			hasNum = True
	firstNameLower = firstName.lower()
	lastNameLower = lastName.lower()
	usernameLower = username.lower()
	passwordLower = password.lower()

	if firstNameLower not in passwordLower:
		noFirst = True
	if lastNameLower not in passwordLower:
		noLast = True
	if usernameLower not in passwordLower:
		noUser = True

	return hasUpper & hasLower & hasNum & noFirst & noLast & noUser


@app.route('/login', methods=(['POST']))
def login():
	global db_name
	usernameLogin = request.form['username']
	passwordLogin = request.form['password']

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	cursor.execute("SELECT hashPass FROM user WHERE username = ?",(usernameLogin,))
	storedHashResult = (cursor.fetchone())
	if storedHashResult == None:
		return json.dumps({"status": 2, "jwt": "NULL"})
	storedHash = storedHashResult[0]
	cursor.execute("SELECT salt FROM user WHERE username = ?", (usernameLogin,))
	storedSalt = (cursor.fetchone())[0]
	conn.close()

	checkHash = hashlib.sha256((passwordLogin + storedSalt).encode('utf-8')).hexdigest()

	header = (json.dumps({"alg": "HS256", "typ": "JWT"})).encode('utf-8')
	headerb64 = (base64.urlsafe_b64encode(header)).decode('utf-8')
	payload = (json.dumps({"username": usernameLogin})).encode('utf-8')
	payloadb64 = (base64.urlsafe_b64encode(payload)).decode('utf-8')
	
	with open('key.txt', 'r') as k:
		key = k.read()
	
	headerAndPayload = headerb64 + "." +  payloadb64
	signature = (hmac.new(key.encode('utf-8'), headerAndPayload.encode('utf-8'), hashlib.sha256)).hexdigest()
	token = headerb64 + "." + payloadb64 + "." + signature


	if checkHash == storedHash:
		return json.dumps({"status": 1, "jwt": token})
	else:
		return json.dumps({"status": 2, "jwt": 'NULL'})
	
#end of project 1/2 user management code

@app.route('/rate', methods=(['POST']))
def rate():
	global db_name
	username = request.form['username']
	rating = request.form['rating']
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

	#pull email from username
	cursor.execute("SELECT * FROM user WHERE username = ?",(userFromPayload,))
	userExists = cursor.fetchall()
	if len(userExists) == 0:
		conn.close()
		return json.dumps({"status": 2})
	
	cursor.execute("SELECT email FROM user WHERE username = ?",(userFromPayload,))
	email = (cursor.fetchone())[0]

	cursor.execute("SELECT isDriver FROM user WHERE email = ?",(email,))
	userStatus = (cursor.fetchone())[0]

	#checking if the reviewee exists
	cursor.execute("SELECT * FROM user WHERE username = ?",(username,))
	userExists = cursor.fetchall()
	if len(userExists) == 0:
		conn.close()
		return json.dumps({"status": 2})

	#0 means passenger, passenger can only rate driver
	if str(userStatus) == "False":
		cursor.execute("SELECT isDriver FROM user WHERE username = ?", (username,))
		ratingStatus = (cursor.fetchone())[0]
		if str(ratingStatus) != "True":
			conn.close()
			return json.dumps({"status": 2})
		
	
	#1 means driver, driver can only rate passenger
	if str(userStatus) == "True":
		cursor.execute("SELECT isDriver FROM user WHERE username = ?", (username,))
		ratingStatus = (cursor.fetchone())[0]
		if str(ratingStatus) != "False":
			conn.close()
			return json.dumps({"status": 2})
		
	reviewer = userFromPayload
	reviewee = username

	#do they have a reservation with each other?
	url = "http://reservations:5000/has_reservation"
	r = requests.get(url, params={"passenger": reviewer if userStatus == "False" else reviewee,
								"driver": reviewer if userStatus == "True" else reviewee})

	res = r.json()
	if res["has_reservation"] is False:
		conn.close()
		return json.dumps({"status": 2})

	if int(rating) < 0 or int(rating) > 5:
		conn.close()
		return json.dumps({"status": 2})
	
	cursor.execute("INSERT INTO ratings (reviewer, reviewee, rating) VALUES (?, ?, ?)",(userFromPayload, username, int(rating)))
	conn.commit()	
	conn.close()
	return json.dumps({"status": 1})

@app.route('/verify_driver', methods=['GET'])
def verify_driver():
	global db_name
	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	token = request.headers.get('Authorization')

	if token is None: 
		conn.close()
		return json.dumps({"status": 3})
	
	header_b64, payload_b64, signature = token.split('.')

	#verify JWT
	with open('key.txt', 'r') as k:
		key = k.read()
	header_and_payload = header_b64 + "." + payload_b64
	expectedSig = hmac.new(key.encode('utf-8'), header_and_payload.encode('utf-8'), hashlib.sha256).hexdigest()

	if expectedSig != signature:
		conn.close()
		return json.dumps({"status": 3})
	
	#pull username from payload
	payloadJSON = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
	payload_2 = json.loads(payloadJSON)
	userFromPayload = payload_2.get('username')

	cursor.execute("SELECT isDriver FROM user WHERE username = ?",(userFromPayload,))
	userStatus = (cursor.fetchone())[0]

	if str(userStatus) == "True": 
		conn.close()
		return json.dumps({"status": 1, "username": userFromPayload})
	else: 
		conn.close()
		return json.dumps({"status": 2})


@app.route('/verify_passenger', methods=['GET'])
def verify_passenger():
	global db_name
	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	token = request.headers.get('Authorization')

	if token is None: 
		conn.close()
		return json.dumps({"status": 3})
	
	header_b64, payload_b64, signature = token.split('.')

	#verify JWT
	with open('key.txt', 'r') as k:
		key = k.read()
	header_and_payload = header_b64 + "." + payload_b64
	expectedSig = hmac.new(key.encode('utf-8'), header_and_payload.encode('utf-8'), hashlib.sha256).hexdigest()

	if expectedSig != signature:
		conn.close()
		return json.dumps({"status": 3})
	
	#pull username from payload
	payloadJSON = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
	payload_2 = json.loads(payloadJSON)
	userFromPayload = payload_2.get('username')

	cursor.execute("SELECT isDriver FROM user WHERE username = ?",(userFromPayload,))
	userStatus = (cursor.fetchone())[0]

	if str(userStatus) == "False": 
		conn.close()
		return json.dumps({"status": 1, "username": userFromPayload})
	else: 
		conn.close()
		return json.dumps({"status": 2})
	#1 = JWT valid, user is a passenger
	#2 = JWT valid, user it NOT a passenger
	#3 = JWT invalid

@app.route('/get_rating', methods = ['GET'])
def get_rating():
	global db_name
	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()
	username = request.args.get('username')

	cursor.execute("SELECT rating FROM ratings WHERE reviewee = ?", (username,))
	rows = cursor.fetchall()
	if len(rows) == 0:
		conn.close()
		return json.dumps({"status": 1, "rating": "0.00"})
	
	total = 0
	for r in rows: 
		total += r[0]

	avg = total/len(rows)

	conn.close()
	return json.dumps({"status": 1, "rating": f"{avg:.2f}"})
