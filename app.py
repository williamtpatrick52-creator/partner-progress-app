import os
from types import SimpleNamespace
from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

USERS = {
    "tj": generate_password_hash("Adidas40!"),
    "ryan": generate_password_hash("Adidas40!")
}

ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif",
    "mp4", "mov", "webm",
    "pdf", "docx", "xlsx", "txt"
}


# -------------------------
# MODELS
# -------------------------
class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(20), default="📌")


class Update(db.Model):
    __tablename__ = "updates"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)
    author = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(300))
    attachment = db.Column(db.String(300))
    attachment_type = db.Column(db.String(50))


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.String(100), nullable=False)


# -------------------------
# SAFE INIT DB (DISABLED)
# -------------------------
@app.route("/init-db")
def init_db():
    return "Init DB is disabled in production. Contact admin if needed."


# -------------------------
# HELPERS
# -------------------------
def login_required():
    return "username" in session


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename):
    if not filename:
        return None

    ext = filename.rsplit(".", 1)[1].lower()

    if ext in ["png", "jpg", "jpeg", "gif"]:
        return "image"

    if ext in ["mp4", "mov", "webm"]:
        return "video"

    return "document"


def save_uploaded_file(file):
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        saved_name = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], saved_name))
        return saved_name

    return None


def make_update_view(update, project):
    return SimpleNamespace(
        id=update.id,
        project_id=update.project_id,
        author=update.author,
        status=update.status,
        note=update.note,
        created_at=update.created_at,
        image=update.image,
        attachment=update.attachment,
        attachment_type=update.attachment_type,
        project_name=project.name if project else "Unknown Project",
        project_icon=project.icon if project else "📌"
    )


# -------------------------
# AUTH
# -------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        if username in USERS and check_password_hash(USERS[username], password):
            session["username"] = username
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid username or password.")

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
        return redirect(url_for("login"))

    selected_project_id = request.args.get("project_id", type=int)

    projects = Project.query.order_by(Project.name).all()
    selected_project = None

    if selected_project_id:
        selected_project = Project.query.get(selected_project_id)

        rows = (
            db.session.query(Update, Project)
            .join(Project, Update.project_id == Project.id)
            .filter(Project.id == selected_project_id)
            .order_by(Update.id.desc())
            .limit(30)
            .all()
        )
    else:
        rows = (
            db.session.query(Update, Project)
            .join(Project, Update.project_id == Project.id)
            .order_by(Update.id.desc())
            .limit(30)
            .all()
        )

    latest_updates = [make_update_view(update, project) for update, project in rows]

    status_order = {
        "Needs Attention": 1,
        "Pending": 2,
        "Possible": 3,
        "Done": 4
    }

    tasks = Task.query.all()
    tasks = sorted(tasks, key=lambda t: (status_order.get(t.status, 5), -t.id))

    return render_template(
        "dashboard.html",
        projects=projects,
        latest_updates=latest_updates,
        tasks=tasks,
        username=session["username"],
        selected_project=selected_project,
        selected_project_id=selected_project_id
    )


# -------------------------
# PROJECTS
# -------------------------
@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        project = Project(
            name=request.form["name"],
            description=request.form["description"],
            icon=request.form["icon"]
        )

        db.session.add(project)
        db.session.commit()

        return redirect(url_for("dashboard", project_id=project.id))

    return render_template("add_project.html")


@app.route("/edit-project/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):
    if not login_required():
        return redirect(url_for("login"))

    project = Project.query.get(project_id)

    if project is None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        project.name = request.form["name"]
        project.description = request.form["description"]
        project.icon = request.form["icon"]

        db.session.commit()

        return redirect(url_for("dashboard", project_id=project.id))

    return render_template("edit_project.html", project=project)


@app.route("/delete-project/<int:project_id>", methods=["POST"])
def delete_project(project_id):
    if not login_required():
        return redirect(url_for("login"))

    Update.query.filter_by(project_id=project_id).delete()
    Project.query.filter_by(id=project_id).delete()

    db.session.commit()

    return redirect(url_for("dashboard"))


# -------------------------
# UPDATES
# -------------------------
@app.route("/add-update", methods=["GET", "POST"])
def add_update():
    if not login_required():
        return redirect(url_for("login"))

    projects = Project.query.order_by(Project.name).all()

    if request.method == "POST":
        project_id = int(request.form["project_id"])
        uploaded_file = request.files.get("attachment")

        attachment = save_uploaded_file(uploaded_file)
        attachment_type = get_file_type(attachment) if attachment else None

        update = Update(
            project_id=project_id,
            author=session["username"],
            status=request.form["status"],
            note=request.form["note"],
            created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            image=attachment if attachment_type == "image" else None,
            attachment=attachment,
            attachment_type=attachment_type
        )

        db.session.add(update)
        db.session.commit()

        return redirect(url_for("dashboard", project_id=project_id))

    return render_template("add_update.html", projects=projects)


@app.route("/delete-update/<int:update_id>", methods=["POST"])
def delete_update(update_id):
    if not login_required():
        return redirect(url_for("login"))

    update = Update.query.get(update_id)

    if update:
        db.session.delete(update)
        db.session.commit()

    return redirect(url_for("dashboard"))


# -------------------------
# TASKS
# -------------------------
@app.route("/add-task", methods=["POST"])
def add_task():
    if not login_required():
        return redirect(url_for("login"))

    task = Task(
        text=request.form["text"],
        status=request.form["status"],
        created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
    )

    db.session.add(task)
    db.session.commit()

    return redirect(url_for("dashboard"))


@app.route("/set-task-status/<int:task_id>/<status>", methods=["POST"])
def set_task_status(task_id, status):
    if not login_required():
        return redirect(url_for("login"))

    task = Task.query.get(task_id)

    if task:
        task.status = status
        db.session.commit()

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)