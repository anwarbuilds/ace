"""React Router's turbo-stream, as a server-rendered page embeds it.

A page built with React Router 7 carries its loader data in a
``streamController.enqueue("...")`` script: one JSON array in which every
object, array and string is written once and referred to by its index.
An object is ``{"_<key index>": <value index>}``, an array is a list of
indices, and a few values JSON cannot hold have negative codes. Decoded,
it is the same data the page renders.
"""

from __future__ import annotations

import json
import re


_ENQUEUE = re.compile(
    r"streamController\.enqueue\((\".*?\")\);",
    re.DOTALL,
)

# turbo-stream's codes for what JSON cannot write: a hole, NaN, the
# infinities, negative zero, null and undefined.
_SPECIAL = {
    -1: None,
    -2: float("nan"),
    -3: float("-inf"),
    -4: -0.0,
    -5: None,
    -6: float("inf"),
    -7: None,
}


def loader_data(
    markup: str,
) -> dict:
    """The loader data a server-rendered page carries, by route."""

    found = _ENQUEUE.search(
        markup
    )

    if found is None:
        raise ValueError(
            "The page carried no turbo-stream data."
        )

    # The first line is the page's data; any after it settle promises
    # the page deferred.
    values = json.loads(
        json.loads(
            found.group(1)
        ).split(
            "\n",
            1,
        )[0]
    )

    decoded: dict[int, object] = {}

    def decode(
        index: int,
    ) -> object:
        if index < 0:
            return _SPECIAL.get(
                index
            )

        if index in decoded:
            return decoded[index]

        value = values[index]

        if isinstance(value, dict):
            result: dict = {}
            decoded[index] = result

            for key, item in value.items():
                result[str(values[int(key[1:])])] = decode(
                    item
                )

            return result

        if isinstance(value, list):
            # A typed value: ["D", ...] is a date; the rest -- promises,
            # maps, sets, errors -- carry nothing read here.
            if value and isinstance(value[0], str):
                return value[1] if value[0] == "D" and len(value) > 1 else None

            items: list = []
            decoded[index] = items

            items.extend(
                decode(item)
                for item in value
            )

            return items

        return value

    root = decode(
        0
    )

    return (
        root.get("loaderData") or {}
        if isinstance(root, dict)
        else {}
    )
