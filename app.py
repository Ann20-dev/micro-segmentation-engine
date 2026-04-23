from flask import Flask, request, jsonify, session
from flask_cors import CORS
from segmentation_engine import default_app, LoginStatus, Decision
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

APP = default_app()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    outcome = APP.begin_login(username, password)
    if outcome.status == LoginStatus.OTP_REQUIRED:
        session["pending_user"] = username
        return jsonify({"status": "otp_required", "message": outcome.message})
    return jsonify({"status": "error", "message": outcome.message}), 401


@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    username = session.get("pending_user")
    otp_code = data.get("otp_code")
    if not username:
        return jsonify({"status": "error", "message": "No pending login"}), 400
    outcome = APP.verify_otp(username, otp_code)
    if outcome.status == LoginStatus.SUCCESS and outcome.session:
        session["user"] = username
        session.pop("pending_user", None)
        return jsonify(
            {
                "status": "success",
                "user": username,
                "role": outcome.session.role,
                "zone": outcome.session.zone,
            }
        )
    return jsonify({"status": "error", "message": outcome.message}), 401


@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    username = session.get("user")
    if not username:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    identity = APP._identities.get(username)
    alerts = APP.sms_alerts_for(username)
    return jsonify(
        {
            "user": username,
            "role": identity.role if identity else "",
            "zone": identity.home_zone if identity else "",
            "alerts": [
                {"category": a.category, "message": a.message} for a in alerts[-5:]
            ],
        }
    )


@app.route("/api/chat/send", methods=["POST"])
def chat_send():
    username = session.get("user")
    if not username:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    sess = APP.login(username, "dummy")  # Get session, assuming logged in
    if not sess:
        return jsonify({"status": "error", "message": "Invalid session"}), 401
    data = request.json
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"status": "error", "message": "Empty message"}), 400
    # Log the chat access
    APP.access_page(sess, "chat_page", "write")
    # Generate response based on logs
    logs = APP.access_logs_for(username)
    response = generate_chat_response(message, logs, username)
    return jsonify({"response": response})


def generate_chat_response(message: str, logs: list, username: str) -> str:
    text = message.lower()
    recent_logs = logs[-10:]  # Last 10 logs
    if "log" in text or "activity" in text or "recent" in text:
        if recent_logs:
            log_summary = "\n".join(
                [
                    f"{l.timestamp}: {l.resource} - {l.decision} ({l.message})"
                    for l in recent_logs
                ]
            )
            return f"Here are your recent access logs:\n{log_summary}"
        else:
            return "No recent activity logs found."
    if "finance" in text:
        finance_logs = [l for l in recent_logs if "airtime" in l.resource]
        if finance_logs:
            return f"You have {len(finance_logs)} recent finance access attempts. Last: {finance_logs[-1].message}"
        return "Finance pages are restricted to finance roles."
    if "suspicious" in text:
        suspicious_logs = [l for l in recent_logs if "blocked" in l.message.lower()]
        if suspicious_logs:
            return f"Suspicious behavior detected in {len(suspicious_logs)} attempts."
        return "No suspicious activity detected in recent logs."
    return "I can help with your access logs, finance access, or suspicious activity. Ask about 'recent logs' or 'finance activity'."


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(debug=True)
