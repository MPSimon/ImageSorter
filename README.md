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
   - `IMAGESORTER_SECRET_KEY` (required for login sessions)
   - `IMAGESORTER_PASSWORD` (set to enable login; leave empty to disable)
   - `IMAGESORTER_UPLOAD_TOKEN` (token for `POST /api/upload`)

2. Run:
   ```
   docker compose up -d --build
   ```

3. The container reads `/Users/max/www/ImageSorter/settings.docker.json` (mounted as `/app/settings.json`) and uses `/data/...` paths inside the container.

## API

- `POST /api/label` (session required if `IMAGESORTER_PASSWORD` is set)
  - JSON: `{ "filename": "...", "label": "good|regenerate|upscale|bad" }`

- `POST /api/upload` (token required)
  - Header: `X-Upload-Token: <token>`
  - Multipart: `file=@image.jpg`

## Usage
1. Set your input and output directories in the sidebar (or edit `settings.json`)
2. Click "Save Settings" to persist your configuration
3. Click "Load Images" to display images from your input directory
4. Click a quadrant on an image to label it (the file is moved immediately)
5. Repeat until all images are sorted

## Development Notes

- `settings.json` is used for local development paths.
- `settings.docker.json` is the default config for Docker (uses `/data/...` mount points).
