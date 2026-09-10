/* Fills the form, and stops there.

   Nothing here submits, and nothing overwrites a box that already has
   something in it. The user is about to send this to an employer, so
   every uncertain case is left for them and reported rather than
   guessed at. */

(function () {
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

    setter.call(field, value);

    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
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

    return /^(select|choose|please select|-+|)\s*\.*$/.test(
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

        touched.classList.add("ace-filled");

        lastFill.push({
          field: touched,
          previous: previous,
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

      touched.classList.add("ace-filled");

      lastFill.push({
        field: touched,
        previous: previous,
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
  function comboboxOptions() {
    var box = document.querySelector("[role=listbox]");

    return box
      ? Array.prototype.slice.call(box.querySelectorAll("[role=option]"))
      : [];
  }

  function waitForComboboxOptions(timeoutMs) {
    return new Promise(function (resolve) {
      var start = Date.now();

      (function poll() {
        var options = comboboxOptions();

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

  function fillOneCombobox(field, value, alts) {
    var toggle =
      field.parentElement &&
      field.parentElement.querySelector("button");

    if (toggle) toggle.click();
    else field.click();

    return waitForComboboxOptions(1500).then(function (options) {
      if (!options.length) {
        closeCombobox(field);
        return { matched: false };
      }

      var texts = options.map(function (option) {
        return option.textContent;
      });

      var index = aceChooseOption(texts, value, alts);

      if (index < 0) {
        // No option fits. Closed rather than left open with nothing
        // chosen, and nothing is typed into the input either -- a
        // wrong option is worse than this question staying blank for
        // the user to answer themselves.
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

            field.classList.add("ace-filled");

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
      record.field.classList.remove("ace-filled");
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

  /* React reconciles the nodes it owns and drops the class ACE put on
     them, so on a React form the outline vanishes a moment after the
     fill and the user cannot see what was touched. */
  function paint() {
    lastFill.forEach(function (record) {
      if (record.field.isConnected) {
        record.field.classList.add("ace-filled");
      }
    });
  }

  function panel() {
    var existing = document.querySelector(".ace-panel");
    if (existing) return existing;

    var host = document.createElement("div");
    host.className = "ace-panel";
    document.body.appendChild(host);
    return host;
  }

  function close() {
    dismissed = true;
    var existing = document.querySelector(".ace-panel");
    if (existing) existing.remove();
  }

  function shell(title, subtitle, body, footer) {
    return '<div class="ace-head">' +
        '<div class="ace-mark">A</div>' +
        '<div><div class="ace-title">' + esc(title) + '</div>' +
        (subtitle ? '<div class="ace-sub">' + esc(subtitle) + '</div>' : "") +
        '</div>' +
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
      '<span class="ace-note">or press Alt+A</span>'
    ));
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
        : "")
    ));
  }

  function refresh() {
    if (!loaded) return;

    // Many boards route client-side between postings without a full
    // reload -- the same DOM-mutation signal that re-triggers refresh()
    // also fires on that navigation. Treat a URL change as a genuinely
    // new page: an earlier dismissal was about the posting the user
    // was just looking at, not this one.
    if (location.href !== lastHref) {
      lastHref = location.href;
      dismissed = false;
      lastResult = null;
    }

    paint();

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
    var host = panel();
    var result = plan();

    var comboFields = fillable().filter(aceIsAutocomplete);

    if (!comboFields.length) {
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
      lastResult = result;
      showResult(host, result);
    });
  }

  document.addEventListener("click", function (event) {
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

    if (action === "undo") {
      undo();
      lastResult = null;
      close();
    }
  }, true);

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
})();
