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
    return "Init DB is disabled in production."

# -------------------------
# HELPERS
# -------------------------
def login_required():
    return "username" in session

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        saved_name = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], saved_name))
        return saved_name
    return None

def get_file_type(filename):
    ext = filename.rsplit(".", 1)[1].lower()
    if ext in ["png", "jpg", "jpeg", "gif"]:
        return "image"
    if ext in ["mp4", "mov", "webm"]:
        return "video"
    return "document"

def get_files_for_update(update_id):
    result = db.session.execute(
        db.text("SELECT * FROM update_files WHERE update_id = :id"),
        {"id": update_id}
    )
    return result.fetchall()

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
        return redirect(url_for("login"))

    selected_project_id = request.args.get("project_id", type=int)

    projects = Project.query.order_by(Project.name).all()

    rows = (
        db.session.query(Update, Project)
        .join(Project, Update.project_id == Project.id)
        .order_by(Update.id.desc())
        .all()
    )

    updates = []
    for update, project in rows:
        files = get_files_for_update(update.id)
        updates.append(SimpleNamespace(
            id=update.id,
            project_id=update.project_id,
            author=update.author,
            status=update.status,
            note=update.note,
            created_at=update.created_at,
            project_name=project.name,
            project_icon=project.icon,
            files=files
        ))

    return render_template(
        "dashboard.html",
        projects=projects,
        latest_updates=updates,
        username=session["username"]
    )

# -------------------------
# ADD UPDATE (MULTI FILE)
# -------------------------
@app.route("/add-update", methods=["GET", "POST"])
def add_update():
    if not login_required():
        return redirect(url_for("login"))

    projects = Project.query.order_by(Project.name).all()

    if request.method == "POST":
        project_id = int(request.form["project_id"])

        update = Update(
            project_id=project_id,
            author=session["username"],
            status=request.form["status"],
            note=request.form["note"],
            created_at=datetime.now().strftime("%Y-%m-%d %I:%M %p")
        )

        db.session.add(update)
        db.session.commit()

        files = request.files.getlist("attachments")

        for file in files:
            saved = save_uploaded_file(file)
            if saved:
                db.session.execute(
                    db.text("""
                        INSERT INTO update_files (update_id, file_url, file_type)
                        VALUES (:u, :f, :t)
                    """),
                    {
                        "u": update.id,
                        "f": saved,
                        "t": get_file_type(saved)
                    }
                )

        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("add_update.html", projects=projects)

if __name__ == "__main__":
    app.run(debug=True)