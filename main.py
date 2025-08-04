# main.py
# -----------------------------------------------------------------------------
# Remote Web Control — Web Interface Version (Vercel Compatible)
#
# This version is adapted for Vercel deployment by removing system-dependent
# libraries (mss, pynput) that don't work in serverless environments.
#
# QUICK START
#   pip install fastapi uvicorn
#   python main.py
#   -> open http://127.0.0.1:8000  (login: user / userpass)
# -----------------------------------------------------------------------------

# stdlib
import json, os
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

# ---- Configuration ------------------------------------------------------------
SECRET_KEY     = os.environ.get("RWC_SECRET", "dev-secret-change-me")
LOGIN_USER     = os.environ.get("RWC_USER", "user")
LOGIN_PASS     = os.environ.get("RWC_PASS", "userpass")

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
.content{height:calc(100% - 54px);display:flex;align-items:center;justify-content:center}
.status{font-size:12px;color:#9fb0d6;margin-left:auto}
.info-card{background:#121a2b;padding:32px;border-radius:16px;text-align:center;max-width:400px}
.info-card h2{color:#1d63ff;margin-bottom:16px}
.info-card p{color:#9fb0d6;line-height:1.6;margin-bottom:12px}
</style></head>
<body>
  <div class="topbar">
    <div class="pill">Web Interface</div>
    <div class="pill">Status: <span id="status">Connected</span></div>
    <button class="btn" onclick="logout()">Logout</button>
  </div>
  <div class="content">
    <div class="info-card">
      <h2>Remote Web Control</h2>
      <p>This is the web interface version of Remote Web Control, adapted for Vercel deployment.</p>
      <p>The full remote control functionality (screen sharing, mouse/keyboard control) requires a desktop environment and cannot run in serverless environments.</p>
      <p>For full functionality, run the desktop version locally:</p>
      <p><code>python main.py</code></p>
    </div>
  </div>
<script>
function logout(){ fetch('/logout').then(()=>location.href='/login'); }
</script></body></html>"""

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

@app.get("/api/status")
async def status():
    return {"status": "online", "version": "web-interface", "message": "This is a web-only version adapted for Vercel deployment"}

# ---------------------------------- Main --------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("Starting Remote Web Control (Web Interface) on http://127.0.0.1:8000")
    print("Note: This is a web-only version. For full remote control functionality, run the desktop version.")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info", reload=False)
