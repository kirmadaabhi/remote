# main.py
# -----------------------------------------------------------------------------
# Remote Web Control — **HD text, crisp UI, fast** (localhost, browser client)
#
# WHAT’S NEW VS YOUR WORKING VERSION
# ----------------------------------
# 1) **HiDPI/Retina perfect rendering** in the browser (uses devicePixelRatio).
#    This alone fixes the “blurry text” you’re seeing in many cases.
# 2) **4:4:4 JPEG** (no chroma subsampling) and optional **WebP lossless**.
# 3) Optional **TurboJPEG** fast-path if installed (keeps text sharp at high FPS).
# 4) Tunables via env: FPS, QUALITY, CODEC, SUBSAMPLING, SCALE.
#
# QUICK START
#   pip install fastapi uvicorn mss Pillow
#   # optional speed-up:
#   pip install turbojpeg  # requires libjpeg-turbo on your system
#   python main.py
#   -> open http://127.0.0.1:8000  (login: user / userpass)
#
# TUNING (set as environment variables before running):
#   RWC_FPS=20            # default 12
#   RWC_QUALITY=90        # 1..100 (JPEG/WebP)
#   RWC_SUBSAMPLING=0     # 0=4:4:4 (sharp text), 1=4:2:2, 2=4:2:0
#   RWC_CODEC=jpeg        # jpeg | webp | png  (webp can be lossless below)
#   RWC_WEBP_LOSSLESS=1   # 1=lossless WebP (very crisp; heavier CPU)
#   RWC_SCALE=1.0         # 1.0 = native; e.g. 0.85 for perf on 4K
#
# SECURITY: Binds to 127.0.0.1 by default. Don’t expose to the internet without
# proper auth, TLS, firewall, consent prompts, etc.
# -----------------------------------------------------------------------------

# stdlib
import asyncio, io, json, os, time, contextlib, zlib
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

from PIL import Image
import mss

# ---- Optional TurboJPEG fast-path --------------------------------------------
HAVE_TURBOJPEG = False
try:
    from turbojpeg import TurboJPEG, TJPF_BGR, TJSAMP_444, TJSAMP_422, TJSAMP_420
    jpeg_encoder = TurboJPEG()
    HAVE_TURBOJPEG = True
except Exception:
    jpeg_encoder = None

try:
    import numpy as np
    HAVE_NUMPY = True
except Exception:
    np = None
    HAVE_NUMPY = False

# ---- Configuration ------------------------------------------------------------
APP_HOST       = os.environ.get("RWC_HOST", "127.0.0.1")
APP_PORT       = int(os.environ.get("RWC_PORT", "8000"))
SECRET_KEY     = os.environ.get("RWC_SECRET", "dev-secret-change-me")
LOGIN_USER     = os.environ.get("RWC_USER", "user")
LOGIN_PASS     = os.environ.get("RWC_PASS", "userpass")

# Faster default refresh; override with RWC_FPS env var
FPS            = int(os.environ.get("RWC_FPS", "24"))

# Optional: skip sending frames that are byte-identical to the previous one.
# Set RWC_SKIP_DUP=0 to disable.
SKIP_DUPLICATE = os.environ.get("RWC_SKIP_DUP", "1") == "1"

QUALITY        = int(os.environ.get("RWC_QUALITY", "90"))
SUBSAMPLING    = int(os.environ.get("RWC_SUBSAMPLING", "0"))     # 0=444 (best for text)
CODEC          = os.environ.get("RWC_CODEC", "jpeg").lower()     # jpeg|webp|png
WEBP_LOSSLESS  = os.environ.get("RWC_WEBP_LOSSLESS", "0") == "1"
SCALE          = float(os.environ.get("RWC_SCALE", "1.0"))

if SUBSAMPLING not in (0, 1, 2): SUBSAMPLING = 0
if CODEC not in ("jpeg", "webp", "png"): CODEC = "jpeg"

# ---- App ----------------------------------------------------------------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))

