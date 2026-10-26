"""The email shown in Inbox: its own HTML, rebuilt so nothing in it can act."""

import base64

from backend.app.inbox import display

EM, EN = "\u2014", "\u2013"


def b64(value: str | bytes) -> str:
    return base64.urlsafe_b64encode(value.encode() if isinstance(value, str) else value).decode()


def html_payload(markup: str, *extra: dict) -> dict:
    return {"mimeType": "multipart/related", "parts": [
        {"mimeType": "text/html", "headers": [{"name": "Content-Type", "value": 'text/html; charset="utf-8"'}], "body": {"data": b64(markup)}},
        *extra]}


def test_active_and_remote_content_never_survives():
    markup = ('<html><head><title>Hidden title</title><meta http-equiv="refresh" content="0;url=https://elsewhere.example">'
              '<base href="https://elsewhere.example/"><link rel="stylesheet" href="https://cdn.example/a.css">'
              '<style>@import url(https://cdn.example/b.css); p{color:#333;background:url(https://tracker.example/bg.png)}</style>'
              '</head><body onload="steal()" style="background:#f4f4f4">'
              '<p onclick="steal()">Hello</p><script>steal()</script><iframe src="https://elsewhere.example"><p>inner</p></iframe>'
              '<form action="https://elsewhere.example"><input name="q"><button>Send</button><span>kept text</span></form>'
              '<svg><script>steal()</script><text>svg text</text></svg><svg/><p>after the svg</p>'
              '<a href="javascript:steal()">bad link</a> <a href=" https://careers.example/jobs?a=1&b=2 ">Careers</a>'
              '<a href="#top">Top</a><img src="https://tracker.example/pixel.gif" width="1" height="1">'
              '<img src="https://cdn.example/banner.png" alt="Fictional banner"><img src="https://cdn.example/logo.png">'
              '<!--[if mso]><p>outlook only</p><![endif]--></body></html>')
    shown = display.show(html_payload(markup))
    doc = shown.document
    for gone in ("<script", "steal", "<iframe", "inner", "<form", "<input", "<button", "Send", "svg text", "<svg",
                 "Hidden title", "http-equiv=\"refresh\"", "<base", "<link", "@import", "tracker.example", "cdn.example",
                 "javascript:", "outlook only", "onload", "onclick"):
        assert gone not in doc, gone
    assert shown.kind == "html"
    assert shown.blocked_images == 2  # The banner and the logo; a 1 by 1 pixel is not counted.
    assert '<span class="ace-alt">Fictional banner</span>' in doc
    assert "kept text" in doc and "after the svg" in doc
    assert 'href="https://careers.example/jobs?a=1&amp;b=2" target="_blank" rel="noopener noreferrer"' in doc
    assert '<a href="#top">' in doc and ">bad link</a>" in doc
    assert "p{color:#333;background:none}" in doc
    assert '<div style="background:#f4f4f4" class="ace-body">' in doc
    assert display.FRAME_POLICY in doc and 'name="referrer" content="no-referrer"' in doc


def test_images_attached_to_the_email_are_shown():
    picture = {"mimeType": "image/png", "headers": [{"name": "Content-ID", "value": "<logo@fixture>"}],
               "body": {"attachmentId": "attachment-1", "size": 12}}
    inline = {"mimeType": "image/gif", "headers": [{"name": "Content-ID", "value": "<dot@fixture>"}], "body": {"data": b64(b"GIF89a")}}
    unused = {"mimeType": "image/png", "headers": [{"name": "Content-ID", "value": "<unused@fixture>"}], "body": {"attachmentId": "attachment-2"}}
    fetched = []

    def fetch(key: str) -> str:
        fetched.append(key)
        return b64(b"\x89PNG fictional")

    doc = display.show(html_payload('<p><img src="cid:logo@fixture" alt="Logo"><img src="CID:dot@fixture"></p>', picture, inline, unused), fetch).document
    assert fetched == ["attachment-1"]
    assert "data:image/png;base64," + base64.b64encode(b"\x89PNG fictional").decode() in doc
    assert "data:image/gif;base64," in doc and "cid:" not in doc.lower()


def test_dashes_become_punctuation_and_drawn_rules_disappear():
    markup = (f"<p>Hello <b>Fixture</b> {EM} thanks for applying.</p><p>Wayfern - Full-Stack Software Engineer</p>"
              f"<p>Hours 9{EN}5, Monday {EN} Friday, 10 - 20 people</p><p>{EM} The Talent Team</p><p>-----</p>"
              f"<p><b>Role</b> {EM} <b>Engineer</b></p><td>{EM}</td><hr><p title='A {EM} B'>Full-Stack stays</p>"
              "<p><b>Team</b> - Fiction</p><ul><li>- first</li></ul>")
    doc = display.show(html_payload(markup)).document
    assert EM not in doc and EN not in doc and "-----" not in doc and "<hr" not in doc
    assert "Hello <b>Fixture</b>, thanks for applying." in doc
    assert "<b>Team</b>, Fiction" in doc and "<li>\u2022 first</li>" in doc
    assert "Wayfern, Full-Stack Software Engineer" in doc
    assert "Hours 9 to 5, Monday, Friday, 10 to 20 people" in doc
    assert "<p>The Talent Team</p>" in doc
    assert "<b>Role</b>, <b>Engineer</b>" in doc
    assert 'title="A, B"' in doc and "Full-Stack stays" in doc
    assert '<div class="ace-gap"></div>' in doc


def test_plain_text_email_keeps_its_lines_and_links_its_addresses():
    text = (f"Hi Fixture,\n\nThanks for applying {EM} we reviewed it.\n- First point\n* Second point\n"
            "==========\nSee https://careers.example/jobs/1. Or <https://careers.example/team>\n")
    shown = display.show({"mimeType": "text/plain", "body": {"data": b64(text)}})
    assert shown.kind == "text" and shown.blocked_images == 0
    doc = shown.document
    assert "Thanks for applying, we reviewed it." in doc
    assert "\u2022 First point\n\u2022 Second point" in doc and "=====" not in doc
    assert '<a href="https://careers.example/jobs/1" target="_blank" rel="noopener noreferrer">https://careers.example/jobs/1</a>.' in doc
    assert "&lt;<a href=\"https://careers.example/team\"" in doc


def test_an_email_whose_html_shows_nothing_falls_back_to_its_text():
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/plain", "body": {"data": b64("The readable version")}},
        {"mimeType": "text/html", "body": {"data": b64("<html><body><script>never closed")}}]}
    shown = display.show(payload)
    assert shown.kind == "text" and "The readable version" in shown.document


def test_a_large_body_kept_apart_by_gmail_is_fetched():
    payload = {"mimeType": "text/html", "body": {"attachmentId": "body-1", "size": 900000}}
    shown = display.show(payload, lambda key: b64("<p>Big fictional body</p>") if key == "body-1" else "")
    assert "<p>Big fictional body</p>" in shown.document
