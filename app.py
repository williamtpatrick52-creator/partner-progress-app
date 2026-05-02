import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from supabase import create_client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = "uploads"

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

USERS = {
    "tj": generate_password_hash("Adidas40!"),
    "ryan": generate_password_hash("Adidas40!")
}


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


class UpdateComment(db.Model):
    __tablename__ = "update_comments"

    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, nullable=False)
    author = db.Column(db.String(100))
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(100))


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    status = db.Column(db.String(100))
    created_at = db.Column(db.String(100))


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

    supabase.storage.from_(SUPABASE_BUCKET).upload(
        storage_name,
        file.read(),
        {"content-type": file.content_type}
    )

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(storage_name)


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower().strip()
        password = request.form["password"]

        if username in USERS and check_password_hash(USERS[username], password):
            session["username"] = username
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid username or password.")

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

    for update in updates:
        project = Project.query.get(update.project_id)
        files = UpdateFile.query.filter_by(update_id=update.id).all()
        comments = UpdateComment.query.filter_by(update_id=update.id).order_by(UpdateComment.id.asc()).all()

        latest_updates.append({
            "id": update.id,
            "project_name": project.name if project else "Unknown",
            "project_icon": project.icon if project else "📁",
            "status": update.status,
            "author": update.author,
            "note": update.note,
            "created_at": update.created_at,
            "files": files,
            "comments": comments
        })

    tasks = Task.query.all()

    return render_template(
        "dashboard.html",
        username=session["username"],
        projects=projects,
        latest_updates=latest_updates,
        tasks=tasks
    )


@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        project = Project(
            name=request.form["name"],
            description=request.form.get("description", ""),
            icon=request.form.get("icon", "📁")
        )

        db.session.add(project)
        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_project.html")


@app.route("/edit-project/<int:id>", methods=["GET", "POST"])
def edit_project(id):
    if not login_required():
        return redirect("/")

    project = Project.query.get_or_404(id)

    if request.method == "POST":
        project.name = request.form["name"]
        project.description = request.form.get("description", "")
        project.icon = request.form.get("icon", "📁")

        db.session.commit()

        return redirect("/dashboard")

    return render_template("edit_project.html", project=project)


@app.route("/delete-project/<int:id>", methods=["GET", "POST"])
def delete_project(id):
    if not login_required():
        return redirect("/")

    updates = Update.query.filter_by(project_id=id).all()

    for update in updates:
        UpdateFile.query.filter_by(update_id=update.id).delete()
        UpdateComment.query.filter_by(update_id=update.id).delete()
        db.session.delete(update)

    Project.query.filter_by(id=id).delete()

    db.session.commit()

    return redirect("/dashboard")


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
                file_url = upload_file_to_supabase(file)
                file_type = get_file_type(file.filename)

                db.session.add(UpdateFile(
                    update_id=update.id,
                    file_url=file_url,
                    file_type=file_type
                ))

        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_update.html", projects=projects)


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


@app.route("/delete-update/<int:id>", methods=["GET", "POST"])
def delete_update(id):
    if not login_required():
        return redirect("/")

    UpdateFile.query.filter_by(update_id=id).delete()
    UpdateComment.query.filter_by(update_id=id).delete()
    Update.query.filter_by(id=id).delete()

    db.session.commit()

    return redirect("/dashboard")


@app.route("/add-comment/<int:update_id>", methods=["POST"])
def add_comment(update_id):
    if not login_required():
        return redirect("/")

    comment_text = request.form.get("comment", "").strip()

    if comment_text:
        comment = UpdateComment(
            update_id=update_id,
            author=session["username"],
            comment=comment_text,
            created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
        )

        db.session.add(comment)
        db.session.commit()

    return redirect("/dashboard")


@app.route("/delete-comment/<int:id>", methods=["GET", "POST"])
def delete_comment(id):
    if not login_required():
        return redirect("/")

    UpdateComment.query.filter_by(id=id).delete()
    db.session.commit()

    return redirect("/dashboard")


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


@app.route("/edit-task/<int:id>", methods=["GET", "POST"])
def edit_task(id):
    if not login_required():
        return redirect("/")

    task = Task.query.get_or_404(id)

    if request.method == "POST":
        task.text = request.form["text"]
        task.status = request.form["status"]

        db.session.commit()

        return redirect("/dashboard")

    return render_template("edit_task.html", task=task)


@app.route("/delete-task/<int:id>", methods=["GET", "POST"])
def delete_task(id):
    if not login_required():
        return redirect("/")

    Task.query.filter_by(id=id).delete()

    db.session.commit()

    return redirect("/dashboard")


@app.route("/init-db")
def init_db():
    return "Init DB is disabled in production."


if __name__ == "__main__":
    app.run(debug=True)