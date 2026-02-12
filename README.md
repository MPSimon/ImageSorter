# ImageSorter
This app loads a directory of images and lets you label each image by clicking a quadrant:

- Top-left: `good`
- Top-right: `regenerate`
- Bottom-left: `upscale`
- Bottom-right: `bad`

Each click immediately moves the file into the corresponding folder inside the active project.

## Project-Centric Storage

All data is now project-scoped:

- `{IMAGESORTER_DATA_ROOT}/projects/{project}/unlabeled`
- `{IMAGESORTER_DATA_ROOT}/projects/{project}/good`
- `{IMAGESORTER_DATA_ROOT}/projects/{project}/regenerate`
- `{IMAGESORTER_DATA_ROOT}/projects/{project}/upscale`
- `{IMAGESORTER_DATA_ROOT}/projects/{project}/bad`

On startup, legacy global folders (`input/good/regenerate/upscale/bad`) are migrated once into:

- `projects/2026-02-12/*`

## Getting Started

### Docker (runtime)

1. Set environment variables (example):
   - `IMAGESORTER_SECRET_KEY` (required for login sessions; set a long random string)
   - `IMAGESORTER_PASSWORD` (required to protect the UI; single shared password)
   - `IMAGESORTER_UPLOAD_TOKEN` (optional; enables token-based uploads to `POST /api/upload`)
   - `IMAGESORTER_MAX_UPLOAD_MB` (optional; defaults to `20`)

   Copy `.env.example` to `.env` and fill it in.

2. Run:
   ```bash
   docker compose up -d --build
   ```

3. The container uses `/data` as its runtime data root.
   - By default, `docker-compose.yml` mounts `./storage` to `/data`.
   - Project data is created under `/data/projects`.

4. Open:
   - `http://localhost:5050/`
   - On a VPS: run behind nginx (recommended) so the app is not exposed on `:5050` publicly.

## Nginx (VPS)

- Docker is configured to bind only to `127.0.0.1:5050` on the server.
- Use nginx to proxy a domain to the container.
- For this project, default server name is `images.bitreq.nl`: `deploy/nginx/imagesorter.conf`
- For repeatable multi-project deploys, use the env template:
  ```bash
  IMAGESORTER_SERVER_NAME=images.bitreq.nl \
  envsubst < deploy/nginx/imagesorter.conf.template | sudo tee /etc/nginx/sites-available/imagesorter
  ```
  Then symlink it into `sites-enabled` and run `sudo nginx -t && sudo systemctl reload nginx`.

## API

- `GET /api/projects` (session required if password is set)
  - Returns `{ "projects": [...], "active_project": "..." }`

- `POST /api/projects` (session required)
  - JSON: `{ "name": "project-name" }`
  - Creates project and sets it active for current session

- `POST /api/projects/select` (session required)
  - JSON: `{ "project": "project-name" }`
  - Sets active project for current session

- `GET /images`
  - Query: `count`, `folder=unlabeled|good|regenerate|upscale|bad` (`input` accepted as alias), optional `project`

- `GET /counts`
  - Query: optional `project`

- `POST /api/label` (session required)
  - JSON: `{ "filename": "...", "label": "good|regenerate|upscale|bad|unlabeled", "source": "unlabeled|good|regenerate|upscale|bad", "project": "optional" }`
  - Backward-compatible alias: `input` is accepted for `label` and `source`

- `POST /api/process` (session required)
  - JSON: `{ "folder": "good|regenerate|upscale|bad", "project": "optional" }`
  - Placeholder endpoint for future automation

- `POST /api/upload`
  - If `IMAGESORTER_PASSWORD` is set: allowed for logged-in users; optional token support.
  - If `IMAGESORTER_PASSWORD` is not set: allowed for local/dev; optionally enforce with token.
  - Header (optional): `X-Upload-Token: <token>`
  - Multipart: `file=@image.jpg`, `project=<optional>`
  - Upload target: active project's `unlabeled` folder
  - Size limit: controlled by `IMAGESORTER_MAX_UPLOAD_MB` (default `20`)

## Usage

1. Use the sidebar project selector to switch projects.
2. Create a project from the sidebar (`project-name`, lowercase/digits/`-`/`_`).
3. Click "Reload Images" to refresh current project/folder view.
4. `grid_columns` and `image_count` are browser-local preferences (`localStorage`).
5. Click a quadrant on an image to label it (file moves inside active project).
6. Use top tabs to browse `Unlabeled`, `Good`, `Regen`, `Upscale`, `Bad` for active project.
7. In labeled folders, click "Unlabel" to send an image back to `Unlabeled`.
8. Drag and drop images onto the grid while on `Unlabeled`.

## Development Notes

- Runtime path root is `IMAGESORTER_DATA_ROOT` (`/data` in container, `storage` in local Python runs).
- Project names are validated to prevent traversal and enforce filesystem-safe names.
- Strict isolation: all reads/writes are scoped to one active project.

## Linting

1. Install dev tools:
   ```bash
   pip install -r requirements-dev.txt
   ```
2. Run:
   ```bash
   ruff check .
   ```
