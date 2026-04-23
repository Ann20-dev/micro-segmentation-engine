# Micro-Segmentation Engine

A small Python policy engine that demonstrates micro-segmentation across three security zones and the following talking APIs:

- `SMS`
- `USSD`
- `Airtime`
- `Voice`
- `Insights`
- `Chat`

The engine enforces strict role-based access so that:

- each identity is pinned to a home zone
- each API is pinned to a specific zone
- cross-zone access must be explicitly allowed
- compromised accounts have limited lateral movement
- SMS is used for security alerts and OTP verification

## Security Model

### Zones

- `admin`: privileged systems and administrative tooling
- `finance`: payment, billing, airtime, and accounting systems
- `users`: user-facing applications and communications services

### API Placement

- `Insights` is segmented into `admin`
- `Airtime` is segmented into `finance`
- `SMS`, `USSD`, `Voice`, and `Chat` are segmented into `users`

### SMS Security Use Cases

- suspicious login detected: send SMS alert to the user
- account locked after repeated failed logins: send SMS notification
- successful password check: send OTP by SMS before browser login completes

### Roles

- `super_admin`: full administrative access across all zones
- `admin_operator`: administrative access limited to the `admin` zone
- `finance_analyst`: finance access limited to the `finance` zone
- `finance_auditor`: read-only finance access
- `support_agent`: operational access limited to the `users` zone
- `end_user`: self-service access limited to the `users` zone

## Files

- `segmentation_engine.py`: policy model and access enforcement
- `test_segmentation_engine.py`: tests that verify isolation and limited movement

## Run

```powershell
python main.py
```

To run it in your browser:

```powershell
python web_app.py
```

Then open `http://127.0.0.1:8000` in your browser.

Browser login flow:

1. Enter username and password.
2. Read the OTP from the local SMS inbox shown on the login page.
3. Submit the OTP to complete login.
4. Open `Finance Page` or simulate suspicious behavior and review the SMS inbox updates.

Default browser demo user:

- `normal_user` / `user123` / `0711731098`
- `finance_user` / `finance123` / `0711731098`
- `admin_user` / `admin123` / `0711731098`

To run the tests:

```powershell
python -m unittest -v
```

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
