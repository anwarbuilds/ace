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
        "'alex@example.com');1"
    )

    assert filler.eval(
        "document.getElementById('ace-probe').value"
    ) == "alex@example.com"

    assert filler.eval(
        "window.__seen.events.join('|')"
    ) == (
        "input:alex@example.com"
        "|change:alex@example.com"
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
        "Alex",
    )

    filler.eval(
        "window.__aceInternals.setNatively("
        "document.getElementById('ace-probe'),"
        "'Alex');1"
    )

    assert filler.eval(
        "document.getElementById('ace-probe')"
        "._valueTracker.read()"
    ) != "Alex", (
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
        "'Alex');1"
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
        "'Alex');1"
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
    {"label": "First name", "value": "Alex", "aliases": []},
    {"label": "Last name", "value": "Rivera", "aliases": []},
    {"label": "Phone", "value": "+1 555 010 0000", "aliases": []},
    {"label": "Email", "value": "x@example.com", "aliases": []},
    {"label": "City", "value": "Ashfield", "aliases": []},
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
  var ALL=['Ashfield, Washington, United States',
           'Lakeview, Washington, United States',
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
        "'Ashfield',[]);1"
    )

    filler.wait_for(
        "!!window.__picked",
        timeout=12,
    )

    assert filler.eval(
        "window.__picked"
    ) == "Ashfield, Washington, United States"


def test_a_city_written_shorter_than_the_list_writes_it(
    filler,
) -> None:
    """"Lakeview WA" against "Lakeview, Washington, United States".

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
        "'Lakeview WA',[]);1"
    )

    filler.wait_for(
        "!!window.__picked",
        timeout=12,
    )

    assert filler.eval(
        "window.__picked"
    ) == "Lakeview, Washington, United States"


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


def _fill_then_clobber(
    page,
    wrote: str,
    clobbered_to: str,
) -> str:
    """Fill a box, record it the way plan() does, then let the page
    overwrite it, and run the real check. Returns the final value."""

    page.eval(
        "(function(){document.body.insertAdjacentHTML("
        "'beforeend','<input id=\"probe\">');return 1;})()"
    )

    page.eval(
        "(function(){var I=window.__aceInternals,"
        "f=document.getElementById('probe');"
        "I.setNatively(f," + repr(
            wrote
        ).replace(
            "'",
            '"',
        ) + ");"
        "I.recordFill({field:f,previous:'',wrote:" + repr(
            wrote
        ).replace(
            "'",
            '"',
        ) + ",ticked:false});"
        "I.setNatively(f," + repr(
            clobbered_to
        ).replace(
            "'",
            '"',
        ) + ");"
        "I.restoreClobbered();return 1;})()"
    )

    return page.eval(
        "document.getElementById('probe').value"
    )


def test_a_field_the_page_overwrote_is_put_back(
    filler,
) -> None:
    """The Jump Trading form: Phone came back reading "+1".

    Comboboxes are filled in a second pass, because each has to be
    opened and waited on. A phone widget rewrites the number box when
    its country is chosen, so ACE filled the number, then chose the
    country beside it, and the number it had just written was gone.

    Exposed by making the country fillable at all: before that it was
    never chosen and the number always survived.
    """

    assert _fill_then_clobber(
        filler,
        "+ 555 010 0100",
        "+1",
    ) == "+ 555 010 0100", (
        "the number ACE wrote was not put back"
    )


def test_a_reformatted_value_is_left_alone(
    filler,
) -> None:
    """A widget that renders the number differently has kept it.

    Rewriting it would fight the page and never settle, so the
    comparison is on the digits alone and a long enough overlap counts
    as the same content.
    """

    assert _fill_then_clobber(
        filler,
        "+1 555 010 0100",
        "(555) 010-0100",
    ) == "(555) 010-0100", (
        "a reformatted number was rewritten, which is a fight "
        "with the page that never settles"
    )


def test_only_fields_ace_wrote_are_considered(
    filler,
) -> None:
    """The check walks ACE's own record, not the form.

    A field ACE never filled is never looked at, whatever is in it.
    Within the record, anything that is not the value ACE wrote is
    restored, and that is deliberately blunt: the check runs once,
    seconds after the fill, in the gap the combobox pass occupies. In
    that window a changed value is a widget, not a person. If the user
    edits afterwards, nothing runs again to undo them.
    """

    assert _fill_then_clobber(
        filler,
        "+ 555 010 0100",
        "replaced by the widget",
    ) == "+ 555 010 0100"

    filler.eval(
        "(function(){document.body.insertAdjacentHTML("
        "'beforeend','<input id=\"untouched\" value=\"mine\">');"
        "window.__aceInternals.restoreClobbered();return 1;})()"
    )

    assert filler.eval(
        "document.getElementById('untouched').value"
    ) == "mine"


def test_a_lone_checkbox_is_a_yes_no_not_an_option_list(
    filler,
) -> None:
    """"I currently work here" was never ticked on any form.

    A checkbox reaches the choice path, which matches the stored answer
    against the option text of the group. For a lone checkbox that text
    is the statement it asserts, so an answer of "Yes" matched nothing
    and the box was reported as "your answer matched no option".

    A single checkbox carries no choice. It is the answer.
    """

    filler.eval(
        """
        (function(){
          document.body.insertAdjacentHTML('beforeend',
            '<label for="cur">I currently work here</label>'+
            '<input type="checkbox" id="cur">');
          return 1;})()
        """
    )

    assert filler.eval(
        "window.__aceInternals.fillOne("
        "document.getElementById('cur'),'Yes')"
    ) is True

    assert filler.eval(
        "document.getElementById('cur').checked"
    ), "the box was not ticked"


def test_a_lone_checkbox_stays_clear_on_no(
    filler,
) -> None:
    """A past role must not be marked as the current one.

    The asymmetry matters: a missed tick is a box you notice and click,
    while a wrong tick tells an employer you still work somewhere you
    left in 2024.
    """

    filler.eval(
        """
        (function(){
          document.body.insertAdjacentHTML('beforeend',
            '<label for="past">I currently work here</label>'+
            '<input type="checkbox" id="past">');
          return 1;})()
        """
    )

    filler.eval(
        "window.__aceInternals.fillOne("
        "document.getElementById('past'),'No');1"
    )

    assert not filler.eval(
        "document.getElementById('past').checked"
    ), "a past role was ticked as current"


# Padded to four fields, which is what makes a page read as an
# application form at all rather than a search box with a label.
PHONE_WIDGET = (
    '<form>'
    '<label for="fn">First Name</label><input id="fn">'
    '<label for="ln">Last Name</label><input id="ln">'
    '<label for="cc">Country code</label>'
    '<div id="ccouter"><div id="ccwrap" class="select__control">'
    '<input id="cc" role="combobox"></div>'
    '<div id="ccmenu"></div></div>'
    '<label for="ph">Phone</label><input id="ph">'
    '</form>'
)

# A real international phone widget: choosing the country resets the
# number box to that country's dial code. That is not a bug in the
# widget -- a number typed for one country does not mean the same thing
# under another -- which is exactly why the country has to be settled
# before the number goes in.
PHONE_WIDGET_BEHAVIOUR = """
(function(){
  var input=document.getElementById('cc');
  var menu=document.getElementById('ccmenu');
  var phone=document.getElementById('ph');
  window.__wipes=0;
  function show(){
    if(menu.innerHTML) return;
    menu.innerHTML='<div role="listbox">'+
      ['United States +1','United Kingdom +44','India +91']
        .map(function(c){return '<div role="option">'+c+'</div>';}).join('')+
      '</div>';
    [].slice.call(menu.querySelectorAll('[role=option]')).forEach(function(o){
      o.addEventListener('click',function(){
        input.value=o.textContent;
        window.__wipes+=1;
        phone.value='+'+(/\\+(\\d+)/.exec(o.textContent)||[0,''])[1];
      });});
  }
  input.addEventListener('focus',show);
  document.getElementById('ccwrap').addEventListener('click',show);
  return 1;})()
"""


def test_the_phone_country_is_chosen_before_the_number(
    page,
) -> None:
    """Reported from a live form: Phone came out holding just "+1".

    The country box beside it was left empty, because "country code"
    was ruled out of the country rule -- true of a bare box, which
    wants "+1" and not a country name, and wrong of a dropdown, whose
    options read "United States +1".

    Left empty, the user picked the country themselves, after ACE had
    finished. The widget did what it always does and reset the number
    to the dial code, and nothing was still running to put it back.

    So the country is answered, and answered in the pass *before* the
    plain fields rather than the one after them. restoreClobbered()
    still covers a widget that rewrites the number anyway; this is
    what stops it having to.
    """

    _boot_form(
        page,
        PHONE_WIDGET,
    )

    page.eval(
        PHONE_WIDGET_BEHAVIOUR
    )

    page.wait_for(
        "!!document.querySelector('.ace-root')",
        timeout=12,
    )

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "/^Filled/.test("
        "document.querySelector('.ace-root')"
        ".shadowRoot.querySelector('.ace-title')"
        ".textContent)",
        timeout=15,
    )

    assert page.eval(
        "document.getElementById('cc').value"
    ) == "United States +1", (
        "the phone widget's country was left for the user, which is "
        "what let it wipe the number once they answered it"
    )

    assert page.eval(
        "window.__wipes"
    ) == 1, "the country was never actually chosen"

    # The national number, not the stored value whole: the selector
    # beside this box already carries the dial code, and writing it
    # twice is what the duplicate-"+1" report was about. What this
    # test is for is that the number *survived* the country being
    # chosen, which is a separate thing from what shape it takes.
    assert page.eval(
        "document.getElementById('ph').value"
    ) == "555 010 0000", (
        "the number was written before the country and did not "
        "survive it"
    )


# The same widget, reformatting instead of resetting. Until it knows
# which country it is formatting for, it cannot read a leading dial
# code, and drops the digit, leaving a number that is wrong rather than
# merely missing.
#
# This is the case restoreClobbered() cannot rescue. It writes the
# number back, the widget reformats it again on the input event, and
# the check runs once. Only filling the country first avoids it.
PHONE_WIDGET_REFORMATS = """
(function(){
  var input=document.getElementById('cc');
  var menu=document.getElementById('ccmenu');
  var phone=document.getElementById('ph');
  var code='';
  function show(){
    if(menu.innerHTML) return;
    menu.innerHTML='<div role="listbox">'+
      ['United States +1','India +91']
        .map(function(c){return '<div role="option">'+c+'</div>';}).join('')+
      '</div>';
    [].slice.call(menu.querySelectorAll('[role=option]')).forEach(function(o){
      o.addEventListener('click',function(){
        input.value=o.textContent;
        code=(/\\+(\\d+)/.exec(o.textContent)||[0,''])[1];
      });});
  }
  input.addEventListener('focus',show);
  document.getElementById('ccwrap').addEventListener('click',show);
  phone.addEventListener('input',function(){
    var raw=phone.value;
    if(raw.charAt(0)!=='+') return;
    var digits=raw.slice(1).replace(/\\D/g,'');
    // Knows its country: the code is understood and the number kept.
    if(code && digits.indexOf(code)===0) return;
    // Does not: the leading digit is eaten.
    phone.value='+'+digits.slice(1);
  });
  return 1;})()
"""


def test_a_number_typed_before_the_country_is_mangled_by_the_widget(
    page,
) -> None:
    """A number that is wrong, rather than merely missing.

    A phone widget cannot read a leading dial code until it knows which
    country it is formatting for. Written to before the country is
    chosen, it eats the code -- and wrong is what gets sent to the
    employer.

    restoreClobbered() cannot reach this one. It writes the number back
    and the widget reformats it again on the input event, and the check
    runs once, seconds after the fill. Ordering is the whole fix here,
    which is why this test exists alongside the reset one: that case
    passes either way, this one does not.
    """

    _boot_form(
        page,
        PHONE_WIDGET,
    )

    page.eval(
        PHONE_WIDGET_REFORMATS
    )

    page.wait_for(
        "!!document.querySelector('.ace-root')",
        timeout=12,
    )

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "/^Filled/.test("
        "document.querySelector('.ace-root')"
        ".shadowRoot.querySelector('.ace-title')"
        ".textContent)",
        timeout=15,
    )

    assert page.eval(
        "document.getElementById('ph').value"
    ) == "555 010 0000", (
        "the number went in before the widget knew its country, so "
        "the widget ate the dial code"
    )


def test_a_country_code_box_with_no_options_is_still_the_user_s(
    filler,
) -> None:
    """The other half of the same rule.

    A bare text box labelled "country code" wants +1. Answering it
    with "United States" would be a wrong answer on a form about to be
    sent to an employer, which is worse than the blank.
    """

    assert filler.eval(
        "aceAnswerNameFor(aceNormalise('Country code'),'text')"
    ) is None

    assert filler.eval(
        "aceAnswerNameFor(aceNormalise('Country code'),'choice')"
    ) == "Country"


DIAGNOSTIC_FORM = (
    '<form>'
    '<label for="fn">First Name</label><input id="fn">'
    '<label for="ln">Last Name</label><input id="ln">'
    '<label for="em">Email</label><input id="em">'
    '<label for="ph">Phone</label><input id="ph">'
    # What a Workday date section looks like: no label, no text near it,
    # nothing aceQuestionFor can read. These were dropped from the
    # report entirely, which is why a form full of them looked fine in
    # a diagnostic and empty on the page.
    '<div><input data-automation-id="dateSectionMonth-input"></div>'
    # One of them already holding something, so the privacy test below
    # has an unnamed field with a value in it to catch. Without that it
    # passes whatever the unnamed-field lines print, because every
    # unnamed field on the page is empty.
    '<div><input data-automation-id="dateSectionYear-input" '
    'value="x@example.com"></div>'
    '</form>'
)


def test_a_field_ace_cannot_name_is_reported_not_dropped(
    page,
) -> None:
    """The report existed for exactly this failure and hid it.

    A control ACE cannot read a question for is why a box stays empty,
    so it is the most useful line in the report -- and it was the one
    line that was skipped. A form whose date widgets ACE could not name
    produced a diagnostic that listed only the fields that worked.
    """

    _boot_form(
        page,
        DIAGNOSTIC_FORM,
    )

    page.wait_for(
        "!!window.__aceInternals",
        timeout=12,
    )

    report = page.eval(
        "window.__aceInternals.diagnostics()"
    )

    assert "could not read a question for (2)" in report, (
        "the unnamed date sections were dropped from the report"
    )

    assert "dateSectionMonth-input" in report, (
        "the report does not say what the unreadable field calls "
        "itself, which is the only thing that identifies it"
    )


def test_the_diagnostic_carries_no_answers(
    page,
) -> None:
    """It goes on a clipboard and into a conversation.

    The bank behind it holds a home address and the EEO answers, so the
    report names questions and control shapes and never values. The new
    unnamed-field lines print attribute *names*; an attribute value
    could itself be an answer.
    """

    _boot_form(
        page,
        DIAGNOSTIC_FORM,
    )

    page.wait_for(
        "!!window.__aceInternals",
        timeout=12,
    )

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "!!document.getElementById('em').value",
        timeout=12,
    )

    report = page.eval(
        "window.__aceInternals.diagnostics()"
    )

    # Every value in the test bank, including the ones now sitting in
    # the boxes the report is describing.
    for secret in (
        "Alex",
        "Rivera",
        "x@example.com",
        "+1 555 010 0000",
        "425 000 0000",
        "linkedin.com/in/x",
        "Ashfield",
    ):
        assert secret not in report, (
            "the diagnostic leaked a stored answer: " + secret
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


# Greenhouse's own phone widget, which labels its dial-code selector
# bare "Country" -- the same three words the mailing-address question
# uses. No wording rule can separate those two, so the shape has to:
# this one is a combobox sitting immediately beside Phone.
GREENHOUSE_PHONE_WIDGET = (
    '<form>'
    '<label for="fn">First Name</label><input id="fn">'
    '<label for="ln">Last Name</label><input id="ln">'
    '<label for="cc">Country</label>'
    '<div id="ccouter"><div id="ccwrap" class="select__control">'
    '<input id="cc" role="combobox"></div>'
    '<div id="ccmenu"></div></div>'
    '<label for="ph">Phone</label><input id="ph">'
    '</form>'
)


def test_a_bare_country_label_beside_phone_is_the_dial_code_selector(
    page,
) -> None:
    """Reported from a live Greenhouse form.

    The selector is labelled "Country", not "Country code", so the
    wording list that recognises a phone widget's own country did not
    match it and the ordering fix never applied. Nothing in the words
    could have matched: a mailing address asks "Country" too.

    What separates them is the shape. This one is a combobox sitting
    immediately next to Phone, which is the layout the widget always
    uses and an address never does.
    """

    _boot_form(
        page,
        GREENHOUSE_PHONE_WIDGET,
    )

    page.wait_for(
        "!!window.__aceInternals",
        timeout=12,
    )

    assert page.eval(
        "window.__aceInternals.gatesAPlainField("
        "document.getElementById('cc'))"
    ), (
        "a bare 'Country' combobox beside Phone was not recognised "
        "as the phone widget's own selector, so the number still "
        "goes in before the country"
    )


def test_a_country_selector_far_from_phone_is_left_alone(
    page,
) -> None:
    """The guard on the shape test, and the reason it is one hop.

    A mailing-address Country is the same word and can be the same
    kind of control. What it is not is the box next to Phone, so a
    Country with other questions between it and the number must not be
    treated as a dial-code selector -- mis-reading one strips the
    country code off a number that needed it.
    """

    _boot_form(
        page,
        '<form>'
        '<label for="fn">First Name</label><input id="fn">'
        '<label for="cc">Country</label>'
        '<div id="ccouter"><div id="ccwrap" class="select__control">'
        '<input id="cc" role="combobox"></div>'
        '<div id="ccmenu"></div></div>'
        '<label for="ci">City</label><input id="ci">'
        '<label for="pc">Postcode</label><input id="pc">'
        '<label for="ph">Phone</label><input id="ph">'
        '</form>',
    )

    page.wait_for(
        "!!window.__aceInternals",
        timeout=12,
    )

    assert not page.eval(
        "window.__aceInternals.gatesAPlainField("
        "document.getElementById('cc'))"
    ), (
        "a mailing-address Country two questions away from Phone was "
        "read as a dial-code selector"
    )


def test_the_number_does_not_repeat_the_dial_code_beside_it(
    page,
) -> None:
    """Reported with a screenshot: Country showing "+1" and Phone
    reading "+1 425-568-6378" right next to it.

    The selector already carries the code, so the box beside it takes
    the national number alone. The duplicate was not merely untidy --
    the widget treats the pair as one value, so editing the extra "+1"
    out of the number reset the selector too, and there was no way to
    correct one side by hand.
    """

    _boot_form(
        page,
        GREENHOUSE_PHONE_WIDGET,
    )

    page.wait_for(
        "!!document.querySelector('.ace-root')",
        timeout=12,
    )

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "!!document.getElementById('ph').value",
        timeout=15,
    )

    written = page.eval(
        "document.getElementById('ph').value"
    )

    assert "+" not in written, (
        "the number repeated the dial code the selector already "
        f"shows: {written!r}"
    )

    # The number itself still has to arrive whole. Stripping the code
    # must not take digits with it.
    assert "".join(
        c for c in written if c.isdigit()
    ) == "5550100000", written


def test_a_lone_number_box_still_gets_the_whole_number(
    page,
) -> None:
    """The other direction, and the reason the strip is conditional.

    With no selector beside it, the number box is the only place the
    country code can go. Taking it off there would submit a number
    missing its country code to every ordinary form.
    """

    _boot_form(
        page,
        '<form>'
        '<label for="fn">First Name</label><input id="fn">'
        '<label for="ln">Last Name</label><input id="ln">'
        '<label for="em">Email</label><input id="em">'
        '<label for="ph">Phone</label><input id="ph">'
        '</form>',
    )

    page.wait_for(
        "!!document.querySelector('.ace-root')",
        timeout=12,
    )

    page.eval(
        "document.dispatchEvent(new KeyboardEvent("
        "'keydown',{key:'a',altKey:true,bubbles:true}));1"
    )

    page.wait_for(
        "!!document.getElementById('ph').value",
        timeout=15,
    )

    assert page.eval(
        "document.getElementById('ph').value"
    ) == "+1 555 010 0000", (
        "an ordinary phone box lost its country code"
    )
