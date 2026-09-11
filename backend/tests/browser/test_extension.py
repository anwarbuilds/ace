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

import json
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


def test_a_menu_belonging_to_another_field_is_never_read(
    filler,
) -> None:
    """The bug that left a whole DoorDash form blank.

    The option lookup was ``document.querySelector("[role=listbox]")``
    -- the first listbox in the document, whatever it belonged to.
    That form keeps a phone country-code list of 244 options mounted
    at all times, so every combobox question on it was answered
    against a list of countries, matched nothing, and was left empty.

    A near-match was the worse outcome available: a stored country of
    "United States Of America" against an option reading "United
    States +1" would have clicked inside the phone widget instead.
    """

    filler.eval(
        """
        (function(){
          document.body.insertAdjacentHTML('beforeend',
            '<div id="stranger" role="listbox">'+
            '<div role="option">Afghanistan +93</div>'+
            '<div role="option">United States +1</div></div>'+
            '<div id="mine"><input id="combo" role="combobox"></div>');
          return 1;
        })()
        """
    )

    assert filler.eval(
        "window.__aceInternals.comboboxOptions("
        "document.getElementById('combo')).length"
    ) == 0, (
        "ACE read a listbox belonging to another field"
    )


def test_a_field_s_own_menu_is_found_without_aria_controls(
    filler,
) -> None:
    """react-select points at nothing and nests the menu instead.

    Greenhouse renders react-select, so the menu is a sibling inside
    the field's own container rather than something the input names by
    id. Climbing to it is what makes the fill work at all; stopping
    the climb at a second combobox is what keeps it honest.
    """

    filler.eval(
        """
        (function(){
          document.body.insertAdjacentHTML('beforeend',
            '<div id="wrap"><div class="select__control">'+
            '<input id="own" role="combobox"></div>'+
            '<div role="listbox"><div role="option">Yes</div>'+
            '<div role="option">No</div></div></div>');
          return 1;
        })()
        """
    )

    assert filler.eval(
        "window.__aceInternals.comboboxOptions("
        "document.getElementById('own')).map("
        "function(o){return o.textContent;}).join(',')"
    ) == "Yes,No"


def test_the_climb_stops_at_a_neighbouring_combobox(
    filler,
) -> None:
    """Two questions in one container must not share a menu."""

    filler.eval(
        """
        (function(){
          document.body.insertAdjacentHTML('beforeend',
            '<div id="pair">'+
            '<div><input id="a" role="combobox"></div>'+
            '<div><input id="b" role="combobox"></div>'+
            '<div role="listbox"><div role="option">Yes</div></div>'+
            '</div>');
          return 1;
        })()
        """
    )

    assert filler.eval(
        "window.__aceInternals.comboboxOptions("
        "document.getElementById('a')).length"
    ) == 0, "a menu shared with a neighbour was claimed as this field's"


PAGE_ONE = (
    '<form>'
    '<label for="a">LinkedIn Profile</label>'
    '<input id="a">'
    '<label for="b">GitHub</label><input id="b">'
    '<label for="c">First Name</label><input id="c">'
    '<label for="d">Last Name</label><input id="d">'
    '</form>'
)

PAGE_TWO = (
    '<form>'
    '<label for="e">Phone</label><input id="e">'
    '<label for="f">Email</label><input id="f">'
    '<label for="g">City</label><input id="g">'
    '<label for="h">Country</label><input id="h">'
    '</form>'
)

BANK = [
    {"label": "LinkedIn", "value": "https://linkedin.com/in/x",
     "aliases": []},
    {"label": "GitHub", "value": "https://github.com/x", "aliases": []},
    {"label": "First name", "value": "Sohail", "aliases": []},
    {"label": "Last name", "value": "Shaik", "aliases": []},
    {"label": "Phone", "value": "+1 425 000 0000", "aliases": []},
    {"label": "Email", "value": "x@example.com", "aliases": []},
    {"label": "City", "value": "Bothell", "aliases": []},
    {"label": "Country", "value": "United States", "aliases": []},
]


def _boot_form(
    page,
    markup: str,
):
    """Put a form on the page, then load the real content script."""

    page.eval(
        "document.body.innerHTML="
        + json.dumps(
            markup
        )
        + ";1"
    )

    page.eval(
        "window.__items="
        + json.dumps(
            BANK
        )
        + ";1"
    )

    page.eval(
        """window.chrome={runtime:{
          onMessage:{addListener:function(){}},
          getURL:function(p){return p;},
          getManifest:function(){return{version:'test'};},
          sendMessage:function(msg,cb){
            if(msg.type==='answers') cb({ok:true,items:window.__items});
            else cb({ok:true,work:[],education:[]});
          }}};1"""
    )

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

    page.eval(
        source + "\n;1"
    )


def _panel_title(
    page,
) -> str:
    return page.eval(
        """(function(){
          var h=document.querySelector('.ace-root');
          if(!h||!h.shadowRoot) return '';
          var t=h.shadowRoot.querySelector('.ace-title');
          return t?t.textContent:'';})()"""
    )


