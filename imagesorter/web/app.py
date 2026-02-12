import os
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    send_from_directory,
    session,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from imagesorter.application.services import ImageSorterService
from imagesorter.infrastructure.image_store import ImageStore
from imagesorter.infrastructure.project_store import LABELS, SOURCE_FOLDER, ProjectStore
from imagesorter.web.auth import check_password, login_required, upload_token_ok

DEFAULT_IMAGE_COUNT = 20
DEFAULT_GRID_COLUMNS = 5


def _default_data_root() -> Path:
    container_root = Path("/data")
    if container_root.exists():
        return container_root
    return Path("storage")


def _data_root() -> Path:
    raw = os.getenv("IMAGESORTER_DATA_ROOT")
    if raw:
        return Path(raw)
    return _default_data_root()


def _secret_key() -> str:
    v = os.getenv("IMAGESORTER_SECRET_KEY")
    if v:
        return v
    return "dev-secret-change-me"


def _max_upload_mb() -> int:
    raw = os.getenv("IMAGESORTER_MAX_UPLOAD_MB", "20")
    try:
        mb = int(raw)
    except ValueError:
        mb = 12
    return max(1, mb)


def _safe_int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _canonical_folder(raw: str | None) -> str:
    folder = str(raw or SOURCE_FOLDER)
    if folder == "input":
        return SOURCE_FOLDER
    return folder


