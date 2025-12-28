from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "milk-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------
DEFAULT_USER_ID = 1

# --------------------------------------------------
# MODELS
# --------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class MilkLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    day = db.Column(db.Date)
    quantity = db.Column(db.Integer)  # 1 or 2

class MonthlyPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    year = db.Column(db.Integer)
    month = db.Column(db.Integer)
    price = db.Column(db.Integer)

# --------------------------------------------------
# INIT DB
# --------------------------------------------------

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            db.session.add(User(name="Milk User"))
            db.session.commit()

# --------------------------------------------------
# SPLASH / BANNER PAGE
# --------------------------------------------------

@app.route("/")
def splash():
    return render_template("splash.html")

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
def dashboard():
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    return render_template(
        "dashboard.html",
        year=year,
        month=month
    )

# --------------------------------------------------
# API: MONTH DATA
# --------------------------------------------------

@app.route("/api/month")
def api_month():
    user_id = DEFAULT_USER_ID

    year = int(request.args["year"])
    month = int(request.args["month"])

    today = date.today()
    is_current_month = (year == today.year and month == today.month)

    # Milk logs
    logs = MilkLog.query.filter(
        MilkLog.user_id == user_id,
        db.extract("year", MilkLog.day) == year,
        db.extract("month", MilkLog.day) == month
    ).all()

    days = {log.day.strftime("%Y-%m-%d"): log.quantity for log in logs}

    # Monthly price (applies only to that month)
    price_row = MonthlyPrice.query.filter_by(
        user_id=user_id,
        year=year,
        month=month
    ).first()

    price = price_row.price if price_row else 0

    total_qty = sum(days.values())
    milk_days = len(days)
    total_bill = total_qty * price

    return jsonify({
        "editable": is_current_month,
        "days": days,
        "summary": {
            "milk_days": milk_days,
            "total_quantity": total_qty,
            "price": price,
            "total_bill": total_bill
        }
    })

# --------------------------------------------------
# API: SET DAY (ONLY CURRENT MONTH)
# --------------------------------------------------

@app.route("/api/day", methods=["POST"])
def api_day():
    user_id = DEFAULT_USER_ID
    data = request.json

    day = datetime.strptime(data["date"], "%Y-%m-%d").date()
    qty = int(data["quantity"])

    today = date.today()
    if not (day.year == today.year and day.month == today.month):
        return jsonify({"error": "Read only month"}), 403

    log = MilkLog.query.filter_by(user_id=user_id, day=day).first()

    if qty == 0:
        if log:
            db.session.delete(log)
    else:
        if log:
            log.quantity = qty
        else:
            db.session.add(
                MilkLog(
                    user_id=user_id,
                    day=day,
                    quantity=qty
                )
            )

    db.session.commit()
    return jsonify({"success": True})

# --------------------------------------------------
# API: UPDATE PRICE (CURRENT MONTH ONLY)
# --------------------------------------------------

@app.route("/api/price", methods=["POST"])
def api_price():
    user_id = DEFAULT_USER_ID
    price = int(request.json["price"])

    today = date.today()

    row = MonthlyPrice.query.filter_by(
        user_id=user_id,
        year=today.year,
        month=today.month
    ).first()

    if row:
        row.price = price
    else:
        db.session.add(
            MonthlyPrice(
                user_id=user_id,
                year=today.year,
                month=today.month,
                price=price
            )
        )

    db.session.commit()
    return jsonify({"success": True})

# --------------------------------------------------
# START
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