def test_the_next_page_of_a_form_is_filled_too(
    page,
) -> None:
    """An application is often several pages, and ACE saw only one.

    Workday's is a wizard that swaps the whole step without touching
    location.href. lastResult was cleared only on a URL change, so
    after the first page was filled every later step returned early
    from refresh(): the panel never came back and nothing was filled
    again. The user reported exactly this, and it is invisible on any
    single-page form, which is every form tested until now.
    """

    _boot_form(
        page,
        PAGE_ONE,
    )

    page.wait_for(
        "!!document.querySelector('.ace-root')",
        timeout=12,
    )

    assert "Fill" in _panel_title(
        page
    ), "no preview on the first page"

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "/^Filled/.test("
        "document.querySelector('.ace-root')"
        ".shadowRoot.querySelector('.ace-title')"
        ".textContent)",
        timeout=12,
    )

    assert page.eval(
        "document.getElementById('a').value"
    ), "the first page was not filled"

    # The wizard advances: same URL, entirely new questions.
    page.eval(
        "document.body.innerHTML="
        + json.dumps(
            PAGE_TWO
        )
        + ";1"
    )

    page.wait_for(
        "/^Fill/.test("
        "document.querySelector('.ace-root')"
        ".shadowRoot.querySelector('.ace-title')"
        ".textContent)",
        timeout=12,
    )

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "!!document.getElementById('e').value",
        timeout=12,
    )

    assert page.eval(
        "document.getElementById('f').value"
    ) == "x@example.com", (
        "the second page of the form was never filled"
    )


TYPE_AHEAD = """
(function(){
  document.body.insertAdjacentHTML('beforeend',
    '<div id="wrap"><div class="select__control">'+
    '<input id="city" role="combobox"></div><div id="menu"></div></div>');
  var input=document.getElementById('city');
  var menu=document.getElementById('menu');
  window.__picked=null;
  var ALL=['Bothell, Washington, United States',
           'Seattle, Washington, United States',
           'Boston, Massachusetts, United States'];
  // Offers nothing at all until something is typed, which is what
  // every city and university list on Greenhouse does.
  input.addEventListener('input',function(){
    var q=input.value.trim().toLowerCase();
    if(!q){ menu.innerHTML=''; return; }
    var hits=ALL.filter(function(c){return c.toLowerCase().indexOf(q)===0;});
    menu.innerHTML='<div role="listbox">'+hits.map(function(c){
      return '<div role="option">'+c+'</div>';}).join('')+'</div>';
    [].slice.call(menu.querySelectorAll('[role=option]')).forEach(function(o){
      o.addEventListener('click',function(){ window.__picked=o.textContent; });});
  });
  return 1;})()
"""


def test_a_list_that_shows_nothing_until_you_type(
    filler,
) -> None:
    """City, school and degree were empty on every Greenhouse form.

    Those lists hold every city on earth and every university, so they
    offer no options at all until something is typed. ACE opened them,
    saw an empty menu and gave up, and the user filled them by hand
    every time.
    """

    filler.eval(
        TYPE_AHEAD
    )

    filler.eval(
        "window.__done=window.__aceInternals"
        ".fillOneCombobox("
        "document.getElementById('city'),"
        "'Bothell',[]);1"
    )

    filler.wait_for(
        "!!window.__picked",
        timeout=12,
    )

    assert filler.eval(
        "window.__picked"
    ) == "Bothell, Washington, United States"


def test_a_city_written_shorter_than_the_list_writes_it(
    filler,
) -> None:
    """"Seattle WA" against "Seattle, Washington, United States".

    Typing the whole answer finds nothing, because the widget matches
    what it was handed. The first word is tried after it, which is the
    difference between a match and a blank field.
    """

    filler.eval(
        TYPE_AHEAD
    )

    filler.eval(
        "window.__aceInternals.fillOneCombobox("
        "document.getElementById('city'),"
        "'Seattle WA',[]);1"
    )

    filler.wait_for(
        "!!window.__picked",
        timeout=12,
    )

    assert filler.eval(
        "window.__picked"
    ) == "Seattle, Washington, United States"


def test_a_search_that_finds_nothing_leaves_the_box_empty(
    filler,
) -> None:
    """Half a typed city left sitting in a required field is worse
    than the blank it replaced, and worse than saying so."""

    filler.eval(
        TYPE_AHEAD
    )

    filler.eval(
        "window.__aceInternals.fillOneCombobox("
        "document.getElementById('city'),"
        "'Hyderabad',[]).then(function(r){"
        "window.__outcome=r;});1"
    )

    filler.wait_for(
        "!!window.__outcome",
        timeout=12,
    )

    assert filler.eval(
        "window.__outcome.matched"
    ) is False

    assert filler.eval(
        "document.getElementById('city').value"
    ) == "", "ACE left its search text in the field"


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
