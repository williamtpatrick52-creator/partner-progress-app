from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "change_this_to_a_secret_key"

DATABASE = "progress.db"
UPLOAD_FOLDER = "static/uploads"
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


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn, table, column):
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(col["name"] == column for col in columns)


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


def init_db():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT DEFAULT '📌'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            image TEXT,
            attachment TEXT,
            attachment_type TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    if not column_exists(conn, "projects", "icon"):
        conn.execute("ALTER TABLE projects ADD COLUMN icon TEXT DEFAULT '📌'")

    if not column_exists(conn, "updates", "image"):
        conn.execute("ALTER TABLE updates ADD COLUMN image TEXT")

    if not column_exists(conn, "updates", "attachment"):
        conn.execute("ALTER TABLE updates ADD COLUMN attachment TEXT")

    if not column_exists(conn, "updates", "attachment_type"):
        conn.execute("ALTER TABLE updates ADD COLUMN attachment_type TEXT")

    existing = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    if existing == 0:
        starter_projects = [
            ("2D Game", "Godot game progress, player movement, art, levels, and mechanics.", "🎮"),
            ("Business", "Business planning, calls, leads, and partner updates.", "💼"),
            ("Website", "Website, branding, content, and launch progress.", "🌐"),
        ]

        conn.executemany(
            "INSERT INTO projects (name, description, icon) VALUES (?, ?, ?)",
            starter_projects
        )

    conn.commit()
    conn.close()


@app.before_request
def setup():
    init_db()


def login_required():
    return "username" in session


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


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    selected_project_id = request.args.get("project_id", type=int)

    conn = get_db()
    projects = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()

    selected_project = None

    if selected_project_id:
        selected_project = conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (selected_project_id,)
        ).fetchone()

        latest_updates = conn.execute("""
            SELECT updates.*, projects.name AS project_name, projects.icon AS project_icon
            FROM updates
            JOIN projects ON updates.project_id = projects.id
            WHERE projects.id = ?
            ORDER BY updates.id DESC
            LIMIT 30
        """, (selected_project_id,)).fetchall()
    else:
        latest_updates = conn.execute("""
            SELECT updates.*, projects.name AS project_name, projects.icon AS project_icon
            FROM updates
            JOIN projects ON updates.project_id = projects.id
            ORDER BY updates.id DESC
            LIMIT 30
        """).fetchall()

    tasks = conn.execute("""
        SELECT * FROM tasks
        ORDER BY
            CASE status
                WHEN 'Needs Attention' THEN 1
                WHEN 'Pending' THEN 2
                WHEN 'Possible' THEN 3
                WHEN 'Done' THEN 4
                ELSE 5
            END,
            id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        projects=projects,
        latest_updates=latest_updates,
        tasks=tasks,
        username=session["username"],
        selected_project=selected_project,
        selected_project_id=selected_project_id
    )


@app.route("/set-task-status/<int:task_id>/<status>", methods=["POST"])
def set_task_status(task_id, status):
    if not login_required():
        return redirect(url_for("login"))

    allowed_statuses = ["Needs Attention", "Pending", "Possible", "Done"]

    if status not in allowed_statuses:
        return redirect(url_for("dashboard"))

    conn = get_db()
    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/project/<int:project_id>")
def project(project_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()

    updates = conn.execute("""
        SELECT * FROM updates
        WHERE project_id = ?
        ORDER BY id DESC
    """, (project_id,)).fetchall()

    conn.close()

    if project is None:
        return redirect(url_for("dashboard"))

    return render_template("project.html", project=project, updates=updates)


@app.route("/add-update", methods=["GET", "POST"])
def add_update():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    projects = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()

    if request.method == "POST":
        project_id = request.form["project_id"]
        status = request.form["status"]
        note = request.form["note"]
        author = session["username"]
        created_at = datetime.now().strftime("%Y-%m-%d %I:%M %p")

        uploaded_file = request.files.get("attachment")
        attachment = save_uploaded_file(uploaded_file)
        attachment_type = get_file_type(attachment) if attachment else None

        conn.execute("""
            INSERT INTO updates (
                project_id, author, status, note, created_at,
                image, attachment, attachment_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, author, status, note, created_at,
            attachment if attachment_type == "image" else None,
            attachment, attachment_type
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard", project_id=project_id))

    conn.close()
    return render_template("add_update.html", projects=projects)


@app.route("/edit-update/<int:update_id>", methods=["GET", "POST"])
def edit_update(update_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    update = conn.execute(
        "SELECT * FROM updates WHERE id = ?",
        (update_id,)
    ).fetchone()

    projects = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()

    if update is None:
        conn.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        project_id = request.form["project_id"]
        status = request.form["status"]
        note = request.form["note"]

        uploaded_file = request.files.get("attachment")
        attachment = save_uploaded_file(uploaded_file)
        attachment_type = get_file_type(attachment) if attachment else None

        if attachment:
            conn.execute("""
                UPDATE updates
                SET project_id = ?, status = ?, note = ?,
                    image = ?, attachment = ?, attachment_type = ?
                WHERE id = ?
            """, (
                project_id, status, note,
                attachment if attachment_type == "image" else None,
                attachment, attachment_type, update_id
            ))
        else:
            conn.execute("""
                UPDATE updates
                SET project_id = ?, status = ?, note = ?
                WHERE id = ?
            """, (project_id, status, note, update_id))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard", project_id=project_id))

    conn.close()
    return render_template("edit_update.html", update=update, projects=projects)


@app.route("/delete-update/<int:update_id>", methods=["POST"])
def delete_update(update_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    update = conn.execute("SELECT * FROM updates WHERE id = ?", (update_id,)).fetchone()
    project_id = update["project_id"] if update else None

    conn.execute("DELETE FROM updates WHERE id = ?", (update_id,))
    conn.commit()
    conn.close()

    if project_id:
        return redirect(url_for("dashboard", project_id=project_id))

    return redirect(url_for("dashboard"))


@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        icon = request.form["icon"]

        conn = get_db()
        conn.execute("""
            INSERT INTO projects (name, description, icon)
            VALUES (?, ?, ?)
        """, (name, description, icon))
        conn.commit()

        new_project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.close()

        return redirect(url_for("dashboard", project_id=new_project_id))

    return render_template("add_project.html")


@app.route("/edit-project/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()

    if project is None:
        conn.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        icon = request.form["icon"]

        conn.execute("""
            UPDATE projects
            SET name = ?, description = ?, icon = ?
            WHERE id = ?
        """, (name, description, icon, project_id))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard", project_id=project_id))

    conn.close()
    return render_template("edit_project.html", project=project)


@app.route("/delete-project/<int:project_id>", methods=["POST"])
def delete_project(project_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("DELETE FROM updates WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/add-task", methods=["POST"])
def add_task():
    if not login_required():
        return redirect(url_for("login"))

    text = request.form["text"]
    status = request.form["status"]
    created_at = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    conn = get_db()
    conn.execute("""
        INSERT INTO tasks (text, status, created_at)
        VALUES (?, ?, ?)
    """, (text, status, created_at))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if task is None:
        conn.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        text = request.form["text"]
        status = request.form["status"]

        conn.execute("""
            UPDATE tasks
            SET text = ?, status = ?
            WHERE id = ?
        """, (text, status, task_id))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit_task.html", task=task)


@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)