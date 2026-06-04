# ESP32-CAM Gallery Frontend

A standalone vanilla HTML/CSS/JS single-page application for the ESP32-CAM visualization backend.

## Features

- 📷 Image gallery with hover effects and lazy loading
- 📹 ESP32 live stream preview (when configured)
- 📊 Real-time statistics panel
- 🗑️ Delete images with confirmation
- 📸 Remote trigger capture
- 🔔 Toast notifications
- 🔄 Auto-refresh every 10 seconds
- 📱 Responsive design (mobile-friendly)
- 🌙 Dark theme matching the backend aesthetic

## Prerequisites

- Backend server running on `localhost:5000` (or configure `API_BASE_URL` in `js/app.js`)
- Modern web browser with JavaScript enabled
- CORS enabled on the backend

## Quick Start

### Option 1: Python HTTP Server (Recommended)

```bash
# Navigate to frontend directory
cd frontend

# Python 3
python -m http.server 8080

# Python 2
python -m SimpleHTTPServer 8080
```

Then open: http://localhost:8080

### Option 2: Node.js HTTP Server

```bash
# Install serve globally (if not already installed)
npm install -g serve

# Navigate to frontend directory
cd frontend

# Start server
serve -p 8080
```

Then open: http://localhost:8080

### Option 3: Live Server (VS Code Extension)

1. Install the "Live Server" extension in VS Code
2. Right-click on `index.html`
3. Select "Open with Live Server"

### Option 4: Open Directly in Browser

Some browsers may block CORS requests when opening files directly. If you encounter CORS errors, use one of the server options above.

## Configuration

Edit `js/app.js` to change the backend URL:

```javascript
// Change this to match your backend server
const API_BASE_URL = 'http://localhost:5000';
const REFRESH_INTERVAL = 10000; // 10 seconds
```

## API Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/images` | GET | Fetch image list |
| `/api/stats` | GET | Fetch system statistics |
| `/api/image/<filename>` | DELETE | Delete an image |
| `/trigger` | GET | Trigger ESP32 capture |
| `/image/<filename>` | GET | Get image file |
| `/latest` | GET | Get latest image |

## File Structure

```
frontend/
├── index.html      # Main HTML page
├── css/
│   └── style.css   # Dark theme styling
├── js/
│   └── app.js      # Application logic
└── README.md       # This file
```

## Browser Support

- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

## Troubleshooting

### CORS Errors

If you see CORS errors in the browser console:

1. Ensure the backend has CORS enabled
2. Use a local HTTP server (not file:// protocol)
3. Check that `API_BASE_URL` matches the backend address

### Images Not Loading

1. Verify the backend is running
2. Check the browser console for errors
3. Ensure the `processed` folder has images

### ESP32 Stream Not Showing

1. Verify ESP32 is configured in the backend (`ESP32_URL` environment variable)
2. Check that the ESP32 is accessible from your network
3. The stream URL is derived by replacing `/capture` with `/stream`

## Development

This is a pure vanilla JS application with no build step required. Simply edit the files and refresh the browser.

### Adding New Features

1. **New UI elements**: Add HTML to `index.html`, style in `css/style.css`
2. **New API calls**: Add functions to `js/app.js`
3. **New endpoints**: Update the backend and add corresponding frontend code

## License

Same as the parent project.
