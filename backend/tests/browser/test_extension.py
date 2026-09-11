"""DOM-level tests for the extension's fill mechanics.

``extension/test-rules.js`` covers which question a field *is*. Nothing
covered what happens after ACE decides to answer one, and both bugs
this file pins were reported from live application forms:

- a box with the right answer visibly in it still submitted as "this
  field is required", because the page's own form library had never
  been told anything changed;
- a permanent gold ring on every filled field, in the colour range
  forms use for warnings, so correctly filled boxes read as errors.

Chrome will not run an unpacked extension headlessly, so this injects
the real ``content.js`` into a real page instead. That remains a gap
and is recorded as one in the knowledge base rather than papered over.
"""

import pathlib

import pytest


EXTENSION = (
    pathlib.Path(
        __file__
    )
    .resolve()
    .parents[3]
    / "extension"
)


@pytest.fixture(name="filler")
def fixture_filler(
    page,
):
    """Load the real content.js and hand back its internals."""

    # Same order the manifest declares: content.js calls into the
    # matcher, so loading it alone dies on the first question.
    source = "\n;\n".join(
        (
            EXTENSION / name
        ).read_text(
            encoding="utf-8"
        )
        for name in (
            "fields.js",
            "content.js",
        )
    )

    # The script reaches for the extension APIs on load. Stubbing them
    # is what the earlier harnesses did too; it is the DOM behaviour
    # below that is real here, not the messaging.
    page.eval(
        "window.chrome={runtime:{"
        "onMessage:{addListener:function(){}},"
        "sendMessage:function(){},"
        "getURL:function(p){return p;}}};1"
    )

    page.eval(
        source + "\n;1"
    )

    assert page.eval(
        "!!window.__aceInternals"
    ), "content.js exposed no seam to test through"

    return page


def _make_field(
    page,
    recorded: str,
) -> None:
    """Put one text box on the page, tracked the way React tracks one.

    React keeps the last value it saw on the node and ignores an input
    event whose value still equals that record, which is why filling
    through a plain assignment can leave a framework believing the box
    is empty.
    """

    page.eval(
        """
        (function(){
          var i=document.createElement('input');
          i.type='text';
          i.id='ace-probe';
          document.body.appendChild(i);
          window.__seen={events:[],focused:0,blurred:0};
          i.addEventListener('input',function(){
            window.__seen.events.push('input:'+i.value);
            // Recorded here because headless Chrome never fires focus
            // or blur: the document itself is not focused. The input
            // event does fire, and activeElement is accurate, so the
            // focus is observed at the moment the value is committed.
            window.__seen.activeDuringInput=
              document.activeElement===i; });
          i.addEventListener('change',function(){
            window.__seen.events.push('change:'+i.value); });
          i.addEventListener('focus',function(){
            window.__seen.focused++; });
          i.addEventListener('blur',function(){
            window.__seen.blurred++; });
          var recorded=%s;
          i._valueTracker={
            getValue:function(){return recorded;},
            setValue:function(v){recorded=v;},
            read:function(){return recorded;}
          };
          Object.getOwnPropertyDescriptor(
            HTMLInputElement.prototype,'value'
          ).set.call(i, recorded);
          return 1;
        })()
        """
        % repr(
            recorded
        ).replace(
            "'",
            '"',
        )
    )


def test_the_page_s_own_framework_is_told_the_value_changed(
    filler,
) -> None:
    """The input and change events are what a framework listens to."""

    _make_field(
        filler,
        "",
    )

    filler.eval(
        "window.__aceInternals.setNatively("
        "document.getElementById('ace-probe'),"
        "'sohail@example.com');1"
    )

    assert filler.eval(
        "document.getElementById('ace-probe').value"
    ) == "sohail@example.com"

    assert filler.eval(
        "window.__seen.events.join('|')"
    ) == (
        "input:sohail@example.com"
        "|change:sohail@example.com"
    )


def test_a_value_the_framework_already_recorded_still_registers(
    filler,
) -> None:
    """React discards an input event that agrees with its own record.

    The tracker is rewound first so the comparison cannot match and
    the change is always seen. Without it this fill is a no-op as far
    as the page is concerned, and the field submits as never answered.
    """

    _make_field(
        filler,
        "Sohail",
    )

    filler.eval(
        "window.__aceInternals.setNatively("
        "document.getElementById('ace-probe'),"
        "'Sohail');1"
    )

    assert filler.eval(
        "document.getElementById('ace-probe')"
        "._valueTracker.read()"
    ) != "Sohail", (
        "the tracker still agreed with the new value, "
        "so the framework would ignore the change"
    )


def test_a_filled_field_is_focused_and_then_blurred(
    filler,
) -> None:
    """Formik and React Hook Form validate a field on blur.

    Until it blurs, a filled box can still submit as "this field is
    required", which is exactly what the user reported.

    Asserted through activeElement rather than focus and blur events,
    because headless Chrome does not focus the document and so fires
    neither, while moving activeElement correctly.
    """

    _make_field(
        filler,
        "",
    )

    filler.eval(
        "window.__aceInternals.setNatively("
        "document.getElementById('ace-probe'),"
        "'Sohail');1"
    )

    assert filler.eval(
        "window.__seen.activeDuringInput"
    ), "the field was not focused when its value was committed"

    assert not filler.eval(
        "document.activeElement==="
        "document.getElementById('ace-probe')"
    ), "the field never blurred, so validation never ran"


def test_the_fill_marker_takes_itself_off_again(
    filler,
) -> None:
    """It marks what ACE just touched, and the panel lists all of it.

    Left on permanently it was read as a validation error, because a
    ring around a filled box is what a form uses to say something is
    wrong with it.
    """

    _make_field(
        filler,
        "",
    )

    filler.eval(
        "window.__aceInternals.markFilled("
        "document.getElementById('ace-probe'));1"
    )

    assert filler.eval(
        "document.getElementById('ace-probe')"
        ".classList.contains('ace-filled')"
    ), "nothing marked the field at all"

    filler.wait_for(
        "!document.getElementById('ace-probe')"
        ".classList.contains('ace-filled')",
        timeout=12,
    )


def test_the_marker_is_not_the_colour_of_a_warning() -> None:
    """Gold is ACE's signal colour and a form's warning colour.

    Pinned in the stylesheet rather than by rendering, because the
    fill marker is one declaration and the thing that went wrong was
    the value in it.
    """

    css = (
        EXTENSION / "content.css"
    ).read_text(
        encoding="utf-8"
    )

    marker = [
        line
        for line in css.splitlines()
        if line.startswith(
            ".ace-filled{"
        )
    ]

    assert marker, "the fill marker rule is gone"

    assert (
        "#c9a227" not in marker[0]
    ), "the fill marker is gold again"
