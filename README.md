# 🔐 Micro-Segmentation Engine

> Zero-trust access control for telecom APIs with SMS-based security alerts

## The Problem

Traditional network security assumes everything inside the perimeter is trusted. But in a world of breaches and lateral movement, that's a dangerous assumption. This project demonstrates **micro-segmentation** — a security architecture where every API call is explicitly verified, regardless of where it originates.

## What This Project Does

This is a **Python policy engine** that enforces zero-trust access control across three security zones:

| Zone | Purpose | APIs |
|------|---------|------|
| `admin` | Privileged systems & admin tooling | Insights |
| `finance` | Payment, billing & accounting | — |
| `users` | User-facing communications | SMS, USSD, Chat |

### Key Security Features

- **Identity pinning** — each user is locked to their home zone
- **API isolation** — services can only be accessed from their designated zone
- **Explicit cross-zone access** — movement between zones requires explicit policy
- **Lateral movement containment** — compromised accounts are confined to their zone
- **SMS security alerts** — real-time notifications for:
  - Suspicious login detection
  - Account lockout after failed attempts
  - OTP delivery for multi-factor authentication

## Architecture Highlights

```
┌─────────────────────────────────────────────────────────────┐
│                     Segmentation Policy                      │
├─────────────────────────────────────────────────────────────┤
│  Role Policies    │  Service Policies   │  Zone Enforcement │
│  ─────────────    │  ────────────────   │  ──────────────── │
│  super_admin      │  SMS  → users       │  Identity → Zone  │
│  admin_operator   │  USSD → users       │  API    → Zone    │
│  finance_analyst  │  Chat → users       │  Cross-zone check │
│  finance_auditor  │                     │                   │
│  support_agent    │                     │                   │
│  end_user         │                     │                   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```powershell
# Run the CLI demo
python main.py

# Launch the web interface
python web_app.py
```

Then open **http://127.0.0.1:8000** in your browser.

### Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| `normal_user` | `user123` | end_user |
| `finance_user` | `finance123` | finance_analyst |
| `admin_user` | `admin123` | admin_operator |

### Browser Demo Flow

1. Login with credentials above
2. Retrieve OTP from the on-page SMS inbox
3. Submit OTP to complete authentication
4. Try accessing pages outside your zone — watch the denial
5. Trigger "suspicious behavior" and see SMS alerts appear

### Run Tests

```powershell
python -m unittest -v
```

## Why This Matters for Hackathons

- ✅ **Real security concept** — micro-segmentation is industry-standard (used by Google, AWS, Azure)
- ✅ **Interactive demo** — tangible web UI shows policy enforcement in action
- ✅ **SMS integration** — demonstrates multi-factor auth & alert workflows
- ✅ **Extensible** — easy to add new roles, zones, or APIs
- ✅ **Python-native** — clean, readable code that's easy to present

## Project Structure

```
├── segmentation_engine.py    # Core policy engine & data models
├── test_segmentation_engine.py  # Unit tests for isolation guarantees
├── main.py                   # CLI demo runner
├── web_app.py                # Web interface with login flow
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

## Tech Stack

- **Python 3.10+** — core engine
- **Flask + Flask-CORS** — web framework
- **Built-in http.server** — no heavy dependencies
- **Vanilla HTML/JS** — simple, portable frontend

---

**Built for security engineers, demonstrated for hackers.** 🚀

## Example

```python
from segmentation_engine import Decision, default_app

app = default_app()

normal_session = app.login("normal_user", "user123")
print(app.access_page(normal_session, "finance_page").decision == Decision.DENY)

finance_session = app.login("finance_user", "finance123")
print(app.access_page(finance_session, "finance_page").decision == Decision.ALLOW)

app.simulate_suspicious_behavior("finance_user")
blocked = app.access_page(finance_session, "finance_page")
print(blocked.message)
```

## Demo Scenarios

- Login as normal user and try `finance_page`: denied
- Login as finance user and try `finance_page`: granted
- Simulate suspicious behavior for a logged-in user: blocked immediately
- Failed logins generate SMS security alerts
- Repeated failed logins trigger an account lock SMS
- Browser logins require an OTP delivered through the local SMS inbox

## Extension Ideas

- connect identities to your real IAM provider
- map resources to workloads, VLANs, subnets, or application services
- enforce MFA, device trust, or time-based controls before privileged access
- export decisions to audit logs or SIEM pipelines
