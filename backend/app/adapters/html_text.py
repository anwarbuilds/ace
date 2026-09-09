"""Shared HTML-to-text decoding for ACE adapters.

Five adapters each wrote their own single call to ``html.unescape``.
14,855 stored Greenhouse descriptions were found still holding the
literal six-character string ``&nbsp;`` rather than a real space,
because their raw content is double-encoded: the source's own HTML
already contained the entity ``&nbsp;``, and it was written out through
a template that escaped it a second time to ``&amp;nbsp;``. One
``html.unescape`` pass correctly resolves the outer layer and produces
exactly ``&nbsp;`` -- a value that looks fully clean and is not.

This is not cosmetic. Every rule in the eligibility gate that matches a
multi-word phrase depends on a real whitespace character sitting
between the words: ``security\\s+clearance`` never matches
``security&nbsp;clearance``, because the six literal characters are not
whitespace to a regex engine. A posting stating a security clearance
requirement, a citizenship requirement or an experience figure using
this exact phrasing read as silent, and the posting passed the gate
carrying a requirement the user could not meet.
"""

from __future__ import annotations

import html


# However many entities a template can plausibly nest before something
# else is wrong. Bounded so a pathological or adversarial input cannot
# spin forever; ACE has never observed more than one level of double
# encoding.
MAX_UNESCAPE_PASSES = 5


def unescape_fully(text: str) -> str:
    """Decode HTML entities until nothing further decodes.

    A single ``html.unescape`` call is what let 14,855 postings keep a
    literal ``&nbsp;`` in their stored description. Repeating the call
    until it stops changing anything resolves any depth of nesting a
    real source has been observed to produce, and costs nothing on the
    overwhelming majority of content that was never double-encoded in
    the first place: the second pass is a no-op and the loop exits
    immediately.
    """

    decoded = text

    for _ in range(MAX_UNESCAPE_PASSES):
        next_pass = html.unescape(decoded)

        if next_pass == decoded:
            break

        decoded = next_pass

    return decoded
