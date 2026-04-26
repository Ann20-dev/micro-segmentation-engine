from __future__ import annotations

from datetime import datetime
import html
import json
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from segmentation_engine import AccessLog, Decision, LoginStatus, Session, default_app


APP = default_app()
SESSION_COOKIE = "microseg_session"
SESSIONS: dict[str, Session] = {}
PENDING_LOGIN_USERS: set[str] = set()
CHAT_HISTORY: dict[str, list[tuple[str, str]]] = {}
APP_BUILD = "Build 2026-04-24"
CHAT_CONTEXT_WINDOW = 6


def page_template(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe6;
      --panel: #fffaf2;
      --ink: #1b1f23;
      --muted: #59636e;
      --line: #d9ccba;
      --accent: #155eef;
      --danger: #b42318;
      --success: #067647;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, #fff7df 0, transparent 32%),
        linear-gradient(135deg, #f4efe6, #efe4d2);
      color: var(--ink);
      min-height: 100vh;
    }}
    .wrap {{
      max-width: 860px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 50px rgba(38, 30, 20, 0.08);
      padding: 24px;
      margin-bottom: 20px;
    }}
    h1, h2 {{ margin-top: 0; }}
    p {{ line-height: 1.5; }}
    .meta {{ color: var(--muted); }}
    .banner {{
      padding: 12px 14px;
      border-radius: 12px;
      margin-bottom: 16px;
      font-weight: 600;
    }}
    .build-tag {{
      display: inline-block;
      margin-bottom: 14px;
      padding: 8px 12px;
      border-radius: 999px;
      background: #fff8eb;
      border: 1px solid var(--line);
      color: var(--ink);
      font-size: 0.92rem;
      font-weight: 700;
    }}
    .allow {{ background: #e7f6ec; color: var(--success); }}
    .deny {{ background: #fdecea; color: var(--danger); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .tile {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      background: #fff;
    }}
    label {{ display: block; margin-bottom: 12px; font-weight: 700; }}
    input {{
      width: 100%;
      margin-top: 6px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      font: inherit;
      background: #fff;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    button, .button {{
      display: inline-block;
      text-decoration: none;
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      padding: 11px 16px;
      font: inherit;
      cursor: pointer;
    }}
    .button.secondary {{
      background: #fff;
      color: var(--ink);
      border: 1px solid var(--line);
    }}
    .button.danger, button.danger {{ background: var(--danger); }}
    .button.ghost, button.ghost {{
      background: #fff8eb;
      color: var(--ink);
      border: 1px dashed var(--line);
    }}
    .chat-shell {{
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(240px, 0.8fr);
      gap: 20px;
    }}
    .chat-stage {{
      background: linear-gradient(180deg, #fffdf9, #fff6ea);
      border: 1px solid var(--line);
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 18px 50px rgba(38, 30, 20, 0.1);
    }}
    .chat-topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 18px 20px;
      background: linear-gradient(120deg, #1d4ed8, #0f766e);
      color: #fff;
    }}
    .chat-title {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .chat-orb {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: radial-gradient(circle at 30% 30%, #fff7cc, #f59e0b);
      box-shadow: inset 0 0 18px rgba(255, 255, 255, 0.4);
    }}
    .chat-log {{
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      height: 420px;
      overflow-y: auto;
      background:
        radial-gradient(circle at top right, rgba(21, 94, 239, 0.07), transparent 30%),
        linear-gradient(180deg, #fffcf7, #fff7ed);
    }}
    .bubble {{
      max-width: 78%;
      padding: 14px 16px;
      border-radius: 18px;
      line-height: 1.45;
      box-shadow: 0 10px 24px rgba(38, 30, 20, 0.08);
    }}
    .bubble.user {{
      align-self: flex-end;
      background: linear-gradient(135deg, #155eef, #5b8cff);
      color: #fff;
      border-bottom-right-radius: 6px;
    }}
    .bubble.bot {{
      align-self: flex-start;
      background: #fff;
      color: var(--ink);
      border: 1px solid #e6d8c4;
      border-bottom-left-radius: 6px;
    }}
    .bubble.system {{
      align-self: center;
      background: #fff8eb;
      color: var(--muted);
      border: 1px dashed var(--line);
      box-shadow: none;
      font-size: 0.95rem;
    }}
    .bubble.bot strong {{
      display: block;
      margin-bottom: 6px;
      color: #0f766e;
      font-size: 0.95rem;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }}
    .chat-composer {{
      padding: 18px 20px 20px;
      border-top: 1px solid var(--line);
      background: #fffaf2;
    }}
    .chat-composer textarea {{
      width: 100%;
      min-height: 96px;
      resize: vertical;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      font: inherit;
      background: #fff;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--ink);
      padding: 9px 12px;
      font: inherit;
      cursor: pointer;
    }}
    .composer-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .chat-status {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .typing-indicator {{
      display: none;
      align-self: flex-start;
      gap: 5px;
      padding: 12px 14px;
    }}
    .typing-indicator.visible {{
      display: inline-flex;
    }}
    .typing-indicator span {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #94a3b8;
      animation: blink 1.1s infinite;
    }}
    .typing-indicator span:nth-child(2) {{ animation-delay: 0.15s; }}
    .typing-indicator span:nth-child(3) {{ animation-delay: 0.3s; }}
    .chat-toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .insight-list {{
      display: grid;
      gap: 10px;
    }}
    .insight-item {{
      padding: 12px 14px;
      border-radius: 14px;
      background: #fff;
      border: 1px solid var(--line);
    }}
    .banner {{
      animation: slideIn 0.5s ease-out;
    }}
    @keyframes slideIn {{
      from {{ transform: translateY(-20px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}
    .tile.safe {{
      border-color: #067647;
      background: #f0fdf4;
    }}
    .tile.warning {{
      border-color: #d97706;
      background: #fffbeb;
    }}
    .tile.blocked {{
      border-color: #b42318;
      background: #fef2f2;
    }}
    .status-indicator {{
      display: inline-block;
      padding: 6px 12px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 0.9rem;
      margin-bottom: 12px;
    }}
    .status-indicator.normal {{
      background: #e7f6ec;
      color: #067647;
    }}
    .status-indicator.blocked {{
      background: #fdecea;
      color: #b42318;
      animation: pulse 1s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.7; }}
    }}
    @keyframes blink {{
      0%, 80%, 100% {{ transform: translateY(0); opacity: 0.35; }}
      40% {{ transform: translateY(-3px); opacity: 1; }}
    }}
    .side-stack {{
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    @media (max-width: 760px) {{
      .chat-shell {{
        grid-template-columns: 1fr;
      }}
      .bubble {{
        max-width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    {body}
  </div>
    <script>
    function useLatestOtp() {{
      const otpInput = document.querySelector('input[name="otp_code"]');
      const otpSource = document.querySelector('[data-latest-otp]');
      if (!otpInput || !otpSource) {{
        return;
      }}
      otpInput.value = otpSource.getAttribute('data-latest-otp') || '';
      otpInput.focus();
    }}

    document.addEventListener('DOMContentLoaded', function() {{
      const form = document.getElementById('chat-form');
      const textarea = form ? form.querySelector('textarea[name="message"]') : null;
      const status = document.getElementById('chat-status');
      const typing = document.getElementById('typing-indicator');
      const log = document.querySelector('.chat-log');
      const quickButtons = document.querySelectorAll('[data-quick-message]');

      function appendBubble(kind, message) {{
        if (!log) {{
          return;
        }}
        const bubble = document.createElement('div');
        bubble.className = 'bubble ' + kind;
        bubble.innerHTML = message;
        log.appendChild(bubble);
        log.scrollTop = log.scrollHeight;
      }}

      function fallbackSubmit(message) {{
        const fallbackForm = document.createElement('form');
        fallbackForm.method = 'POST';
        fallbackForm.action = '/chat-message';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'message';
        input.value = message;
        fallbackForm.appendChild(input);

        document.body.appendChild(fallbackForm);
        fallbackForm.submit();
      }}

      quickButtons.forEach(function(button) {{
        button.addEventListener('click', function() {{
          if (!textarea) {{
            return;
          }}
          textarea.value = button.getAttribute('data-quick-message') || '';
          textarea.focus();
        }});
      }});

      if (textarea) {{
        textarea.addEventListener('keydown', function(event) {{
          if (event.key === 'Enter' && !event.shiftKey) {{
            event.preventDefault();
            form.requestSubmit();
          }}
        }});
      }}

      if (form) {{
        form.addEventListener('submit', async function(e) {{
          e.preventDefault();
          const formData = new FormData(this);
          const userMessage = (formData.get('message') || '').toString().trim();
          if (!userMessage) {{
            return;
          }}
          formData.append('ajax', 'yes');
          appendBubble('user', userMessage);
          if (textarea) {{
            textarea.value = '';
            textarea.focus();
          }}
          if (typing) {{
            typing.classList.add('visible');
          }}
          if (status) {{
            status.textContent = 'Assistant is thinking...';
          }}
          try {{
            const response = await fetch('/chat-message', {{
              method: 'POST',
              body: formData,
              credentials: 'same-origin',
              headers: {{
                'Accept': 'application/json'
              }}
            }});
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok || !contentType.includes('application/json')) {{
              throw new Error('Non-JSON chat response');
            }}
            const data = await response.json();
            if (typing) {{
              typing.classList.remove('visible');
            }}
            if (status) {{
              status.textContent = 'Assistant responded just now.';
            }}
            appendBubble('bot', data.bot);
          }} catch (error) {{
            if (typing) {{
              typing.classList.remove('visible');
            }}
            if (status) {{
              status.textContent = 'Live chat retrying...';
            }}
            appendBubble('system', 'Live response retried through the safe server path.');
            fallbackSubmit(userMessage);
            console.error('Error sending message:', error);
          }}
        }});
      }}
    }});
  </script>
</body>
</html>"""


def sms_inbox_view(username: str) -> str:
    alerts = APP.sms_alerts_for(username)
    if not alerts:
        return '<div class="tile">No SMS messages yet.</div>'
    items = []
    for alert in reversed(alerts[-5:]):
        sender = (
            "SECURE-SYS"
            if alert.category == "otp"
            else "SECURE-ALERT"
            if alert.category in ("security_alert", "account_lock")
            else "SECURE-SYS"
        )
        status_class = (
            "safe"
            if alert.category == "otp"
            else "blocked"
            if alert.category in ("security_alert", "account_lock")
            else "warning"
        )
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        items.append(
            '<div class="tile {status_class}"><strong>{sender} - {timestamp}</strong><br><span class="meta">{message}</span></div>'.format(
                status_class=status_class,
                sender=html.escape(sender),
                timestamp=html.escape(timestamp),
                message=html.escape(alert.message),
            )
        )
    return "".join(items)


def login_view(message: str = "", pending_user: str = "") -> str:
    banner = ""
    if message:
        banner = f'<div class="banner deny">{html.escape(message)}</div>'
    otp_panel = ""
    latest_otp_code = ""
    ussd_panel = ""
    if pending_user:
        latest_otp = APP.latest_otp_for(pending_user)
        if latest_otp is not None and " is " in latest_otp.message:
            latest_otp_code = latest_otp.message.split(" is ", 1)[1].split(".", 1)[0]
        if latest_otp_code:
            otp_panel = f"""
            <div class="card">
              <h2>OTP Verification</h2>
              <p class="meta">An OTP was sent by SMS for <strong>{html.escape(pending_user)}</strong>.</p>
              <form method="post" action="/verify-otp">
                <input type="hidden" name="username" value="{html.escape(pending_user)}">
                <label>OTP Code
                  <input name="otp_code" inputmode="numeric" required>
                </label>
                <div class="actions">
                  <button class="ghost" type="button" onclick="useLatestOtp()">Use Latest OTP</button>
                  <button type="submit">Verify OTP</button>
                </div>
              </form>
            </div>
            """
        alerts = APP.sms_alerts_for(pending_user)
        latest_ussd_otp = APP._pending_ussd_otps.get(pending_user)
        if latest_ussd_otp:
            ussd_panel = f"""
            <div class="card">
              <h2>USSD Confirmation</h2>
              <p class="meta">Confirmation code sent by SMS for <strong>{html.escape(pending_user)}</strong>.</p>
              <form method="post" action="/verify-ussd-otp">
                <input type="hidden" name="username" value="{html.escape(pending_user)}">
                <label>Confirmation Code
                  <input name="ussd_code" inputmode="numeric" required>
                </label>
                <div class="actions">
                  <button type="submit">Verify USSD Code</button>
                </div>
              </form>
            </div>
            """
        elif any(a.category == "security_alert" for a in alerts):
            ussd_panel = f"""
            <div class="card">
              <h2>USSD Prompt ☎️</h2>
              <p>User logs in from suspicious location 🌍, system flags it 🚨, user gets USSD prompt ☎️.</p>
              <p>SMS alert sent 📩. Approve or deny to update access dynamically 🔐.</p>
              <form method="post" action="/ussd-approve" style="display:inline">
                <input type="hidden" name="username" value="{html.escape(pending_user)}">
                <button type="submit">Approve ✅</button>
              </form>
              <form method="post" action="/ussd-deny" style="display:inline">
                <input type="hidden" name="username" value="{html.escape(pending_user)}">
                <button type="submit" class="danger">Deny ❌</button>
              </form>
            </div>
            """
    body = f"""
    <div class="card">
      <div class="build-tag">{APP_BUILD}</div>
      <h1>Micro-Segmentation Engine</h1>
      <p class="meta">Login with a role-based demo account, receive an SMS OTP, and test browser access control.</p>
      {banner}
      <div class="actions" style="margin-bottom:16px;">
        <form method="post" action="/reset-demo" style="display:inline">
          <button class="button secondary" type="submit">Reset Demo</button>
        </form>
      </div>
      <form method="post" action="/login">
        <label>Username
          <input name="username" autocomplete="username" required>
        </label>
        <label>Password
          <input name="password" type="password" autocomplete="current-password" required>
        </label>
        <label>
          <input type="checkbox" name="suspicious_location"> Login from suspicious location 🌍
        </label>
        <div class="actions">
          <button type="submit">Login</button>
        </div>
      </form>
    </div>
    {otp_panel}
    {ussd_panel}
    <div class="card">
      <h2>Demo Users</h2>
      <div class="grid">
        <div class="tile"><strong>normal_user</strong><br><span class="meta">Password: user123</span><br><span class="meta">Phone: 0711731098</span></div>
        <div class="tile"><strong>finance_user</strong><br><span class="meta">Password: finance123</span><br><span class="meta">Phone: 0711731098</span></div>
        <div class="tile"><strong>admin_user</strong><br><span class="meta">Password: admin123</span><br><span class="meta">Phone: 0711731098</span></div>
      </div>
    </div>
    <div class="card">
      <h2>Local SMS Inbox</h2>
      <div class="grid">
        {sms_inbox_view(pending_user) if pending_user else '<div class="tile">Enter valid credentials to receive OTP, security alerts, and risk score notifications here.</div>'}
      </div>
      {'<div class="meta" data-latest-otp="' + html.escape(latest_otp_code) + '">Demo helper ready: click Use Latest OTP.</div>' if pending_user and latest_otp_code else ""}
    </div>
    """
    return page_template("Login", body)


def dashboard_view(session: Session, message: str = "", status: str = "") -> str:
    banner = ""
    if message:
        banner = f'<div class="banner {status}">{html.escape(message)}</div>'
    blocked = APP._detector.is_blocked(session.username)
    status_indicator = f'<div class="status-indicator {"blocked" if blocked else "normal"}">Status: {"Blocked 🚨" if blocked else "Normal ✅"}</div>'
    body = f"""
    <div class="card">
      <div class="build-tag">{APP_BUILD}</div>
      <h1>Welcome, {html.escape(session.username)}</h1>
      <p class="meta">Role: {html.escape(session.role)} | Zone: {html.escape(session.zone)}</p>
      {status_indicator}
      {banner}
      <div class="card">
        <h2>🗺️ Zone Visualization</h2>
        <div class="zone-map">
          <div class="zone user-zone {"allowed" if session.zone == "user" else "blocked"}">User Zone<br>{"✅ (Active)" if session.zone == "user" else "❌"}</div>
          <div class="zone finance-zone {"allowed" if session.zone == "finance" else "blocked"}">Finance Zone<br>{"✅ (Active)" if session.zone == "finance" else "❌"}</div>
          <div class="zone admin-zone {"allowed" if session.zone == "admin" else "blocked"}">Admin Zone<br>{"✅ (Active)" if session.zone == "admin" else "❌"}</div>
          <div class="zone ussd-zone limited">USSD Zone<br>⚠ Limited</div>
        </div>
         <style>
           .zone-map {{ display: flex; gap: 10px; justify-content: center; margin: 20px 0; }}
           .zone {{ padding: 10px; border: 2px solid #ccc; border-radius: 8px; text-align: center; font-weight: bold; }}
           .zone.allowed {{ background: #e7f6ec; color: #067647; border-color: #067647; }}
           .zone.blocked {{ background: #fdecea; color: #b42318; border-color: #b42318; }}
           .zone.limited {{ background: #fffbeb; color: #d97706; border-color: #d97706; }}
         </style>
       </div>
       <div class="actions">
        <a class="button" href="/finance">Try Finance Page</a>
        <a class="button secondary" href="/ussd">Try USSD Page</a>
        <a class="button secondary" href="/chat">Open Chat Page</a>
        <form method="post" action="/simulate-suspicious" style="display:inline">
          <button class="danger" type="submit">Simulate Suspicious Behavior</button>
        </form>
        <form method="post" action="/reset-demo" style="display:inline">
          <button class="button secondary" type="submit">Reset Demo</button>
        </form>
        {'<form method="post" action="/approve-admin-finance" style="display:inline"> <button class="button secondary" type="submit">Approve Finance Access</button> </form>' if session.role == "super_admin" else ""}
        <form method="post" action="/logout" style="display:inline">
          <button class="button secondary" type="submit">Logout</button>
        </form>
      </div>
    </div>
    <div class="card">
      <h2>Expected Flow</h2>
      <div class="grid">
        <div class="tile">`normal_user` opening finance should be denied.</div>
        <div class="tile">`finance_user` opening finance should be granted.</div>
        <div class="tile">USSD: Status checks, Approvals, Limited actions. No Database ❌, No Admin panel ❌.</div>
        <div class="tile">Failed login: USSD → request action 📱, SMS → send OTP 📩, Backend → verify.</div>
        <div class="tile">Suspicious location: User logs in 🌍, system flags 🚨, USSD prompt ☎️, approve/deny, dynamic access 🔐.</div>
        <div class="tile">Suspicious behavior simulation 🚨 blocks access, sends SMS 📩, user confirms via USSD 📱, chatbot explains 💬.</div>
      </div>
    </div>
    <div class="card">
      <h2>SMS Inbox</h2>
      <div class="grid" id="sms-inbox">
        {sms_inbox_view(session.username)}
      </div>
    </div>
    {'<div class="card"><h2>Admin Access Log</h2><div class="insight-list">' + "".join(f'<div class="insight-item">{format_access_log(log)}</div>' for log in APP.access_logs_for(session.username)[-5:]) + "</div></div>" if session.role == "super_admin" else ""}
    <script>
    async function checkAccess(url, redirectUrl) {{
      const response = await fetch(url + '?ajax=yes');
      const data = await response.json();
      if (data.decision === 'deny') {{
        alert('🚨 Access Blocked: ' + data.message);
        return false;
      }} else {{
        window.location.href = redirectUrl;
        return true;
      }}
    }}

    document.addEventListener('DOMContentLoaded', function() {{
      const financeLink = document.querySelector('a[href="/finance"]');
      if (financeLink) {{
        financeLink.addEventListener('click', function(e) {{
          e.preventDefault();
          checkAccess('/finance', '/finance');
        }});
      }}
      const ussdLink = document.querySelector('a[href="/ussd"]');
      if (ussdLink) {{
        ussdLink.addEventListener('click', function(e) {{
          e.preventDefault();
          checkAccess('/ussd', '/ussd');
        }});
      }}
      const chatLink = document.querySelector('a[href="/chat"]');
      if (chatLink) {{
        chatLink.addEventListener('click', function(e) {{
          e.preventDefault();
          checkAccess('/chat', '/chat');
        }});
      }}
      const simulateForm = document.querySelector('form[action="/simulate-suspicious"]');
      if (simulateForm) {{
        simulateForm.addEventListener('submit', function(e) {{
          alert('🚨 Simulating suspicious behavior... Access will be blocked!');
        }});
      }}
      const resetForm = document.querySelector('form[action="/reset-demo"]');
      if (resetForm) {{
        resetForm.addEventListener('submit', function(e) {{
          if (!confirm('Reset the demo? This will clear all sessions and data.')) {{
            e.preventDefault();
          }}
        }});
      }}
      const logoutForm = document.querySelector('form[action="/logout"]');
      if (logoutForm) {{
        logoutForm.addEventListener('submit', function(e) {{
          if (!confirm('Logout?')) {{
            e.preventDefault();
          }}
        }});
      }}

      async function refreshSMS() {{
        try {{
          const response = await fetch('/api/sms-inbox');
          if (response.ok) {{
            const html = await response.text();
            document.getElementById('sms-inbox').innerHTML = html;
          }}
        }} catch (error) {{
          console.error('Failed to refresh SMS:', error);
        }}
      }}

      // Refresh immediately if there's a deny banner (e.g., after simulation)
      if (document.querySelector('.banner.deny')) {{
        refreshSMS();
      }}

      setInterval(refreshSMS, 5000); // Refresh every 5 seconds
    }});
    </script>
    """
    return page_template("Dashboard", body)


def resource_view(
    title: str, outcome_message: str, allowed: bool, back_path: str = "/dashboard"
) -> str:
    status = "allow" if allowed else "deny"
    body = f"""
    <div class="card">
      <div class="build-tag">{APP_BUILD}</div>
      <h1>{html.escape(title)}</h1>
      <div class="banner {status}">{html.escape(outcome_message)}</div>
      <div class="actions">
        <a class="button secondary" href="{html.escape(back_path)}">Back to Dashboard</a>
      </div>
    </div>
    """
    return page_template(title, body)


def finance_view(session: Session) -> str:
    blocked = APP._detector.is_blocked(session.username)
    risk_score = session.risk_score
    risk_color = "🔴 High" if risk_score > 50 else "🟢 Low"
    access_level = "Restricted" if blocked else "Full Finance Access"
    session_status = "Blocked" if blocked else "Secure"

    if blocked:
        body = f"""
        <div class="card">
          <div class="build-tag">{APP_BUILD}</div>
          <h1>🚨 Access Restricted</h1>
          <div class="banner deny">Finance access blocked due to suspicious behavior.</div>
          <p><strong>Reasons:</strong></p>
          <ul>
            <li>Suspicious location detected 🌍</li>
            <li>Risk score: {risk_score} {risk_color}</li>
          </ul>
          <div class="actions">
            <form method="post" action="/confirm-suspicious" style="display:inline">
              <input type="hidden" name="username" value="{html.escape(session.username)}">
              <button type="submit">Approve via USSD 📱</button>
            </form>
            <a class="button" href="/chat?message=Why+am+I+blocked%3F">Ask Chatbot for Explanation 💬</a>
          </div>
        </div>
        """
    else:
        # Calculate duration
        now = datetime.now()
        duration = now - session.login_time
        duration_str = f"{duration.seconds // 60} mins"

        body = f"""
        <div class="card">
          <div class="build-tag">{APP_BUILD}</div>
          <h1>Access Granted ✅</h1>
          <div class="banner allow">Access granted to finance_page.</div>
          <p><strong>Role:</strong> {html.escape(session.role)}</p>
          <p><strong>Zone:</strong> Finance</p>
          <p><strong>Reasons:</strong></p>
          <ul>
            <li>Role matches required access ✔</li>
            <li>Device trusted ✔</li>
            <li>Risk score: {risk_score} ({risk_color}) ✔</li>
          </ul>
        </div>
        <div class="card">
          <h2>💰 Financial Dashboard</h2>
          <div class="grid">
            <div class="tile"><strong>Total Transactions Today:</strong> 1,245</div>
            <div class="tile"><strong>Flagged Transactions:</strong> 3 ⚠️</div>
            <div class="tile"><strong>Last Access:</strong> {session.login_time.strftime("%H:%M %p")}</div>
          </div>
        </div>
        <div class="card">
          <h2>🔐 Security Status</h2>
          <div class="grid">
            <div class="tile"><strong>Risk Score:</strong> {risk_score} {risk_color}</div>
            <div class="tile"><strong>Access Level:</strong> {access_level}</div>
            <div class="tile"><strong>Session Status:</strong> {session_status}</div>
          </div>
        </div>
        <div class="card">
          <h2>🗺️ Visual Zone Map</h2>
          <div class="zone-map">
            <div class="zone user-zone blocked">User Zone<br>❌ Finance Zone</div>
            <div class="zone finance-zone allowed">Finance Zone<br>✅ Finance Data</div>
            <div class="zone ussd-zone blocked">USSD Zone<br>Limited Access Only</div>
          </div>
          <style>
            .zone-map {{ display: flex; gap: 10px; justify-content: center; margin: 20px 0; }}
            .zone {{ padding: 10px; border: 2px solid #ccc; border-radius: 8px; text-align: center; font-weight: bold; }}
            .zone.allowed {{ background: #e7f6ec; color: #067647; border-color: #067647; }}
            .zone.blocked {{ background: #fdecea; color: #b42318; border-color: #b42318; }}
          </style>
        </div>
        </div>
        <div class="card">
          <h2>🔴 Live Security Panel</h2>
          <div class="grid">
            <div class="tile"><strong>User Risk Score:</strong> <span id="risk-score">{risk_score} {risk_color}</span></div>
            <div class="tile"><strong>Status:</strong> <span id="status">{session_status}</span></div>
            <div class="tile"><strong>Current Zone Access:</strong> User ❌ | Finance ✅ | Admin ❌</div>
            <div class="tile"><strong>Active Alerts:</strong> <span id="alerts">{"Suspicious location + rapid access attempts" if blocked else "None"}</span></div>
          </div>
        </div>
        <script>
        setInterval(() => {{
          fetch('/api/security-status')
          .then(response => response.json())
          .then(data => {{
            document.getElementById('risk-score').textContent = data.risk_score + ' ' + data.risk_color;
            document.getElementById('status').textContent = data.status;
            document.getElementById('alerts').textContent = data.reason;
          }})
          .catch(error => console.error('Error updating security panel:', error));
        }}, 2000);
        </script>
        </div>
        <div class="card">
          <h2>⏱️ Session Monitoring</h2>
          <div class="grid">
            <div class="tile"><strong>Login Time:</strong> {session.login_time.strftime("%H:%M %p")}</div>
            <div class="tile"><strong>Active Duration:</strong> {duration_str}</div>
            <div class="tile"><strong>Last Activity:</strong> Viewing transactions</div>
          </div>
        </div>
        </div>
        <div class="actions">
          <a class="button" href="/chat?message=Why+do+I+have+access%3F">Explain This Access 💬</a>
          <a class="button secondary" href="/dashboard">Back to Dashboard</a>
        </div>
        """

    return page_template("Finance Page", body)


def ussd_confirmation_view(session: Session) -> str:
    body = f"""
    <div class="card">
      <div class="build-tag">{APP_BUILD}</div>
      <h1>Suspicious Behavior Detected 🚨</h1>
      <p>System has blocked access due to micro-segmentation.</p>
      <p>SMS alert sent 📩. Confirm your identity via USSD to restore access.</p>
      <form method="post" action="/confirm-suspicious">
        <input type="hidden" name="username" value="{html.escape(session.username)}">
        <div class="actions">
          <button type="submit">Confirm via USSD 📱</button>
        </div>
      </form>
      <div class="actions" style="margin-top:16px;">
        <a class="button secondary" href="/chat">Ask Chatbot for Explanation 💬</a>
      </div>
    </div>
    """
    return page_template("USSD Confirmation", body)


def ussd_interface_view(session: Session) -> str:
    body = f"""
    <div class="card">
      <div class="build-tag">{APP_BUILD}</div>
      <h1>USSD Simulation ☎️</h1>
      <p>Simulate USSD menu navigation for security approvals and status checks.</p>
      <div id="ussd-screen" class="ussd-screen">
        <div class="ussd-display">
          <p id="ussd-text">Dial *123# to start</p>
        </div>
        <div class="ussd-input">
          <input type="text" id="ussd-input" placeholder="Enter code or option" />
          <button id="ussd-submit">Send</button>
        </div>
      </div>
      <div class="actions" style="margin-top:16px;">
        <a class="button secondary" href="/dashboard">Back to Dashboard</a>
      </div>
    </div>
    <style>
      .ussd-screen {{
        border: 2px solid var(--accent);
        border-radius: 12px;
        padding: 20px;
        background: #000;
        color: #0f0;
        font-family: 'Courier New', monospace;
        margin-bottom: 20px;
      }}
      .ussd-display {{
        background: #111;
        padding: 15px;
        border-radius: 8px;
        min-height: 80px;
        margin-bottom: 15px;
      }}
      .ussd-input {{
        display: flex;
        gap: 10px;
      }}
      .ussd-input input {{
        flex: 1;
        background: #111;
        border: 1px solid #333;
        color: #0f0;
        padding: 8px 12px;
        border-radius: 6px;
      }}
      .ussd-input button {{
        background: var(--accent);
        color: #fff;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
      }}
    </style>
    <script>
      let ussdState = 'idle';
      const ussdText = document.getElementById('ussd-text');
      const ussdInput = document.getElementById('ussd-input');
      const ussdSubmit = document.getElementById('ussd-submit');

      ussdSubmit.addEventListener('click', function() {{
        const input = ussdInput.value.trim();
        ussdInput.value = '';
        processUSSD(input);
      }});

      ussdInput.addEventListener('keypress', function(e) {{
        if (e.key === 'Enter') {{
          e.preventDefault();
          ussdSubmit.click();
        }}
      }});

      function processUSSD(input) {{
        ussdText.innerHTML = 'Processing...';
        setTimeout(() => {{
          if (ussdState === 'idle') {{
            if (input === '*123#') {{
              ussdText.innerHTML = 'Welcome to Micro-Segmentation USSD<br><br>1. Check Status<br>2. Approve Login<br><br>Select option:';
              ussdState = 'menu';
            }} else {{
              ussdText.innerHTML = 'Invalid code. Dial *123# to start';
            }}
          }} else if (ussdState === 'menu') {{
            if (input === '1') {{
              ussdText.innerHTML = 'Status Check<br><br>User: {html.escape(session.username)}<br>Role: {html.escape(session.role)}<br>Zone: {html.escape(session.zone)}<br><br>Access: Granted<br><br>0. Back to Menu';
              ussdState = 'status';
            }} else if (input === '2') {{
              ussdText.innerHTML = 'Login attempt from new location.<br><br>Approve?<br><br>1. Yes<br>2. No<br><br>Select option:';
              ussdState = 'approve';
            }} else {{
              ussdText.innerHTML = 'Invalid option.<br><br>1. Check Status<br>2. Approve Login<br><br>Select option:';
            }}
          }} else if (ussdState === 'status') {{
            if (input === '0') {{
              ussdText.innerHTML = 'Welcome to Micro-Segmentation USSD<br><br>1. Check Status<br>2. Approve Login<br><br>Select option:';
              ussdState = 'menu';
            }} else {{
              ussdText.innerHTML = 'Invalid option. 0. Back to Menu';
            }}
          }} else if (ussdState === 'approve') {{
            if (input === '1') {{
              ussdText.innerHTML = 'Login approved. Access granted.<br><br>Dial *123# to continue.';
              ussdState = 'idle';
            }} else if (input === '2') {{
              ussdText.innerHTML = 'Login denied. Access blocked.<br><br>Dial *123# to continue.';
              ussdState = 'idle';
            }} else {{
              ussdText.innerHTML = 'Invalid option.<br><br>Approve?<br><br>1. Yes<br>2. No<br><br>Select option:';
            }}
          }}
        }}, 1000); // Simulate 1 second delay
      }}
    </script>
    """
    return page_template("USSD Simulation", body)


def format_access_log(log: AccessLog) -> str:
    return (
        f"{log.subject} tried {log.action} on {log.resource} and the system "
        f"{log.decision}ed it."
    )


def infer_chat_topic(text: str) -> str | None:
    if any(word in text for word in {"finance", "billing", "accounting"}):
        return "finance"
    if any(word in text for word in {"sms", "otp", "verification"}):
        return "otp"
    if any(word in text for word in {"suspicious", "attack", "behavior", "blocked"}):
        return "security"
    if any(word in text for word in {"role", "roles", "permission"}):
        return "roles"
    if any(word in text for word in {"zone", "zones", "segment"}):
        return "zones"
    if any(word in text for word in {"api", "apis", "service"}):
        return "apis"
    if any(word in text for word in {"login", "authentication", "password"}):
        return "login"
    if any(word in text for word in {"chat", "bot", "chatbot"}):
        return "chat"
    if any(word in text for word in {"log", "history", "recent access"}):
        return "history"
    if any(word in text for word in {"micro-segmentation", "segmentation"}):
        return "segmentation"
    return None


def recent_chat_topic(history: list[tuple[str, str]]) -> str | None:
    for author, message in reversed(history[-CHAT_CONTEXT_WINDOW:]):
        if author != "user":
            continue
        topic = infer_chat_topic(message.lower())
        if topic is not None:
            return topic
    return None


def normalize_message_with_context(message: str, history: list[tuple[str, str]]) -> str:
    text = message.lower().strip()
    topic = recent_chat_topic(history)
    if topic is None:
        return text

    follow_up_markers = {
        "and",
        "also",
        "what about",
        "tell me more",
        "more",
        "why",
        "how",
        "explain",
        "that",
        "this",
    }
    if any(marker in text for marker in follow_up_markers):
        if topic == "finance":
            return text + " finance billing accounting"
        if topic == "otp":
            return text + " sms otp verification"
        if topic == "security":
            return text + " suspicious behavior blocked"
        if topic == "roles":
            return text + " roles permissions"
        if topic == "zones":
            return text + " zones segmentation"
        if topic == "apis":
            return text + " apis services"
        if topic == "login":
            return text + " login authentication password"
        if topic == "history":
            return text + " recent access history"
        if topic == "segmentation":
            return text + " micro-segmentation zones"
    return text


def chat_reply_for(
    session: Session,
    message: str,
    app=APP,
    history: list[tuple[str, str]] | None = None,
) -> str:
    history = history or []
    text = normalize_message_with_context(message, history)
    logs = app.access_logs_for(session.username)
    latest_log = logs[-1] if logs else None

    if any(word in text for word in {"hello", "hey", "hi"}):
        return (
            f"Hello {session.username}. You are currently in the {session.zone} zone. "
            "Ask me about finance access, OTP, SMS alerts, roles, zones, or suspicious behavior."
        )
    if "who am i" in text or "my role" in text or "my zone" in text:
        return (
            f"You are signed in as {session.username} with role {session.role}. "
            f"Your home zone is {session.zone}."
        )
    if "finance" in text or "billing" in text or "accounting" in text:
        if session.role.startswith("finance_") or session.role == "super_admin":
            return (
                "Finance resources are isolated inside the finance zone. "
                "Your current role is allowed to reach that zone, so finance access can be granted when the requested action is permitted."
            )
        return (
            "Finance pages, airtime, and accounting systems are isolated in the finance zone. "
            "Normal users are denied because cross-zone movement into finance is not allowed for their role."
        )
    if "sms" in text or "otp" in text or "verification" in text:
        latest_otp = app.latest_otp_for(session.username)
        otp_hint = ""
        if latest_otp is not None:
            otp_hint = " Your latest OTP is already visible in the SMS inbox panel for this demo."
        return (
            "SMS is used for three security actions here: OTP verification during login, suspicious-login alerts, and account-lock notifications."
            + otp_hint
        )
    if "why" in text.lower() and "blocked" in text.lower():
        return "You were blocked because:\n\nLogin from new location 🌍\n5 rapid requests detected ⚠️\nRisk score exceeded threshold 🚨"
    if (
        "suspicious" in text
        or "attack" in text
        or "behavior" in text
        or "blocked" in text
    ):
        blocked = app._detector.is_blocked(session.username)
        if blocked:
            return (
                "You are currently blocked due to suspicious behavior. "
                "Reasons include: Login from new location 🌍, rapid requests ⚠️, and risk score exceeded 🚨. "
                "Confirm via USSD to restore access."
            )
        return (
            "Suspicious login detected 🚨: System blocks access (micro-segmentation), sends SMS alert 📩, user confirms via USSD 📱, and I explain what happened 💬. "
            "This demonstrates how lateral movement is contained in the demo."
        )
    if "role" in text or "roles" in text or "permission" in text:
        return (
            "Roles define which zones and actions are allowed. "
            "super_admin can cross all zones, finance roles stay focused on finance, support_agent stays in users, and end_user is limited to user-facing services."
        )
    if "zone" in text or "zones" in text or "segment" in text:
        return (
            "The system has three zones: admin for privileged tooling, finance for payment and billing systems, and users for chat, SMS, USSD, and voice services. "
            "Identities and APIs are pinned to these zones to enforce isolation."
        )
    if "api" in text or "apis" in text or "service" in text:
        return (
            "API placement is zone-based: Insights is in admin, Airtime is in finance, and Chat, SMS, USSD, and Voice are in the users zone. "
            "Cross-zone access only works when the role policy explicitly allows it."
        )
    if "login" in text or "authentication" in text or "password" in text:
        return (
            "Login happens in two steps: username/password first, then OTP verification by SMS. "
            "Failed logins trigger alerts, and repeated failures can lock the account."
        )
    if "chat" in text or "bot" in text or "chatbot" in text:
        return "This chat page is a users-zone assistant. It answers questions about the security model while still enforcing the same access policy as the rest of the demo."
    if "log" in text or "history" in text or "recent access" in text:
        if latest_log is None:
            return "There is no recent access history yet for your account. Open a protected page first, then ask again."
        return "Your latest recorded access event is: " + format_access_log(latest_log)
    if "what can i ask" in text or "help" in text:
        return "You can ask about finance access, roles, zones, APIs, OTP verification, SMS alerts, suspicious behavior, your current role, or recent access history."
    if "micro-segmentation" in text or "segmentation" in text:
        return (
            "Micro-segmentation breaks the environment into smaller trusted zones and restricts identities to approved paths. "
            "In this demo that means users cannot drift into finance or admin unless policy explicitly allows it."
        )
    if "demo" in text or "example" in text:
        return "This demo shows browser login with SMS OTP, zone-based page protection, suspicious-behavior blocking, and a chatbot page that explains the model."
    return "I can answer questions about zones, roles, finance access, APIs, OTP and SMS alerts, suspicious behavior, your current account, or recent access history."


def chat_view(session: Session) -> str:
    history = CHAT_HISTORY.setdefault(
        session.username,
        [
            (
                "bot",
                "Welcome to the secure chat assistant. Ask a question and I will answer using the rules and activity in this demo, including zones, roles, finance access, OTP, SMS alerts, and suspicious behavior.",
            )
        ],
    )
    transcript = []
    for author, message in history:
        if author == "user":
            transcript.append(f'<div class="bubble user">{html.escape(message)}</div>')
        elif author == "system":
            transcript.append(
                f'<div class="bubble system">{html.escape(message)}</div>'
            )
        else:
            transcript.append(
                f'<div class="bubble bot"><strong>Assistant</strong>{html.escape(message)}</div>'
            )
    body = f"""
    <div class="chat-shell">
      <section class="chat-stage">
        <div class="chat-topbar">
          <div class="chat-title">
            <div class="chat-orb"></div>
            <div>
              <h1 style="margin:0;font-size:1.5rem;">Secure Chat Console</h1>
              <div style="opacity:0.9;">User: {html.escape(session.username)} | Zone: {html.escape(session.zone)} | {APP_BUILD}</div>
            </div>
          </div>
          <a class="button secondary" href="/dashboard">Back</a>
        </div>
        <div class="chat-log">
          {"".join(transcript)}
          <div class="bubble bot typing-indicator" id="typing-indicator"><span></span><span></span><span></span></div>
        </div>
        <div class="chat-composer" style="padding-bottom:0;">
          <div class="composer-top">
            <div class="chat-status" id="chat-status">Ask anything. Older chats stay visible, but the assistant only uses recent context.</div>
            <div class="chat-toolbar">
              <form method="post" action="/clear-chat" style="display:inline">
                <button class="button secondary" type="submit">Clear Chat</button>
              </form>
            </div>
          </div>
        </div>
        <form class="chat-composer" id="chat-form" method="post" action="/chat-message">
          <label>Message
            <textarea name="message" placeholder="Ask a question like: Why am I denied finance access? How does OTP work? What is my role?" required></textarea>
          </label>
          <div class="chip-row">
            <button class="chip" type="button" data-quick-message="Why is finance access restricted?">Why is finance access restricted?</button>
            <button class="chip" type="button" data-quick-message="How does SMS OTP work here?">How does SMS OTP work here?</button>
            <button class="chip" type="button" data-quick-message="What happens during suspicious behavior?">What happens during suspicious behavior?</button>
            <button class="chip" type="button" data-quick-message="What are the security zones?">What are the security zones?</button>
            <button class="chip" type="button" data-quick-message="Explain user roles">Explain user roles</button>
            <button class="chip" type="button" data-quick-message="How does micro-segmentation work?">How does micro-segmentation work?</button>
          </div>
          <div class="actions">
            <button type="submit">Send Message</button>
          </div>
        </form>
      </section>
      <aside class="side-stack">
        <div class="card">
          <h2>Chat Status</h2>
          <p class="meta">This page behaves like a chatbot while still honoring the same zone-based access policy. Previous chats remain on screen, but follow-up logic only uses the latest part of the conversation.</p>
          <div class="banner allow">Access granted to chat_page.</div>
        </div>
        <div class="card">
          <h2>Suggested Topics</h2>
          <div class="insight-list">
            <div class="insight-item">Ask about why some users are denied finance access.</div>
            <div class="insight-item">Ask how SMS OTP and account-lock alerts work.</div>
            <div class="insight-item">Ask for your current role, zone, or recent access history.</div>
            <div class="insight-item">Ask how APIs and services are divided across zones.</div>
          </div>
        </div>
        <div class="card">
          <h2>SMS Inbox</h2>
          <div class="grid">
            {sms_inbox_view(session.username)}
          </div>
        </div>
      </aside>
    </div>
    """
    return page_template("Chat Page", body)


class MicroSegmentationHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            message = parse_qs(parsed.query).get("message", [""])[0]
            self._send_html(login_view(message=message))
            return
        if parsed.path == "/dashboard":
            session = self._require_session()
            if session is None:
                return
            message = parse_qs(parsed.query).get("message", [""])[0]
            status = parse_qs(parsed.query).get("status", [""])[0]
            self._send_html(dashboard_view(session, message, status))
            return
        if parsed.path == "/finance":
            ajax = parse_qs(parsed.query).get("ajax", [""])[0] == "yes"
            if ajax:
                session = self._require_session()
                if session is None:
                    return
                outcome = APP.access_page(session, "finance_page")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"decision": outcome.decision.value, "message": outcome.message}
                    ).encode("utf-8")
                )
            else:
                self._serve_protected_page("finance_page", "Finance Page")
            return
        if parsed.path == "/chat":
            ajax = parse_qs(parsed.query).get("ajax", [""])[0] == "yes"
            if ajax:
                session = self._require_session()
                if session is None:
                    return
                outcome = APP.access_page(session, "chat_page")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"decision": outcome.decision.value, "message": outcome.message}
                    ).encode("utf-8")
                )
            else:
                self._serve_chat_page()
            return
        if parsed.path == "/ussd":
            ajax = parse_qs(parsed.query).get("ajax", [""])[0] == "yes"
            if ajax:
                session = self._require_session()
                if session is None:
                    return
                outcome = APP.access_page(session, "ussd_page")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"decision": outcome.decision.value, "message": outcome.message}
                    ).encode("utf-8")
                )
            else:
                self._serve_protected_page("ussd_page", "USSD Page")
            return
        if parsed.path == "/api/sms-inbox":
            session = self._require_session()
            if session is None:
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(sms_inbox_view(session.username).encode("utf-8"))
            return
        if parsed.path == "/api/security-status":
            session = self._require_session()
            if session is None:
                return
            blocked = APP._detector.is_blocked(session.username)
            risk_score = 82 if blocked else 18
            risk_color = "🔴 High" if risk_score > 50 else "🟢 Low"
            status = "Restricted" if blocked else "Normal"
            reason = (
                "Suspicious location + rapid access attempts" if blocked else "None"
            )
            data = {
                {
                    "risk_score": risk_score,
                    "risk_color": risk_color,
                    "status": status,
                    "reason": reason,
                }
            }
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return
            session = self._require_session()
            if session is None:
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(sms_inbox_view(session.username).encode("utf-8"))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Page not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/login":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            password = fields.get("password", [""])[0]
            suspicious_location = fields.get("suspicious_location", [""])[0] == "on"
            outcome = APP.begin_login(username, password, suspicious_location)
            if outcome.status == LoginStatus.OTP_REQUIRED:
                PENDING_LOGIN_USERS.add(username)
                self._send_html(
                    login_view(
                        "OTP sent by SMS. Enter it below to finish login.",
                        pending_user=username,
                    )
                )
                return
            if outcome.status == LoginStatus.LOCKED:
                PENDING_LOGIN_USERS.discard(username)
                self._send_html(
                    login_view(
                        "Account locked. Check the SMS inbox for the notification.",
                        pending_user="",
                    ),
                    status=HTTPStatus.UNAUTHORIZED,
                )
                return
            if outcome.status == LoginStatus.DENIED:
                self._send_html(
                    login_view(
                        "Invalid credentials. Check the SMS inbox for the security alert.",
                        pending_user=username,
                    ),
                    status=HTTPStatus.UNAUTHORIZED,
                )
                return
            self._send_html(
                login_view("Unexpected login state."), status=HTTPStatus.BAD_REQUEST
            )
            return

        if parsed.path == "/verify-otp":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            otp_code = fields.get("otp_code", [""])[0]
            outcome = APP.verify_otp(username, otp_code)
            if outcome.status != LoginStatus.SUCCESS or outcome.session is None:
                locked_user = "" if outcome.status == LoginStatus.LOCKED else username
                self._send_html(
                    login_view(outcome.message, pending_user=locked_user),
                    status=HTTPStatus.UNAUTHORIZED,
                )
                return

            token = secrets.token_hex(16)
            SESSIONS[token] = outcome.session
            PENDING_LOGIN_USERS.discard(username)
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/dashboard")
            self.send_header(
                "Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; Path=/"
            )
            self.end_headers()
            return

        if parsed.path == "/approve-admin-finance":
            session = self._require_session()
            if session and session.role == "super_admin":
                APP.approved_admin_finance.add(session.username)
                self._redirect(
                    "/dashboard?message=Finance+access+approved+for+admin.&status=allow"
                )
            return

        if parsed.path == "/simulate-suspicious":
            session = self._require_session()
            if session is None:
                return
            APP.simulate_suspicious_behavior(session.username)
            self._redirect(
                "/dashboard?message=Suspicious+behavior+simulated.+User+is+now+blocked.&status=deny"
            )
            return

        if parsed.path == "/reset-demo":
            APP.reset_demo_state()
            SESSIONS.clear()
            PENDING_LOGIN_USERS.clear()
            CHAT_HISTORY.clear()
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header(
                "Location", "/?message=Demo+state+reset.+All+users+are+unlocked."
            )
            self.send_header(
                "Set-Cookie", f"{SESSION_COOKIE}=deleted; Max-Age=0; Path=/"
            )
            self.end_headers()
            return

        if parsed.path == "/chat-message":
            session = self._require_session()
            if session is None:
                return
            outcome = APP.access_page(session, "chat_page", action="read")
            if outcome.decision.value != "allow":
                self._send_html(
                    resource_view("Chat Page", outcome.message, False),
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            fields = self._read_form()
            message = fields.get("message", [""])[0].strip()
            ajax = fields.get("ajax", [""])[0]
            if message:
                history = CHAT_HISTORY.setdefault(session.username, [])
                history.append(("user", message))
                bot_reply = chat_reply_for(session, message, APP, history[:-1])
                history.append(("bot", bot_reply))
                if ajax == "yes":
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(
                            {
                                "user": html.escape(message),
                                "bot": "<strong>Assistant</strong>"
                                + html.escape(bot_reply),
                            }
                        ).encode("utf-8")
                    )
                    return
            self._redirect("/chat")
            return

        if parsed.path == "/clear-chat":
            session = self._require_session()
            if session is None:
                return
            CHAT_HISTORY[session.username] = [
                (
                    "system",
                    "Chat reset. Start a new conversation with the assistant.",
                ),
                (
                    "bot",
                    "I am ready again. Ask about your role, zones, finance access, OTP, SMS alerts, or recent activity.",
                ),
            ]
            self._redirect("/chat")
            return

        if parsed.path == "/confirm-suspicious":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            if username:
                APP._detector._blocked_users.discard(username)
                APP._failed_logins[username] = 0
                session = self._require_session()
                if session and session.username == username:
                    self._redirect(
                        "/dashboard?message=Access+restored.+Check+SMS+inbox+and+chatbot.&status=allow"
                    )
                else:
                    self._redirect("/?message=Access+restored.+Try+logging+in+again.")
            else:
                self._redirect("/")
            return
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            if username == session.username:
                APP._detector._blocked_users.discard(username)
                self._redirect(
                    "/dashboard?message=Access+restored.+Check+SMS+inbox+and+chatbot.&status=allow"
                )
            else:
                self._redirect("/ussd")
            return

        if parsed.path == "/logout":
            token = self._session_token()
            if token:
                SESSIONS.pop(token, None)
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie", f"{SESSION_COOKIE}=deleted; Max-Age=0; Path=/"
            )
            self.end_headers()
            return

        if parsed.path == "/request-ussd-otp":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            if username and username in APP._identities:
                ussd_otp = f"{secrets.randbelow(1000000):06d}"
                APP._pending_ussd_otps[username] = ussd_otp
                APP._sms_alerts.send(
                    username,
                    APP._identities[username].phone_number,
                    "ussd_otp",
                    f"Your USSD confirmation code is {ussd_otp}.",
                )
                self._redirect(
                    f"/?message=USSD+confirmation+code+sent+by+SMS.&pending_user={username}"
                )
            else:
                self._redirect("/")
            return

        if parsed.path == "/ussd-approve":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            if username:
                APP._detector._blocked_users.discard(username)
                # After approve, send OTP for login
                identity = APP._identities.get(username)
                if identity:
                    otp_code = f"{secrets.randbelow(1000000):06d}"
                    APP._pending_otps[username] = otp_code
                    APP._sms_alerts.send(
                        identity.username,
                        identity.phone_number,
                        "otp",
                        f"Your verification OTP is {otp_code}.",
                    )
                    PENDING_LOGIN_USERS.add(username)
                    self._redirect(
                        f"/?message=Approved.+OTP+sent+by+SMS.+Enter+it+below.&pending_user={username}"
                    )
                else:
                    self._redirect("/")
            else:
                self._redirect("/")
            return

        if parsed.path == "/ussd-deny":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            if username:
                # Keep blocked, perhaps send SMS
                identity = APP._identities.get(username)
                if identity:
                    APP._sms_alerts.send(
                        identity.username,
                        identity.phone_number,
                        "access_denied",
                        "Access denied from suspicious location.",
                    )
                self._redirect(
                    f"/?message=Denied.+Access+remains+blocked.&pending_user={username}"
                )
            else:
                self._redirect("/")
            return

        if parsed.path == "/verify-ussd-otp":
            fields = self._read_form()
            username = fields.get("username", [""])[0]
            ussd_code = fields.get("ussd_code", [""])[0]
            expected = APP._pending_ussd_otps.get(username)
            if expected and expected == ussd_code:
                APP._pending_ussd_otps.pop(username, None)
                APP._detector._blocked_users.discard(username)
                APP._failed_logins[username] = 0
                self._redirect("/?message=Confirmed.+Try+logging+in+again.")
            else:
                self._redirect(f"/?message=Invalid+USSD+code.&pending_user={username}")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Page not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _serve_protected_page(self, page: str, title: str) -> None:
        session = self._require_session()
        if session is None:
            return
        outcome = APP.access_page(session, page)
        if outcome.decision != Decision.ALLOW:
            self._send_html(
                resource_view(title, outcome.message, False),
                status=HTTPStatus.FORBIDDEN,
            )
        else:
            if page == "ussd_page":
                if APP._detector.is_blocked(session.username):
                    self._send_html(ussd_confirmation_view(session))
                else:
                    self._send_html(ussd_interface_view(session))
            elif page == "finance_page":
                self._send_html(finance_view(session))
            else:
                self._send_html(resource_view(title, outcome.message, True))

    def _serve_chat_page(self) -> None:
        session = self._require_session()
        if session is None:
            return
        outcome = APP.access_page(session, "chat_page")
        if outcome.decision.value != "allow":
            self._send_html(
                resource_view("Chat Page", outcome.message, False),
                status=HTTPStatus.FORBIDDEN,
            )
            return
        self._send_html(chat_view(session))

    def _require_session(self) -> Session | None:
        token = self._session_token()
        session = SESSIONS.get(token) if token else None
        if session is None:
            self._redirect("/")
            return None
        return session

    def _session_token(self) -> str | None:
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _read_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8")
        return parse_qs(payload)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), MicroSegmentationHandler)
    print(f"Open http://{host}:{port} in your browser")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
