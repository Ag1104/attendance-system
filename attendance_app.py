from flask import Flask, request, jsonify, render_template
from datetime import datetime, date, time
import csv
import os
import math

app = Flask(__name__)

# ---------------- CONFIG ----------------
OFFICE_LATITUDE = 6.43090
OFFICE_LONGITUDE = 3.43615
ALLOWED_RADIUS_METERS = 30   # perimeter (meters)

SIGNIN_START_TIME = time(5, 0, 0)     # 5:00 AM
ONTIME_END_TIME = time(8, 30, 0)      # 8:30 AM

DATA_FOLDER = "attendance_records"
DATA_FILE = os.path.join(DATA_FOLDER, "attendance.csv")
STAFF_FILE = "staff_list.csv"  # CSV with staff_id,staff_name

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# ---------------- UTILITIES ----------------
def ensure_csv():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["staff_id", "date", "time", "status", "ip", "distance_meters"]
            )
            writer.writeheader()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def load_staff():
    """Load staff_id -> staff_name from CSV"""
    staff = {}
    if os.path.exists(STAFF_FILE):
        with open(STAFF_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                staff[row["staff_id"].strip().upper()] = row["staff_name"].strip()
    return staff

def get_user_ip():
    if "X-Forwarded-For" in request.headers:
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    return request.remote_addr

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    ensure_csv()
    return render_template("index.html")

@app.route("/staff")
def staff_list():
    return jsonify(load_staff())

@app.route("/signed_today")
def signed_today():
    ensure_csv()
    today = date.today().isoformat()
    signed_ids = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"] == today:
                signed_ids.append(row["staff_id"])
    return jsonify(signed_ids)

@app.route("/signin", methods=["POST"])
def signin():
    ensure_csv()
    data = request.json
    staff_id = data.get("staff_id", "").strip().upper()
    lat = data.get("latitude")
    lon = data.get("longitude")
    user_ip = get_user_ip()

    if not staff_id:
        return jsonify({"message": "Staff ID is required"}), 400

    # -------- LOCATION CHECK --------
    distance = calculate_distance(lat, lon, OFFICE_LATITUDE, OFFICE_LONGITUDE)
    if distance > ALLOWED_RADIUS_METERS:
        return jsonify({"message": f"You are outside the office perimeter ({int(distance)}m away)"}), 403

    now = datetime.now()
    today = now.date().isoformat()
    current_time_str = now.strftime("%I:%M %p")

    if now.time() < SIGNIN_START_TIME:
        return jsonify({"message": "Sign-in has not started yet"}), 403

    status = "ON TIME" if now.time() <= ONTIME_END_TIME else "LATE"

    # -------- DUPLICATE CHECKS --------
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check if this staff already signed in today
            if row["staff_id"] == staff_id and row["date"] == today:
                return jsonify({"message": "This staff has already signed in today"}), 409
            # Check if this device/IP already signed in today
            if row["ip"] == user_ip and row["date"] == today:
                return jsonify({"message": "This device has already signed in today"}), 409

    # -------- SAVE --------
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["staff_id", "date", "time", "status", "ip", "distance_meters"])
        writer.writerow({
            "staff_id": staff_id,
            "date": today,
            "time": current_time_str,
            "status": status,
            "ip": user_ip,
            "distance_meters": round(distance, 2)
        })

    return jsonify({"message": "Sign-in successful", "time": current_time_str, "status": status})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)