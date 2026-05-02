import os
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from supabase import create_client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret")

# ======================
# DATABASE
# ======================
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ======================
# SUPABASE
# ======================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "uploads"

# ======================
# MODELS (FIXED)
# ======================

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    icon = db.Column(db.String(10))

class Update(db.Model):
    __tablename__ = "updates"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    status = db.Column(db.String(50))
    author = db.Column(db.String(50))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UpdateFile(db.Model):
    __tablename__ = "update_files"
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer)
    file_url = db.Column(db.Text)
    file_type = db.Column(db.String(20))

class Task(db.Model):
    __tablename__ = "tasks"
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
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{filename}"

# ======================
# AUTH
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
# PROJECTS
# ======================

@app.route("/add-project", methods=["GET","POST"])
def add_project():
    if request.method == "POST":
        db.session.add(Project(
            name=request.form["name"],
            icon=request.form["icon"]
        ))
        db.session.commit()
        return redirect("/dashboard")

    return render_template("add_project.html")

@app.route("/edit-project/<int:id>", methods=["GET","POST"])
def edit_project(id):
    project = Project.query.get(id)

    if request.method == "POST":
        project.name = request.form["name"]
        project.icon = request.form["icon"]
        db.session.commit()
        return redirect("/dashboard")

    return render_template("edit_project.html", project=project)

@app.route("/delete-project/<int:id>")
def delete_project(id):
    project = Project.query.get(id)
    db.session.delete(project)
    db.session.commit()
    return redirect("/dashboard")

# ======================
# UPDATES
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

@app.route("/edit-update/<int:id>", methods=["GET","POST"])
def edit_update(id):
    update = Update.query.get(id)
    projects = Project.query.all()

    if request.method == "POST":
        update.project_id = request.form["project_id"]
        update.status = request.form["status"]
        update.note = request.form["note"]
        db.session.commit()
        return redirect("/dashboard")

    return render_template("edit_update.html", update=update, projects=projects)

@app.route("/delete-update/<int:id>")
def delete_update(id):
    UpdateFile.query.filter_by(update_id=id).delete()
    update = Update.query.get(id)
    db.session.delete(update)
    db.session.commit()
    return redirect("/dashboard")

# ======================
# TASKS
# ======================

@app.route("/add-task", methods=["POST"])
def add_task():
    db.session.add(Task(
        text=request.form["text"],
        status=request.form["status"]
    ))
    db.session.commit()
    return redirect("/dashboard")

@app.route("/edit-task/<int:id>", methods=["GET","POST"])
def edit_task(id):
    task = Task.query.get(id)

    if request.method == "POST":
        task.text = request.form["text"]
        task.status = request.form["status"]
        db.session.commit()
        return redirect("/dashboard")

    return render_template("edit_task.html", task=task)

@app.route("/delete-task/<int:id>")
def delete_task(id):
    task = Task.query.get(id)
    db.session.delete(task)
    db.session.commit()
    return redirect("/dashboard")

# ======================
# RUN
# ======================

if __name__ == "__main__":
    app.run(debug=True)