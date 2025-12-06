import sqlite3
import os
import json
from flask import Flask, request
import hashlib
import base64
import hmac
import requests

app = Flask(__name__)
db_name = "listings.db"
sql_file = "listings.sql"
db_flag = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sql_file = os.path.join(BASE_DIR, "listings.sql")
db_name = os.path.join(BASE_DIR, "listings.db")
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
	cursor.execute("SELECT * FROM listing;")
	result = cursor.fetchall()
	conn.close()

	return result
## end 

@app.route('/listing', methods=(['POST']))
def listing():
	global db_name
	day = request.form['day']
	price = request.form['price']
	listingID = request.form['listingid']
	token = request.headers.get('Authorization')

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	if token is None:
		conn.close()
		return json.dumps({"status": 2})
	
	# LOCALHOST VERSION
	# verifyDriver = "http://localhost:9000/verify_driver"   
	verifyDriver = "http://user:5000/verify_driver"

	response = requests.get(
		url = verifyDriver, headers = {"Authorization": token}
	)

	verify_data = response.json()

	if verify_data["status"] != 1:
		conn.close()
		return json.dumps({"status": 2})
	
	username = verify_data["username"]

	cents = int(float(price)*100)
	
	cursor.execute("INSERT INTO listing (username, day, cents, listingID) VALUES (?, ?, ?, ?)",(username, day, cents, listingID))
	conn.commit()	
	conn.close()

	return json.dumps({"status": 1})

@app.route('/search', methods=(['GET']))
def search():
	global db_name
	day = request.args.get('day')
	token = request.headers.get('Authorization')

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	if token is None:
		conn.close()
		return json.dumps({"status": 2})
	
	#only passenger can search	

	# verifyPassenger = "http://localhost:9000/verify_passenger"   
	verifyPassenger = "http://user:5000/verify_passenger"

	response = requests.get(
		url = verifyPassenger, headers = {"Authorization": token}
	)

	verify_data = response.json()

	if verify_data["status"] != 1:
		conn.close()
		return json.dumps({"status": 2})
	
	username = verify_data["username"]

	cursor.execute("SELECT listingid, username, cents FROM listing WHERE day = ?", (day,))
	rows = cursor.fetchall()

	result = []

	for listingid, driverUsername, price in rows: 
		#get rating from users.sql
		getRating = "http://user:5000/get_rating"
		r = requests.get(url = getRating, params={"username": driverUsername})
		rating_json = r.json()

		rating = rating_json["rating"]
		record = {
			"listingid": listingid,
			"price": f"{float(price)/100:.2f}",
			"driver": driverUsername,
			"rating": rating
		}

		result.append(record)
	conn.close()
	return json.dumps({"status": 1, "data": result})
	
	
@app.route('/get_listing', methods=['GET'])
def get_listing():
	global db_name
	listingID = request.args.get('listingid')

	conn = sqlite3.connect(db_name)
	cursor = conn.cursor()

	cursor.execute("SELECT * FROM listing WHERE listingID = ?", (listingID,))
	rows = cursor.fetchall()

	#listing doesn't exist
	if len(rows) == 0:
		return json.dumps({"status": 2})
	
	row = rows[0]
	driverUsername = row[0]
	day = row[1]
	cents = row[2]
	listingID = row[3]
	price = "{:.2f}".format(cents / 100)
	conn.close()

	return json.dumps({"status": 1, "listingid": listingID, "day": day, "driver": driverUsername, "price": price, "cents": cents})

@app.route('/remove_listing', methods=['POST'])
def remove_listing():
    global db_name
    listingid = request.form.get('listingid')

    #listingid missing
    if listingid is None:
        return json.dumps({"status": 2})

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM listing WHERE listingID = ?", (listingid,))
    conn.commit()
    conn.close()

    return json.dumps({"status": 1})
