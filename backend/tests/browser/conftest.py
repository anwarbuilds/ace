"""Browser-level fixtures for the ACE client.

Every interface bug reported so far was found by a person looking at the
page: a primary action pushed off screen, a list stuck on skeletons, a
sort that silently did nothing, and a delete that took an unrelated
block of functions with it and left the app rendering nothing at all.
None of the 524 unit tests could have caught any of them, because the
client is one HTML file with no seam to test through.

These drive real Chrome over the DevTools protocol against the running
app. They are skipped, never failed, when Chrome or the server is
absent, so a checkout without either still has a green suite.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import pytest


APP_URL = os.environ.get(
    "ACE_BROWSER_TEST_URL",
    "http://localhost:8000",
)

CHROME_NAMES = (
    "google-chrome",
    "chromium",
    "chromium-browser",
    "google-chrome-stable",
)


def _find_chrome() -> str | None:
    """Return a usable Chrome binary, if one is installed."""

    for name in CHROME_NAMES:
        path = shutil.which(
            name
        )

        if path:
            return path

    return None


def _server_is_up() -> bool:
    """Return whether the app is answering."""

    try:
        with urllib.request.urlopen(
            APP_URL + "/healthz",
            timeout=3,
        ) as response:
            return response.status == 200
    except Exception:
        return False


def _free_port() -> int:
    """Return a port nothing is listening on."""

    with socket.socket() as sock:
        sock.bind(
            (
                "127.0.0.1",
                0,
            )
        )

        return int(
            sock.getsockname()[1]
        )


class Browser:
    """A very small DevTools client, scoped to what these tests need."""

    def __init__(
        self,
        ws,
    ) -> None:
        self._ws = ws

        self._next_id = 0

    def _send(
        self,
        method: str,
        params: dict | None = None,
    ) -> dict:
        self._next_id += 1

        self._ws.send(
            json.dumps(
                {
                    "id": self._next_id,
                    "method": method,
                    "params": params or {},
                }
            )
        )

        while True:
            message = json.loads(
                self._ws.recv()
            )

            if (
                message.get(
                    "id"
                )
                == self._next_id
            ):
                return message

    def open(
        self,
        path: str = "/",
    ) -> None:
        """Load a page and wait for the client to settle.

        Cache-busted, because a test that silently reads a previous
        run's page proves nothing.
        """

        # The cache-buster goes before the fragment. Appending it after
        # produced "#job/12?t=..." which routes to nothing.
        route, _, fragment = path.partition(
            "#"
        )

        separator = (
            "&"
            if "?" in route
            else "?"
        )

        url = (
            APP_URL
            + route
            + separator
            + "t="
            + str(
                time.time()
            )
            + (
                "#" + fragment
                if fragment
                else ""
            )
        )

        self._send(
            "Page.navigate",
            {
                "url": url,
            },
        )

        # Fail fast on a blank app rather than letting every assertion
        # wait out its own timeout. A broken render once turned an
        # eight-second suite into an eight-minute one, which buries the
        # single fact that matters.
        try:
            self.wait_for(
                "document.getElementById('app')"
                ".innerHTML.length > 500",
                timeout=12,
            )
        except AssertionError:
            raise AssertionError(
                "the app rendered nothing. "
                + str(
                    self.eval(
                        "(function(){try{render();"
                        "return 'render() succeeded, so "
                        "the failure is elsewhere';}"
                        "catch(e){return 'render() threw: '"
                        "+e.message;}})()"
                    )
                )
            ) from None

        # A job page has no rows, so settle on either shape.
        self.wait_for(
            "!state.loading && ("
            "document.querySelectorAll("
            "'.row, .empty').length > 0 || "
            "!!document.querySelector('.jp-title'))",
            timeout=20,
        )

    def eval(
        self,
        expression: str,
    ):
        """Evaluate JavaScript, raising if the page threw."""

        result = self._send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        ).get(
            "result",
            {},
        )

        if "exceptionDetails" in result:
            detail = result[
                "exceptionDetails"
            ]

            raise AssertionError(
                "page raised: "
                + str(
                    (
                        detail.get(
                            "exception"
                        )
                        or {}
                    ).get(
                        "description",
                        detail.get(
                            "text"
                        ),
                    )
                )
            )

        return result.get(
            "result",
            {},
        ).get(
            "value"
        )

    def wait_for(
        self,
        expression: str,
        *,
        timeout: float = 12.0,
    ):
        """Poll until an expression is truthy, or fail saying what it was."""

        deadline = time.time() + timeout

        last = None

        while time.time() < deadline:
            try:
                last = self.eval(
                    expression
                )
            except AssertionError:
                last = None

            if last:
                return last

            time.sleep(
                0.25
            )

        raise AssertionError(
            f"timed out waiting for {expression!r}, "
            f"last value {last!r}"
        )

    def click(
        self,
        selector: str,
    ) -> None:
        """Click the first match, failing clearly when it is absent."""

        found = self.eval(
            "(function(){var el=document."
            f"querySelector({json.dumps(selector)});"
            "if(!el) return false; el.click(); "
            "return true;})()"
        )

        if not found:
            raise AssertionError(
                f"no element matched {selector!r}"
            )

    def text(
        self,
        selector: str,
    ) -> str:
        """Return an element's trimmed text, or "" when absent."""

        return self.eval(
            "(function(){var el=document."
            f"querySelector({json.dumps(selector)});"
            "return el? el.textContent.trim() : '';})()"
        )

    def count(
        self,
        selector: str,
    ) -> int:
        """Return how many elements match."""

        return int(
            self.eval(
                "document.querySelectorAll("
                f"{json.dumps(selector)}).length"
            )
        )

    def screenshot(
        self,
        path: str,
    ) -> None:
        """Capture the viewport, for diagnosing a failure."""

        data = self._send(
            "Page.captureScreenshot",
            {
                "format": "png",
            },
        )["result"]["data"]

        with open(
            path,
            "wb",
        ) as handle:
            handle.write(
                base64.b64decode(
                    data
                )
            )


