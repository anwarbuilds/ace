/* Fills the form, and stops there.

   Nothing here submits, and nothing overwrites a box that already has
   something in it. The user is about to send this to an employer, so
   every uncertain case is left for them and reported rather than
   guessed at. */

(function () {
  var answers = {};
  var lastFill = [];
  var loaded = false;
  // The element fillOne actually ticked, which for a group is not
  // the one it was handed.
  var lastPicked = null;
  var filledOnce = false;
  var lastResult = null;
  var pending = null;

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

    // Ashby's Yes/No widget is two real <button> elements, excluded by
    // the plain input/select/textarea query above and by every other
    // provider's own submit buttons, which is why data-option is
    // required rather than matching every button on the page.
    var choiceButtons = Array.prototype.filter.call(
      document.querySelectorAll("button[data-option]"),
      function (field) {
        return !field.disabled && field.offsetParent;
      }
    );

    return normal.concat(choiceButtons);
  }

  function chooseOption(select, wanted) {
    var options = Array.prototype.slice.call(select.options);

    // A placeholder is not an answer, and leaving it in the running
    // lets "Select ..." win a containment match against anything.
    var offered = options.filter(function (option, index) {
      return !(index === 0 && !option.value);
    });

    var index = aceChooseOption(
      offered.map(function (option) { return option.textContent; }),
      wanted
    );

    return index >= 0 ? offered[index] : null;
  }

  /* Every input in this control's group, in the order a person reads
     them. Radios and checkboxes are one question spread over several
     elements, so the choice is made across the whole group at once
     rather than by testing each box against the answer alone. */
  function groupMembers(field) {
    if (field.tagName === "BUTTON") {
      // No shared name attribute links Ashby's Yes/No buttons to each
      // other; the pair only shares an immediate parent.
      var siblings = field.parentElement
        ? Array.prototype.slice.call(
            field.parentElement.querySelectorAll("button[data-option]")
          )
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

  function fillOne(field, value) {
    if (field.tagName === "SELECT") {
      var option = chooseOption(field, value);
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

      var chosen = aceChooseOption(members.map(aceOptionText), value);

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

  function plan() {
    var filled = [];
    var unknown = [];
    // A question ACE knows, holding an answer that matches none of the
    // offered options. Silence here is the worst kind: the user thinks
    // it was handled. Naming it tells them exactly what to reword.
    var unmatched = [];
    var already = 0;

    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;

      var name = aceAnswerNameFor(question);

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

      if (!fillOne(field, value)) {
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

  function fillOneCombobox(field, value) {
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

      var index = aceChooseOption(texts, value);

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

          var name = aceAnswerNameFor(question);
          if (!name) return;

          var value = answers[name];
          if (!value) return;

          if (!aceIsEmpty(field)) return;

          var previous = field.value;

          return fillOneCombobox(field, value).then(function (outcome) {
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

    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;

      var name = aceAnswerNameFor(question);
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
        var option = chooseOption(field, value);
        if (!option) {
          seen["a:" + name] = 1;
          noOption.push([name, tidy(value)]);
          return;
        }
        shown = tidy(option.textContent);
      } else if (aceIsChoiceControl(field)) {
        var index = aceChooseOption(group.map(aceOptionText), value);
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

    paint();

    if (lastResult) return;

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
  (function boot() {
    if (!document.body) {
      setTimeout(boot, 50);
      return;
    }

    start();
  })();
})();
