# ImageSorter
This app loads a directory of images and lets you label each image by clicking a quadrant:

- Top-left: `good`
- Top-right: `regenerate`
- Bottom-left: `upscale`
- Bottom-right: `bad`

Each click immediately moves the file into the corresponding folder.

<img width="1900" alt="Screenshot 2025-04-25 210923" src="https://github.com/user-attachments/assets/bf6d44af-49e0-4e61-99cb-698cd92e032b" />

## Getting Started

### Docker (Only runtime)

1. Set environment variables (example):
   - `IMAGESORTER_SECRET_KEY` (required for login sessions; set a long random string)
   - `IMAGESORTER_PASSWORD` (required to protect the UI; single shared password)
   - `IMAGESORTER_UPLOAD_TOKEN` (optional; enables token-based uploads to `POST /api/upload`)
   - `IMAGESORTER_MAX_UPLOAD_MB` (optional; defaults to `20`)

   Copy `.env.example` to `.env` and fill it in.

2. Run:
   ```
   docker compose up -d --build
   ```

3. The container reads `settings.json` (mounted as `/app/settings.json`) and uses `/data/...` paths inside the container.
   - Default host folders are project-local: `./storage/input`, `./storage/good`, `./storage/regenerate`, `./storage/upscale`, `./storage/bad`.
   - You can override host paths with `IMAGESORTER_*_DIR` environment variables.

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

- `POST /api/label` (session required if `IMAGESORTER_PASSWORD` is set)
  - JSON: `{ "filename": "...", "label": "good|regenerate|upscale|bad|input", "source": "input|good|regenerate|upscale|bad" }`

- `POST /api/process` (session required)
  - JSON: `{ "folder": "good|regenerate|upscale" }`
  - Note: currently a placeholder for future automation.

- `POST /api/upload`
  - If `IMAGESORTER_PASSWORD` is set: allowed for logged-in users; optional token support.
  - If `IMAGESORTER_PASSWORD` is not set: allowed for local/dev; optionally enforce with token.
  - Header (optional): `X-Upload-Token: <token>`
  - Multipart: `file=@image.jpg` (uploads into Unlabeled)
  - Size limit: controlled by `IMAGESORTER_MAX_UPLOAD_MB` (default `20`)

## Usage
1. Click "Reload Images" to refresh the current folder view
2. `grid_columns` and `image_count` auto-save when changed
3. Click a quadrant on an image to label it (the file is moved immediately)
4. Use the top tabs to browse labeled folders and re-label images
5. In labeled folders, click "Unlabel" to send an image back to Unlabeled
6. In Good/Regen/Upscale, click "Process Images In This Folder" to trigger future automation
7. Drag and drop images onto the grid while on Unlabeled to upload them

## Development Notes

- `settings.json` is the single source of truth for runtime settings.
- Host folders are mounted to `/data/...` via `docker-compose.yml`.
- Default host-side storage is `./storage/...` (inside the project directory), suitable for local and VPS Docker deployments.
- Sidebar directory path fields and click-zone legend were intentionally removed to keep the UI focused on rating.

## Linting

1. Install dev tools:
   ```
   pip install -r requirements-dev.txt
   ```
2. Run:
   ```
   ruff check .
   ```
