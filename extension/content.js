/* Fills the form, and stops there.

   Nothing here submits, and nothing overwrites a box that already has
   something in it. The user is about to send this to an employer, so
   every uncertain case is left for them and reported rather than
   guessed at. */

(function () {
  var answers = {};
  var lastFill = [];
  var loaded = false;
  var filledOnce = false;
  var lastResult = null;

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
  function aceIsEmpty(field) {
    // A checkbox reports value "on" whether or not it is ticked, so
    // testing value counted every unticked box as already answered and
    // ACE skipped whole groups it could have filled.
    if (field.type === "checkbox" || field.type === "radio") {
      return !field.checked;
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
    return Array.prototype.filter.call(
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
  }

  function chooseOption(select, wanted) {
    var target = aceNormalise(wanted);
    var options = Array.prototype.slice.call(select.options);

    var exact = options.filter(function (option) {
      return aceNormalise(option.textContent) === target;
    })[0];

    if (exact) return exact;

    // A form's wording rarely matches the user's wording, so a
    // containment match is the realistic case: "Yes" against
    // "Yes, I am authorized to work".
    return options.filter(function (option) {
      var text = aceNormalise(option.textContent);
      return text && (text.indexOf(target) >= 0 || target.indexOf(text) >= 0);
    })[0] || null;
  }

  function fillOne(field, value) {
    if (field.tagName === "SELECT") {
      var option = chooseOption(field, value);
      if (!option) return false;
      setNatively(field, option.value);
      return true;
    }

    if (field.type === "radio" || field.type === "checkbox") {
      // The rule already established that this group is the right
      // question. This only decides which option in it to tick, and
      // ticks nothing unless the option and the answer agree.
      var option = aceOptionText(field);
      var wanted = aceNormalise(value);

      if (!option || !wanted) return false;

      // Whole words. "female" contains "male", so a substring test
      // ticked both boxes in a gender group on a real Lever form.
      var same =
        option === wanted ||
        acePhraseIn(option, wanted) ||
        acePhraseIn(wanted, option);

      if (!same) return false;
      if (field.checked) return false;

      field.click();
      return true;
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

      if (!aceIsEmpty(field)) {
        already += 1;
        return;
      }

      var previous = field.value;

      var isChoice =
        field.tagName === "SELECT" ||
        field.type === "radio" ||
        field.type === "checkbox";

      if (!fillOne(field, value)) {
        if (isChoice && unmatched.indexOf(name) < 0) unmatched.push(name);
        return;
      }

      field.classList.add("ace-filled");

      lastFill.push({
        field: field,
        previous: previous,
        ticked: field.type === "radio" || field.type === "checkbox"
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

  function undo() {
    lastFill.forEach(function (record) {
      if (record.ticked) {
        record.field.checked = false;
        record.field.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        setNatively(record.field, record.previous);
      }
      record.field.classList.remove("ace-filled");
    });
    lastFill = [];
  }

  function badge() {
    var existing = document.querySelector(".ace-badge");
    if (existing) existing.remove();

    var host = document.createElement("div");
    host.className = "ace-badge";
    document.body.appendChild(host);
    return host;
  }

  function render(host, body) {
    host.innerHTML = body;
  }

  function countReady() {
    var ready = 0;

    fillable().forEach(function (field) {
      var name = aceAnswerNameFor(aceQuestionFor(field));
      if (name && answers[name] && aceIsEmpty(field)) ready += 1;
    });

    return ready;
  }

  function looksLikeForm() {
    return fillable().filter(function (field) {
      return field.type !== "radio" && field.type !== "checkbox";
    }).length >= 4;
  }

  function describe(result) {
    return '<div class="ace-t">Filled ' + result.filled.length + ' field' +
      (result.filled.length === 1 ? "" : "s") + '</div>' +
      (result.already
        ? '<div class="ace-s">' + result.already +
          ' already had a value and were left alone.</div>'
        : "") +
      (result.unmatched.length
        ? '<div class="ace-s ace-warn">Your answer matched none of the options for: ' +
          result.unmatched.join("; ") + '. Reword it in ACE to match.</div>'
        : "") +
      (result.unknown.length
        ? '<div class="ace-s">Not answered: ' +
          result.unknown.slice(0, 4).map(function (question) {
            return question.replace(/[<>&]/g, "");
          }).join("; ") + '</div>'
        : "") +
      '<div class="ace-s ace-warn">Check it before you submit.</div>';
  }

  function offer(host, ready) {
    render(host,
      '<div class="ace-t">ACE can fill ' + ready + ' field' +
        (ready === 1 ? "" : "s") + '</div>' +
      (filledOnce ? '<div class="ace-s">New questions appeared on this step.</div>' : "") +
      '<button class="ace-go">Fill</button>');

    host.querySelector(".ace-go").addEventListener("click", function () {
      var result = plan();
      filledOnce = true;
      lastResult = result;

      render(host, describe(result) + '<button class="ace-go ace-undo">Undo</button>');

      host.querySelector(".ace-undo").addEventListener("click", function () {
        undo();
        filledOnce = false;
        lastResult = null;
        host.remove();
      });
    });
  }

  /* Recomputed whenever the page changes, because these forms are not
     there when the script is.

     Waiting for the first input to exist was not enough: a Netflix
     application page has cookie-consent checkboxes in the markup from
     the start, so the check passed instantly and the real form mounted
     seconds later against a badge that had already given up. The same
     applies as the user moves between steps of a multi-step form. */
  /* React reconciles the nodes it owns and drops the class ACE put on
     them, so on a React form the outline vanishes a moment after the
     fill and the user cannot see what was touched. Re-applied whenever
     the page settles. */
  function paint() {
    lastFill.forEach(function (record) {
      if (record.field.isConnected) {
        record.field.classList.add("ace-filled");
      }
    });
  }

  function refresh() {
    if (!ready()) return;

    paint();

    var host = document.querySelector(".ace-badge") || badge();
    var count = countReady();

    if (count) {
      offer(host, count);
      return;
    }

    if (lastResult) {
      render(host, describe(lastResult) +
        '<button class="ace-go ace-undo">Undo</button>');
      host.querySelector(".ace-undo").addEventListener("click", function () {
        undo();
        filledOnce = false;
        lastResult = null;
        host.remove();
      });
      return;
    }

    if (looksLikeForm()) {
      render(host,
        '<div class="ace-t">Nothing left to fill</div>' +
        '<div class="ace-s">Every field ACE knows already has a value, ' +
        'or this form asks questions your bank has no answer for.</div>');
    } else {
      host.remove();
    }
  }

  function ready() {
    return loaded;
  }

  function start() {
    chrome.runtime.sendMessage({ type: "answers" }, function (reply) {
      if (chrome.runtime.lastError) return;

      if (!reply || !reply.ok) {
        render(badge(),
          '<div class="ace-t">ACE is not reachable</div>' +
          '<div class="ace-s">Start it, or set the address from the toolbar icon.</div>');
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
        render(badge(),
          '<div class="ace-t">No answers saved yet</div>' +
          '<div class="ace-s">Fill them in once in ACE and they land here.</div>');
        return;
      }

      loaded = true;
      refresh();

      // Debounced, because a React form mounting fires a great many
      // mutations and each one would otherwise rebuild the badge.
      var pending = null;

      new MutationObserver(function () {
        clearTimeout(pending);
        pending = setTimeout(refresh, 400);
      }).observe(document.body, { childList: true, subtree: true });
    });
  }

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
