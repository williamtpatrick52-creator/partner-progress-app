import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from supabase import create_client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = "uploads"

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ================= MODELS =================

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


# ================= HELPERS =================

def login_required():
    return "username" in session


def get_file_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        return "image"

    if ext in ["mp4", "mov", "webm"]:
        return "video"

    return "document"


def upload_file_to_supabase(file):
    name = file.filename.replace(" ", "_")
    storage_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{name}"

    file_bytes = file.read()

    supabase.storage.from_(SUPABASE_BUCKET).upload(
        storage_name,
        file_bytes,
        {"content-type": file.content_type}
    )

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(storage_name)


# ================= ROUTES =================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["username"] = request.form["username"]
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

        for f in files:
            if f and f.filename:
                url = upload_file_to_supabase(f)
                file_type = get_file_type(f.filename)

                db.session.add(UpdateFile(
                    update_id=update.id,
                    file_url=url,
                    file_type=file_type
                ))

        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_update.html", projects=projects)


# ================= EDIT UPDATE =================

@app.route("/edit-update/<int:id>", methods=["GET", "POST"])
def edit_update(id):
    if not login_required():
        return redirect("/")

    update = Update.query.get_or_404(id)
    projects = Project.query.all()

    if request.method == "POST":
        update.project_id = request.form["project_id"]
        update.status = request.form["status"]
        update.note = request.form["note"]

        db.session.commit()

        return redirect("/dashboard")

    return render_template("edit_update.html", update=update, projects=projects)


# ================= DELETE =================

@app.route("/delete-update/<int:id>")
def delete_update(id):
    UpdateFile.query.filter_by(update_id=id).delete()
    Update.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect("/dashboard")


# ================= TASKS =================

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


@app.route("/update-task/<int:id>/<status>")
def update_task(id, status):
    task = Task.query.get_or_404(id)
    task.status = status
    db.session.commit()
    return redirect("/dashboard")


@app.route("/delete-task/<int:id>")
def delete_task(id):
    Task.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect("/dashboard")


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)