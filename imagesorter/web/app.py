import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

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
from imagesorter.web.auth import check_password, login_required, upload_token_ok

LABELS = ("good", "regenerate", "upscale", "bad")
DEFAULT_IMAGE_COUNT = 20
DEFAULT_GRID_COLUMNS = 5


@dataclass(frozen=True)
class RuntimePaths:
    input_dir: Path
    label_dirs: Dict[str, Path]
    archive_dir: Path


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


def _runtime_paths() -> RuntimePaths:
    root = _data_root()
    return RuntimePaths(
        input_dir=root / "input",
        label_dirs={label: root / label for label in LABELS},
        archive_dir=root / "archive",
    )


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


def _build_service(paths: RuntimePaths) -> ImageSorterService:
    image_store = ImageStore(input_dir=paths.input_dir, label_dirs=paths.label_dirs, archive_dir=paths.archive_dir)
    return ImageSorterService(
        store=image_store,
        labels=list(LABELS),
        default_image_count=DEFAULT_IMAGE_COUNT,
        default_grid_columns=DEFAULT_GRID_COLUMNS,
    )


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.secret_key = _secret_key()
    app.config["MAX_CONTENT_LENGTH"] = _max_upload_mb() * 1024 * 1024
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    paths = _runtime_paths()
    service = _build_service(paths=paths)

    try:
        service._store.ensure_dirs()
    except Exception:
        pass

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

    @app.get("/images")
    @login_required
    def images():
        count = _safe_int(request.args.get("count"), DEFAULT_IMAGE_COUNT)
        folder = str(request.args.get("folder") or "input")
        images, total = service.list_images(count=count, folder=folder)
        return jsonify({"images": images, "total_available": total})

    @app.get("/counts")
    @login_required
    def counts():
        try:
            return jsonify(service.counts())
        except Exception as e:
            return jsonify({"error": str(e), "input": 0}), 500

    @app.get("/image/<path:filename>")
    @login_required
    def image(filename: str):
        folder = str(request.args.get("folder") or "input")
        if folder == "input":
            directory = paths.input_dir
        else:
            directory = paths.label_dirs.get(folder) or paths.input_dir
        return send_from_directory(directory, filename)

    @app.post("/api/label")
    @login_required
    def api_label():
        data = request.get_json(force=True, silent=True) or {}
        filename = str(data.get("filename") or "")
        label = str(data.get("label") or "")
        source = str(data.get("source") or "input")
        if not filename or not label:
            return jsonify({"error": "filename and label required"}), 400
        try:
            service.label_image(filename=filename, label=label, source_folder=source)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/process")
    @login_required
    def api_process():
        data = request.get_json(force=True, silent=True) or {}
        folder = str(data.get("folder") or "")
        if folder not in LABELS:
            return jsonify({"error": "folder must be one of: good, regenerate, upscale, bad"}), 400

        if folder == "bad":
            try:
                deleted = service.archive_images(folder=folder)
                return jsonify({"success": True, "deleted": deleted})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        _images, total = service.list_images(count=0, folder=folder)
        return jsonify({"success": True, "folder": folder, "total_available": total})

    @app.get("/api/config")
    @login_required
    def api_config():
        return jsonify(service.public_config())

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

        f = request.files["file"]
        name = f.filename or "upload"
        data = f.read()
        out = service.upload(filename=name, data=data)
        return jsonify({"success": True, "filename": out})

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        max_mb = _max_upload_mb()
        return jsonify({"error": f"file too large (max {max_mb} MB)"}), 413

    return app
