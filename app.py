import os
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from supabase import create_client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret")

# DATABASE
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# SUPABASE
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "uploads"

# ======================
# MODELS
# ======================

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    icon = db.Column(db.String(10))

class Update(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    status = db.Column(db.String(50))
    author = db.Column(db.String(50))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UpdateFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer)
    file_url = db.Column(db.Text)
    file_type = db.Column(db.String(20))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    status = db.Column(db.String(20))

# ======================
# HELPERS
# ======================

def logged_in():
    return "username" in session

def get_file_type(filename):
    ext = filename.split(".")[-1].lower()
    if ext in ["png","jpg","jpeg","gif"]:
        return "image"
    if ext in ["mp4","mov"]:
        return "video"
    return "file"

def upload_to_supabase(file):
    filename = f"{datetime.now().timestamp()}_{file.filename}"

    supabase.storage.from_(BUCKET).upload(filename, file.read())

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{filename}"

    return public_url

# ======================
# ROUTES
# ======================

@app.route("/")
def home():
    if not logged_in():
        return redirect("/login")
    return redirect("/dashboard")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        session["username"] = request.form["username"]
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ======================
# DASHBOARD
# ======================

@app.route("/dashboard")
def dashboard():
    if not logged_in():
        return redirect("/login")

    projects = Project.query.all()
    tasks = Task.query.all()
    updates = Update.query.order_by(Update.created_at.desc()).all()

    latest_updates = []

    for u in updates:
        project = Project.query.get(u.project_id)
        files = UpdateFile.query.filter_by(update_id=u.id).all()

        latest_updates.append({
            "id": u.id,
            "project_name": project.name if project else "",
            "project_icon": project.icon if project else "",
            "status": u.status,
            "author": u.author,
            "note": u.note,
            "created_at": u.created_at.strftime("%Y-%m-%d %I:%M %p"),
            "files": files
        })

    return render_template("dashboard.html",
        username=session["username"],
        projects=projects,
        latest_updates=latest_updates,
        tasks=tasks
    )

# ======================
# ADD UPDATE (SUPABASE FILES)
# ======================

@app.route("/add-update", methods=["GET","POST"])
def add_update():
    projects = Project.query.all()

    if request.method == "POST":
        update = Update(
            project_id=request.form["project_id"],
            status=request.form["status"],
            author=session["username"],
            note=request.form["note"]
        )

        db.session.add(update)
        db.session.commit()

        files = request.files.getlist("attachments")

        for f in files:
            if f.filename:
                url = upload_to_supabase(f)
                file_type = get_file_type(f.filename)

                db.session.add(UpdateFile(
                    update_id=update.id,
                    file_url=url,
                    file_type=file_type
                ))

        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_update.html", projects=projects)

# ======================
# RUN
# ======================

if __name__ == "__main__":
    app.run(debug=True)