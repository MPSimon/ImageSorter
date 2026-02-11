import os
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
from imagesorter.domain.settings import Settings
from imagesorter.infrastructure.image_store import ImageStore
from imagesorter.infrastructure.settings_store import SettingsStore
from imagesorter.web.auth import check_password, login_required, upload_token_ok


def _settings_path() -> Path:
    return Path(os.getenv("IMAGESORTER_SETTINGS", "settings.json"))


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


def _build_service(store: SettingsStore) -> ImageSorterService:
    settings = store.load()
    label_dirs: Dict[str, Path] = {k: Path(v) for k, v in settings.label_dirs.items()}
    archive_dir = Path(settings.archive_dir) if settings.archive_dir else None
    image_store = ImageStore(input_dir=Path(settings.input_dir), label_dirs=label_dirs, archive_dir=archive_dir)
    return ImageSorterService(store=image_store, settings=settings)


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.secret_key = _secret_key()
    app.config["MAX_CONTENT_LENGTH"] = _max_upload_mb() * 1024 * 1024
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    store = SettingsStore(_settings_path())
    def svc() -> ImageSorterService:
        return _build_service(store=store)

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

    @app.get("/settings")
    @login_required
    def settings_get():
        return jsonify(svc().public_config())

    @app.post("/settings")
    @login_required
    def settings_post():
        current = store.load()
        incoming = request.get_json(force=True, silent=True) or {}
        merged = dict(current.to_public_dict())
        merged.update(incoming)
        new_settings = Settings.from_dict(merged)
        store.save(new_settings)
        try:
            _build_service(store=store)._store.ensure_dirs()
        except Exception:
            pass
        return jsonify({"success": True})

    @app.get("/images")
    @login_required
    def images():
        count = int(request.args.get("count") or svc().public_config().get("image_count") or 20)
        folder = str(request.args.get("folder") or "input")
        images, total = svc().list_images(count=count, folder=folder)
        return jsonify({"images": images, "total_available": total})

    @app.get("/counts")
    @login_required
    def counts():
        try:
            return jsonify(svc().counts())
        except Exception as e:
            return jsonify({"error": str(e), "input": 0}), 500

    @app.get("/image/<path:filename>")
    @login_required
    def image(filename: str):
        settings = store.load()
        folder = str(request.args.get("folder") or "input")
        if folder == "input":
            directory = settings.input_dir
        else:
            directory = settings.label_dirs.get(folder) or settings.input_dir
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
            svc().label_image(filename=filename, label=label, source_folder=source)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/process")
    @login_required
    def api_process():
        data = request.get_json(force=True, silent=True) or {}
        folder = str(data.get("folder") or "")
        if folder not in ("good", "regenerate", "upscale", "bad"):
            return jsonify({"error": "folder must be one of: good, regenerate, upscale, bad"}), 400

        if folder == "bad":
            # Archive (soft delete) all images in the bad folder
            try:
                deleted = svc().archive_images(folder=folder)
                return jsonify({"success": True, "deleted": deleted})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        # Placeholder for future background processing integration.
        _images, total = svc().list_images(count=0, folder=folder)
        return jsonify({"success": True, "folder": folder, "total_available": total})

    @app.get("/api/config")
    @login_required
    def api_config():
        return jsonify(svc().public_config())

    @app.post("/api/upload")
    def api_upload():
        # Upload is allowed when:
        # - app is password-protected AND caller has a logged-in session, OR
        # - caller provides a valid upload token, OR
        # - password is disabled (dev/local use)
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
        out = svc().upload(filename=name, data=data)
        return jsonify({"success": True, "filename": out})

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        max_mb = _max_upload_mb()
        return jsonify({"error": f"file too large (max {max_mb} MB)"}), 413

    return app
