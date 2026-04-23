from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import secrets


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class LoginStatus(str, Enum):
    SUCCESS = "success"
    OTP_REQUIRED = "otp_required"
    DENIED = "denied"
    LOCKED = "locked"


@dataclass(frozen=True)
class AccessRequest:
    subject: str
    role: str
    source_zone: str
    target_zone: str
    action: str
    resource: str


@dataclass(frozen=True)
class RolePolicy:
    role: str
    home_zone: str
    allowed_actions: frozenset[str]
    reachable_zones: frozenset[str]


@dataclass(frozen=True)
class ServicePolicy:
    service: str
    zone: str
    allowed_actions: frozenset[str]


@dataclass(frozen=True)
class Identity:
    username: str
    password: str
    role: str
    home_zone: str
    phone_number: str


@dataclass(frozen=True)
class Session:
    username: str
    role: str
    zone: str


@dataclass(frozen=True)
class AccessOutcome:
    decision: Decision
    message: str


@dataclass(frozen=True)
class SmsAlert:
    username: str
    recipient: str
    category: str
    message: str


@dataclass(frozen=True)
class AccessLog:
    timestamp: str
    subject: str
    resource: str
    action: str
    decision: str
    message: str


@dataclass(frozen=True)
class LoginOutcome:
    status: LoginStatus
    message: str
    session: Session | None = None


class SegmentationPolicy:
    def __init__(
        self,
        role_policies: dict[str, RolePolicy],
        service_policies: dict[str, ServicePolicy],
    ) -> None:
        self._role_policies = role_policies
        self._service_policies = service_policies

    def evaluate(self, request: AccessRequest) -> Decision:
        role_policy = self._role_policies.get(request.role)
        if role_policy is None:
            return Decision.DENY

        service_policy = self._service_policies.get(request.resource)
        if service_policy is None:
            return Decision.DENY

        # Block spoofed placement: identities may only originate from their assigned zone.
        if request.source_zone != role_policy.home_zone:
            return Decision.DENY

        # APIs are pinned to a specific security segment.
        if request.target_zone != service_policy.zone:
            return Decision.DENY

        if request.target_zone not in role_policy.reachable_zones:
            return Decision.DENY

        if request.action not in role_policy.allowed_actions:
            return Decision.DENY

        if request.action not in service_policy.allowed_actions:
            return Decision.DENY

        return Decision.ALLOW

    def zone_for_service(self, service: str) -> str:
        service_policy = self._service_policies[service]
        return service_policy.zone


class SuspiciousActivityDetector:
    def __init__(self, blocked_users: set[str] | None = None) -> None:
        self._blocked_users = blocked_users or set()

    def flag(self, username: str) -> None:
        self._blocked_users.add(username)

    def is_blocked(self, username: str) -> bool:
        return username in self._blocked_users

    def clear(self) -> None:
        self._blocked_users.clear()


class SmsAlertService:
    def __init__(self) -> None:
        self._alerts: list[SmsAlert] = []

    def send(self, username: str, recipient: str, category: str, message: str) -> None:
        self._alerts.append(
            SmsAlert(
                username=username,
                recipient=recipient,
                category=category,
                message=message,
            )
        )

    def latest_for(
        self, username: str, category: str | None = None
    ) -> SmsAlert | None:
        for alert in reversed(self._alerts):
            if alert.username != username:
                continue
            if category is not None and alert.category != category:
                continue
            return alert
        return None

    def list_for(self, username: str) -> list[SmsAlert]:
        return [alert for alert in self._alerts if alert.username == username]

    def clear(self) -> None:
        self._alerts.clear()