def _build_service(store: ImageStore) -> ImageSorterService:
    return ImageSorterService(
        store=store,
        labels=list(LABELS),
        default_image_count=DEFAULT_IMAGE_COUNT,
        default_grid_columns=DEFAULT_GRID_COLUMNS,
    )


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.secret_key = _secret_key()
    app.config["MAX_CONTENT_LENGTH"] = _max_upload_mb() * 1024 * 1024
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    data_root = _data_root()
    project_store = ProjectStore(data_root=data_root)
    project_store.migrate_legacy_layout_once()

    def service_for_project(project_name: str) -> ImageSorterService:
        project_paths = project_store.paths_for_project(project_name)
        image_store = ImageStore(source_dir=project_paths.source_dir, label_dirs=project_paths.label_dirs)
        return _build_service(store=image_store)

    def resolve_project(explicit: Optional[str] = None) -> str:
        if explicit:
            project = project_store.normalize_project_name(explicit)
            if not project_store.project_exists(project):
                raise FileNotFoundError(project)
            session["active_project"] = project
            return project

        active = session.get("active_project")
        if isinstance(active, str):
            try:
                normalized = project_store.normalize_project_name(active)
            except ValueError:
                normalized = ""
            if normalized and project_store.project_exists(normalized):
                project_store.ensure_project_dirs(normalized)
                session["active_project"] = normalized
                return normalized

        default_project = project_store.ensure_default_project()
        session["active_project"] = default_project
        return default_project

    @app.get("/login")
    def login():
        if session.get("authed") is True:
            return redirect("/")
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        pw = request.form.get("password", "")
        if not check_password(pw):
            return render_template("login.html", error="Invalid password"), 401
        session["authed"] = True
        nxt = request.args.get("next") or "/"
        return redirect(nxt)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/")
    @login_required
    def index():
        with open("index.html", "r", encoding="utf-8") as f:
            return render_template_string(f.read())

    @app.get("/api/projects")
    @login_required
    def api_projects():
        projects = project_store.list_projects()
        if not projects:
            projects = [project_store.ensure_default_project()]

        active_raw = session.get("active_project")
        active = active_raw if isinstance(active_raw, str) else ""
        if not active or active not in projects:
            active = project_store.ensure_default_project()
            session["active_project"] = active
        return jsonify({"projects": projects, "active_project": active})

    @app.post("/api/projects")
    @login_required
    def api_projects_create():
        data = request.get_json(force=True, silent=True) or {}
        raw_name = str(data.get("name") or "")
        if not raw_name:
            return jsonify({"error": "name is required"}), 400
        try:
            project_name = project_store.create_project(raw_name)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileExistsError:
            return jsonify({"error": "project already exists"}), 409

        session["active_project"] = project_name
        return jsonify({"success": True, "project": project_name}), 201

    @app.post("/api/projects/select")
    @login_required
    def api_projects_select():
        data = request.get_json(force=True, silent=True) or {}
        raw_project = str(data.get("project") or "")
        if not raw_project:
            return jsonify({"error": "project is required"}), 400

        try:
            project = resolve_project(explicit=raw_project)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404

        return jsonify({"success": True, "active_project": project})

    @app.get("/images")
    @login_required
    def images():
        count = _safe_int(request.args.get("count"), DEFAULT_IMAGE_COUNT)
        folder = _canonical_folder(request.args.get("folder"))
        explicit_project = request.args.get("project")

        try:
            project = resolve_project(explicit=explicit_project)
            service = service_for_project(project)
            images, total = service.list_images(count=count, folder=folder)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404
        return jsonify({"images": images, "total_available": total, "project": project})

    @app.get("/counts")
    @login_required
    def counts():
        explicit_project = request.args.get("project")
        try:
            project = resolve_project(explicit=explicit_project)
            service = service_for_project(project)
            payload = service.counts()
            payload["project"] = project
            return jsonify(payload)
        except ValueError as e:
            return jsonify({"error": str(e), SOURCE_FOLDER: 0}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found", SOURCE_FOLDER: 0}), 404
        except Exception as e:
            return jsonify({"error": str(e), SOURCE_FOLDER: 0}), 500

    @app.get("/image/<path:filename>")
    @login_required
    def image(filename: str):
        folder = _canonical_folder(request.args.get("folder"))
        explicit_project = request.args.get("project")
        try:
            project = resolve_project(explicit=explicit_project)
            project_paths = project_store.paths_for_project(project)
            if folder == SOURCE_FOLDER:
                directory = project_paths.source_dir
            else:
                directory = project_paths.label_dirs.get(folder) or project_paths.source_dir
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404

        return send_from_directory(directory, filename)

    @app.post("/api/label")
    @login_required
    def api_label():
        data = request.get_json(force=True, silent=True) or {}
        filename = str(data.get("filename") or "")
        raw_label = data.get("label")
        if raw_label is None or str(raw_label) == "":
            return jsonify({"error": "filename and label required"}), 400
        label = _canonical_folder(raw_label)
        source = _canonical_folder(data.get("source"))
        explicit_project = data.get("project")

        if not filename:
            return jsonify({"error": "filename and label required"}), 400
        try:
            project = resolve_project(explicit=explicit_project)
            service = service_for_project(project)
            service.label_image(filename=filename, label=label, source_folder=source)
            return jsonify({"success": True, "project": project})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/process")
    @login_required
    def api_process():
        data = request.get_json(force=True, silent=True) or {}
        folder = _canonical_folder(data.get("folder"))
        explicit_project = data.get("project")

        if folder not in LABELS:
            return jsonify({"error": "folder must be one of: good, regenerate, upscale, bad"}), 400

        try:
            project = resolve_project(explicit=explicit_project)
            service = service_for_project(project)
            _images, total = service.list_images(count=0, folder=folder)
            return jsonify({"success": True, "folder": folder, "total_available": total, "project": project})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404

    @app.get("/api/config")
    @login_required
    def api_config():
        explicit_project = request.args.get("project")
        try:
            project = resolve_project(explicit=explicit_project)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404

        service = service_for_project(project)
        payload = service.public_config()
        payload.update({"source_folder": SOURCE_FOLDER, "active_project": project})
        return jsonify(payload)

    @app.post("/api/upload")
    def api_upload():
        pw_enabled = bool(os.getenv("IMAGESORTER_PASSWORD", ""))
        if pw_enabled and session.get("authed") is True:
            pass
        else:
            token = request.headers.get("X-Upload-Token", "")
            if pw_enabled and not upload_token_ok(token):
                return jsonify({"error": "unauthorized"}), 401
            if (not pw_enabled) and token and (not upload_token_ok(token)):
                return jsonify({"error": "unauthorized"}), 401

        if "file" not in request.files:
            return jsonify({"error": "multipart form field 'file' required"}), 400

        explicit_project = request.form.get("project") or request.args.get("project")
        try:
            project = resolve_project(explicit=explicit_project)
            service = service_for_project(project)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError:
            return jsonify({"error": "project not found"}), 404

        f = request.files["file"]
        name = f.filename or "upload"
        data = f.read()

        try:
            out = service.upload(filename=name, data=data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"success": True, "filename": out, "project": project})

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        max_mb = _max_upload_mb()
        return jsonify({"error": f"file too large (max {max_mb} MB)"}), 413

    return app
