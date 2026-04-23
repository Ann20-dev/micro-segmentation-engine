import unittest

from segmentation_engine import (
    AccessRequest,
    Decision,
    LoginStatus,
    default_app,
    default_policy,
)
from web_app import chat_reply_for


class SegmentationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = default_policy()

    def test_admin_operator_is_confined_to_admin_zone(self) -> None:
        request = AccessRequest(
            subject="ops-admin",
            role="admin_operator",
            source_zone="admin",
            target_zone="finance",
            action="read",
            resource="airtime",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)

    def test_finance_analyst_cannot_reach_admin_zone(self) -> None:
        request = AccessRequest(
            subject="alice",
            role="finance_analyst",
            source_zone="finance",
            target_zone="admin",
            action="read",
            resource="insights",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)

    def test_finance_analyst_can_reach_users_zone_for_chat(self) -> None:
        request = AccessRequest(
            subject="alice",
            role="finance_analyst",
            source_zone="finance",
            target_zone="users",
            action="read",
            resource="chat",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.ALLOW)

    def test_finance_auditor_is_read_only(self) -> None:
        request = AccessRequest(
            subject="auditor",
            role="finance_auditor",
            source_zone="finance",
            target_zone="finance",
            action="write",
            resource="airtime",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)

    def test_end_user_cannot_escalate_by_targeting_finance(self) -> None:
        request = AccessRequest(
            subject="eve",
            role="end_user",
            source_zone="users",
            target_zone="finance",
            action="read",
            resource="airtime",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)

    def test_compromised_support_account_cannot_spoof_admin_origin(self) -> None:
        request = AccessRequest(
            subject="mallory",
            role="support_agent",
            source_zone="admin",
            target_zone="admin",
            action="read",
            resource="insights",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)

    def test_super_admin_can_cross_zones_when_explicitly_authorized(self) -> None:
        request = AccessRequest(
            subject="root-admin",
            role="super_admin",
            source_zone="admin",
            target_zone="finance",
            action="approve",
            resource="airtime",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.ALLOW)

    def test_legitimate_user_access_in_home_zone_is_allowed(self) -> None:
        request = AccessRequest(
            subject="bob",
            role="end_user",
            source_zone="users",
            target_zone="users",
            action="read",
            resource="chat",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.ALLOW)

    def test_support_agent_can_send_sms_in_users_zone(self) -> None:
        request = AccessRequest(
            subject="carol",
            role="support_agent",
            source_zone="users",
            target_zone="users",
            action="write",
            resource="sms",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.ALLOW)

    def test_end_user_cannot_administer_insights_service(self) -> None:
        request = AccessRequest(
            subject="dave",
            role="end_user",
            source_zone="users",
            target_zone="admin",
            action="admin",
            resource="insights",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)

    def test_unknown_service_is_denied(self) -> None:
        request = AccessRequest(
            subject="erin",
            role="super_admin",
            source_zone="admin",
            target_zone="admin",
            action="read",
            resource="email",
        )

        self.assertEqual(self.policy.evaluate(request), Decision.DENY)


class MicroSegmentationAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = default_app()

    def test_normal_user_is_denied_finance_page(self) -> None:
        session = self.app.login("normal_user", "user123")

        self.assertIsNotNone(session)
        outcome = self.app.access_page(session, "finance_page")
        self.assertEqual(outcome.decision, Decision.DENY)
        self.assertEqual(outcome.message, "Access denied to finance_page.")

    def test_finance_user_is_granted_finance_page(self) -> None:
        session = self.app.login("finance_user", "finance123")

        self.assertIsNotNone(session)
        outcome = self.app.access_page(session, "finance_page")
        self.assertEqual(outcome.decision, Decision.ALLOW)
        self.assertEqual(outcome.message, "Access granted to finance_page.")

    def test_suspicious_behavior_blocks_access(self) -> None:
        session = self.app.login("finance_user", "finance123")

        self.assertIsNotNone(session)
        self.app.simulate_suspicious_behavior("finance_user")
        outcome = self.app.access_page(session, "finance_page")
        self.assertEqual(outcome.decision, Decision.DENY)
        self.assertEqual(
            outcome.message, "Suspicious behavior detected. Access blocked."
        )

    def test_blocked_user_cannot_login_again(self) -> None:
        self.app.simulate_suspicious_behavior("normal_user")

        session = self.app.login("normal_user", "user123")
        self.assertIsNone(session)

    def test_suspicious_login_sends_sms_alert(self) -> None:
        session = self.app.login("normal_user", "wrong-password")

        self.assertIsNone(session)
        latest_alert = self.app.sms_alerts_for("normal_user")[-1]
        self.assertEqual(latest_alert.category, "security_alert")
        self.assertIn("Suspicious login detected", latest_alert.message)

    def test_account_lock_sends_sms_notification(self) -> None:
        for _ in range(3):
            self.app.login("normal_user", "wrong-password")

        latest_alert = self.app.sms_alerts_for("normal_user")[-1]
        self.assertEqual(latest_alert.category, "account_lock")
        self.assertIn("Account locked", latest_alert.message)

    def test_begin_login_sends_otp_sms(self) -> None:
        outcome = self.app.begin_login("finance_user", "finance123")

        self.assertEqual(outcome.status, LoginStatus.OTP_REQUIRED)
        latest_otp = self.app.latest_otp_for("finance_user")
        self.assertIsNotNone(latest_otp)
        self.assertEqual(latest_otp.category, "otp")
        self.assertIn("verification OTP", latest_otp.message)

    def test_verify_otp_completes_login(self) -> None:
        outcome = self.app.begin_login("finance_user", "finance123")

        self.assertEqual(outcome.status, LoginStatus.OTP_REQUIRED)
        otp_alert = self.app.latest_otp_for("finance_user")
        otp_code = otp_alert.message.split(" is ")[1].split(".")[0]
        verified = self.app.verify_otp("finance_user", otp_code)

        self.assertEqual(verified.status, LoginStatus.SUCCESS)
        self.assertIsNotNone(verified.session)

    def test_reset_demo_state_unlocks_users_and_clears_alerts(self) -> None:
        for _ in range(3):
            self.app.login("normal_user", "wrong-password")

        self.assertTrue(self.app.sms_alerts_for("normal_user"))
        self.app.reset_demo_state()
        self.assertEqual(self.app.sms_alerts_for("normal_user"), [])

        session = self.app.login("normal_user", "user123")
        self.assertIsNotNone(session)

    def test_sms_inbox_is_scoped_per_user_even_with_shared_phone_number(self) -> None:
        self.app.login("normal_user", "wrong-password")
        self.app.begin_login("finance_user", "finance123")

        normal_alerts = self.app.sms_alerts_for("normal_user")
        finance_alerts = self.app.sms_alerts_for("finance_user")

        self.assertTrue(all("normal_user" in alert.message for alert in normal_alerts))
        self.assertTrue(any(alert.category == "otp" for alert in finance_alerts))
        self.assertTrue(all("normal_user" not in alert.message for alert in finance_alerts if alert.category != "otp"))

    def test_chat_reply_explains_current_role(self) -> None:
        session = self.app.login("normal_user", "user123")

        self.assertIsNotNone(session)
        reply = chat_reply_for(session, "What is my role and zone?", self.app)
        self.assertIn("normal_user", reply)
        self.assertIn("end_user", reply)
        self.assertIn("users", reply)

    def test_chat_reply_uses_recent_access_history(self) -> None:
        session = self.app.login("normal_user", "user123")

        self.assertIsNotNone(session)
        self.app.access_page(session, "finance_page")
        reply = chat_reply_for(session, "Show my recent access log", self.app)
        self.assertIn("latest recorded access event", reply)
        self.assertIn("airtime", reply)

    def test_chat_reply_uses_previous_topic_for_follow_up_question(self) -> None:
        session = self.app.login("normal_user", "user123")

        self.assertIsNotNone(session)
        history = [("user", "How does SMS OTP work here?"), ("bot", "placeholder")]
        reply = chat_reply_for(session, "Explain that more", self.app, history)
        self.assertIn("SMS is used for three security actions", reply)

    def test_chat_reply_ignores_stale_topics_outside_recent_context_window(self) -> None:
        session = self.app.login("normal_user", "user123")

        self.assertIsNotNone(session)
        history = [
            ("user", "How does SMS OTP work here?"),
            ("bot", "placeholder"),
            ("user", "hello"),
            ("bot", "placeholder"),
            ("user", "hello again"),
            ("bot", "placeholder"),
            ("user", "still here"),
            ("bot", "placeholder"),
            ("user", "checking in"),
            ("bot", "placeholder"),
            ("user", "new topic soon"),
            ("bot", "placeholder"),
            ("user", "random question"),
            ("bot", "placeholder"),
        ]
        reply = chat_reply_for(session, "Explain that more", self.app, history)
        self.assertNotIn("SMS is used for three security actions", reply)


if __name__ == "__main__":
    unittest.main()
