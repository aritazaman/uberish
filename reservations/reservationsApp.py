import sqlite3
import os
import json
from flask import Flask, request
import hashlib
import base64
import hmac
import requests

app = Flask(__name__)
db_name = "reservations.db"
sql_file = "reservations.sql"
db_flag = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sql_file = os.path.join(BASE_DIR, "reservations.sql")
db_name = os.path.join(BASE_DIR, "reservations.db")
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
	cursor.execute("SELECT * FROM reservations;")
	result = cursor.fetchall()
	conn.close()

	return result

@app.route('/reserve', methods=(['POST']))
def reserve():
	global db_name
	listingID = request.form['listingid']
	token = request.headers.get('Authorization')

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	if token is None:
		conn.close()
		return json.dumps({"status": 2})
	
	verifyPassenger = "http://user:5000/verify_passenger"

	response = requests.get(
		url = verifyPassenger, headers = {"Authorization": token}
	)

	verify_data = response.json()

	#JWT NOT VALID: RETURN 2
	if verify_data["status"] == 3:
		conn.close()
		return json.dumps({"status": 2})
	
	#not a passenger: return 3
	if verify_data["status"] == 2:
		conn.close()
		return json.dumps({"status": 3})
	
	passengerUsername = verify_data["username"]

	listingurl = "http://availability:5000/get_listing"
	r = requests.get(url = listingurl, params={"listingid": listingID})

	getListing = r.json()

	#listing doesn't exist
	if getListing["status"] == 2:
		conn.close()
		return json.dumps({"status": 3})
	
	price = getListing["price"]
	cents = getListing["cents"]
	driver = getListing["driver"]
	day = getListing["day"]


	balanceUrl = "http://payments:5000/get_balance"
	balanceR = requests.get(url = balanceUrl, params={"username": passengerUsername})
	getBalance = balanceR.json()["balance_inCents"]

	#user doesn't have enough money
	if float(getBalance) < float(cents):
		return json.dumps({"status": 3})
	
	#transfer money from passenger -> driver
	requests.post("http://payments:5000/transfer", data={"passenger": passengerUsername, "driver": driver, "amount": price})

	conn.execute("INSERT INTO rides (listingID, passenger, driver, price) VALUES (?, ?, ?, ?)", (listingID, passengerUsername, driver, cents))

	conn.commit()

	requests.post("http://availability:5000/remove_listing", data={"listingid": listingID})

	return json.dumps({"status": 1})

@app.route('/view', methods=(['GET']))
def view():
	global db_name
	token = request.headers.get('Authorization')

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()
	passenger = None
	driver = None

	if token is None:
		conn.close()
		return json.dumps({"status": 2})
	
	verifyPassenger = "http://user:5000/verify_passenger"
	response = requests.get(
		url = verifyPassenger, headers = {"Authorization": token}
	)
	verify_data = response.json()

	if verify_data["status"] == 3:
		conn.close()
		return json.dumps({"status": 2, "data": "NULL"})
	
	if verify_data["status"] == 1: 
		passenger = verify_data["username"]

	verifyDriver = "http://user:5000/verify_driver"
	response = requests.get(
		url = verifyDriver, headers = {"Authorization": token}
	)
	verify_data = response.json()

	if verify_data["status"] == 3:
		conn.close()
		return json.dumps({"status": 2, "data": "NULL"})
	
	if verify_data["status"] == 1:
		driver = verify_data["username"]

	#passenger wants to view their reservation
	if passenger is not None: 
		cursor.execute("SELECT listingID, driver, price FROM rides WHERE passenger = ? ORDER BY number DESC LIMIT 1", (passenger,))
		row = cursor.fetchone()

		listingid = row[0]
		driver = row[1]
		price = row[2]
		priceStr = "{:.2f}".format(price / 100.0)

		#get driver rating
		#call get_rating from users

		ratingurl = "http://user:5000/get_rating"
		r = requests.get(url = ratingurl, params={"username": driver})
		getRating = r.json()

		#listing doesn't exist
		rating = getRating["rating"]
		rating = "{:.2f}".format(float(rating))
		
		conn.close()
		return json.dumps({
			"status": 1, 
			"data": {
				"listingid": listingid,
				"price": priceStr,
				"user": driver,
				"rating": rating
			}
		})

	#driver wants to view their reservation
	if driver is not None: 
		cursor.execute("SELECT listingID, passenger, price FROM rides WHERE driver = ? ORDER BY number DESC LIMIT 1", (driver,))
		row = cursor.fetchone()

		listingid = row[0]
		passenger = row[1]
		price = row[2]
		priceStr = "{:.2f}".format(price / 100.0)

		#get passenger rating
		#call get_rating from users

		ratingurl = "http://user:5000/get_rating"
		r = requests.get(url = ratingurl, params={"username": passenger})
		getRating = r.json()

		#listing doesn't exist
		rating = getRating["rating"]
		rating = "{:.2f}".format(float(rating))

		conn.close()
		return json.dumps({
			"status": 1, 
			"data": {
				"listingid": listingid,
				"price": priceStr,
				"user": passenger,
				"rating": rating
			}
		})


@app.route('/has_reservation', methods=(['GET']))
def has_reservation():
    global db_name
    passenger = request.args.get("passenger")
    driver = request.args.get("driver")

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM rides WHERE passenger = ? AND driver = ?",(passenger, driver))
    rows = cursor.fetchall()
    conn.close()

    if len(rows) == 0:
        return json.dumps({"status": 1, "has_reservation": False})

    return json.dumps({"status": 1, "has_reservation": True})
