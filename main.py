from segmentation_engine import default_app


def print_result(title: str, message: str) -> None:
    print(title)
    print(message)
    print()


def main() -> None:
    app = default_app()

    normal_session = app.login("normal_user", "user123")
    if normal_session is None:
        raise SystemExit("Login failed for normal_user.")
    normal_outcome = app.access_page(normal_session, "finance_page")
    print_result(
        "Scenario 1: Login as normal user -> try finance page",
        normal_outcome.message,
    )

    normal_chat_outcome = app.access_page(normal_session, "chat_page")
    print_result(
        "Scenario 1b: Login as normal user -> access chat page",
        normal_chat_outcome.message,
    )

    finance_session = app.login("finance_user", "finance123")
    if finance_session is None:
        raise SystemExit("Login failed for finance_user.")
    finance_outcome = app.access_page(finance_session, "finance_page")
    print_result(
        "Scenario 2: Login as finance user -> access finance page",
        finance_outcome.message,
    )

    finance_chat_outcome = app.access_page(finance_session, "chat_page")
    print_result(
        "Scenario 2b: Login as finance user -> access chat page",
        finance_chat_outcome.message,
    )

    app.simulate_suspicious_behavior("finance_user")
    blocked_outcome = app.access_page(finance_session, "finance_page")
    print_result(
        "Scenario 3: Simulate suspicious behavior -> system blocks access",
        blocked_outcome.message,
    )

    blocked_chat_outcome = app.access_page(finance_session, "chat_page")
    print_result(
        "Scenario 3b: After suspicious behavior -> access chat page",
        blocked_chat_outcome.message,
    )


if __name__ == "__main__":
    main()
