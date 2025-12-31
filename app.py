from flask import Flask, render_template, request, jsonify, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy.engine.url import URL

app = Flask(__name__)
app.secret_key = "milk-secret-key"

# --------------------------------------------------
# DATABASE CONFIG (UNCHANGED – SUPABASE via IP)
# --------------------------------------------------

DATABASE = {
    "drivername": "postgresql+psycopg2",
    "username": "postgres.bjagqrlyskreptjbikzj",
    "password": "kzZPFVv3uW7t5OYA",
    "database": "postgres",
    "query": {"sslmode": "require"}
}

ENGINE_OPTIONS = {
    "connect_args": {
        "hostaddr": "3.111.225.200",
        "port": 5432
    }
}

app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(**DATABASE)
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = ENGINE_OPTIONS
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------------------------------------
# MODELS
# --------------------------------------------------

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True)
    pin = db.Column(db.String(4), nullable=False)

    # 🔔 Reminder fields
    reminder_enabled = db.Column(db.Boolean, default=False)
    reminder_time = db.Column(db.Time, nullable=True)

class MilkLog(db.Model):
    __tablename__ = "milk_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    day = db.Column(db.Date)
    quantity = db.Column(db.Integer)

class MonthlyPrice(db.Model):
    __tablename__ = "monthly_price"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    year = db.Column(db.Integer)
    month = db.Column(db.Integer)
    price = db.Column(db.Integer)

# --------------------------------------------------
# AUTH
# --------------------------------------------------

@app.route("/")
def root():
    return redirect("/auth")

@app.route("/auth", methods=["GET", "POST"])
def auth():
    if request.method == "GET":
        return render_template("auth.html")

    data = request.json
    mode = data.get("mode")
    pin = data.get("pin", "").strip()
    name = data.get("name", "").strip()

    if not pin.isdigit() or len(pin) != 4:
        return jsonify({"error": "PIN must be exactly 4 digits"}), 400

    # ---------- REGISTER ----------
    if mode == "register":
        if not name:
            return jsonify({"error": "Name required"}), 400

        if User.query.filter_by(pin=pin).first():
            return jsonify({"error": "PIN already exists"}), 400

        user = User(name=name, pin=pin)
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["username"] = user.name

        return jsonify({"success": True})

    # ---------- LOGIN ----------
    user = User.query.filter_by(pin=pin).first()
    if not user:
        return jsonify({"error": "Invalid PIN"}), 401

    session["user_id"] = user.id
    session["username"] = user.name

    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/auth")

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/auth")

    today = date.today()
    return render_template(
        "dashboard.html",
        year=today.year,
        month=today.month,
        username=session["username"]
    )

# --------------------------------------------------
# 🔔 REMINDER APIs
# --------------------------------------------------

@app.route("/api/reminder", methods=["GET"])
def get_reminder():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.get(session["user_id"])

    return jsonify({
        "enabled": user.reminder_enabled,
        "time": user.reminder_time.strftime("%H:%M") if user.reminder_time else None
    })

@app.route("/api/reminder", methods=["POST"])
def set_reminder():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    enabled = bool(data.get("enabled"))
    time_str = data.get("time")

    user = User.query.get(session["user_id"])

    user.reminder_enabled = enabled

    if enabled and time_str:
        user.reminder_time = datetime.strptime(time_str, "%H:%M").time()
    else:
        user.reminder_time = None

    db.session.commit()

    return jsonify({"success": True})

# --------------------------------------------------
# API: MONTH
# --------------------------------------------------

@app.route("/api/month")
def api_month():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    year = int(request.args["year"])
    month = int(request.args["month"])

    today = date.today()
    editable = (year == today.year and month == today.month)

    logs = MilkLog.query.filter(
        MilkLog.user_id == user_id,
        db.extract("year", MilkLog.day) == year,
        db.extract("month", MilkLog.day) == month
    ).all()

    days = {log.day.strftime("%Y-%m-%d"): log.quantity for log in logs}

    price_row = MonthlyPrice.query.filter_by(
        user_id=user_id, year=year, month=month
    ).first()

    price = price_row.price if price_row else 0
    total_qty = sum(days.values())

    return jsonify({
        "editable": editable,
        "days": days,
        "summary": {
            "milk_days": len(days),
            "total_quantity": total_qty,
            "price": price,
            "total_bill": total_qty * price
        }
    })

# --------------------------------------------------
# API: DAY
# --------------------------------------------------

@app.route("/api/day", methods=["POST"])
def api_day():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    data = request.json

    day = datetime.strptime(data["date"], "%Y-%m-%d").date()
    qty = int(data["quantity"])

    today = date.today()
    if day.year != today.year or day.month != today.month:
        return jsonify({"error": "Read only"}), 403

    log = MilkLog.query.filter_by(user_id=user_id, day=day).first()

    if qty == 0:
        if log:
            db.session.delete(log)
    else:
        if log:
            log.quantity = qty
        else:
            db.session.add(MilkLog(user_id=user_id, day=day, quantity=qty))

    db.session.commit()
    return jsonify({"success": True})

# --------------------------------------------------
# API: PRICE
# --------------------------------------------------

@app.route("/api/price", methods=["POST"])
def api_price():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    price = int(request.json["price"])
    today = date.today()

    row = MonthlyPrice.query.filter_by(
        user_id=user_id, year=today.year, month=today.month
    ).first()

    if row:
        row.price = price
    else:
        db.session.add(MonthlyPrice(
            user_id=user_id,
            year=today.year,
            month=today.month,
            price=price
        ))

    db.session.commit()
    return jsonify({"success": True})

# --------------------------------------------------
# START
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
