import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------
# MODELS (FIXED TABLE NAMES)
# -----------------------------

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(20))


class Update(db.Model):
    __tablename__ = "updates"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)
    author = db.Column(db.String(100))
    status = db.Column(db.String(50))
    note = db.Column(db.Text)
    created_at = db.Column(db.String(100))


class UpdateFile(db.Model):
    __tablename__ = "update_files"

    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, nullable=False)
    file_url = db.Column(db.Text)
    file_type = db.Column(db.String(50))


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    status = db.Column(db.String(100))
    created_at = db.Column(db.String(100))


# -----------------------------
# HELPERS
# -----------------------------

def login_required():
    return "username" in session


# -----------------------------
# ROUTES
# -----------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username and password:
            session["username"] = username
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/")

    project_id = request.args.get("project_id")

    projects = Project.query.all()

    updates_query = Update.query

    if project_id:
        updates_query = updates_query.filter_by(project_id=project_id)

    updates = updates_query.order_by(Update.id.desc()).all()

    latest_updates = []

    for u in updates:
        project = Project.query.get(u.project_id)
        files = UpdateFile.query.filter_by(update_id=u.id).all()

        latest_updates.append({
            "id": u.id,
            "project_name": project.name if project else "Unknown",
            "project_icon": project.icon if project else "📁",
            "status": u.status,
            "author": u.author,
            "note": u.note,
            "created_at": u.created_at,
            "files": files
        })

    tasks = Task.query.all()

    return render_template(
        "dashboard.html",
        username=session["username"],
        projects=projects,
        latest_updates=latest_updates,
        tasks=tasks
    )


# -----------------------------
# ADD PROJECT
# -----------------------------

@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        project = Project(
            name=request.form["name"],
            description=request.form.get("description"),
            icon=request.form.get("icon", "📁")
        )

        db.session.add(project)
        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_project.html")


# -----------------------------
# ADD UPDATE (MULTI FILE)
# -----------------------------

@app.route("/add-update", methods=["GET", "POST"])
def add_update():
    if not login_required():
        return redirect("/")

    projects = Project.query.all()

    if request.method == "POST":
        update = Update(
            project_id=request.form["project_id"],
            author=session["username"],
            status=request.form["status"],
            note=request.form["note"],
            created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
        )

        db.session.add(update)
        db.session.commit()

        files = request.files.getlist("files")

        for file in files:
            if file and file.filename:
                filename = file.filename

                path = os.path.join("static/uploads", filename)
                file.save(path)

                file_type = "file"

                if filename.lower().endswith(("png","jpg","jpeg","gif")):
                    file_type = "image"
                elif filename.lower().endswith(("mp4","mov")):
                    file_type = "video"

                new_file = UpdateFile(
                    update_id=update.id,
                    file_url=filename,
                    file_type=file_type
                )

                db.session.add(new_file)

        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_update.html", projects=projects)


# -----------------------------
# TASKS
# -----------------------------

@app.route("/add-task", methods=["POST"])
def add_task():
    if not login_required():
        return redirect("/")

    task = Task(
        text=request.form["text"],
        status=request.form["status"],
        created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
    )

    db.session.add(task)
    db.session.commit()

    return redirect("/dashboard")


@app.route("/delete-task/<int:id>")
def delete_task(id):
    if not login_required():
        return redirect("/")

    Task.query.filter_by(id=id).delete()
    db.session.commit()

    return redirect("/dashboard")


# -----------------------------
# RUN
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)