from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret123"

# DATABASE
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ======================
# MODELS
# ======================

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    icon = db.Column(db.String(10))

class Update(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    status = db.Column(db.String(50))
    author = db.Column(db.String(50))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UpdateFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, db.ForeignKey('update.id', ondelete="CASCADE"))
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

# ======================
# ROUTES
# ======================

@app.route("/")
def home():
    if not logged_in():
        return redirect("/login")
    return redirect("/dashboard")

@app.route("/login", methods=["GET", "POST"])
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
            "project_name": project.name if project else "Unknown",
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
                           tasks=tasks)

# ======================
# PROJECTS
# ======================

@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if request.method == "POST":
        name = request.form["name"]
        icon = request.form["icon"]
        db.session.add(Project(name=name, icon=icon))
        db.session.commit()
        return redirect("/dashboard")
    return render_template("add_project.html")

@app.route("/edit-project/<int:id>", methods=["GET", "POST"])
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

@app.route("/add-update", methods=["GET", "POST"])
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

        # MULTI FILE UPLOAD
        files = request.files.getlist("files")

        for f in files:
            if f.filename:
                filename = f.filename
                path = os.path.join("static/uploads", filename)
                f.save(path)

                file_type = "file"
                if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                    file_type = "image"
                elif filename.lower().endswith((".mp4", ".mov")):
                    file_type = "video"

                db.session.add(UpdateFile(
                    update_id=update.id,
                    file_url=filename,
                    file_type=file_type
                ))

        db.session.commit()
        return redirect("/dashboard")

    return render_template("add_update.html", projects=projects)

@app.route("/edit-update/<int:id>", methods=["GET", "POST"])
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
    update = Update.query.get(id)

    # delete files too
    UpdateFile.query.filter_by(update_id=id).delete()

    db.session.delete(update)
    db.session.commit()
    return redirect("/dashboard")

# ======================
# TASKS (PRIORITY LIST)
# ======================

@app.route("/add-task", methods=["POST"])
def add_task():
    task = Task(
        text=request.form["text"],
        status=request.form["status"]
    )
    db.session.add(task)
    db.session.commit()
    return redirect("/dashboard")

@app.route("/edit-task/<int:id>", methods=["GET", "POST"])
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