# ------------------------------ HTML (inline) ---------------------------------
LOGIN_HTML = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Remote Web Control - Login</title>
<style>
body{font-family:system-ui,Arial,sans-serif;background:#0b1220;color:#e6e8ee;
display:flex;min-height:100vh;align-items:center;justify-content:center}
.card{background:#121a2b;padding:24px;border-radius:16px;width:320px;
box-shadow:0 10px 40px rgba(0,0,0,.3)}
h1{font-size:18px;margin:0 0 12px}
label{display:block;margin:12px 0 6px;font-size:13px;color:#9fb0d6}
input{width:100%;padding:10px 12px;border-radius:10px;border:1px solid #2b395b;
background:#0e1627;color:#e6e8ee}
button{width:100%;padding:10px 12px;margin-top:16px;border:none;border-radius:10px;
background:#1d63ff;color:#fff;font-weight:600;cursor:pointer}
.err{color:#ff8585;margin-top:10px;min-height:1em}
.hint{margin-top:12px;font-size:12px;color:#9fb0d6}
</style></head><body><div class="card"><h1>Remote Web Control</h1>
<form id="loginForm"><label>Username</label>
<input id="user" value="user" autocomplete="username"/>
<label>Password</label>
<input id="pass" type="password" value="userpass" autocomplete="current-password"/>
<button type="submit">Sign in</button><div class="err" id="err"></div>
<div class="hint">Default creds are for local testing only.</div></form></div>
<script>
document.getElementById('loginForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const username=document.getElementById('user').value;
  const password=document.getElementById('pass').value;
  const res=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username,password})});
  if(res.ok){ location.href='/viewer'; } else {
    document.getElementById('err').textContent='Invalid credentials';
  }
});
</script></body></html>"""

VIEWER_HTML = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Remote Web Control - Viewer</title>
<style>
html,body{height:100%;margin:0;background:#0b1220;color:#e6e8ee;font-family:system-ui,Arial,sans-serif}
.topbar{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#0e1627;border-bottom:1px solid #2b395b}
.pill{padding:6px 10px;border-radius:999px;background:#121a2b;border:1px solid #2b395b;font-size:12px}
.btn{padding:8px 12px;border-radius:10px;background:#1d63ff;color:#fff;border:none;cursor:pointer;font-weight:600}
.btn.alt{background:#2b395b}
.content{height:calc(100% - 54px);display:flex}
#canvas{flex:1;display:block;background:#000;width:100%;height:100%}
.status{font-size:12px;color:#9fb0d6;margin-left:auto}
.ck{display:flex;align-items:center;gap:6px}
</style></head>
<body>
  <div class="topbar">
    <div class="pill">Local session (DPR-aware)</div>
    <label class="pill ck"><input type="checkbox" id="viewOnly" checked/> View only</label>
    <div class="pill">Codec: <span id="codecLabel">auto</span></div>
    <div class="pill">Quality: <span id="qLabel">auto</span></div>
    <button class="btn" onclick="logout()">Logout</button>
    <div class="status" id="status">Connecting...</div>
  </div>
  <div class="content"><canvas id="canvas" tabindex="0"></canvas></div>
<script>
const statusEl=document.getElementById('status');
const canvas=document.getElementById('canvas');
const ctx=canvas.getContext('2d',{alpha:false,desynchronized:true});
let ws, remoteW=0, remoteH=0, viewOnly=true;
let viewW=0, viewH=0, DPR=1;
let lastMove=0;

function resizeCanvas(){
  viewW=window.innerWidth; viewH=window.innerHeight-54;
  DPR=window.devicePixelRatio||1;
  canvas.style.width=viewW+'px';
  canvas.style.height=viewH+'px';
  canvas.width=Math.floor(viewW*DPR);
  canvas.height=Math.floor(viewH*DPR);
  // Use CSS units for all interaction math; draw scaled by DPR.
}
window.addEventListener('resize', resizeCanvas); resizeCanvas();
document.getElementById('viewOnly').addEventListener('change', (e)=>{ viewOnly=e.target.checked; canvas.focus(); });
function logout(){ fetch('/logout').then(()=>location.href='/login'); }

function normXY(clientX, clientY){
  const imgW=remoteW, imgH=remoteH; if(!imgW||!imgH) return {nx:0,ny:0};
  const scale=Math.min(viewW/imgW, viewH/imgH);
  const dw=imgW*scale, dh=imgH*scale;
  const dx=(viewW-dw)/2, dy=(viewH-dh)/2;
  let x=(clientX-dx)/dw, y=(clientY-dy)/dh;
  x=Math.max(0,Math.min(1,x)); y=Math.max(0,Math.min(1,y));
  return {nx:x,ny:y};
}

// ----- Mouse -----
canvas.addEventListener('mousemove',(e)=>{
  if(viewOnly) return;
  const now=performance.now(); if(now-lastMove<12) return; lastMove=now;
  const r=canvas.getBoundingClientRect(); const {nx,ny}=normXY(e.clientX-r.left,e.clientY-r.top);
  send({type:'input',device:'mouse',etype:'move',nx,ny});
});
canvas.addEventListener('mousedown',(e)=>{
  if(viewOnly) return;
  const r=canvas.getBoundingClientRect(); const {nx,ny}=normXY(e.clientX-r.left,e.clientY-r.top);
  const button=e.button===0?'left':(e.button===1?'middle':'right');
  send({type:'input',device:'mouse',etype:'click',nx,ny,button,pressed:true});
});
canvas.addEventListener('mouseup',(e)=>{
  if(viewOnly) return;
  const r=canvas.getBoundingClientRect(); const {nx,ny}=normXY(e.clientX-r.left,e.clientY-r.top);
  const button=e.button===0?'left':(e.button===1?'middle':'right');
  send({type:'input',device:'mouse',etype:'click',nx,ny,button,pressed:false});
});
canvas.addEventListener('dblclick',(e)=>{
  if(viewOnly) return;
  const r=canvas.getBoundingClientRect(); const {nx,ny}=normXY(e.clientX-r.left,e.clientY-r.top);
  send({type:'input',device:'mouse',etype:'dblclick',nx,ny,button:'left'});
});
canvas.addEventListener('wheel',(e)=>{
  if(viewOnly) return; e.preventDefault();
  const dy=Math.sign(e.deltaY); send({type:'input',device:'mouse',etype:'scroll',dx:0,dy});
},{passive:false});

// ----- Keyboard -----
canvas.addEventListener('keydown',(e)=>{
  if(viewOnly) return;
  if(e.key.length===1 && !e.ctrlKey && !e.metaKey && !e.altKey){
    send({type:'input',device:'keyboard',etype:'text',text:e.key});
  }else{
    const k=mapKeyName(e.key); if(k) send({type:'input',device:'keyboard',etype:'keydown',key:k});
  }
  e.preventDefault();
});
canvas.addEventListener('keyup',(e)=>{
  if(viewOnly) return;
  const k=mapKeyName(e.key); if(k) send({type:'input',device:'keyboard',etype:'keyup',key:k});
  e.preventDefault();
});
function mapKeyName(k){
  const m={'Enter':'enter','Backspace':'backspace','Tab':'tab','Escape':'escape',
    'ArrowUp':'up','ArrowDown':'down','ArrowLeft':'left','ArrowRight':'right',
    'Delete':'delete','Home':'home','End':'end','PageUp':'pageup','PageDown':'pagedown'};
  if(m[k]) return m[k]; if(k.length===1) return k; return null;
}

// WebSocket + DPR-aware drawing (no extra blur)
function connectWS(){
  const proto=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(proto+'://'+location.host+'/ws');
  ws.binaryType='blob';
  ws.onopen=()=>{ statusEl.textContent='Connected'; canvas.focus(); };
  ws.onclose=()=>{ statusEl.textContent='Disconnected. Reconnecting in 2s...'; setTimeout(connectWS,2000); };
  ws.onerror=()=>{ statusEl.textContent='WebSocket error'; };
  ws.onmessage=async (ev)=>{
    if(typeof ev.data==='string'){
      try{
        const msg=JSON.parse(ev.data);
        if(msg.type==='info'){
          remoteW=msg.screen_w; remoteH=msg.screen_h;
          document.getElementById('codecLabel').textContent=msg.codec||'jpeg';
          document.getElementById('qLabel').textContent=String(msg.quality||'');
        }
      }catch(_){}
      return;
    }
    const bmp=await createImageBitmap(ev.data);
    // Compute CSS-space fit first
    const scale=Math.min(viewW/bmp.width, viewH/bmp.height);
    const dw=bmp.width*scale, dh=bmp.height*scale;
    const dx=(viewW-dw)/2, dy=(viewH-dh)/2;
    // Draw in device pixels (multiply by DPR) for crisp result
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(bmp, dx*DPR, dy*DPR, dw*DPR, dh*DPR);
  };
}
function send(obj){ try{ ws && ws.readyState===WebSocket.OPEN && ws.send(JSON.stringify(obj)); }catch(e){} }
connectWS();
</script></body></html>
"""