class MicroSegmentationApp:
    def __init__(
        self,
        policy: SegmentationPolicy,
        identities: dict[str, Identity],
        page_to_service: dict[str, str],
        detector: SuspiciousActivityDetector | None = None,
        sms_alerts: SmsAlertService | None = None,
    ) -> None:
        self._policy = policy
        self._identities = identities
        self._page_to_service = page_to_service
        self._detector = detector or SuspiciousActivityDetector()
        self._sms_alerts = sms_alerts or SmsAlertService()
        self._pending_otps: dict[str, str] = {}
        self._failed_logins: dict[str, int] = {}
        self._lock_threshold = 3
        self._access_logs: list[AccessLog] = []

    def login(self, username: str, password: str) -> Session | None:
        identity = self._identities.get(username)
        if identity is None:
            return None

        if identity.password != password:
            self._record_failed_login(identity)
            return None

        if self._detector.is_blocked(username):
            self._notify_account_locked(identity)
            return None

        return Session(
            username=identity.username,
            role=identity.role,
            zone=identity.home_zone,
        )

    def begin_login(self, username: str, password: str) -> LoginOutcome:
        identity = self._identities.get(username)
        if identity is None:
            return LoginOutcome(LoginStatus.DENIED, "Invalid username or password.")

        if self._detector.is_blocked(username):
            self._notify_account_locked(identity)
            return LoginOutcome(
                LoginStatus.LOCKED, "Account locked. SMS notification sent."
            )

        if identity.password != password:
            self._record_failed_login(identity)
            if self._detector.is_blocked(username):
                return LoginOutcome(
                    LoginStatus.LOCKED, "Account locked. SMS notification sent."
                )
            return LoginOutcome(
                LoginStatus.DENIED, "Invalid username or password. SMS alert sent."
            )

        self._failed_logins[username] = 0
        otp_code = f"{secrets.randbelow(1000000):06d}"
        self._pending_otps[username] = otp_code
        self._sms_alerts.send(
            identity.username,
            identity.phone_number,
            "otp",
            f"Your verification OTP is {otp_code}.",
        )
        return LoginOutcome(LoginStatus.OTP_REQUIRED, "OTP sent by SMS.")

    def verify_otp(self, username: str, otp_code: str) -> LoginOutcome:
        identity = self._identities.get(username)
        if identity is None:
            return LoginOutcome(LoginStatus.DENIED, "Invalid OTP request.")

        if self._detector.is_blocked(username):
            self._notify_account_locked(identity)
            return LoginOutcome(
                LoginStatus.LOCKED, "Account locked. SMS notification sent."
            )

        expected = self._pending_otps.get(username)
        if expected is None or expected != otp_code:
            return LoginOutcome(LoginStatus.DENIED, "Invalid OTP.")

        self._pending_otps.pop(username, None)
        session = Session(
            username=identity.username,
            role=identity.role,
            zone=identity.home_zone,
        )
        return LoginOutcome(LoginStatus.SUCCESS, "Login successful.", session=session)

    def access_page(
        self, session: Session, page: str, action: str = "read"
    ) -> AccessOutcome:
        if self._detector.is_blocked(session.username) and page != "chat_page":
            return AccessOutcome(
                Decision.DENY, "Suspicious behavior detected. Access blocked."
            )

        service = self._page_to_service.get(page)
        if service is None:
            return AccessOutcome(Decision.DENY, f"Unknown page: {page}")

        decision = self._policy.evaluate(
            AccessRequest(
                subject=session.username,
                role=session.role,
                source_zone=session.zone,
                target_zone=self._policy.zone_for_service(service),
                action=action,
                resource=service,
            )
        )

        log = AccessLog(
            timestamp=datetime.now().isoformat(),
            subject=session.username,
            resource=service,
            action=action,
            decision=decision.value,
            message=f"Access {'granted' if decision == Decision.ALLOW else 'denied'} to {page}.",
        )
        self._access_logs.append(log)

        if decision == Decision.ALLOW:
            return AccessOutcome(Decision.ALLOW, f"Access granted to {page}.")

        return AccessOutcome(Decision.DENY, f"Access denied to {page}.")

    def simulate_suspicious_behavior(self, username: str) -> None:
        self._detector.flag(username)
        identity = self._identities.get(username)
        if identity is not None:
            self._sms_alerts.send(
                identity.username,
                identity.phone_number,
                "security_alert",
                "Suspicious activity detected on your account. Access has been blocked.",
            )

    def sms_alerts_for(self, username: str) -> list[SmsAlert]:
        identity = self._identities.get(username)
        if identity is None:
            return []
        return self._sms_alerts.list_for(identity.username)

    def latest_otp_for(self, username: str) -> SmsAlert | None:
        identity = self._identities.get(username)
        if identity is None:
            return None
        return self._sms_alerts.latest_for(identity.username, "otp")

    def access_logs_for(self, username: str) -> list[AccessLog]:
        return [log for log in self._access_logs if log.subject == username]

    def reset_demo_state(self) -> None:
        self._detector.clear()
        self._sms_alerts.clear()
        self._pending_otps.clear()
        self._failed_logins.clear()
        self._access_logs.clear()

    def _record_failed_login(self, identity: Identity) -> None:
        attempts = self._failed_logins.get(identity.username, 0) + 1
        self._failed_logins[identity.username] = attempts
        self._sms_alerts.send(
            identity.username,
            identity.phone_number,
            "security_alert",
            f"Suspicious login detected for {identity.username}. Failed attempts: {attempts}.",
        )
        if attempts >= self._lock_threshold:
            self._detector.flag(identity.username)
            self._notify_account_locked(identity)

    def _notify_account_locked(self, identity: Identity) -> None:
        self._sms_alerts.send(
            identity.username,
            identity.phone_number,
            "account_lock",
            f"Account locked for {identity.username}. Contact support to regain access.",
        )


