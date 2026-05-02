from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

# DATABASE
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# UPLOAD CONFIG
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "pdf", "doc", "docx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# ----------------------------
# MODELS
# ----------------------------

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.Text)

class Update(db.Model):
    __tablename__ = "updates"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    author = db.Column(db.Text)
    status = db.Column(db.Text)
    note = db.Column(db.Text)
    created_at = db.Column(db.Text)

class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.String(100), nullable=False)

# ----------------------------
# HELPERS
# ----------------------------

def login_required():
    return "username" in session

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return filename
    return None

def get_file_type(filename):
    ext = filename.split(".")[-1].lower()
    if ext in ["png", "jpg", "jpeg", "gif"]:
        return "image"
    elif ext in ["mp4", "mov"]:
        return "video"
    else:
        return "file"

def get_files_for_update(update_id):
    result = db.session.execute(
        db.text("SELECT * FROM update_files WHERE update_id = :id"),
        {"id": update_id}
    )
    return result.fetchall()

# ----------------------------
# ROUTES
# ----------------------------

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["username"] = request.form["username"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    projects = Project.query.order_by(Project.name).all()
    project_id = request.args.get("project_id")

    updates = []
    if project_id:
        updates = Update.query.filter_by(project_id=project_id).order_by(Update.id.desc()).all()

    # attach files to updates
    updates_with_files = []
    for update in updates:
        files = get_files_for_update(update.id)
        update.files = files
        updates_with_files.append(update)

    return render_template(
        "dashboard.html",
        projects=projects,
        updates=updates_with_files,
        project_id=project_id
    )

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
        return redirect(url_for("dashboard"))

    return render_template("add_project.html")

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

        # MULTIPLE FILES
        files = request.files.getlist("attachments")

        for file in files:
            saved_file = save_uploaded_file(file)

            if saved_file:
                file_type = get_file_type(saved_file)

                db.session.execute(
                    db.text("""
                        INSERT INTO update_files (update_id, file_url, file_type)
                        VALUES (:update_id, :file_url, :file_type)
                    """),
                    {
                        "update_id": update.id,
                        "file_url": saved_file,
                        "file_type": file_type
                    }
                )

        db.session.commit()

        return redirect(url_for("dashboard", project_id=project_id))

    return render_template("add_update.html", projects=projects)

@app.route("/init-db")
def init_db():
    return "Init DB is disabled in production."

# ----------------------------
# RUN
# ----------------------------

if __name__ == "__main__":
    app.run(debug=True)