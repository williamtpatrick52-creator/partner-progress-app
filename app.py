import os
from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

# -------------------------
# DATABASE (SUPABASE)
# -------------------------

database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------------
# FILE UPLOAD
# -------------------------

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -------------------------
# USERS
# -------------------------

USERS = {
    "tj": generate_password_hash("Adidas40!"),
    "ryan": generate_password_hash("Adidas40!")
}

# -------------------------
# MODELS
# -------------------------

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    description = db.Column(db.Text)
    icon = db.Column(db.String(10), default="📌")

class Update(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    author = db.Column(db.String(100))
    status = db.Column(db.String(50))
    note = db.Column(db.Text)
    created_at = db.Column(db.String(50))
    image = db.Column(db.String(200))
    attachment = db.Column(db.String(200))
    attachment_type = db.Column(db.String(50))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200))
    status = db.Column(db.String(50))
    created_at = db.Column(db.String(50))

# -------------------------
# INIT DB (RUN ONCE)
# -------------------------

with app.app_context():
    db.create_all()

# -------------------------
# AUTH
# -------------------------

def login_required():
    return "username" in session

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        if username in USERS and check_password_hash(USERS[username], password):
            session["username"] = username
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
# DASHBOARD
# -------------------------

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/")

    projects = Project.query.all()
    updates = Update.query.order_by(Update.id.desc()).limit(30).all()
    tasks = Task.query.all()

    return render_template(
        "dashboard.html",
        projects=projects,
        latest_updates=updates,
        tasks=tasks,
        username=session["username"]
    )

# -------------------------
# PROJECTS
# -------------------------

@app.route("/add-project", methods=["POST"])
def add_project():
    project = Project(
        name=request.form["name"],
        description=request.form["description"],
        icon=request.form["icon"]
    )
    db.session.add(project)
    db.session.commit()
    return redirect("/dashboard")

@app.route("/delete-project/<int:id>", methods=["POST"])
def delete_project(id):
    Project.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect("/dashboard")

# -------------------------
# TASKS
# -------------------------

@app.route("/add-task", methods=["POST"])
def add_task():
    task = Task(
        text=request.form["text"],
        status=request.form["status"],
        created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
    )
    db.session.add(task)
    db.session.commit()
    return redirect("/dashboard")

@app.route("/set-task-status/<int:id>/<status>", methods=["POST"])
def set_task_status(id, status):
    task = Task.query.get(id)
    task.status = status
    db.session.commit()
    return redirect("/dashboard")

# -------------------------
# UPDATES
# -------------------------

@app.route("/add-update", methods=["POST"])
def add_update():
    update = Update(
        project_id=request.form["project_id"],
        author=session["username"],
        status=request.form["status"],
        note=request.form["note"],
        created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
    )
    db.session.add(update)
    db.session.commit()
    return redirect("/dashboard")

# -------------------------
# RUN
# -------------------------

if __name__ == "__main__":
    app.run(debug=True)