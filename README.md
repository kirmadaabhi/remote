# Remote Web Control - Web Interface Version

This is a Vercel-compatible version of the Remote Web Control application.

## Changes Made for Vercel Deployment

The original application used system-dependent libraries that don't work in serverless environments:

- **Removed**: `mss` (screen capture library)
- **Removed**: `pynput` (mouse/keyboard control library)  
- **Removed**: `Pillow`, `turbojpeg`, `numpy` (image processing libraries)

## What This Version Provides

- ✅ Web interface with login system
- ✅ Session management
- ✅ Responsive design
- ❌ Screen sharing (not possible in serverless)
- ❌ Remote control (not possible in serverless)

## Deployment

This version is designed to deploy successfully on Vercel. The application will show an informational page explaining that full functionality requires a desktop environment.

## For Full Functionality

To use the complete remote control features, run the desktop version locally:

```bash
cd ..  # Go to parent directory
pip install -r requirements.txt
python main.py
```

Then access at `http://127.0.0.1:8000`
