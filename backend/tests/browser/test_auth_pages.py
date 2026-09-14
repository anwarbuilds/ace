"""Tests for the sign-in surface.

These pages are the only thing an unauthenticated visitor can reach, so
what they say, and what they refuse to say, is the whole security
boundary of a deployed instance.
"""

import urllib.error
import urllib.parse
import urllib.request

from .conftest import APP_URL


def _get(
    path: str,
) -> tuple[int, str]:
    """Fetch a page without following redirects or signing in."""

    class _NoRedirect(
        urllib.request.HTTPRedirectHandler,
    ):
        def redirect_request(
            self,
            *args,
            **kwargs,
        ):
            return None

    opener = urllib.request.build_opener(
        _NoRedirect(),
    )

    try:
        with opener.open(
            APP_URL + path,
            timeout=10,
        ) as response:
            return response.status, response.read().decode(
                "utf-8",
                "replace",
            )
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(
            "utf-8",
            "replace",
        )


def _post(
    path: str,
    fields: dict,
) -> tuple[int, str]:
    class _NoRedirect(
        urllib.request.HTTPRedirectHandler,
    ):
        def redirect_request(
            self,
            *args,
            **kwargs,
        ):
            return None

    opener = urllib.request.build_opener(
        _NoRedirect(),
    )

    request = urllib.request.Request(
        APP_URL + path,
        data=urllib.parse.urlencode(
            fields,
        ).encode(),
        method="POST",
    )

    try:
        with opener.open(
            request,
            timeout=10,
        ) as response:
            return response.status, response.read().decode(
                "utf-8",
                "replace",
            )
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(
            "utf-8",
            "replace",
        )


def test_the_sign_in_page_offers_a_way_to_recover(
    browser,
) -> None:
    """A sign-in page with no way forward is half a page."""

    status, body = _get(
        "/login",
    )

    assert status == 200
    assert '/forgot' in body


def test_the_sign_in_page_renders_one_heading(
    browser,
) -> None:
    """The shared shell emitted a stray heading outside the card, so
    the page rendered an extra "ACE" floating beside it."""

    _, body = _get(
        "/login",
    )

    assert body.count(
        "<h1>ACE</h1>",
    ) == 1


def test_registration_is_closed_once_an_account_exists(
    browser,
) -> None:
    """A register form is a door. It is open exactly long enough to
    make the first account on a fresh deployment."""

    status, body = _get(
        "/register",
    )

    assert status == 403
    assert "closed" in body.lower()

    # And the closed door is not advertised on the sign-in page.
    _, login = _get(
        "/login",
    )

    assert '/register' not in login


def test_registration_is_refused_on_post_too(
    browser,
) -> None:
    """Not only when rendering the form.

    A form left open in a tab must not be able to create the second
    account after the first one exists.
    """

    status, _ = _post(
        "/register",
        {
            "email": "intruder@example.com",
            "password": "a-long-enough-password",
        },
    )

    assert status in (
        303,
        403,
    )

    # Whatever it answered, the account does not exist. Checked
    # through the front door rather than the database, because that is
    # the thing an attacker would actually try next.
    login_status, _ = _post(
        "/login",
        {
            "email": "intruder@example.com",
            "password": "a-long-enough-password",
        },
    )

    assert login_status == 401


def test_the_reset_form_does_not_say_who_has_an_account(
    browser,
) -> None:
    """Otherwise it is a way to ask which addresses are registered
    here, which is exactly what an attacker wants to know first."""

    known_status, known = _post(
        "/forgot",
        {
            "email": "sohailshaik275@gmail.com",
        },
    )

    unknown_status, unknown = _post(
        "/forgot",
        {
            "email": "definitely-nobody@example.com",
        },
    )

    assert known_status == unknown_status
    assert known == unknown


def test_a_junk_reset_link_is_refused(
    browser,
) -> None:
    status, body = _get(
        "/reset?token=not-a-real-token",
    )

    assert status == 400
    assert "not valid" in body.lower()