# ------------------------------ Routes ----------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/viewer", status_code=302)
    return HTMLResponse(LOGIN_HTML)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/viewer", status_code=302)
    return HTMLResponse(LOGIN_HTML)

@app.post("/api/login")
async def api_login(request: Request):
    try:
        data = await request.json()
    except Exception:
        return PlainTextResponse("invalid payload", status_code=400)
    user = (data.get("username") or "").strip()
    pw = (data.get("password") or "").strip()
    if user == LOGIN_USER and pw == LOGIN_PASS:
        request.session["user"] = user
        return {"ok": True}
    return PlainTextResponse("invalid credentials", status_code=401)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.get("/viewer", response_class=HTMLResponse)
async def viewer(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    return HTMLResponse(VIEWER_HTML)

# -------------------------- Encoding helpers ----------------------------------
def _pillow_encode(img_rgb: Image.Image, codec: str) -> bytes:
    buf = io.BytesIO()
    if codec == "jpeg":
        # subsampling=0 => 4:4:4 (sharp text)
        img_rgb.save(buf, format="JPEG", quality=QUALITY,
                     subsampling=0 if SUBSAMPLING == 0 else (1 if SUBSAMPLING == 1 else 2),
                     optimize=True)
    elif codec == "webp":
        try:
            img_rgb.save(buf, format="WEBP",
                         quality=QUALITY, method=6,
                         lossless=True if WEBP_LOSSLESS else False)
        except Exception:
            # Fallback to JPEG if this Pillow build lacks WebP or lossless
            img_rgb.save(buf, format="JPEG", quality=QUALITY,
                         subsampling=0, optimize=True)
    elif codec == "png":
        # Lossless; crispest but largest
        img_rgb.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def _turbojpeg_encode_from_bgr(bgr_np) -> bytes:
    subs = {0: TJSAMP_444, 1: TJSAMP_422, 2: TJSAMP_420}[SUBSAMPLING]
    return jpeg_encoder.encode(bgr_np, quality=QUALITY,
                               pixel_format=TJPF_BGR, subsampling=subs)

# ---------------------------- Streaming loop ----------------------------------
async def send_frames(ws: WebSocket):
    # Get real screen size
    with mss.mss() as sct:
        mon = sct.monitors[1]
        base_w, base_h = mon["width"], mon["height"]

    await ws.send_text(json.dumps({
        "type": "info",
        "screen_w": base_w,
        "screen_h": base_h,
        "codec": CODEC,
        "quality": QUALITY
    }))

    frame_interval = 1.0 / max(1, FPS)
    last = 0.0
    prev_crc = None  # used when SKIP_DUPLICATE is True

    with mss.mss() as sct:
        mon = sct.monitors[1]
        while True:
            now = time.time()
            if now - last < frame_interval:
                await asyncio.sleep(0.001)
                continue
            last = now

            shot = sct.grab(mon)

            # Skip identical frames early to save encode & network cost
            if SKIP_DUPLICATE:
                crc = zlib.adler32(shot.rgb)
                if crc == prev_crc:
                    continue  # nothing changed
                prev_crc = crc

            w, h = shot.width, shot.height

            # Preferred fast path: TurboJPEG on JPEG
            if CODEC == "jpeg" and HAVE_TURBOJPEG and HAVE_NUMPY:
                bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(h, w, 4)
                bgr = bgra[:, :, :3]
                if SCALE != 1.0:
                    # Use Pillow for high-quality resample, then back to BGR
                    pil = Image.frombytes("RGB", (w, h), shot.rgb)
                    sw, sh = max(1, int(w * SCALE)), max(1, int(h * SCALE))
                    if sw != w or sh != h:
                        pil = pil.resize((sw, sh), Image.LANCZOS)
                    rgb_np = np.asarray(pil, dtype=np.uint8)
                    bgr = rgb_np[:, :, ::-1]
                data = await asyncio.to_thread(_turbojpeg_encode_from_bgr, bgr)
                await ws.send_bytes(data)
                continue

            # Pillow path (supports JPEG/WebP/PNG)
            pil = Image.frombytes("RGB", (w, h), shot.rgb)
            if SCALE != 1.0:
                sw, sh = max(1, int(w * SCALE)), max(1, int(h * SCALE))
                if sw != w or sh != h:
                    pil = pil.resize((sw, sh), Image.LANCZOS)
            data = await asyncio.to_thread(_pillow_encode, pil, CODEC)
            await ws.send_bytes(data)

# ------------------------------- Input ----------------------------------------
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

mouse = MouseController()
keyboard = KeyboardController()

SPECIAL_KEYS = {
    'enter': Key.enter, 'backspace': Key.backspace, 'tab': Key.tab,
    'escape': Key.esc, 'esc': Key.esc,
    'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
    'delete': Key.delete, 'home': Key.home, 'end': Key.end,
    'pageup': Key.page_up, 'pagedown': Key.page_down,
}

def apply_mouse(evt, screen_w, screen_h):
    etype = evt.get("etype")
    nx = float(evt.get("nx", 0.0)); ny = float(evt.get("ny", 0.0))
    x = int(nx * screen_w); y = int(ny * screen_h)
    if etype == "move":
        mouse.position = (x, y)
    elif etype == "click":
        btn = evt.get("button", "left")
        pressed = bool(evt.get("pressed", False))
        b = Button.left if btn == "left" else Button.right if btn == "right" else Button.middle
        if pressed: mouse.press(b)
        else:       mouse.release(b)
    elif etype == "dblclick":
        mouse.position = (x, y)
        for _ in range(2):
            mouse.press(Button.left); mouse.release(Button.left)
    elif etype == "scroll":
        dx = int(evt.get("dx", 0)); dy = int(evt.get("dy", 0))
        mouse.scroll(dx, dy)

def apply_key(evt):
    etype = evt.get("etype")
    if etype == "text":
        txt = evt.get("text", "")
        if txt: keyboard.type(txt)
        return
    key_name = (evt.get("key") or "").lower()
    k = SPECIAL_KEYS.get(key_name)
    if k is None:
        if len(key_name) == 1:  # letters/numbers
            keyboard.type(key_name)
        return
    if etype == "keydown": keyboard.press(k)
    elif etype == "keyup": keyboard.release(k)

# ------------------------------- WebSocket ------------------------------------
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = websocket.session
    if not session or not session.get("user"):
        await websocket.close(code=4401); return

    with mss.mss() as sct:
        mon = sct.monitors[1]
        screen_w, screen_h = mon['width'], mon['height']

    sender = asyncio.create_task(send_frames(websocket))
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                continue
            if msg.get("type") == "input":
                if msg.get("device") == "mouse":
                    apply_mouse(msg, screen_w, screen_h)
                elif msg.get("device") == "keyboard":
                    apply_key(msg)
    except WebSocketDisconnect:
        pass
    finally:
        if not sender.done():
            sender.cancel()
            with contextlib.suppress(Exception):
                await sender

# ---------------------------------- Main --------------------------------------
if __name__ == "__main__":
    import uvicorn
    print(f"Starting Remote Web Control on http://{APP_HOST}:{APP_PORT}")
    print("Tip: For razor-sharp text set RWC_SUBSAMPLING=0 and RWC_QUALITY=90..95.")
    print("     For max fidelity try RWC_CODEC=webp and RWC_WEBP_LOSSLESS=1 (heavier CPU).")
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, log_level="info", reload=False)
