from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import calendar

app = Flask(__name__)
app.secret_key = "milk-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------ MODELS ------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class MilkLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    day = db.Column(db.Date, nullable=False)
    taken = db.Column(db.Boolean, default=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price_per_day = db.Column(db.Integer, nullable=False)

# ------------------ INIT DB (Flask 3.x SAFE) ------------------

def init_db():
    with app.app_context():
        db.create_all()

        # Seed data only once
        if not User.query.first():
            db.session.add_all([
                User(name="Rushi"),
                User(name="Shruti")
            ])
            db.session.add(Settings(price_per_day=80))
            db.session.commit()

# ------------------ LOGIN ------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user_id"] = request.form["user_id"]
        return redirect("/dashboard")

    users = User.query.all()
    return render_template("login.html", users=users)

# ------------------ DASHBOARD ------------------

@app.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/")

    user_id = int(user_id)
    today = date.today()
    year = today.year
    month = today.month

    days_in_month = calendar.monthrange(year, month)[1]

    logs = {
        log.day.day: log
        for log in MilkLog.query.filter_by(user_id=user_id)
        if log.day.month == month and log.day.year == year
    }

    price = Settings.query.first().price_per_day
    taken_days = sum(1 for log in logs.values() if log.taken)
    bill = taken_days * price

    return render_template(
        "dashboard.html",
        days=range(1, days_in_month + 1),
        logs=logs,
        price=price,
        bill=bill,
        month=today.strftime("%B"),
        year=year
    )

# ------------------ TOGGLE MILK ------------------

@app.route("/toggle", methods=["POST"])
def toggle():
    user_id = int(session.get("user_id"))
    day = int(request.form["day"])

    today = date.today()
    log_date = date(today.year, today.month, day)

    log = MilkLog.query.filter_by(user_id=user_id, day=log_date).first()

    if log:
        log.taken = not log.taken
    else:
        db.session.add(
            MilkLog(user_id=user_id, day=log_date, taken=True)
        )

    db.session.commit()
    return redirect("/dashboard")



@app.route("/update-price", methods=["POST"])
def update_price():
    new_price = int(request.form["price"])

    settings = Settings.query.first()
    settings.price_per_day = new_price
    db.session.commit()

    return redirect("/dashboard")


# ------------------ LOGOUT ------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ------------------ APP START ------------------

if __name__ == "__main__":
    init_db()
    app.run()
