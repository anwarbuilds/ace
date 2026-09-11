/* Fills the form, and stops there.

   Nothing here submits, and nothing overwrites a box that already has
   something in it. The user is about to send this to an employer, so
   every uncertain case is left for them and reported rather than
   guessed at. */

(function () {
  /* Injected on demand as well as declared in the manifest, so this
     runs twice on a page where both happen. Two copies means two
     panels and two fills, so the second one leaves quietly.

     A content script gets its own isolated world, but the same world
     each time, so a flag on window is visible to the next injection
     and invisible to the page. */
  if (window.__aceLoaded) return;
  window.__aceLoaded = true;

  var answers = {};
  var aliases = {};
  // Work and study history, most recent first. Kept apart from answers
  // because they are a list, not a value: the second block on a form
  // asks the same questions as the first and must get a different job.
  var histories = { work: [], education: [] };
  // The fields the history pass owns on this page, so the flat pass
  // leaves them alone. Without this the bank's single "University"
  // would be typed into every school box of every education block.
  var historyOwned = null;
  var lastFill = [];
  var loaded = false;
  // The element fillOne actually ticked, which for a group is not
  // the one it was handed.
  var lastPicked = null;
  var filledOnce = false;
  var lastResult = null;
  var pending = null;
  // Set when the user explicitly closes the panel. Without this,
  // closing it was only ever temporary: the MutationObserver below
  // fires on essentially any DOM change, and refresh() re-created the
  // panel within 400ms regardless of why it had been closed -- on a
  // page where ACE's own panel sat over the real Submit button, there
  // was no way to get it out of the way to click through.
  var dismissed = false;
  var lastHref = "";
  var lastSignature = "";
  var filling = false;

  function setNatively(field, value) {
    // React tracks its own value on the node and ignores a plain
    // assignment, so the change never reaches its state and the box
    // reverts the moment it re-renders. The prototype setter is what
    // React's own listeners see.
    var prototype =
      field instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : field instanceof HTMLSelectElement
          ? HTMLSelectElement.prototype
          : HTMLInputElement.prototype;

    var setter = Object.getOwnPropertyDescriptor(prototype, "value").set;

    // Focused first. Some widgets only accept input into the focused
    // control, and the blur at the end is what a validation library
    // waits for. preventScroll because filling a long form otherwise
    // jumps the page to each field in turn.
    try {
      field.focus({ preventScroll: true });
    } catch (error) {
      /* a detached or disabled field cannot take focus; fill anyway */
    }

    // React records the last value it saw in a tracker on the node and
    // compares against it when the input event arrives. Assigning
    // through the prototype deliberately bypasses that tracker, which
    // is what makes the event look like a real edit. When the value
    // being written is one React already has recorded, the comparison
    // matches and React discards the event as "nothing changed", so
    // the tracker is rewound to guarantee it disagrees.
    var tracker = field._valueTracker;

    if (tracker && typeof tracker.setValue === "function") {
      tracker.setValue(value === field.value ? "" : field.value);
    }

    setter.call(field, value);

    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));

    // Blurred last. Formik and React Hook Form mark a field touched,
    // and run its validator, on blur and not before: without this a
    // box with the right answer visibly in it still submits as "this
    // field is required", which is what the user was hitting.
    try {
      field.blur();
    } catch (error) {
      /* nothing to restore if it never took focus */
    }
  }

  /* A select showing "Select ..." is empty, whatever its value says.
     Treating a placeholder as an answer made ACE skip the disability
     status question on a real Lever form and report it as already
     filled. */
  // A radio and checkbox report emptiness through .checked; Ashby's
  // button pair has no such property and uses aria-pressed instead.
  function aceIsChosen(field) {
    if (field.tagName === "BUTTON") {
      return field.getAttribute("aria-pressed") === "true";
    }

    return !!field.checked;
  }

  function aceIsEmpty(field) {
    // A checkbox reports value "on" whether or not it is ticked, so
    // testing value counted every unticked box as already answered and
    // ACE skipped whole groups it could have filled.
    if (aceIsChoiceControl(field)) {
      return !aceIsChosen(field);
    }

    if (field.tagName !== "SELECT") return !field.value;

    var option = field.options[field.selectedIndex];
    if (!option) return true;
    if (!option.value) return true;

    // "No answer" is JazzHR's default for every dropdown, and it is a
    // placeholder however it reads: treating it as an answer made ACE
    // skip the relocation and felony questions on a real form and
    // report them as already filled.
    //
    // Deliberately not including "none", which a person can mean.
    // These are all wordings a form ships selected, never ones a
    // person chooses.
    return /^(select|choose|please select|please choose|select one|no answer|n\/a|-+|)\s*\.*$/.test(
      aceNormalise(option.textContent)
    );
  }

  function fillable() {
    var normal = Array.prototype.filter.call(
      document.querySelectorAll("input, select, textarea"),
      function (field) {
        if (field.disabled || field.readOnly) return false;
        if (field.type === "hidden" || field.type === "file") return false;
        if (field.type === "submit" || field.type === "button") return false;
        if (!field.offsetParent && field.type !== "radio") return false;
        if (aceShouldSkip(field)) return false;
        return true;
      }
    );

    // A Yes/No rendered as two real <button> elements is excluded by
    // the plain input/select/textarea query above. Every button on the
    // page is considered and then filtered through aceIsChoiceControl,
    // which requires one of the attributes that declare a button to be
    // a choice: Ashby's own data-option, or the accessibility state
    // that Oracle's Candidate Experience uses instead. A submit button
    // carries none of them. Matching only data-option meant ACE could
    // not see a single one of the twenty-two questions on a real Dell
    // application.
    var choiceButtons = Array.prototype.filter.call(
      document.querySelectorAll("button"),
      function (field) {
        if (field.disabled || !field.offsetParent) return false;
        if (field.type === "submit") return false;
        return aceIsChoiceControl(field);
      }
    );

    return normal.concat(choiceButtons);
  }

  function chooseOption(select, wanted, alts) {
    var options = Array.prototype.slice.call(select.options);

    // A placeholder is not an answer, and leaving it in the running
    // lets "Select ..." win a containment match against anything.
    var offered = options.filter(function (option, index) {
      return !(index === 0 && !option.value);
    });

    var index = aceChooseOption(
      offered.map(function (option) { return option.textContent; }),
      wanted,
      alts
    );

    return index >= 0 ? offered[index] : null;
  }

  /* What shape of answer this control can accept.

     Computed from the options themselves rather than declared, because
     a Yes/No pair and a gender list are the same markup. Passing it to
     the matcher is what stops a free-text answer reaching a control
     that offers only Yes and No -- on a real Dell form that alone
     stopped a stored degree being offered to "are you a recent
     graduate", and a stored state to three separate questions naming
     the United States. */
  function kindOf(field) {
    if (!aceIsChoiceControl(field)) {
      return aceFieldKind(field, null);
    }

    return aceFieldKind(
      field,
      groupMembers(field).map(aceOptionText)
    );
  }

  /* Every input in this control's group, in the order a person reads
     them. Radios and checkboxes are one question spread over several
     elements, so the choice is made across the whole group at once
     rather than by testing each box against the answer alone. */
  function groupMembers(field) {
    if (field.tagName === "BUTTON") {
      // No shared name attribute links these buttons to each other;
      // the pair only shares an immediate parent.
      // Ashby marks its pair with data-option; Oracle's Candidate
      // Experience, which Dell runs on, marks the same shape with the
      // accessibility state instead. Both are gathered and then
      // filtered, so a decorative button in the same parent is not
      // mistaken for one of the choices.
      var siblings = field.parentElement
        ? Array.prototype.slice.call(
            field.parentElement.querySelectorAll("button")
          ).filter(aceIsChoiceControl)
        : [];

      return siblings.length ? siblings : [field];
    }

    var name = field.getAttribute("name");
    var scope = field.closest("fieldset, [role=radiogroup], [role=group]");

    if (!scope && name) {
      var node = field.parentElement;
      for (var depth = 0; node && depth < 8; depth++) {
        if (node.querySelectorAll('[name="' + CSS.escape(name) + '"]').length > 1) {
          scope = node;
          break;
        }
        node = node.parentElement;
      }
    }

    if (!scope) return [field];

    var selector = 'input[type="' + field.type + '"]' +
      (name ? '[name="' + CSS.escape(name) + '"]' : "");

    var members = Array.prototype.slice.call(scope.querySelectorAll(selector));

    return members.length ? members : [field];
  }

  /* `alts` is the other wordings ACE ships for this same answer. It is
     passed rather than looked up, because fillOne is handed a value and
     never the question it came from. */
  function fillOne(field, value, alts) {
    if (field.tagName === "SELECT") {
      var option = chooseOption(field, value, alts);
      if (!option) return false;
      setNatively(field, option.value);
      return true;
    }

    if (aceIsChoiceControl(field)) {
      // Decided across the group, so the answer competes with every
      // option at once. Testing one box in isolation ticked both
      // "male" and "female", because one contains the other.
      var members = groupMembers(field);

      if (members[0] !== field) return false;

      var chosen = aceChooseOption(
        members.map(aceOptionText),
        value,
        alts
      );

      if (chosen < 0) return false;

      var target = members[chosen];

      if (aceIsChosen(target)) return false;

      target.click();

      // Reported against the element actually ticked, not the first in
      // the group, so undo and the outline follow the right box.
      lastPicked = target;

      return true;
    }

    if (aceIsAutocomplete(field)) {
      // Never the generic text path: a raw value it does not
      // recognise does not stay as harmless unmatched text, it gets
      // silently replaced by whatever the widget defaults to. Handled
      // separately in fillComboboxes, which can actually see its
      // options.
      return false;
    }

    setNatively(field, value);
    return true;
  }

  /* Every history block on the page, in the order a person reads them.

     The employer box is the anchor: one per block, present in every
     block, and the thing the block is about. A block is then the
     smallest ancestor holding that box and no other employer box --
     the same climb aceOwnGroup does for a single question, widened to
     a repeating unit. Every other history field is assigned to
     whichever block contains it.

     Returns a list of {node, fields:[{field, role}]}, or an empty list
     on a page that has no such section, which is most of them. */
  function historyBlocks(kind) {
    var anchors = [];

    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;

      if (aceHistoryRole(field, question) === "employer") {
        anchors.push(field);
      }
    });

    if (anchors.length < 1) return [];

    var blocks = anchors.map(function (field) {
      return { node: blockAround(field, anchors), fields: [] };
    }).filter(function (block) {
      return !!block.node;
    });

    if (!blocks.length) return [];

    // Assign every history field to its block. Done as a second pass
    // rather than by querying inside each block, because a date
    // dropdown's side depends on where it sits within the block and
    // that is only knowable once the block is known.
    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;

      var role = aceHistoryRole(field, question);
      if (!role) return;

      for (var i = 0; i < blocks.length; i++) {
        if (!blocks[i].node.contains(field)) continue;

        if (role === "month" || role === "year") {
          var side = aceDateSide(field, blocks[i].node);
          if (!side) return;
          role = side + (role === "month" ? "Month" : "Year");
        }

        blocks[i].fields.push({ field: field, role: role });
        return;
      }
    });

    return blocks;
  }

  /* The smallest ancestor holding this employer box and no other. */
  function blockAround(field, anchors) {
    var node = field.parentElement;
    var best = null;

    for (var depth = 0; node && depth < 12; depth++) {
      var inside = anchors.filter(function (other) {
        return node.contains(other);
      });

      if (inside.length > 1) break;

      best = node;
      node = node.parentElement;
    }

    return best;
  }

  /* Which fields the history pass will handle, so the flat pass skips
     them. Recomputed per pass, because a Remove link changes it. */
  function historyFieldSet() {
    var owned = [];

    ["work", "education"].forEach(function (kind) {
      historyBlocks(kind).forEach(function (block) {
        block.fields.forEach(function (entry) {
          owned.push(entry.field);
        });
      });
    });

    return owned;
  }

  function ownedByHistory(field) {
    if (historyOwned === null) historyOwned = historyFieldSet();

    return historyOwned.indexOf(field) >= 0;
  }

  /* What the history pass would do, block by block.

     A page's blocks are matched to stored entries by position: the
     first block gets the most recent job, because that is the order
     every one of these forms lists them in. A block with no entry
     behind it is left entirely alone rather than half-filled.

     `apply` false reports without touching the page, which is what
     the preview needs. */
  function runHistory(kind, apply) {
    var entries = histories[kind] || [];
    if (!entries.length) return [];

    var done = [];

    // A Yes/No group is two elements holding one answer, so without
    // this the preview lists "Job 1 current: Yes" twice and reads like
    // a mistake.
    var reported = {};

    historyBlocks(kind).forEach(function (block, index) {
      var entry = entries[index];
      if (!entry) return;

      block.fields.forEach(function (slot) {
        var value = aceHistoryValue(entry, slot.role);
        if (!value) return;

        var group = aceIsChoiceControl(slot.field)
          ? groupMembers(slot.field)
          : [slot.field];

        if (!group.every(aceIsEmpty)) return;

        var label = historyLabel(kind, index, slot.role);

        if (!apply) {
          if (reported[label]) return;
          reported[label] = 1;

          done.push([
            label,
            value
          ]);
          return;
        }

        lastPicked = null;

        var previous = slot.field.value;

        if (!fillOne(slot.field, value)) return;

        var touched = lastPicked || slot.field;

          lastFill.push({
          field: touched,
          previous: previous,
          wrote: value,
          ticked: aceIsChoiceControl(touched)
        });

        if (reported[label]) return;
        reported[label] = 1;

        done.push([
          label,
          value
        ]);
      });
    });

    return done;
  }

  var ACE_ROLE_LABELS = {
    employer: "employer",
    jobTitle: "title",
    location: "location",
    isCurrent: "current",
    startMonth: "start month",
    startYear: "start year",
    endMonth: "end month",
    endYear: "end year",
    description: "description"
  };

  function historyLabel(kind, index, role) {
    return (kind === "work" ? "Job " : "Study ") + (index + 1) +
      " " + (ACE_ROLE_LABELS[role] || role);
  }

  function plan() {
    var filled = [];
    var unknown = [];
    // A question ACE knows, holding an answer that matches none of the
    // offered options. Silence here is the worst kind: the user thinks
    // it was handled. Naming it tells them exactly what to reword.
    var unmatched = [];
    var already = 0;

    historyOwned = null;

    fillable().forEach(function (field) {
      // A repeating block's fields belong to the history pass below.
      // The bank holds one value per question, so left to the flat
      // pass its single "University" would be typed into every school
      // box of every education block.
      if (ownedByHistory(field)) return;

      var question = aceQuestionFor(field);
      if (!question) return;

      var name = aceAnswerNameFor(question, kindOf(field));

      if (!name) {
        // Only worth reporting once per question, and only for things
        // that look like real questions rather than search boxes.
        var short = question.split(" | ")[0].slice(0, 60);
        if (short && unknown.indexOf(short) < 0) unknown.push(short);
        return;
      }

      var value = answers[name];
      if (!value) return;

      // A group with any box ticked is answered, whichever box it is.
      // Testing only the element in hand treated every unticked option
      // of an answered question as still needing an answer.
      var group = aceIsChoiceControl(field)
        ? groupMembers(field)
        : [field];

      if (!group.every(aceIsEmpty)) {
        if (group[0] === field) already += 1;
        return;
      }

      var previous = field.value;

      lastPicked = null;

      var isChoice =
        field.tagName === "SELECT" ||
        aceIsChoiceControl(field);

      if (!fillOne(field, value, aliases[name])) {
        if (isChoice && unmatched.indexOf(name) < 0) unmatched.push(name);
        return;
      }

      var touched = lastPicked || field;

      lastFill.push({
        field: touched,
        previous: previous,
        wrote: value,
        ticked: aceIsChoiceControl(touched)
      });

      filled.push(name);
    });

    // A group ticked by one of its options is answered, whatever its
    // other options reported on the way past.
    unmatched = unmatched.filter(function (name) {
      return filled.indexOf(name) < 0;
    });

    ["work", "education"].forEach(function (kind) {
      runHistory(kind, true).forEach(function (pair) {
        filled.push(pair[0]);
      });
    });

    return {
      filled: filled,
      unknown: unknown,
      unmatched: unmatched,
      already: already
    };
  }

  /* An Ashby-style autocomplete is a fourth control shape: its real
     options exist only after the listbox opens, and that render is
     asynchronous, confirmed against the live widget -- reading
     [role=option] in the same synchronous tick as the click that
     opens it finds nothing. Everything else in this file runs
     synchronously; this is deliberately kept separate rather than
     making the whole pipeline async for one widget type. */
  /* The menu belonging to one field, never just any menu on the page.

     This was `document.querySelector("[role=listbox]")`, which is the
     first listbox in the document regardless of what it belongs to.
     DoorDash's Greenhouse form keeps a phone country-code list of 244
     options permanently mounted, so every combobox question on that
     form was answered against a list of countries: "Yes" matched none
     of them and the field was left blank, which is what the user saw.

     Worse than blank was possible. A stored country of "United States
     Of America" against a phone list containing "United States+1" is
     exactly the kind of near-match aceChooseOption accepts, and the
     click would have landed in the phone widget: a wrong answer on a
     form about to be sent to an employer, which is the one outcome
     this extension is built to avoid. */
  function comboboxOptions(field) {
    var box = null;

    // What the field itself says its menu is. The explicit answer,
    // when the widget bothers to give one.
    var id =
      field.getAttribute("aria-controls") ||
      field.getAttribute("aria-owns");

    if (id) box = document.getElementById(id);

    // react-select, which is what Greenhouse renders, points at
    // nothing and simply puts the menu inside the field's own
    // container. Climb until a listbox turns up, and stop climbing the
    // moment the subtree holds a second combobox: past that point any
    // listbox found could belong to the neighbour rather than to this
    // field, which is the mistake this whole function exists to not
    // make again.
    if (!box) {
      var scope = field.parentElement;

      // Bounded deliberately. On Greenhouse the menu sits four levels
      // above the input, as a sibling of the control; anything beyond
      // that is the page, not the widget. An unbounded climb reaches
      // <body> and finds the first listbox in the document, which is
      // the bug this replaced.
      for (var depth = 0; depth < 5 && scope; depth++) {
        if (scope === document.body) break;
        if (scope.tagName === "FORM") break;

        // Past a second combobox the subtree covers a neighbour too,
        // and a menu found here could be theirs.
        if (scope.querySelectorAll("[role=combobox]").length > 1) break;

        box = scope.querySelector("[role=listbox]");
        if (box) break;

        scope = scope.parentElement;
      }
    }

    return box
      ? Array.prototype.slice.call(box.querySelectorAll("[role=option]"))
      : [];
  }

  /* Get the menu open.

     A plain .click() is enough for a widget with a real toggle button,
     which is what Ashby renders and what this used to assume. It is
     not enough for react-select: that opens on mousedown, and
     dispatching a click sends no mousedown at all, so the menu stayed
     shut and ACE went on to read whatever listbox it could find. */
  function openCombobox(field) {
    var toggle =
      field.parentElement &&
      field.parentElement.querySelector("button");

    if (toggle) {
      toggle.click();
      return;
    }

    try {
      field.focus({ preventScroll: true });
    } catch (error) {
      /* a field that cannot take focus can still be tried below */
    }

    var control =
      field.closest('[class*="control"]') ||
      field.parentElement ||
      field;

    [
      "pointerdown",
      "mousedown",
      "mouseup",
      "click"
    ].forEach(function (type) {
      control.dispatchEvent(
        new MouseEvent(type, {
          bubbles: true,
          cancelable: true,
          view: window,
          button: 0,
          detail: 1
        })
      );
    });

    // ARIA's own way to open a combobox, for anything that ignores a
    // pointer sequence it did not receive from a person.
    field.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "ArrowDown",
        code: "ArrowDown",
        keyCode: 40,
        which: 40,
        bubbles: true
      })
    );
  }

  function waitForComboboxOptions(field, timeoutMs) {
    return new Promise(function (resolve) {
      var start = Date.now();

      (function poll() {
        var options = comboboxOptions(field);

        if (options.length || Date.now() - start > timeoutMs) {
          resolve(options);
          return;
        }

        setTimeout(poll, 60);
      })();
    });
  }

  function closeCombobox(field) {
    field.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Escape",
        code: "Escape",
        keyCode: 27,
        bubbles: true
      })
    );

    field.blur();
  }

  /* Type into a combobox without closing it.

     Deliberately not setNatively: that blurs at the end, and blurring
     a combobox closes the menu the typing just opened. Everything
     else about committing a value to a framework is the same.  */
  function typeIntoCombobox(field, text) {
    var setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value"
    ).set;

    try {
      field.focus({ preventScroll: true });
    } catch (error) {
      /* an unfocusable field still gets the value and the event */
    }

    var tracker = field._valueTracker;

    if (tracker && typeof tracker.setValue === "function") {
      tracker.setValue(text === field.value ? "" : field.value);
    }

    setter.call(field, text);

    field.dispatchEvent(new Event("input", { bubbles: true }));
  }

  /* The queries to try, longest first.

     Some lists hold every city on earth and every university, and
     offer nothing at all until something is typed, which is why ACE
     left them empty on every Greenhouse form the user filled. The
     whole answer is tried first, because "University of Washington"
     is written the way the list writes it. A city is not: the answer
     says "Bothell" or "Seattle WA" and the list says "Bothell,
     Washington, United States", so the first word is tried after it.  */
  function searchTerms(value) {
    var whole = String(value == null ? "" : value).trim();
    if (!whole) return [];

    var first = whole.split(/\s+/)[0];

    return first && first !== whole ? [whole, first] : [whole];
  }

  function optionsByTyping(field, value) {
    var terms = searchTerms(value);

    return terms.reduce(function (chain, term) {
      return chain.then(function (found) {
        if (found && found.length) return found;

        typeIntoCombobox(field, term);

        return waitForComboboxOptions(field, 1200);
      });
    }, Promise.resolve([]));
  }

  function fillOneCombobox(field, value, alts) {
    var typed = false;

    openCombobox(field);

    return waitForComboboxOptions(field, 900).then(function (options) {
      if (options.length) return options;

      typed = true;

      return optionsByTyping(field, value);
    }).then(function (options) {
      if (!options.length) {
        if (typed) typeIntoCombobox(field, "");
        closeCombobox(field);
        return { matched: false };
      }

      var texts = options.map(function (option) {
        return option.textContent;
      });

      var index = aceChooseOption(texts, value, alts);

      if (index < 0) {
        // No option fits. Closed rather than left open with nothing
        // chosen, and the search text is taken back out -- a wrong
        // option is worse than this question staying blank for the
        // user to answer themselves, and a half-typed city left
        // sitting in the box is worse than either.
        if (typed) typeIntoCombobox(field, "");
        closeCombobox(field);
        return { matched: false };
      }

      options[index].click();

      return { matched: true, text: texts[index] };
    });
  }

  /* Every autocomplete on the page, filled one at a time -- two open
     listboxes at once would make comboboxOptions() ambiguous about
     which one it is reading. */
  function fillComboboxes() {
    var filled = [];
    var unmatched = [];

    var fields = fillable().filter(aceIsAutocomplete);

    return fields
      .reduce(function (chain, field) {
        return chain.then(function () {
          var question = aceQuestionFor(field);
          if (!question) return;

          var name = aceAnswerNameFor(question, kindOf(field));
          if (!name) return;

          var value = answers[name];
          if (!value) return;

          if (!aceIsEmpty(field)) return;

          var previous = field.value;

          return fillOneCombobox(field, value, aliases[name])
            .then(function (outcome) {
            if (!outcome.matched) {
              if (unmatched.indexOf(name) < 0) unmatched.push(name);
              return;
            }

            lastFill.push({
              field: field,
              previous: previous,
              ticked: false
            });

            filled.push(name);
          });
        });
      }, Promise.resolve())
      .then(function () {
        return { filled: filled, unmatched: unmatched };
      });
  }

  /* Put back anything the page overwrote after ACE wrote it.

     Comboboxes are filled in a second pass, because each one has to be
     opened and waited on, and a widget can rewrite a field that the
     first pass already filled. A phone box is the case that showed it:
     ACE filled the number, then chose the country beside it, and the
     phone widget reset the field to its dial code. The user was left
     looking at a Phone reading "+1".

     Only fields ACE wrote itself are touched, and only when the value
     is no longer the one it wrote, so this can never overwrite the
     user or fight a widget that legitimately reformats what it was
     given. Reformatting is why the comparison is on the digits and
     letters alone: a phone box that renders "+1 425 568 6378" as
     "(425) 568-6378" has kept the number, and rewriting it would
     start a loop.  */
  function restoreClobbered() {
    lastFill.forEach(function (record) {
      if (record.ticked) return;
      if (!record.wrote) return;
      if (!record.field.isConnected) return;

      var now = aceNormalise(String(record.field.value || ""));
      var meant = aceNormalise(String(record.wrote));

      if (!meant) return;
      if (now === meant) return;

      // Same content, differently punctuated, is not a clobbering. A
      // phone box that renders "+1 425 568 6378" as "(425) 568-6378"
      // has kept the number, and rewriting it would start a loop.
      var bareNow = now.replace(/[^a-z0-9]/g, "");
      var bareMeant = meant.replace(/[^a-z0-9]/g, "");

      if (bareNow === bareMeant) return;

      var shorter = bareNow.length <= bareMeant.length
        ? bareNow
        : bareMeant;

      var longer = bareNow.length <= bareMeant.length
        ? bareMeant
        : bareNow;

      // Long enough to be the content rather than a fragment of it:
      // the field this exists for came back holding "1".
      if (shorter.length >= 5 && longer.indexOf(shorter) >= 0) return;

      setNatively(record.field, record.wrote);
    });
  }

  function undo() {
    lastFill.forEach(function (record) {
      if (record.ticked && record.field.tagName === "BUTTON") {
        // Ashby's Yes/No widget has no property to unset; clicking the
        // same button again is what toggles it back off, confirmed
        // against the live control rather than assumed.
        record.field.click();
      } else if (record.ticked) {
        record.field.checked = false;
        record.field.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        setNatively(record.field, record.previous);
      }
    });
    lastFill = [];
  }

  /* Long option text is a definition paragraph in EEO questions, and
     the panel is 330px wide. */
  function tidy(text) {
    var value = String(text == null ? "" : text)
      .replace(/\s+/g, " ")
      .trim();

    return value.length > 54 ? value.slice(0, 51).trim() + "..." : value;
  }

  function esc(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render(host, html) {
    host.innerHTML = html;
  }

  /* Whether this page is a form at all.

     Silence on a covered site looks the same as an extension that
     failed to load, so ACE says "nothing to fill" where the page is
     clearly a form and stays quiet everywhere else. */
  function looksLikeForm() {
    return fillable().filter(function (field) {
      return field.type !== "radio" && field.type !== "checkbox";
    }).length >= 4;
  }

  /* Whether this page is an application form worth waking up for.

     The manifest used to name the boards ACE ran on, and that list
     could not be made to hold: a substantial share of one real user's applications
     went through 19 hosts it did not cover, because most companies
     self-host on their own domain -- stripe.com, careers.roblox.com,
     nuro.ai -- and Oracle hands each tenant a subdomain of its own.
     Adding them one at a time is a game with no last move.

     So the extension runs everywhere and decides for itself, and this
     is the decision. Counting boxes is not enough on a page that could
     be anything, so it also requires that ACE recognise a couple of the
     questions. That costs nothing -- naming a question needs no
     network and no answers -- and it is the honest test: a page where
     ACE knows none of the questions is a page it has nothing to say
     about, whatever the host. */
  function looksLikeApplication() {
    if (!looksLikeForm()) return false;

    var recognised = 0;

    var fields = fillable();

    for (var i = 0; i < fields.length; i++) {
      var question = aceQuestionFor(fields[i]);
      if (!question) continue;

      if (aceAnswerNameFor(question, kindOf(fields[i]))) {
        recognised += 1;
        if (recognised >= 2) return true;
      }
    }

    return false;
  }

  /* The panel's own stylesheet, carried here rather than injected into
     the page, because it is mounted in a shadow root and the page's
     stylesheet cannot reach inside one.

     It used to be a plain div under document.body with content.css
     injected alongside it. That put ACE's markup at the mercy of
     whatever the employer's site does to a bare div: on Ashby the
     panel's own lines were drawn on top of each other and the whole
     thing was unreadable. No amount of defensive CSS wins that
     argument reliably, because the next board will reset something
     else. A shadow root ends it: nothing the page declares crosses
     the boundary, in either direction. */
  var PANEL_CSS = "/* Deliberately narrow selectors and a high stacking context: this\n   panel lives inside somebody else's stylesheet and must neither\n   inherit from it nor be painted over by it. */\n/* Anchored top-right, not bottom-right: a form's own Submit control\n   is almost always at the bottom of the page, and a fixed panel\n   sitting on top of it blocks the one click the user needs most. */\n.ace-panel{\n  position:fixed;right:18px;top:18px;z-index:2147483647;\n  width:330px;max-height:min(70vh,560px);display:flex;flex-direction:column;\n  background:#1c1229;color:#f4f0fa;border:1px solid #4a3468;border-radius:12px;\n  box-shadow:0 16px 48px rgba(0,0,0,.42);\n  font:13px/1.5 -apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif;\n  overflow:hidden}\n.ace-panel *{box-sizing:border-box;font-family:inherit}\n\n.ace-head{display:flex;align-items:center;gap:9px;padding:12px 14px;border-bottom:1px solid #33244a}\n.ace-mark{width:20px;height:20px;border-radius:5px;background:#c9a227;color:#231633;\n  font-weight:700;font-size:11px;display:flex;align-items:center;justify-content:center;flex:0 0 auto}\n.ace-title{font-weight:600;font-size:13px}\n.ace-sub{font-size:11px;color:#b3a3cd;margin-top:1px}\n.ace-ver{margin-left:auto;font-size:10px;color:#6f6090;letter-spacing:.04em;flex:0 0 auto}\n.ace-x{margin-left:6px;background:none;border:0;color:#8d7ca8;cursor:pointer;\n  font-size:17px;line-height:1;padding:2px 4px;border-radius:4px}\n.ace-x:hover{background:#2a1b3d;color:#f4f0fa}\n\n.ace-body{overflow-y:auto;padding:6px 0;flex:1 1 auto}\n.ace-body::-webkit-scrollbar{width:8px}\n.ace-body::-webkit-scrollbar-thumb{background:#3d2b58;border-radius:4px}\n\n.ace-group{font-size:10px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;\n  color:#8d7ca8;padding:10px 14px 4px}\n.ace-item{display:flex;gap:9px;align-items:flex-start;padding:5px 14px}\n.ace-item .k{color:#b3a3cd;font-size:11.5px;flex:0 0 40%;word-break:break-word}\n.ace-item .v{color:#f4f0fa;font-size:11.5px;flex:1 1 auto;word-break:break-word}\n.ace-item.miss .v{color:#e8b84b}\n.ace-item.skip .v{color:#8d7ca8}\n\n.ace-foot{padding:11px 14px;border-top:1px solid #33244a;display:flex;gap:8px;align-items:center}\n.ace-btn{background:#c9a227;color:#231633;border:0;padding:8px 14px;border-radius:7px;\n  font-weight:600;font-size:12.5px;cursor:pointer}\n.ace-btn:hover{background:#dcb534}\n.ace-btn.ghost{background:transparent;color:#b3a3cd;border:1px solid #4a3468}\n.ace-btn.ghost:hover{background:#2a1b3d;color:#f4f0fa}\n.ace-link{background:none;border:0;padding:0;margin-left:auto;font-size:11px;\n  color:#8d7ca8;cursor:pointer;text-decoration:underline;font-family:inherit}\n.ace-link:hover{color:#f4f0fa}\n.ace-note{font-size:11px;color:#b3a3cd}\n.ace-note.warn{color:#e8b84b}\n\n\n@media (prefers-reduced-motion:no-preference){\n  .ace-panel{animation:ace-in .16s ease-out}\n  @keyframes ace-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}\n}";

  function panel() {
    var existing = document.querySelector(".ace-root");

    if (existing && existing.shadowRoot) {
      return existing.shadowRoot.querySelector(".ace-panel");
    }

    var host = document.createElement("div");
    host.className = "ace-root";

    // The host itself is the one node the page can see, so it carries
    // nothing for a stylesheet to act on beyond taking it out of flow.
    host.style.cssText =
      "all:initial;position:fixed;top:0;left:0;width:0;height:0;" +
      "z-index:2147483647";

    var root = host.attachShadow({ mode: "open" });

    root.innerHTML =
      "<style>" + PANEL_CSS + "</style>" +
      '<div class="ace-panel"></div>';

    // Listened for in here rather than on the document: an event that
    // crosses a shadow boundary is retargeted to the host, so a
    // document-level closest("[data-ace]") would find nothing.
    root.addEventListener("click", onAceClick, true);

    document.body.appendChild(host);

    return root.querySelector(".ace-panel");
  }

  function close() {
    dismissed = true;
    var existing = document.querySelector(".ace-root");
    if (existing) existing.remove();
  }

  /* Which build is on the page, said out loud.

     A content script only injects while a page loads, so reloading the
     extension leaves every already-open tab running the previous one.
     Twice now a bug has been reported from a screenshot of a build
     that had already been fixed, and nothing on screen could tell the
     two apart. */
  function version() {
    try {
      return chrome.runtime.getManifest().version;
    } catch (error) {
      return "";
    }
  }

  function shell(title, subtitle, body, footer) {
    var tag = version();

    return '<div class="ace-head">' +
        '<div class="ace-mark">A</div>' +
        '<div><div class="ace-title">' + esc(title) + '</div>' +
        (subtitle ? '<div class="ace-sub">' + esc(subtitle) + '</div>' : "") +
        '</div>' +
        (tag ? '<span class="ace-ver">' + esc(tag) + '</span>' : "") +
        '<button class="ace-x" data-ace="close" title="Close">&times;</button>' +
      '</div>' +
      (body ? '<div class="ace-body">' + body + '</div>' : "") +
      (footer ? '<div class="ace-foot">' + footer + '</div>' : "");
  }

  function rows(items, kind) {
    return items.map(function (item) {
      return '<div class="ace-item ' + kind + '">' +
        '<span class="k">' + esc(item[0]) + '</span>' +
        '<span class="v">' + esc(item[1]) + '</span>' +
      '</div>';
    }).join("");
  }

  /* What ACE would do, without doing it.

     A preview rather than a bare count, because the count was the only
     thing on offer and it said nothing about whether the answers were
     the right ones. Seeing "Work authorisation -> Yes" before the
     click is the difference between trusting it and checking every
     field afterwards. */
  function preview() {
    var willFill = [];
    var noOption = [];
    var noAnswer = [];
    var seen = {};

    historyOwned = null;

    fillable().forEach(function (field) {
      if (ownedByHistory(field)) return;

      var question = aceQuestionFor(field);
      if (!question) return;

      var name = aceAnswerNameFor(question, kindOf(field));
      var label = question.split(" | ")[0].slice(0, 44);

      if (!name) {
        if (!seen["q:" + label]) {
          seen["q:" + label] = 1;
          noAnswer.push([label, "no answer saved"]);
        }
        return;
      }

      if (seen["a:" + name]) return;

      var value = answers[name];
      if (!value) {
        seen["a:" + name] = 1;
        noAnswer.push([name, "blank in ACE"]);
        return;
      }

      var group = aceIsChoiceControl(field)
        ? groupMembers(field)
        : [field];

      if (!group.every(aceIsEmpty)) return;

      var shown = value;

      if (field.tagName === "SELECT") {
        // Judged with the same aliases the fill will use. Without them
        // the preview reported a stored "Male" as matching no option on
        // a form offering "Man", and then the fill picked it anyway --
        // the two disagreeing about the same field is worse than either
        // being wrong alone.
        var option = chooseOption(
          field,
          value,
          aliases[name]
        );
        if (!option) {
          seen["a:" + name] = 1;
          noOption.push([name, tidy(value)]);
          return;
        }
        shown = tidy(option.textContent);
      } else if (aceIsChoiceControl(field)) {
        var index = aceChooseOption(
          group.map(aceOptionText),
          value,
          aliases[name]
        );
        if (index < 0) {
          seen["a:" + name] = 1;
          noOption.push([name, tidy(value)]);
          return;
        }
        shown = aceOptionLabel(group[index]);
      } else if (aceIsAutocomplete(field)) {
        // Its real options exist only once opened, which preview must
        // not do -- nothing changes on the page until Fill is
        // clicked. Shown honestly as a guess rather than a promise: a
        // raw value with no matching option here is exactly how "Job
        // Portal" silently became "Search Engine" on a real form.
        shown = tidy(value) + " (if listed)";
      }

      seen["a:" + name] = 1;
      willFill.push([name, tidy(shown)]);
    });

    // Reported per block and per field, because "Job 2 start month" is
    // the only version of this the user can check at a glance. A count
    // of eighteen filled fields tells them nothing about whether the
    // second job went into the second block.
    ["work", "education"].forEach(function (kind) {
      runHistory(kind, false).forEach(function (pair) {
        willFill.push([pair[0], tidy(pair[1])]);
      });
    });

    return {
      willFill: willFill,
      noOption: noOption,
      noAnswer: noAnswer
    };
  }

  function showPreview(host) {
    var plan = preview();
    pending = plan;

    if (!plan.willFill.length && !plan.noOption.length) {
      if (!looksLikeForm()) {
        close();
        return;
      }

      render(host, shell(
        "Nothing to fill",
        "Every field ACE knows already has a value.",
        "",
        '<span class="ace-note">' +
          plan.noAnswer.length + ' question' +
          (plan.noAnswer.length === 1 ? "" : "s") +
          ' ACE has no answer for</span>'
      ));
      return;
    }

    var body =
      (plan.willFill.length
        ? '<div class="ace-group">Will fill</div>' + rows(plan.willFill, "")
        : "") +
      (plan.noOption.length
        ? '<div class="ace-group">Your answer matches no option</div>' +
          rows(plan.noOption, "miss")
        : "") +
      (plan.noAnswer.length
        ? '<div class="ace-group">Left for you</div>' +
          rows(plan.noAnswer.slice(0, 12), "skip")
        : "");

    render(host, shell(
      "Fill " + plan.willFill.length + " field" +
        (plan.willFill.length === 1 ? "" : "s"),
      "Review before filling. ACE never submits.",
      body,
      '<button class="ace-btn" data-ace="fill">Fill</button>' +
      '<span class="ace-note">or press Alt+A</span>' +
      '<button class="ace-link" data-ace="copy">Copy what ACE sees</button>' +
      '<span class="ace-note ace-copied"></span>'
    ));
  }

  /* What ACE sees on this page, as text the user can paste.

     Workday, Oracle and the rest put their application forms behind an
     account, so a form that misbehaves cannot be opened and read from
     outside the user's own session. Every rule in fields.js written
     from a guess about markup turned out wrong, so the way to fix one
     of those forms is to see it, and this is how it gets seen without
     asking anyone to open developer tools.

     Deliberately carries no answer values. It reports which question
     ACE matched and what the page offered, never what the user would
     have answered: this text is going to be pasted somewhere, and the
     bank holds a home address and demographic answers. */
  function diagnostics() {
    var lines = [
      "ACE " + version() + " on " + location.host,
      ""
    ];

    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;

      var name = aceAnswerNameFor(question, kindOf(field));

      var shape = aceIsAutocomplete(field)
        ? "combobox"
        : field.tagName === "SELECT"
          ? "select"
          : aceIsChoiceControl(field)
            ? "choice"
            : field.tagName.toLowerCase();

      var line =
        "- " + question.slice(0, 90) +
        "\n    " + shape +
        ", " + (aceIsEmpty(field) ? "empty" : "has a value") +
        ", matched: " + (name || "nothing");

      if (aceIsAutocomplete(field)) {
        var options = comboboxOptions(field);

        line += "\n    options: " + (options.length
          ? options.slice(0, 8).map(function (option) {
              return tidy(option.textContent);
            }).join(" / ")
          : "none visible until opened");
      }

      lines.push(line);
    });

    return lines.join("\n");
  }

  function copyDiagnostics(host) {
    var text = diagnostics();

    function done(ok) {
      var note = host.querySelector(".ace-copied");
      if (note) note.textContent = ok ? "Copied" : "Copy failed";
    }

    try {
      navigator.clipboard.writeText(text).then(
        function () { done(true); },
        function () { done(false); }
      );
    } catch (error) {
      done(false);
    }
  }

  function showResult(host, result) {
    var body =
      (result.filled.length
        ? '<div class="ace-group">Filled</div>' +
          rows(result.filled.map(function (name) {
            return [name, tidy(answers[name])];
          }), "")
        : "") +
      (result.unmatched.length
        ? '<div class="ace-group">Reword these in ACE</div>' +
          rows(result.unmatched.map(function (name) {
            return [name, tidy(answers[name])];
          }), "miss")
        : "");

    render(host, shell(
      "Filled " + result.filled.length + " field" +
        (result.filled.length === 1 ? "" : "s"),
      "Check it before you submit.",
      body,
      '<button class="ace-btn ghost" data-ace="undo">Undo</button>' +
      (result.already
        ? '<span class="ace-note">' + result.already +
          ' already had a value</span>'
        : "") +
      '<button class="ace-link" data-ace="copy">Copy what ACE sees</button>' +
      '<span class="ace-note ace-copied"></span>'
    ));
  }

  /* The questions on screen, as one string.

     Used only to notice a page that replaced its questions without
     replacing its URL. Truncated per question because a label that
     re-renders with a changed count would otherwise read as a whole
     new page. */
  function formSignature() {
    return fillable()
      .map(function (field) {
        var question = aceQuestionFor(field);
        return question ? question.slice(0, 40) : "";
      })
      .join("|");
  }

  /* Whether this is a new page of the form.

     An application is often several pages, and Workday's is a wizard
     that swaps the whole step without touching location.href. ACE
     filled the first page, set lastResult, and then refresh() returned
     early on every step after it: the panel never came back and
     nothing was filled again, which is exactly what the user hit.

     The reliable evidence is the fields themselves. ACE holds the
     nodes it filled, and a step that has been replaced has taken all
     of them out of the document. That is narrow on purpose: a
     conditional question appearing in answer to something ACE just
     filled leaves those fields connected, so the result panel stays up
     rather than being replaced by a fresh preview the moment it
     reports.

     With nothing filled there are no nodes to ask, so the questions
     themselves are compared instead. */
  function movedOn() {
    if (lastFill.length) {
      return lastFill.every(function (record) {
        return !record.field.isConnected;
      });
    }

    return formSignature() !== lastSignature;
  }

  function refresh() {
    if (!loaded) return;

    // Many boards route client-side between postings without a full
    // reload -- the same DOM-mutation signal that re-triggers refresh()
    // also fires on that navigation. Treat a URL change as a genuinely
    // new page: an earlier dismissal was about the posting the user
    // was just looking at, not this one.
    if (location.href !== lastHref || movedOn()) {
      lastHref = location.href;
      dismissed = false;
      lastResult = null;

      // The previous page's undo cannot apply to fields that are no
      // longer in the document, and keeping them would make movedOn()
      // answer about a page that is gone.
      lastFill = [];
    }

    lastSignature = formSignature();

    if (filling) return;
    if (lastResult) return;
    if (dismissed) return;

    showPreview(panel());
  }

  function start() {
    chrome.runtime.sendMessage({ type: "answers" }, function (reply) {
      if (chrome.runtime.lastError) return;

      if (!reply || !reply.ok) {
        render(panel(), shell(
          "ACE is not reachable",
          "Start it, or set the address from the toolbar icon.",
          "",
          ""
        ));
        return;
      }

      var known = 0;

      reply.items.forEach(function (item) {
        if (item.value) {
          answers[item.label] = item.value;
          // The other wordings a form might print for this same
          // answer, shipped by ACE rather than typed by the user. A
          // stored "Job board" has to reach an option reading "Job
          // Board (e.g., LinkedIn, Indeed, Glassdoor)", and knowing
          // those are the same thing is not the user's job.
          aliases[item.label] = item.aliases || [];
          known += 1;
        }
      });

      if (!known) {
        render(panel(), shell(
          "No answers saved yet",
          "Fill them in once in ACE and they land here.",
          "",
          ""
        ));
        return;
      }

      loaded = true;
      lastHref = location.href;

      // Fetched after the answers rather than in parallel: a page with
      // no repeating section is the common case, and the panel should
      // not wait on a request it will not use. refresh() is called
      // again once they land.
      chrome.runtime.sendMessage(
        { type: "history" },
        function (reply) {
          if (chrome.runtime.lastError) return;
          if (!reply || !reply.ok) return;

          histories.work = reply.work || [];
          histories.education = reply.education || [];

          refresh();
        }
      );

      refresh();

      var queued = null;

      new MutationObserver(function () {
        clearTimeout(queued);
        queued = setTimeout(refresh, 400);
      }).observe(document.body, { childList: true, subtree: true });
    });
  }

  function runFill() {
    // A combobox pass takes seconds, and filling the plain fields
    // mutates the page, which wakes the observer, which called
    // refresh() and drew the preview back over the "Filling..." panel
    // -- Fill button and all. Clicking it again ran a second pass that
    // found its own work already done and reported "Filled 0 fields, 7
    // already had a value" over a form ACE had in fact just filled
    // correctly. lastResult was not set until the combobox pass
    // finished, so nothing held the panel still in between.
    if (filling) return;

    filling = true;

    var host = panel();
    var result = plan();

    var comboFields = fillable().filter(aceIsAutocomplete);

    if (!comboFields.length) {
      filling = false;
      lastResult = result;
      showResult(host, result);
      return;
    }

    // Filling comboboxes takes real time -- opening each one and
    // waiting for its options is not instant -- so the badge says so
    // rather than sitting on the last preview while it works.
    render(host, shell(
      "Filling…",
      "Checking " + comboFields.length +
        " field" + (comboFields.length === 1 ? "" : "s") +
        " with its own options.",
      "",
      ""
    ));

    fillComboboxes().then(function (comboResult) {
      result.filled = result.filled.concat(comboResult.filled);
      result.unmatched = result.unmatched.concat(comboResult.unmatched);
      restoreClobbered();
      filling = false;
      lastResult = result;
      showResult(host, result);
    }, function () {
      // A combobox that never offered options should not strand the
      // panel on "Filling..." forever.
      filling = false;
      lastResult = result;
      showResult(host, result);
    });
  }

  function onAceClick(event) {
    var button = event.target.closest("[data-ace]");
    if (!button) return;

    event.preventDefault();
    event.stopPropagation();

    var action = button.getAttribute("data-ace");

    if (action === "close") {
      close();
      return;
    }

    if (action === "fill") {
      runFill();
      return;
    }

    if (action === "copy") {
      copyDiagnostics(panel());
      return;
    }

    if (action === "undo") {
      undo();
      lastResult = null;
      close();
    }
  }

  // Alt+A rather than a bare letter: a form is full of text boxes and
  // a plain shortcut would type into them.
  document.addEventListener("keydown", function (event) {
    if (event.altKey && (event.key === "a" || event.key === "A")) {
      if (loaded && !lastResult) {
        event.preventDefault();
        runFill();
      }
    }
  });

  /* document_idle should guarantee a body, but the script also runs in
     every frame, and a frame can be that early. Without this the first
     appendChild throws and the extension dies silently. */
  /* What the popup asks, so it can say why nothing happened.

     Answered from the page rather than from its host, because the host
     stopped meaning anything once ACE started running everywhere. A
     page where the content script never loaded does not reply at all,
     and the popup reports that separately -- which is the one case a
     host list used to be able to describe. */
  chrome.runtime.onMessage.addListener(
    function (message, sender, respond) {
      if (message && message.type === "wake") {
        // The user clicked Fill in the popup, which is a better signal
        // than any heuristic: run whether or not the page looked like
        // an application, and undo an earlier dismissal.
        dismissed = false;

        if (loaded) {
          lastResult = null;
          refresh();
        } else {
          start();
        }

        respond({ ok: true });
        return;
      }

      if (!message || message.type !== "status") return;

      var recognised = 0;

      fillable().forEach(function (field) {
        var question = aceQuestionFor(field);
        if (!question) return;

        if (aceAnswerNameFor(question, kindOf(field))) {
          recognised += 1;
        }
      });

      respond({
        ok: true,
        fields: recognised
      });
    }
  );

  (function boot() {
    if (!document.body) {
      setTimeout(boot, 50);
      return;
    }

    waitForApplication();
  })();

  /* Start only once the page looks like an application.

     Nothing is fetched before that. Running on every site means this
     script loads on pages ACE has no business on, and reaching for
     localhost on each of them would be both wasteful and a small
     surprise. A form built after load still counts, so a page that is
     not one yet is watched rather than given up on.

     The watcher disconnects on the first start, and start() installs
     its own. */
  function waitForApplication() {
    if (looksLikeApplication()) {
      start();
      return;
    }

    var queued = null;

    var watcher = new MutationObserver(function () {
      clearTimeout(queued);

      queued = setTimeout(function () {
        if (!looksLikeApplication()) return;

        watcher.disconnect();
        start();
      }, 500);
    });

    watcher.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  /* A seam for the DOM-level tests. content.js is one IIFE, so without
     it the only testable surface is fields.js, and every value-commit
     bug lives on this side of that line. A content script has its own
     isolated world, so this is invisible to the page itself. */
  window.__aceInternals = {
    setNatively: setNatively,
    comboboxOptions: comboboxOptions,
    diagnostics: diagnostics,
    formSignature: formSignature,
    openCombobox: openCombobox,
    searchTerms: searchTerms,
    fillOneCombobox: fillOneCombobox,
    restoreClobbered: restoreClobbered,
    recordFill: function (record) { lastFill.push(record); },
    panel: panel,
    shell: shell,
    onAceClick: onAceClick
  };
})();
