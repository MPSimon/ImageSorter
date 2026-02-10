# ImageSorter
This app loads a directory of images and lets you label each image by clicking a quadrant:

- Top-left: `good`
- Top-right: `regenerate`
- Bottom-left: `upscale`
- Bottom-right: `bad`

Each click immediately moves the file into the corresponding folder.

<img width="1900" alt="Screenshot 2025-04-25 210923" src="https://github.com/user-attachments/assets/bf6d44af-49e0-4e61-99cb-698cd92e032b" />

## Getting Started

### Windows
1. Double-click the `start.bat` file
2. The script will:
   - Check if a virtual environment exists
   - Create one if needed and install requirements
   - Activate the environment and launch the application

### macOS and Linux
1. Make the script executable (first time only):
   ```
   chmod +x start.sh
   ```
2. Run the script:
   ```
   ./start.sh
   ```
3. The script will:
   - Check if a virtual environment exists
   - Create one if needed and install requirements
   - Activate the environment and launch the application

## Docker (Recommended for VPS)

1. Set environment variables (example):
   - `IMAGESORTER_SECRET_KEY` (required for login sessions; set a long random string)
   - `IMAGESORTER_PASSWORD` (required to protect the UI; single shared password)
   - `IMAGESORTER_UPLOAD_TOKEN` (optional; enables token-based uploads to `POST /api/upload`)

   Copy `.env.example` to `.env` and fill it in.

2. Run:
   ```
   docker compose up -d --build
   ```

3. The container reads `settings.docker.json` (mounted as `/app/settings.json`) and uses `/data/...` paths inside the container.

4. Open:
   - `http://localhost:5050/`
   - On a VPS: run behind nginx (recommended) so the app is not exposed on `:5050` publicly.

## Nginx (VPS)

- Docker is configured to bind only to `127.0.0.1:5050` on the server.
- Use nginx to proxy a domain to the container.
- Template: `deploy/nginx/imagesorter.conf`

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

## Usage
1. Set your input and output directories in the sidebar (or edit `settings.json`)
2. Click "Save Settings" to persist your configuration
3. Click "Load Images" to display images from your input directory
4. Click a quadrant on an image to label it (the file is moved immediately)
5. Use the top tabs to browse labeled folders and re-label images
6. In labeled folders, click "Unlabel" to send an image back to Unlabeled
7. In Good/Regen/Upscale, click "Process Images In This Folder" to trigger future automation
8. Drag and drop images onto the grid while on Unlabeled to upload them

## Development Notes

- `settings.json` is used for local development paths.
- `settings.docker.json` is the default config for Docker (uses `/data/...` mount points).
