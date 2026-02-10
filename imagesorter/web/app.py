import os
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, redirect, render_template, render_template_string, request, send_from_directory, session

from imagesorter.application.services import AppState, ImageSorterService
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


def _build_service(store: SettingsStore, state: AppState) -> ImageSorterService:
    settings = store.load()
    label_dirs: Dict[str, Path] = {k: Path(v) for k, v in settings.label_dirs.items()}
    image_store = ImageStore(input_dir=Path(settings.input_dir), label_dirs=label_dirs)
    return ImageSorterService(store=image_store, settings=settings, state=state)


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.secret_key = _secret_key()

    store = SettingsStore(_settings_path())
    state = AppState(processed=set())

    def svc() -> ImageSorterService:
        return _build_service(store=store, state=state)

    @app.get("/login")
    def login():
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
            _build_service(store=store, state=state)._store.ensure_dirs()
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

    @app.post("/reset")
    @login_required
    def reset():
        svc().reset_processed()
        return jsonify({"success": True})

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
        if folder not in ("good", "regenerate", "upscale"):
            return jsonify({"error": "folder must be one of: good, regenerate, upscale"}), 400

        # Placeholder for future background processing integration.
        _images, total = svc().list_images(count=0, folder=folder)
        return jsonify({"success": True, "folder": folder, "total_available": total})

    @app.get("/api/config")
    @login_required
    def api_config():
        return jsonify(svc().public_config())

    @app.post("/api/upload")
    def api_upload():
        token = request.headers.get("X-Upload-Token", "")
        if not upload_token_ok(token):
            return jsonify({"error": "unauthorized"}), 401

        if "file" not in request.files:
            return jsonify({"error": "multipart form field 'file' required"}), 400

        f = request.files["file"]
        name = f.filename or "upload"
        data = f.read()
        out = svc().upload(filename=name, data=data)
        return jsonify({"success": True, "filename": out})

    return app