def default_identities() -> dict[str, Identity]:
    return {
        "normal_user": Identity(
            username="normal_user",
            password="user123",
            role="end_user",
            home_zone="users",
            phone_number="0711731098",
        ),
        "finance_user": Identity(
            username="finance_user",
            password="finance123",
            role="finance_analyst",
            home_zone="finance",
            phone_number="0711731098",
        ),
        "admin_user": Identity(
            username="admin_user",
            password="admin123",
            role="super_admin",
            home_zone="admin",
            phone_number="0711731098",
        ),
    }


def default_page_map() -> dict[str, str]:
    return {
        "chat_page": "chat",
        "sms_page": "sms",
        "ussd_page": "ussd",
        "voice_page": "voice",
        "finance_page": "airtime",
        "insights_page": "insights",
    }


def default_app() -> MicroSegmentationApp:
    return MicroSegmentationApp(
        policy=default_policy(),
        identities=default_identities(),
        page_to_service=default_page_map(),
    )


def default_policy() -> SegmentationPolicy:
    return SegmentationPolicy(
        role_policies={
            "super_admin": RolePolicy(
                role="super_admin",
                home_zone="admin",
                allowed_actions=frozenset({"read", "write", "approve", "admin"}),
                reachable_zones=frozenset({"admin", "finance", "users"}),
            ),
            "admin_operator": RolePolicy(
                role="admin_operator",
                home_zone="admin",
                allowed_actions=frozenset({"read", "write", "admin"}),
                reachable_zones=frozenset({"admin"}),
            ),
            "finance_analyst": RolePolicy(
                role="finance_analyst",
                home_zone="finance",
                allowed_actions=frozenset({"read", "write", "approve"}),
                reachable_zones=frozenset({"finance", "users"}),
            ),
            "finance_auditor": RolePolicy(
                role="finance_auditor",
                home_zone="finance",
                allowed_actions=frozenset({"read"}),
                reachable_zones=frozenset({"finance", "users"}),
            ),
            "support_agent": RolePolicy(
                role="support_agent",
                home_zone="users",
                allowed_actions=frozenset({"read", "write"}),
                reachable_zones=frozenset({"users"}),
            ),
            "end_user": RolePolicy(
                role="end_user",
                home_zone="users",
                allowed_actions=frozenset({"read", "write"}),
                reachable_zones=frozenset({"users"}),
            ),
        },
        service_policies={
            "sms": ServicePolicy(
                service="sms",
                zone="users",
                allowed_actions=frozenset({"read", "write"}),
            ),
            "ussd": ServicePolicy(
                service="ussd",
                zone="users",
                allowed_actions=frozenset({"read", "write"}),
            ),
            "airtime": ServicePolicy(
                service="airtime",
                zone="finance",
                allowed_actions=frozenset({"read", "write", "approve"}),
            ),
            "voice": ServicePolicy(
                service="voice",
                zone="users",
                allowed_actions=frozenset({"read", "write"}),
            ),
            "insights": ServicePolicy(
                service="insights",
                zone="admin",
                allowed_actions=frozenset({"read", "admin"}),
            ),
            "chat": ServicePolicy(
                service="chat",
                zone="users",
                allowed_actions=frozenset({"read", "write"}),
            ),
        },
    )
