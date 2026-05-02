from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------
# MODELS
# -----------------------------

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(10))


class Update(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    content = db.Column(db.Text)
    status = db.Column(db.String(50))
    author = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project")


class UpdateFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, db.ForeignKey("update.id", ondelete="CASCADE"))
    file_url = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# -----------------------------
# HELPERS
# -----------------------------

def login_required():
    return "username" in session


# -----------------------------
# ROUTES
# -----------------------------

@app.route("/")
def home():
    if login_required():
        return redirect("/dashboard")
    return redirect("/login")


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


# -----------------------------
# DASHBOARD (FIXED)
# -----------------------------

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/login")

    project_id = request.args.get("project_id")

    projects = Project.query.all()

    updates_query = Update.query

    if project_id:
        updates_query = updates_query.filter_by(project_id=project_id)

    updates = updates_query.order_by(Update.created_at.desc()).all()

    latest_updates = []

    for u in updates:
        files = UpdateFile.query.filter_by(update_id=u.id).all()

        # ✅ SAFE DATE FIX
        if hasattr(u.created_at, "strftime"):
            created_at = u.created_at.strftime("%Y-%m-%d %I:%M %p")
        else:
            created_at = str(u.created_at)

        latest_updates.append({
            "id": u.id,
            "project_name": u.project.name,
            "project_icon": u.project.icon,
            "status": u.status,
            "author": u.author,
            "note": u.content,
            "created_at": created_at,
            "files": files
        })

    return render_template(
        "dashboard.html",
        username=session["username"],
        projects=projects,
        latest_updates=latest_updates
    )


# -----------------------------
# ADD PROJECT
# -----------------------------

@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if not login_required():
        return redirect("/login")

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
# ADD UPDATE (MULTI FILE READY)
# -----------------------------

@app.route("/add-update", methods=["GET", "POST"])
def add_update():
    if not login_required():
        return redirect("/login")

    projects = Project.query.all()

    if request.method == "POST":
        update = Update(
            project_id=request.form["project_id"],
            content=request.form["content"],
            status=request.form["status"],
            author=session["username"]
        )

        db.session.add(update)
        db.session.commit()

        # HANDLE MULTIPLE FILES
        files = request.files.getlist("files")

        for file in files:
            if file and file.filename != "":
                filename = file.filename
                path = os.path.join("static/uploads", filename)
                file.save(path)

                file_type = "file"
                if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                    file_type = "image"
                elif filename.lower().endswith((".mp4", ".mov")):
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
# RUN
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)