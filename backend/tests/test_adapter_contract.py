"""Contract tests across every ACE source adapter.

These exist because of a bug that no per-adapter test caught. When the
conditional-HTTP work changed adapters to return three values, a second
Greenhouse code path still did ``tuple(jobs)`` on the result. That
produced a three-element tuple whose first element was a list instead of
a job -- silently wrong, with no exception and no log line.

Per-adapter tests missed it because they use fake fetchers that return
whatever the test decided. These tests check the *real* functions
instead, so the shape of every adapter and the shape the dispatcher
expects cannot drift apart again.
"""

import inspect

import pytest

from backend.app.adapters.amazon import (
    fetch_amazon_jobs,
)
from backend.app.adapters.ashby import (
    fetch_ashby_jobs,
)
from backend.app.adapters.greenhouse import (
    fetch_greenhouse_jobs,
)
from backend.app.adapters.http_cache import (
    CacheValidators,
)
from backend.app.adapters.lever import (
    fetch_lever_jobs,
)
from backend.app.adapters.simplify import (
    fetch_simplify_jobs,
)
from backend.app.adapters.smartrecruiters import (
    fetch_smartrecruiters_jobs,
)
from backend.app.adapters.workday import (
    fetch_workday_jobs,
)
from backend.app.scheduling.dispatcher import (
    build_default_source_dispatcher,
)
from backend.app.scheduling.types import (
    SourceType,
)


# Adapters that replay HTTP validators. Workday lists via POST and
# Amazon generates its search per request, so neither can.
CONDITIONAL_ADAPTERS = (
    fetch_greenhouse_jobs,
    fetch_ashby_jobs,
    fetch_lever_jobs,
    fetch_smartrecruiters_jobs,
    fetch_simplify_jobs,
)


UNCONDITIONAL_ADAPTERS = (
    fetch_workday_jobs,
    fetch_amazon_jobs,
)


@pytest.mark.parametrize(
    "adapter",
    CONDITIONAL_ADAPTERS,
    ids=lambda fn: fn.__name__,
)
def test_conditional_adapters_accept_validators(
    adapter,
) -> None:
    """Every conditional adapter takes validators to replay."""

    signature = inspect.signature(
        adapter
    )

    assert (
        "validators"
        in signature.parameters
    ), (
        f"{adapter.__name__} cannot replay "
        "HTTP validators"
    )

    default = signature.parameters[
        "validators"
    ].default

    assert default is None, (
        f"{adapter.__name__} must default to "
        "an unconditional fetch"
    )


@pytest.mark.parametrize(
    "adapter",
    CONDITIONAL_ADAPTERS,
    ids=lambda fn: fn.__name__,
)
def test_conditional_adapters_return_three_values(
    adapter,
) -> None:
    """Jobs, an unchanged flag, and the next validators.

    A caller that unpacks fewer would silently mangle the result rather
    than fail, which is exactly the bug these tests exist to prevent.
    """

    annotation = inspect.signature(
        adapter
    ).return_annotation

    rendered = str(
        annotation
    )

    assert rendered.startswith(
        "tuple["
    ), (
        f"{adapter.__name__} must return a "
        f"tuple, not {rendered}"
    )

    assert (
        "CacheValidators" in rendered
    ), (
        f"{adapter.__name__} must return the "
        "validators for the next poll"
    )

    assert "bool" in rendered, (
        f"{adapter.__name__} must report "
        "whether the source was unchanged"
    )


@pytest.mark.parametrize(
    "adapter",
    UNCONDITIONAL_ADAPTERS,
    ids=lambda fn: fn.__name__,
)
def test_unconditional_adapters_return_a_plain_list(
    adapter,
) -> None:
    """Providers that cannot cache keep the simpler contract.

    Workday lists via POST and Amazon builds its search per request, so
    neither offers a usable validator. Pretending otherwise would add a
    contract nobody honours.
    """

    rendered = str(
        inspect.signature(
            adapter
        ).return_annotation
    )

    assert "list[" in rendered

    assert (
        "CacheValidators" not in rendered
    )


def test_every_source_type_has_a_handler() -> None:
    """A source type with no handler fails only in production."""

    dispatcher = (
        build_default_source_dispatcher()
    )

    missing = (
        set(
            SourceType
        )
        - dispatcher.supported_source_types
    )

    assert not missing, (
        "no fetch handler registered for: "
        f"{sorted(s.value for s in missing)}"
    )


def test_validators_round_trip_through_headers() -> None:
    """What a response offers is what the next request sends."""

    validators = CacheValidators(
        etag='W/"abc123"',
        last_modified=(
            "Wed, 21 Oct 2026 07:28:00 GMT"
        ),
    )

    headers = (
        validators.request_headers()
    )

    assert (
        headers["If-None-Match"]
        == 'W/"abc123"'
    )

    assert (
        headers["If-Modified-Since"]
        == "Wed, 21 Oct 2026 07:28:00 GMT"
    )


def test_empty_validators_send_nothing() -> None:
    """A first poll must be unconditional."""

    assert (
        CacheValidators().request_headers()
        == {}
    )

    assert CacheValidators().is_empty
