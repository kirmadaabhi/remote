# Remote Web Control - Vercel Deployment

A high-performance remote desktop application optimized for Vercel serverless deployment.

## ⚠️ Important Limitations for Vercel Deployment

**This application has significant limitations when deployed on Vercel:**

1. **No Screen Capture**: Vercel serverless functions cannot access the host system's screen or input devices
2. **No Mouse/Keyboard Control**: Serverless functions cannot control the local machine
3. **WebSocket Limitations**: Vercel has restrictions on long-running WebSocket connections

## 🚀 Local Development (Recommended)

For actual remote desktop functionality, run locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (this will work for remote access)
python main.py

# Access at http://localhost:8000
# Login: user / userpass
```

## 🔧 Vercel Deployment (Limited Functionality)

If you still want to deploy to Vercel for testing/demo purposes:

### 1. Install Vercel CLI
```bash
npm i -g vercel
```

### 2. Configure Environment Variables
Create a `.env` file or set in Vercel dashboard:
```env
RWC_SECRET=your-secret-key-here
RWC_USER=your-username
RWC_PASS=your-password
RWC_FPS=15
RWC_QUALITY=80
RWC_SCALE=0.75
```

### 3. Deploy
```bash
vercel
```

### 4. Access Your App
Your app will be available at: `https://your-project.vercel.app`

## 📁 Project Structure

```
├── main.py              # Local development server
├── api/
│   └── index.py         # Vercel serverless function
├── static/
│   ├── login.html       # Login page
│   └── viewer.html      # Viewer interface
├── requirements.txt     # Python dependencies
├── vercel.json         # Vercel configuration
└── README.md           # This file
```

## 🎯 Performance Optimizations

### Local Deployment
- **FPS**: 24 FPS (configurable via `RWC_FPS`)
- **Quality**: 90% JPEG (configurable via `RWC_QUALITY`)
- **Duplicate Frame Skipping**: Enabled by default
- **TurboJPEG**: Fast encoding when available

### Vercel Deployment
- **FPS**: 15 FPS (lower for serverless constraints)
- **Quality**: 80% JPEG (optimized for bandwidth)
- **Scale**: 0.75 (reduced resolution for performance)

## 🔒 Security

- **Authentication**: Session-based login system
- **HTTPS**: Automatic on Vercel
- **Input Validation**: All user inputs are validated
- **Session Management**: Secure session handling

## 🛠️ Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RWC_SECRET` | `vercel-secret-change-me` | Session secret key |
| `RWC_USER` | `user` | Login username |
| `RWC_PASS` | `userpass` | Login password |
| `RWC_FPS` | `15` (Vercel) / `24` (Local) | Frame rate |
| `RWC_QUALITY` | `80` (Vercel) / `90` (Local) | JPEG quality (1-100) |
| `RWC_SCALE` | `0.75` (Vercel) / `1.0` (Local) | Screen scaling factor |
| `RWC_SKIP_DUP` | `1` | Skip duplicate frames (0/1) |
| `RWC_CODEC` | `jpeg` | Encoding format (jpeg/webp/png) |

## 🚨 Troubleshooting

### Vercel Deployment Issues
1. **Function Timeout**: Increase `maxDuration` in `vercel.json`
2. **Memory Issues**: Reduce `RWC_FPS` and `RWC_QUALITY`
3. **WebSocket Errors**: Vercel has WebSocket limitations

### Local Development Issues
1. **Screen Capture Fails**: Ensure you have proper permissions
2. **Input Not Working**: Check if `pynput` is properly installed
3. **Performance Issues**: Install `turbojpeg` for faster encoding

## 📝 License

This project is for educational and personal use only.

## 🤝 Contributing

Feel free to submit issues and enhancement requests!