@pytest.fixture(scope="session")
def browser():
    """Start headless Chrome pointed at the running app."""

    chrome = _find_chrome()

    if chrome is None:
        pytest.skip(
            "no Chrome available for browser tests"
        )

    if not _server_is_up():
        pytest.skip(
            f"ACE is not answering at {APP_URL}"
        )

    websocket = pytest.importorskip(
        "websocket",
        reason=(
            "websocket-client is needed "
            "for browser tests"
        ),
    )

    port = _free_port()

    profile = tempfile.mkdtemp(
        prefix="ace-browser-test-"
    )

    process = subprocess.Popen(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--window-size=1600,1000",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    connection = None

    try:
        deadline = time.time() + 25

        target = None

        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json",
                    timeout=2,
                ) as response:
                    pages = [
                        page
                        for page in json.load(
                            response
                        )
                        if page.get(
                            "type"
                        )
                        == "page"
                    ]

                    if pages:
                        target = pages[0]

                        break
            except Exception:
                time.sleep(
                    0.4
                )

        if target is None:
            pytest.skip(
                "Chrome did not expose a debugging target"
            )

        connection = websocket.create_connection(
            target[
                "webSocketDebuggerUrl"
            ],
            timeout=40,
            suppress_origin=True,
        )

        client = Browser(
            connection
        )

        client._send(
            "Page.enable"
        )

        client._send(
            "Runtime.enable"
        )

        yield client

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

        process.terminate()

        try:
            process.wait(
                timeout=10
            )
        except Exception:
            process.kill()

        shutil.rmtree(
            profile,
            ignore_errors=True,
        )


@pytest.fixture
def page(browser):
    """Give each test a freshly loaded Queue."""

    browser.open(
        "/"
    )

    return browser
