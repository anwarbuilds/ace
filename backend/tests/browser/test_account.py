"""Tests for account management from inside the app.

These exist so a password can be changed on a deployed instance
without SSH, and the guards around that are the point: reaching an
open browser must not be enough to take the account over.
"""


def _post(
    page,
    path: str,
    body: str,
):
    """POST JSON from the page, so it carries the session cookie."""

    return page.eval(
        "fetch('" + path + "',{method:'POST',"
        "headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify(" + body + "),cache:'no-store'})"
        ".then(function(r){return r.json().then(function(d){"
        "return JSON.stringify({status:r.status,body:d});});})"
    )


def test_the_settings_page_shows_who_is_signed_in(
    page,
) -> None:
    page.eval(
        "goTo('settings');1"
    )

    page.wait_for(
        "!!document.querySelector('.acct-grid')"
    )

    assert page.eval(
        "!!(state.account && state.account.email)"
    ), "the signed-in account was never loaded"

    # Rendered, not merely fetched: the address is in the row above
    # the forms, not inside the grid that holds them.
    shown = page.eval(
        "document.querySelector('.acct-grid')"
        ".closest('.sect').innerText"
    )

    assert state_email(
        page
    ) in shown, shown


def state_email(
    page,
) -> str:
    return page.eval(
        "state.account.email"
    )


def test_a_password_change_needs_the_current_password(
    page,
) -> None:
    """A session is not proof of knowing the password.

    A borrowed laptop is enough to have one, so without this anyone
    reaching an open browser could lock the owner out of their own
    account.
    """

    import json

    result = json.loads(
        _post(
            page,
            "/api/account/password",
            "{current_password:'definitely-wrong',"
            "new_password:'a-perfectly-long-one'}",
        )
    )

    assert result["status"] == 403
    assert "incorrect" in result["body"]["detail"].lower()


def test_a_short_password_is_refused(
    page,
) -> None:
    """Length is the only rule, so it has to actually be enforced."""

    import json

    result = json.loads(
        _post(
            page,
            "/api/account/password",
            "{current_password:'whatever',new_password:'short'}",
        )
    )

    assert result["status"] == 400
    assert "12" in result["body"]["detail"]


def test_an_email_change_needs_the_current_password(
    page,
) -> None:
    """An address is where a password reset goes, so changing it is a
    credential change and is guarded like one."""

    import json

    result = json.loads(
        _post(
            page,
            "/api/account/email",
            "{current_password:'definitely-wrong',"
            "new_email:'attacker@example.com'}",
        )
    )

    assert result["status"] == 403


def test_a_malformed_email_is_refused(
    page,
) -> None:
    import json

    result = json.loads(
        _post(
            page,
            "/api/account/email",
            "{current_password:'whatever',new_email:'notanemail'}",
        )
    )

    assert result["status"] == 400
