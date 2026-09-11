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


def test_nothing_on_the_page_is_highlighted(
    filler,
) -> None:
    """The user asked for no marker at all.

    It had been a gold ring, then a purple one that cleared itself.
    Both were ACE announcing itself on a form the user is about to
    send to an employer, and the comparison they made was a browser's
    own autofill, which simply fills and says nothing. The panel is
    the record of what was done; the page is left alone.
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
        "document.getElementById('ace-probe')"
        ".getAttribute('class')"
    ) in (
        None,
        "",
    ), "a filled field was left carrying a marker class"


def test_the_panel_survives_a_hostile_stylesheet(
    filler,
) -> None:
    """The bug the user photographed: every line drawn over the last.

    The panel was a plain div under document.body, so an employer's
    stylesheet reached straight into it. On Ashby the title, subtitle
    and every listed field were painted on top of each other and none
    of it could be read. Defensive CSS does not settle that argument,
    because the next board resets something else; a shadow root does,
    because nothing the page declares crosses the boundary.
    """

    filler.eval(
        """
        (function(){
          var s=document.createElement('style');
          s.textContent=
            'div,span,button{line-height:0 !important;'+
            'font-size:0 !important;margin:0 !important}';
          document.head.appendChild(s);
          return 1;
        })()
        """
    )

    filler.eval(
        "(function(){"
        "var p=window.__aceInternals.panel();"
        "p.innerHTML=window.__aceInternals.shell("
        "'Fill 7 fields','Review before filling.','','');"
        "return 1;})()"
    )

    measured = filler.eval(
        """
        (function(){
          var host=document.querySelector('.ace-root');
          if(!host||!host.shadowRoot) return null;
          var t=host.shadowRoot.querySelector('.ace-title');
          if(!t) return null;
          var s=getComputedStyle(t);
          return {
            line: parseFloat(s.lineHeight),
            size: parseFloat(s.fontSize),
            height: t.getBoundingClientRect().height
          };
        })()
        """
    )

    assert measured, "the panel did not mount in a shadow root"

    assert measured["size"] >= 10, (
        "the page flattened the panel's text to "
        + str(
            measured["size"]
        )
        + "px"
    )

    assert measured["height"] >= 10, (
        "the panel's title collapsed to "
        + str(
            measured["height"]
        )
        + "px, which is the overlap the user saw"
    )


def test_the_extension_ships_no_fill_marker() -> None:
    """Pinned in the source, because the marker was three things.

    A class on the field, a rule in a stylesheet, and a repaint that
    put it back after React dropped it. Removing one and leaving the
    others is how a marker comes back.
    """

    assert not (
        EXTENSION / "content.css"
    ).exists(), (
        "content.css is back; the panel styles belong in the "
        "shadow root and the fill marker is gone"
    )

    source = (
        EXTENSION / "content.js"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "ace-filled" not in source
    ), "the fill marker is back in content.js"
