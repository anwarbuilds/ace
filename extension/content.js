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
  var memory = [];
  var memoryAvailable = false;
  var studioTab = "overview";
  var focusMode = "compact";
  var focusPosition = null;
  var reviewSeen = new Set();
  var approvedQuestions = new Set();
  var customOptions = new Map();
  var reviewDrafts = new Map();
  var studioTheme = "day";
  var autoKnown = true;
  var skippedQuestions = new Set();
  var activity = [];
  var studioError = "";
  var reviewQuestion = "";
  var editConcept = "";
  var studioFields = [];
  function activityNote(label, count) {
    activity.unshift({ label: label, count: count || 0, at: new Date().toLocaleTimeString() });
    activity = activity.slice(0, 35);
    if (chrome.storage && chrome.storage.local) chrome.storage.local.set({ aceStudioActivity: activity });
  }
  function memoryFailure(error) {
    var message = String(error || "");
    if (message.indexOf("404") >= 0) return "Answer Memory needs the ACE server V4 update. Existing answers are safe.";
    if (message.indexOf("unpaired") >= 0 || message.indexOf("401") >= 0) return "ACE is not paired. Check the ACE address and pair this browser again.";
    return "Answer Memory cannot reach ACE right now. Check the ACE address and try again.";
  }
  function loadMemory(done) {
    chrome.runtime.sendMessage({ type: "memory" }, function (reply) {
      if (chrome.runtime.lastError || !reply || !reply.ok) {
        memoryAvailable = false;
        studioError = memoryFailure(reply && reply.error || chrome.runtime.lastError && chrome.runtime.lastError.message);
      } else {
        memory.forEach(function (item) { delete answers["Memory:" + item.concept]; });
        // Keep historical records on the server, but never surface or reuse
        // an employer-motivation answer in this extension.
        memory = (Array.isArray(reply.items) ? reply.items : []).filter(function (item) {
          return !aceMemory.isEmployerMotivation(item.question);
        });
        memory.forEach(function (item) {
          answers["Memory:" + item.concept] = item.answer;
          aliases["Memory:" + item.concept] = [];
        });
        memoryAvailable = true;
        if (studioError.indexOf("Answer Memory") === 0) studioError = "";
      }
      var existing = document.querySelector(".ace-root");
      if (existing && !dismissed) renderStudio(existing.shadowRoot.querySelector(".ace-panel"));
      if (done) done();
    });
  }
  function answerNameFor(question, kind) {
    if (aceMemory.policy(question) !== "reusable") return null;
    var saved = aceMemory.resolve(question, kind === "yesno" ? "yesno" : kind === "choice" ? "choice" : "text", memory);
    if (saved) return "Memory:" + saved.concept;
    return aceAnswerNameFor(question, kind, Object.keys(answers));
  }
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
  var manualListingOpen = false;
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
  var lastFields = [];
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
      // Oracle's Yes/No pills are role="radio" and say so with
      // aria-checked; Ashby's pair uses aria-pressed.
      return (
        field.getAttribute("aria-pressed") === "true" ||
        field.getAttribute("aria-checked") === "true"
      );
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

    // Workday's dropdown says what it holds on its own face: "Select
    // One" until something is chosen, the choice after.
    if (aceIsListboxButton(field)) {
      return isPlaceholderText(field.textContent);
    }

    // Workday's search-and-pick box keeps its choice as a pill beside
    // an empty search input. The input being empty is not the question
    // being unanswered, and picking again could take the choice away.
    if (aceIsAutocomplete(field)) {
      var picker = field.closest('[data-automation-id="multiSelectContainer"]');

      if (picker && picker.querySelector('[data-automation-id="selectedItem"]')) {
        return false;
      }
    }

    if (field.tagName !== "SELECT") {
      // A phone widget writes its country's dial code into the number
      // box the moment a country is chosen. "+1" on its own is that
      // widget's placeholder, not a number anybody typed, and reading
      // it as an answer is what made ACE skip the phone field and
      // report it as already filled -- leaving the user looking at a
      // Phone containing "+1" and a panel claiming success.
      //
      // Bounded to a bare code and nothing else, so a real number that
      // happens to start "+1" is untouched.
      if (/^\+\s*\d{1,4}$/.test(String(field.value || "").trim())) {
        return true;
      }

      return !field.value;
    }

    var option = field.options[field.selectedIndex];
    if (!option) return true;
    if (!option.value) return true;

    return isPlaceholderText(option.textContent);
  }

  // "No answer" is JazzHR's default for every dropdown, and it is a
  // placeholder however it reads: treating it as an answer made ACE
  // skip the relocation and felony questions on a real form and report
  // them as already filled.
  //
  // Deliberately not including "none", which a person can mean. These
  // are all wordings a form ships selected, never ones a person
  // chooses.
  function isPlaceholderText(text) {
    return /^(select|choose|please select|please choose|select one|no answer|n\/a|-+|)\s*\.*$/.test(
      aceNormalise(text)
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
        if (aceShouldSkip(field) || aceMemory.isEmployerMotivation(aceQuestionFor(field))) return false;
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
        return aceIsChoiceControl(field) && !aceMemory.isEmployerMotivation(aceQuestionFor(field));
      }
    );

    // Workday's dropdowns, which are buttons too: see
    // aceIsListboxButton in fields.js.
    var listboxButtons = Array.prototype.filter.call(
      document.querySelectorAll('button[aria-haspopup="listbox"]'),
      function (field) {
        if (field.disabled || !field.offsetParent) return false;
        return !aceShouldSkip(field) && !aceMemory.isEmployerMotivation(aceQuestionFor(field));
      }
    );

    return normal.concat(choiceButtons, listboxButtons);
  }

  function chooseOption(select, wanted, alts) {
    var options = Array.prototype.slice.call(select.options);

    // A placeholder is not an answer, and leaving it in the running
    // lets "Select ..." win a containment match against anything.
    var offered = options.filter(function (option, index) {
      return !(index === 0 && !option.value);
    });

    var index = chooseMatchedOption(
      select,
      offered.map(function (option) { return option.textContent; }),
      wanted,
      alts
    );

    return index >= 0 ? offered[index] : null;
  }

  function chooseMatchedOption(field, options, wanted, alts) {
    var name = answerNameFor(aceQuestionFor(field), kindOf(field));
    if (name === "Field of study" || name === "Age range from adult status") {
      // A saved major must beat a nearby but different major. An adult
      // answer may only select an exact 18+ option, never an age band.
      var candidates = [wanted].concat(alts || []);
      for (var i = 0; i < candidates.length; i++) {
        var exact = options.map(aceNormalise).reduce(function (found, text, at) {
          if (text === aceNormalise(candidates[i])) found.push(at);
          return found;
        }, []);
        if (exact.length === 1) return exact[0];
        if (exact.length > 1) return -1;
      }
      if (name === "Age range from adult status") return -1;
    }
    return aceChooseOption(options, wanted, alts);
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
      //
      // Oracle puts each pill in its own list item inside one
      // role="radiogroup", so the shared parent is the group, not the
      // immediate one. Read pill by pill, an answered "No" did not
      // count as answered when ACE's answer was "Yes".
      var scope =
        field.closest("[role=radiogroup]") || field.parentElement;

      var siblings = scope
        ? Array.prototype.slice.call(
            scope.querySelectorAll("button")
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

      // A lone checkbox is a yes/no, not a list to choose between. Its
      // label is the statement it asserts -- "I currently work here" --
      // and no affirmative answer will ever match that as option text,
      // so it was reported as "your answer matched no option" and left
      // unticked on every work-history block.
      if (
        members.length === 1 &&
        members[0].type === "checkbox"
      ) {
        if (aceIntent(value) !== "yes") return false;
        if (aceIsChosen(members[0])) return false;

        members[0].click();
        lastPicked = members[0];

        return true;
      }

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

    if (field.tagName === "INPUT" &&
        (field.type === "date" || field.type === "month")) {
      var date = String(value || "").trim();
      var us = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(date);
      var usMonth = /^(\d{1,2})\/(\d{4})$/.exec(date);
      if (field.type === "date" && us) {
        date = us[3] + "-" + us[1].padStart(2, "0") + "-" +
          us[2].padStart(2, "0");
      } else if (field.type === "month" && usMonth) {
        date = usMonth[2] + "-" + usMonth[1].padStart(2, "0");
      }
      if (field.type === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
      if (field.type === "month" && !/^\d{4}-\d{2}$/.test(date)) return false;
      setNatively(field, date);
      return field.value === date;
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
    var kinds = [];

    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;

      if (aceHistoryRole(field, question) === "employer") {
        anchors.push(field);
        kinds.push(aceHistoryKind(question));
      }
    });

    if (anchors.length < 1) return [];

    // Every anchor bounds every block, whatever its kind, so a lone job
    // block cannot grow to swallow the education section below it. The
    // kind is kept per block and filtered on at the end: work and
    // education used to come back as one list, matched to entries by
    // position across both, and a school block was always claimed --
    // by the work pass, which had two entries.
    var blocks = anchors.map(function (field, index) {
      return {
        node: blockAround(field, anchors),
        kind: kinds[index],
        fields: []
      };
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

    return blocks.filter(function (block) {
      return block.kind === kind;
    });
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
      // With nothing stored for this kind, the first block is answered
      // from the bank -- its University, Degree, Field of study and GPA
      // are exactly that one entry. Claimed by a history pass with
      // nothing to write, Workday's Education block sat empty beside a
      // bank that held every answer. Later blocks stay claimed: the
      // bank's one school must not be typed into a second.
      var stored = (histories[kind] || []).length > 0;

      historyBlocks(kind).forEach(function (block, index) {
        if (!stored && index === 0) return;

        block.fields.forEach(function (entry) {
          owned.push(entry.field);
        });
      });
    });

    return owned;
  }

  function historyEntryForBlock(kind, block, index) {
    var entries = histories[kind] || [];
    if (kind !== "work") return entries[index] || null;

    // A resume import can list jobs in a different order from ACE's
    // saved history. When Workday already names the employer, use that
    // identity before putting dates into its otherwise blank fields.
    var employer = block.fields.find(function (slot) {
      return slot.role === "employer";
    });
    var shown = employer && String(employer.field.value || "").trim();
    if (!shown) return entries[index] || null;

    function key(value) {
      return String(value || "").toLowerCase()
        .replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
    }

    var matches = entries.filter(function (entry) {
      return key(entry.employer) === key(shown);
    });
    if (matches.length === 1) return matches[0];
    if (!matches.length) return null;

    // Two roles at one employer need their titles to distinguish them.
    // If the title is absent or still ambiguous, leave the dates blank.
    var title = block.fields.find(function (slot) {
      return slot.role === "jobTitle";
    });
    var shownTitle = title && String(title.field.value || "").trim();
    if (!shownTitle) return null;

    matches = matches.filter(function (entry) {
      return key(entry.job_title) === key(shownTitle);
    });
    return matches.length === 1 ? matches[0] : null;
  }

  /* The stored history value for a field inside a history block, or
     null when its block has no entry behind it. Undefined when the
     field belongs to no block. */
  function historyValueFor(field) {
    var found;

    ["work", "education"].forEach(function (kind) {
      if (found !== undefined) return;

      historyBlocks(kind).forEach(function (block, index) {
        block.fields.forEach(function (slot) {
          if (found !== undefined || slot.field !== field) return;

          var entry = historyEntryForBlock(kind, block, index);

          found = entry
            ? aceHistoryValue(entry, slot.role, field)
            : null;
        });
      });
    });

    return found;
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
      var entry = historyEntryForBlock(kind, block, index);
      if (!entry) return;

      block.fields.forEach(function (slot) {
        var value = aceHistoryValue(entry, slot.role, slot.field);
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

        // Native date controls reject an invalid string without an
        // exception. Do not claim a history date was filled if the
        // browser left the control empty.
        if (!aceIsChoiceControl(slot.field) && !slot.field.value) return;

        var touched = lastPicked || slot.field;

          lastFill.push({
          field: touched,
          previous: previous,
          wrote: touched.value,
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
    startDate: "start date",
    endDate: "end date",
    description: "description"
  };

  function historyLabel(kind, index, role) {
    return (kind === "work" ? "Job " : "Study ") + (index + 1) +
      " " + (ACE_ROLE_LABELS[role] || role);
  }

  var NAME_ANSWERS = ["First name", "Last name", "Full name"];

  /* A name box holding the résumé's capitals rather than anything the
     user typed: see aceIsCopiedOwnName. */
  function copiedOwnName(field, name) {
    if (NAME_ANSWERS.indexOf(name) < 0) return false;
    if (field.tagName !== "INPUT") return false;

    var own = [];

    NAME_ANSWERS.forEach(function (label) {
      String(answers[label] || "")
        .toLowerCase()
        .split(/[^a-z]+/)
        .forEach(function (word) {
          if (word && own.indexOf(word) < 0) own.push(word);
        });
    });

    return aceIsCopiedOwnName(field.value, own);
  }

  /* A phone box holding the user's own number with its dial code, on a
     form that asks for the code in a box of its own.

     Workday fills Phone Number from the candidate's profile as "+1
     (425) ...", beside a Country Phone Code already holding +1, and then
     refuses it. ACE never overwrites a box that holds something, so the
     refusal stayed. The same number, written without the code the form
     keeps elsewhere, is not an overwrite of anything the user typed. */
  function copiedOwnPhone(field, name) {
    if (name !== "Phone") return false;
    if (field.tagName !== "INPUT") return false;

    var current = String(field.value || "").trim();
    if (current.charAt(0) !== "+") return false;

    var stored = String(answers.Phone || "").replace(/\D/g, "");
    if (!stored) return false;

    if (current.replace(/\D/g, "") !== stored) return false;

    return hasPairedCountrySelector(field);
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

      var name = answerNameFor(question, kindOf(field));

      if (!name) {
        // Only worth reporting once per question, and only for things
        // that look like real questions rather than search boxes.
        var short = question.split(" | ")[0].slice(0, 60);
        if (short && unknown.indexOf(short) < 0) unknown.push(short);
        return;
      }

      var value = answers[name];
      if (!value) return;

      // The country selector beside a split phone widget already shows
      // the dial code, so the number box next to it takes the national
      // number alone. Writing the stored value whole put "+1" in both
      // halves, and the two are one bound value to the widget: editing
      // the duplicate out of the number reset the selector as well, so
      // there was no way to correct one side by hand.
      if (name === "Phone" && hasPairedCountrySelector(field)) {
        value = acePhoneLocalNumber(value);
      }

      // A group with any box ticked is answered, whichever box it is.
      // Testing only the element in hand treated every unticked option
      // of an answered question as still needing an answer.
      var group = aceIsChoiceControl(field)
        ? groupMembers(field)
        : [field];

      if (
        !group.every(aceIsEmpty) &&
        !copiedOwnName(field, name) &&
        !copiedOwnPhone(field, name)
      ) {
        if (group[0] === field) already += 1;
        return;
      }

      var previous = field.value;

      lastPicked = null;

      var isChoice =
        field.tagName === "SELECT" ||
        aceIsChoiceControl(field) ||
        field.type === "date" || field.type === "month";

      if (!fillOne(field, value, aliases[name])) {
        if (isChoice && unmatched.indexOf(name) < 0) unmatched.push(name);
        return;
      }

      var touched = lastPicked || field;

      lastFill.push({
        field: touched,
        previous: previous,
        wrote: touched.value,
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

    if (!box) return [];

    var options = box.querySelectorAll("[role=option]");

    // Oracle's Candidate Experience -- Staples, Dell -- lists its
    // choices as a grid: role="gridcell" in role="row", never
    // role="option". Read as options only, every one of its dropdowns
    // opened onto "nothing to choose", and ZIP code, city and state
    // were left empty on a required page.
    if (!options.length) options = box.querySelectorAll("[role=gridcell]");

    return Array.prototype.slice.call(options);
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
     says "Ashfield" or "Lakeview WA" and the list says "Ashfield,
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

        // A ZIP code is looked up on the employer's server, and the
        // suggestions take longer than a second to come back.
        return waitForComboboxOptions(field, 2500);
      });
    }, Promise.resolve([]));
  }

  /* A press the way a person makes one: the whole pointer sequence,
     not a bare click event. A widget that acts on mousedown never sees
     a .click(), and one that acts on click still gets it here. */
  function press(element) {
    [
      "pointerdown",
      "mousedown",
      "pointerup",
      "mouseup",
      "click"
    ].forEach(function (type) {
      var Kind =
        type.indexOf("pointer") === 0 && typeof PointerEvent === "function"
          ? PointerEvent
          : MouseEvent;

      element.dispatchEvent(
        new Kind(type, {
          bubbles: true,
          cancelable: true,
          view: window,
          button: 0,
          buttons: /down$/.test(type) ? 1 : 0,
          detail: 1
        })
      );
    });
  }

  function shownListboxes() {
    return Array.prototype.filter.call(
      document.querySelectorAll("[role=listbox]"),
      function (box) {
        return box.getClientRects().length > 0;
      }
    );
  }

  /* The menu a Workday dropdown button just opened.

     Workday mounts it elsewhere on the page, not beside the button, and
     often points to it from nothing, so the climb comboboxOptions()
     makes cannot reach it. What identifies it is time: it was not
     showing before the button was pressed, and now it is. A list that
     was already showing is never a candidate, which is what keeps a
     permanently mounted one -- DoorDash's 244 countries -- from being
     read as this button's options. Two new menus at once is ambiguous,
     and ambiguity leaves the question blank. */
  function listboxOpenedBy(field, before) {
    var id =
      field.getAttribute("aria-controls") ||
      field.getAttribute("aria-owns");

    var declared = id ? document.getElementById(id) : null;

    if (declared && declared.querySelector("[role=option]")) return declared;

    var fresh = shownListboxes().filter(function (box) {
      return before.indexOf(box) < 0 && !!box.querySelector("[role=option]");
    });

    // A menu inside another new one is the same menu found twice.
    fresh = fresh.filter(function (box) {
      return !fresh.some(function (other) {
        return other !== box && box.contains(other);
      });
    });

    return fresh.length === 1 ? fresh[0] : null;
  }

  function waitFor(test, timeoutMs) {
    return new Promise(function (resolve) {
      var start = Date.now();

      (function poll() {
        var found = test();

        if (found || Date.now() - start > timeoutMs) {
          resolve(found);
          return;
        }

        setTimeout(poll, 60);
      })();
    });
  }

  function closeListbox(field) {
    [document.activeElement, field].forEach(function (target) {
      if (!target) return;

      target.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          code: "Escape",
          keyCode: 27,
          bubbles: true
        })
      );
    });
  }

  /* Open the dropdown, pick the option, and confirm the button now
     shows it. A press that did not take leaves the question reported
     as unanswered rather than claimed. */
  function fillOneListbox(field, value, alts) {
    var before = shownListboxes();

    press(field);

    return waitFor(function () {
      return listboxOpenedBy(field, before);
    }, 1500).then(function (box) {
      if (!box) {
        closeListbox(field);
        return { matched: false };
      }

      var options = Array.prototype.slice.call(
        box.querySelectorAll("[role=option]")
      );

      var texts = options.map(function (option) {
        return option.textContent;
      });

      var index = chooseMatchedOption(field, texts, value, alts);

      if (index < 0) {
        closeListbox(field);
        return { matched: false };
      }

      press(options[index]);

      return waitFor(function () {
        return !aceIsEmpty(field);
      }, 1200).then(function (took) {
        if (!took) {
          closeListbox(field);
          return { matched: false };
        }

        return { matched: true, text: texts[index] };
      });
    });
  }

  /* Workday's search-and-pick: School, Field of Study, Country Phone
     Code. Read from Workday's own code: typing only edits the box, and
     the search runs on Enter; each result is a role="option" row whose
     click handler sits on an inner element, so a click on the row itself
     never reaches it -- the label inside it is pressed instead; and the
     choice lands as a pill beside the box, which is how it is confirmed. */
  function workdayResults() {
    return Array.prototype.filter.call(
      document.querySelectorAll('[data-automation-id="promptOption"]'),
      function (node) {
        return (
          node.getClientRects().length > 0 &&
          !node.closest('[data-automation-id="selectedItem"]')
        );
      }
    );
  }

  function workdayPicked(field) {
    var picker = field.closest('[data-automation-id="multiSelectContainer"]');

    return !!(
      picker &&
      picker.querySelector('[data-automation-id="selectedItem"]')
    );
  }

  function pressEnter(field) {
    ["keydown", "keypress", "keyup"].forEach(function (type) {
      field.dispatchEvent(
        new KeyboardEvent(type, {
          key: "Enter",
          code: "Enter",
          keyCode: 13,
          which: 13,
          bubbles: true,
          cancelable: true
        })
      );
    });
  }

  function fillOneWorkdayPrompt(field, value, alts) {
    var terms = searchTerms(value);

    return terms.reduce(function (chain, term) {
      return chain.then(function (done) {
        if (done && done.matched) return done;

        typeIntoCombobox(field, term);
        pressEnter(field);

        return waitFor(function () {
          var found = workdayResults();
          return found.length ? found : null;
        }, 3000).then(function (results) {
          if (!results) return { matched: false };

          var texts = results.map(function (node) {
            return node.getAttribute("data-automation-label") ||
              node.textContent;
          });

          var index = chooseMatchedOption(field, texts, value, alts);
          if (index < 0) return { matched: false };

          press(results[index]);

          return waitFor(function () {
            return workdayPicked(field);
          }, 2000).then(function (took) {
            return took
              ? { matched: true, text: texts[index] }
              : { matched: false };
          });
        });
      });
    }, Promise.resolve(null)).then(function (outcome) {
      if (!outcome || !outcome.matched) {
        typeIntoCombobox(field, "");
        closeCombobox(field);
        return { matched: false };
      }

      return outcome;
    });
  }

  function fillOneCombobox(field, value, alts) {
    if (aceIsListboxButton(field)) return fillOneListbox(field, value, alts);
    if (aceIsWorkdayPrompt(field)) return fillOneWorkdayPrompt(field, value, alts);

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

      var index = chooseMatchedOption(field, texts, value, alts);

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

  /* Whether `field` sits immediately next to a field that answers
     `wantedName`, in the order fillable() reads the page.

     One hop each direction, not a search: this is a test of one
     widget's own two adjacent boxes, and a field three questions away
     answering the same name proves nothing about either of them. */
  function aceNeighbours(field, wantedName) {
    var fields = fillable();
    var index = fields.indexOf(field);

    if (index < 0) return false;

    return [index - 1, index + 1].some(function (i) {
      var neighbour = fields[i];
      if (!neighbour) return false;

      var question = aceQuestionFor(neighbour);
      if (!question) return false;

      return answerNameFor(question, kindOf(neighbour)) === wantedName;
    });
  }

  /* Whether this combobox is the country half of a split phone widget
     -- a dial-code selector paired with a plain number box -- rather
     than a single field carrying the whole number, or an unrelated
     mailing-address Country.

     Two signals, because wording alone cannot always tell them apart.
     The question may say so outright ("country code", "dial code",
     ...), which is the common case. Greenhouse's own widget does not:
     it labels the selector bare "Country", identical to the mailing-
     address question, and no wording rule can tell those two apart --
     they are the same three words. What can is the shape: this one is
     a combobox sitting immediately next to Phone, which is the layout
     this widget always uses and a mailing address never does. */
  function acePhoneCountryField(field) {
    var question = aceQuestionFor(field);

    if (question && aceIsPhoneCountry(question)) return true;

    if (!aceIsAutocomplete(field) || !question) return false;

    return answerNameFor(question, kindOf(field)) === "Country" &&
      aceNeighbours(field, "Phone");
  }

  /* A combobox that has to be answered before the plain fields rather
     than after them, because a plain field's value depends on it.

     Only the phone widget's country qualifies: it rewrites the number
     box beside it whenever it changes. restoreClobbered() puts the
     number back when that happens, and still does, but a number that
     was never wiped needs no putting back -- and a widget told which
     country it is formatting for before the number arrives is far
     likelier to keep the number as written. */
  function gatesAPlainField(field) {
    return acePhoneCountryField(field);
  }

  /* Whether Phone sits beside a country selector that already carries
     the dial code, so the number written there should not repeat it.

     Reported directly: the stored "+1 555 010 0123" went into the
     number box next to a selector already reading "+1", and editing
     out the duplicate by hand reset the selector too -- the two read
     as one bound value to the widget, not two independent fields, so
     there was no way to fix just one side. The fix is not writing the
     duplicate in the first place. */
  function hasPairedCountrySelector(field) {
    var fields = fillable();
    var index = fields.indexOf(field);

    if (index < 0) return false;

    var beside = [index - 1, index + 1].some(function (i) {
      var neighbour = fields[i];

      return !!neighbour && acePhoneCountryField(neighbour);
    });

    return beside || pageHasPhoneCountryControl();
  }

  /* Whether the form asks for the dial code anywhere, as its own control.

     Workday's "Country Phone Code" is a picker holding "United States of
     America (+1)" as a pill, three boxes above Phone Number and not next
     to it in any order ACE reads, so the number went in with its "+1"
     and Workday refused it: "Enter a valid format for Phone Number". A
     form that asks for the code on its own wants the number without it.
     Hidden controls count -- the picker's own search box is one -- and
     only short texts, so a paragraph mentioning a country code is not
     taken for the control. */
  function pageHasPhoneCountryControl() {
    return Array.prototype.some.call(
      document.querySelectorAll("label, legend, input, select, button"),
      function (node) {
        var text = /^(INPUT|SELECT|BUTTON)$/.test(node.tagName)
          ? aceQuestionFor(node)
          : aceNormalise(node.textContent);

        return !!text && text.length <= 80 && aceIsPhoneCountry(text);
      }
    );
  }

  /* Every autocomplete on the page, filled one at a time -- two open
     listboxes at once would make comboboxOptions() ambiguous about
     which one it is reading.

     `only` narrows that to one pass's share of them. */
  function fillComboboxes(only) {
    var filled = [];
    var unmatched = [];

    var fields = fillable().filter(aceIsAutocomplete);

    if (only) fields = fields.filter(only);

    return fields
      .reduce(function (chain, field) {
        return chain.then(function () {
          var question = aceQuestionFor(field);
          if (!question) return;

          var name = answerNameFor(question, kindOf(field));
          if (!name) return;

          var value = answers[name];

          // Inside a claimed history block, the block's own entry is the
          // answer, and a block with no entry is left alone.
          if (ownedByHistory(field)) {
            value = historyValueFor(field) || null;
          }

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
     letters alone: a phone box that renders "+1 555 010 0100" as
     "(555) 010-0100" has kept the number, and rewriting it would
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
      // phone box that renders "+1 555 010 0100" as "(555) 010-0100"
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
      } else if (aceIsListboxButton(record.field)) {
        // A Workday dropdown has no value to write back and, once
        // answered, usually no "Select One" left to choose. Left as
        // chosen rather than throwing halfway through the undo.
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
  /* The questions a shop asks too.

     Recognising two questions was the whole test, and two of these is
     what a delivery form is made of: an IKEA checkout asks a name, an
     email and a postcode, ACE recognised three of them, and the panel
     opened over somebody's shopping.

     Everything else in the bank is evidence of an application --
     work authorisation, a degree, an EEO question, a LinkedIn URL. A
     name and an address are evidence of nothing.

     An answer not listed here counts as evidence, so a new one added
     later counts by default. That is the right way round: failing to
     open on a real application costs the user the whole form, and
     opening on a shop costs them one click -- a click that now
     sticks. */
  var GENERIC_QUESTIONS = [
    "First name",
    "Last name",
    "Full name",
    "Email",
    "Phone",
    "Address",
    "City",
    "State",
    "Postcode",
    "Country",
    "Location",
    "Today's date"
  ];

  /* A resume or cover-letter box, which no shop has.

     File inputs are excluded from fillable(), because ACE cannot fill
     one, so this asks the page directly. It is what keeps the barest
     real application working: a form of name, email, phone and a CV
     upload has nothing else in it to go on. */
  function asksForAResume() {
    var inputs = document.querySelectorAll('input[type="file"]');

    for (var i = 0; i < inputs.length; i++) {
      var question = aceQuestionFor(inputs[i]);

      if (question && /resume|cv|cover letter/i.test(question)) {
        return true;
      }
    }

    return false;
  }

  function isWorkdayListing() {
    return /\.myworkday(?:jobs|site)\.com$/i.test(location.hostname) &&
      !/\/apply(?:\/|$)/i.test(location.pathname);
  }

  function looksLikeApplication() {
    // Workday job search and posting pages can contain several filters that
    // resemble application questions. Only its /apply/ flow is an application.
    if (isWorkdayListing()) return false;
    if (!looksLikeForm()) return false;

    var recognised = 0;

    var distinctive = false;

    var fields = fillable();

    for (var i = 0; i < fields.length; i++) {
      var question = aceQuestionFor(fields[i]);
      if (!question) continue;

      // Detection may count a recognized sensitive question even though
      // V4 will hold its answer for Review.
      var name = aceAnswerNameFor(question, kindOf(fields[i]));
      if (!name) continue;

      recognised += 1;

      if (GENERIC_QUESTIONS.indexOf(name) < 0) distinctive = true;
    }

    if (recognised < 2) return false;

    return distinctive || asksForAResume();
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
  var PANEL_CSS = "/* Deliberately narrow selectors and a high stacking context: this\n   panel lives inside somebody else's stylesheet and must neither\n   inherit from it nor be painted over by it. */\n/* Anchored top-right, not bottom-right: a form's own Submit control\n   is almost always at the bottom of the page, and a fixed panel\n   sitting on top of it blocks the one click the user needs most. */\n/* Anthracite grey, as the ace web app is: charcoal surfaces at night,\n   their light version by day, one red action, green for what was\n   filled, amber for what still needs you. */\n.ace-panel{\n  --bg:#232A2C;--head:rgba(241,243,243,.025);--line:rgba(241,243,243,.08);--line2:rgba(241,243,243,.14);\n  --text:#F1F3F3;--sec:#B8C0C2;--muted:#A7B0B2;--hover:rgba(241,243,243,.06);\n  --ok:#5BE083;--warn:#F7B84B;--accent:#E50914;--accent-hi:#F6121D;\n  --shadow:0 24px 64px rgba(14,18,19,.5),0 2px 6px rgba(14,18,19,.3),inset 0 1px 0 rgba(255,255,255,.06);\n  position:fixed;right:18px;top:18px;z-index:2147483647;\n  width:340px;max-height:min(72vh,580px);display:flex;flex-direction:column;\n  background:var(--bg);color:var(--text);border:1px solid var(--line2);border-radius:16px;\n  box-shadow:var(--shadow);\n  font:var(--text-nav)/var(--leading-body) var(--font-ui);\n  letter-spacing:var(--tracking-body);-webkit-font-smoothing:antialiased;\n  overflow:hidden}\n@media (prefers-color-scheme:light){\n  .ace-panel{\n    --bg:#ECF0F0;--head:rgba(31,38,40,.035);--line:rgba(31,38,40,.1);--line2:rgba(31,38,40,.18);\n    --text:#1F2628;--sec:#3F4A4D;--muted:#4E5A5D;--hover:rgba(31,38,40,.055);\n    --ok:#0E6532;--warn:#7A4900;--accent:#D90B15;--accent-hi:#E50914;\n    --shadow:0 24px 64px rgba(41,49,51,.18),0 2px 6px rgba(41,49,51,.08)}\n}\n.ace-panel *{box-sizing:border-box;font-family:inherit}\n\n.ace-head{display:flex;align-items:center;gap:11px;padding:14px 14px 13px 16px;\n  border-bottom:1px solid var(--line);background:var(--head)}\n.ace-mark{font-size:17px;font-weight:var(--weight-wordmark);letter-spacing:var(--tracking-wordmark);line-height:1;color:var(--text);\n  padding-right:11px;border-right:1px solid var(--line2);flex:0 0 auto}\n.ace-title{font-weight:var(--weight-heading);font-size:var(--text-nav);letter-spacing:var(--tracking-card)}\n.ace-sub{font-size:var(--text-meta);color:var(--muted);margin-top:1px}\n.ace-ver{margin-left:auto;font-size:var(--text-small);color:var(--muted);flex:0 0 auto;\n  font-variant-numeric:tabular-nums;padding:2px 7px;border-radius:99px;\n  background:var(--hover)}\n.ace-x{margin-left:4px;background:none;border:0;color:var(--muted);cursor:pointer;\n  font-size:18px;line-height:1;width:28px;height:28px;border-radius:8px;flex:0 0 auto}\n.ace-x:hover{background:var(--hover);color:var(--text)}\n\n.ace-body{overflow-y:auto;padding:6px 0 8px;flex:1 1 auto}\n.ace-body::-webkit-scrollbar{width:10px}\n.ace-body::-webkit-scrollbar-thumb{background:var(--line2);border-radius:99px;\n  border:3px solid transparent;background-clip:content-box}\n\n.ace-group{font-size:var(--text-small);font-weight:var(--weight-heading);letter-spacing:var(--tracking-label);\n  color:var(--muted);padding:12px 16px 5px}\n.ace-item{display:flex;gap:10px;align-items:flex-start;padding:6px 16px}\n.ace-item:hover{background:var(--hover)}\n.ace-item .k{color:var(--sec);font-size:var(--text-meta);flex:0 0 42%;word-break:break-word}\n.ace-item .v{color:var(--text);font-size:var(--text-label);font-weight:var(--weight-medium);flex:1 1 auto;word-break:break-word}\n.ace-item.done .v{color:var(--ok)}\n.ace-item.miss .v{color:var(--warn)}\n.ace-item.skip .v{color:var(--muted);font-weight:400}\n\n.ace-foot{padding:12px 14px;border-top:1px solid var(--line);display:flex;gap:8px;\n  align-items:center;background:var(--head)}\n.ace-btn{background:var(--accent);color:#FFFFFF;border:0;height:36px;padding:0 16px;border-radius:10px;\n  font-weight:var(--weight-semibold);font-size:var(--text-button);cursor:pointer;\n  box-shadow:0 8px 20px -8px rgba(229,9,20,.55),inset 0 1px 0 rgba(255,255,255,.18);\n  transition:background .12s,transform .12s}\n.ace-btn:hover{background:var(--accent-hi)}\n.ace-btn:active{transform:scale(.97)}\n.ace-btn.ghost{background:transparent;color:var(--text);border:1px solid var(--line2);box-shadow:none}\n.ace-btn.ghost:hover{background:var(--hover)}\n.ace-link{background:none;border:0;padding:0;margin-left:auto;font-size:var(--text-meta);\n  color:var(--muted);cursor:pointer;text-decoration:underline;text-underline-offset:3px;font-family:inherit}\n.ace-link:hover{color:var(--text)}\n.ace-note{font-size:var(--text-meta);color:var(--sec)}\n.ace-note.warn{color:var(--warn)}\n\n\n@media (prefers-reduced-motion:no-preference){\n  .ace-panel{animation:ace-in .22s cubic-bezier(.34,1.3,.64,1)}\n  @keyframes ace-in{from{opacity:0;transform:translateY(8px) scale(.98)}to{opacity:1;transform:none}}\n}";
  PANEL_CSS += `
  /* Typography: the website's approved Refined scale (web/src/app/globals.css), in px
     because rem in here would follow the employer page's root size. */
  .ace-panel{--font-ui:"ace-inter","Inter",ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji";--text-tick:11.5px;--text-small:12px;--text-meta:12.5px;--text-label:13px;--text-button:13.5px;--text-nav:14px;--text-card:15.5px;--text-section:19px;--text-metric:25px;--weight-regular:400;--weight-medium:500;--weight-semibold:590;--weight-strong:620;--weight-heading:650;--weight-emphasis:680;--weight-wordmark:760;--leading-heading:1.3;--leading-body:1.52;--leading-relaxed:1.6;--tracking-section:-.025em;--tracking-card:-.018em;--tracking-body:-.008em;--tracking-metric:-.04em;--tracking-label:.005em;--tracking-wordmark:-.082em}
  .ace-panel{--base:#fffafb;--surface:#fff;--soft:#faedf2;--ink:#271722;--secondary:#765969;--muted:#947a87;--line:#ecdbe3;--wine:#96254d;--wine2:#b23e6e;--mint:#157e60;--mintbg:#e9f7f0;--amber:#995520;--amberbg:#fff3e4;right:10px;top:10px;width:min(480px,calc(100vw - 20px));height:calc(100vh - 20px);max-height:none;background:var(--base);color:var(--ink);border:1px solid var(--line);border-radius:15px;box-shadow:0 12px 38px rgba(106,39,67,.16);font:var(--text-nav)/var(--leading-body) var(--font-ui);letter-spacing:var(--tracking-body)}
  .ace-panel.night{--base:#100c11;--surface:#1b131c;--soft:#2d202d;--ink:#fff4fa;--secondary:#d2b9c6;--muted:#a78c9c;--line:#503545;--wine:#f077a7;--wine2:#e75d91;--mint:#85dabc;--mintbg:#1b3e34;--amber:#ffc189;--amberbg:#3c3025}
  .ace-panel button,.ace-panel input,.ace-panel textarea{font:inherit}.ace-panel button{cursor:pointer}.ace-panel button:focus-visible,.ace-panel input:focus-visible,.ace-panel textarea:focus-visible{outline:3px solid #e995ba;outline-offset:2px}
  .studio-head{padding:17px 18px 14px;background:var(--surface);border-bottom:1px solid var(--line)}.studio-top{display:flex;align-items:center;gap:9px}.studio-logo{font-size:24px;font-weight:var(--weight-wordmark);letter-spacing:var(--tracking-wordmark);line-height:1;color:var(--ink)}.studio-logo:first-letter{color:var(--wine)}.studio-live{margin-left:auto;font-size:var(--text-small);font-weight:var(--weight-semibold);background:var(--mintbg);color:var(--mint);padding:6px 9px;border-radius:20px}.studio-icon{border:1px solid var(--line);background:var(--surface);color:var(--secondary);border-radius:9px;padding:6px 9px}.studio-company{display:flex;gap:11px;align-items:center;margin-top:17px}.studio-glyph{width:37px;height:37px;display:grid;place-items:center;border-radius:10px;background:var(--soft);color:var(--wine);font-weight:var(--weight-heading);font-size:var(--text-label)}.studio-company strong{font-size:var(--text-card);font-weight:var(--weight-heading);letter-spacing:var(--tracking-card)}.studio-company small{display:block;color:var(--muted);font-size:var(--text-label)}.studio-tagline{font-size:var(--text-label);color:var(--secondary);margin:13px 0 0}.studio-button svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;vertical-align:middle}
  .studio-company{background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:10px}.studio-company>div{min-width:0;flex:1}.studio-company strong,.studio-company small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.studio-page-pill{background:var(--surface);border:1px solid var(--line);border-radius:20px;color:var(--secondary);padding:4px 7px;font-size:var(--text-small);white-space:nowrap}
  .studio-icon{width:34px;height:34px;display:grid;place-items:center;padding:0}.studio-icon svg,.studio-button svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.studio-button svg{margin-right:5px}.studio-memory-status{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:8px 0 14px}
  .studio-source{align-items:center}.studio-source>span:nth-child(2){flex:1}.studio-source strong{display:block;color:var(--ink);font-size:var(--text-label);font-weight:var(--weight-strong)}.studio-source small{display:block;color:var(--muted);font-size:var(--text-small)}.studio-source-icon{width:28px;height:28px;display:grid;place-items:center;flex:0 0 auto;border-radius:8px;background:var(--soft);color:var(--wine);font-size:16px}.studio-source-count{float:right;background:var(--mintbg);color:var(--mint);border-radius:5px;padding:3px 6px;font-size:var(--text-small);font-weight:var(--weight-strong);font-variant-numeric:tabular-nums}
  .studio-tabs{display:grid;grid-template-columns:repeat(4,1fr);background:var(--surface);border-bottom:1px solid var(--line);padding:0 8px}.studio-tabs button{background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);font-size:var(--text-label);font-weight:var(--weight-semibold);padding:13px 1px}.studio-tabs button.active{color:var(--wine);border-bottom-color:var(--wine)}
  .studio-scroll{overflow-y:auto;flex:1;padding:18px 17px 24px}.studio-eyebrow{font-size:var(--text-label);font-weight:var(--weight-semibold);letter-spacing:var(--tracking-label);color:var(--muted);margin:0 0 10px}.studio-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:15px;margin:0 0 13px}.studio-card h2{font-size:var(--text-card);font-weight:var(--weight-heading);letter-spacing:var(--tracking-card);line-height:var(--leading-heading);margin:0 0 6px}.studio-card p{color:var(--secondary);font-size:var(--text-label);line-height:var(--leading-relaxed);margin:5px 0}.studio-hero h2{font-size:var(--text-section);letter-spacing:var(--tracking-section)}.studio-progress{height:7px;background:var(--soft);border-radius:20px;overflow:hidden;margin:15px 0 8px}.studio-progress i{display:block;height:100%;background:linear-gradient(90deg,var(--wine),var(--wine2))}.studio-between{display:flex;justify-content:space-between;align-items:center;gap:8px}.studio-between span{font-size:var(--text-meta);color:var(--muted)}.studio-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.studio-metric{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:11px}.studio-metric b{font-size:var(--text-metric);font-weight:var(--weight-emphasis);letter-spacing:var(--tracking-metric);line-height:1.2;font-variant-numeric:tabular-nums;display:block}.studio-metric span{font-size:var(--text-small);color:var(--secondary)}.studio-source{display:flex;justify-content:space-between;gap:8px;border-top:1px solid var(--line);padding:10px 0;font-size:var(--text-label)}.studio-source:first-of-type{border:0}.studio-source b{color:var(--wine)}.studio-pill{display:inline-block;border-radius:20px;padding:4px 7px;background:var(--amberbg);color:var(--amber);font-size:var(--text-small);font-weight:var(--weight-semibold)}.studio-pill.good{background:var(--mintbg);color:var(--mint)}.studio-actions{display:flex;gap:7px;margin-top:10px}.studio-button{background:var(--surface);border:1px solid var(--line);border-radius:9px;color:var(--ink);padding:8px 11px;font-size:var(--text-button);font-weight:var(--weight-semibold)}.studio-button.wine{background:linear-gradient(115deg,#91234b,#bb4772);color:white;border-color:#91234b}.night .studio-button.wine{background:linear-gradient(115deg,#a63766,#d15488)}.studio-button.small{padding:6px 9px}.studio-question{font-size:var(--text-button);font-weight:var(--weight-strong);color:var(--ink);margin:9px 0}.studio-search,.studio-input{width:100%;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--ink);padding:10px}.studio-input{min-height:85px;resize:vertical}.studio-checkline{font-size:var(--text-meta);color:var(--secondary);display:flex;align-items:flex-start;gap:7px;margin:9px 0}.studio-error{border:1px solid var(--amber);color:var(--amber);background:var(--amberbg);padding:10px;border-radius:9px;font-size:var(--text-label);margin-bottom:12px}.studio-foot{background:var(--surface);border-top:1px solid var(--line);padding:12px 16px}.studio-foot-actions{display:flex;gap:8px}.studio-foot-actions button{flex:1}.studio-foot small{display:block;text-align:center;color:var(--muted);font-size:var(--text-small);margin-top:9px}.studio-modal{padding:15px;background:var(--surface);border-top:1px solid var(--line)}.studio-modal label{display:block;font-size:var(--text-label);font-weight:var(--weight-semibold);margin-bottom:6px}.studio-empty{color:var(--muted);font-size:var(--text-label);padding:16px;text-align:center}.studio-receipt{font-size:var(--text-small);color:var(--muted);margin-top:6px}.studio-memory-answer{white-space:pre-wrap;word-break:break-word}.studio-activity{border-left:2px solid var(--line);padding:0 0 15px 13px;font-size:var(--text-label)}.studio-activity strong{display:block;font-weight:var(--weight-strong)}.studio-activity small{color:var(--muted)}
  @media(max-width:520px){.ace-panel{right:0;top:0;width:100vw;height:100vh;border-radius:0}.studio-scroll{padding:14px 12px}.studio-head{padding:14px 12px}}
  `;
  PANEL_CSS += `
  .ace-panel.focus-panel{--base:#fffafb;--surface:#fff;--soft:#faf1f5;--ink:#2d1d28;--secondary:#765d6b;--muted:#987d8d;--line:#ecdce5;--wine:#96254d;--wine2:#b23e6e;--mint:#157e60;--mintbg:#e9f7f0;--amber:#995520;--amberbg:#fff3e4;position:fixed;right:auto;bottom:auto;width:min(318px,calc(100vw - 24px));height:auto;max-height:min(74vh,670px);font:12px/1.47 Inter,system-ui,sans-serif;border-radius:16px;box-shadow:0 16px 48px rgba(70,29,50,.16);overflow:hidden;background:var(--surface)}
  .ace-panel.focus-panel.night{--base:#100c11;--surface:#1d151e;--soft:#2a1d29;--ink:#fff4fa;--secondary:#d2b9c6;--muted:#aa91a1;--line:#503545;--wine:#f077a7;--wine2:#e75d91;--mint:#85dabc;--mintbg:#1b3e34;--amber:#ffc189;--amberbg:#3c3025;box-shadow:0 20px 54px rgba(0,0,0,.5)}
  .ace-panel.focus-panel.focus-review{width:min(348px,calc(100vw - 24px));max-height:min(79vh,720px)}
  .ace-panel.focus-panel.focus-workspace{width:min(371px,calc(100vw - 24px));max-height:min(83vh,760px)}
  .ace-panel.focus-panel.focus-dock{width:min(305px,calc(100vw - 24px));max-height:none}
  .focus-panel .studio-head{padding:12px 13px 10px;background:var(--surface)}
  .focus-panel .studio-top{gap:7px}.focus-panel .studio-logo{font-size:23px;line-height:1}.focus-panel .studio-live{margin-left:0;font-size:10px;padding:3px 7px;font-weight:700}
  .focus-panel .studio-icon{border:0;background:transparent;width:26px;height:26px;padding:4px;border-radius:7px}.focus-panel .studio-icon svg{width:15px;height:15px}
  .focus-panel .focus-grip{margin-left:auto;cursor:grab;touch-action:none;user-select:none}.focus-panel .focus-grip svg{stroke:none;fill:currentColor;width:14px;height:19px}
  .focus-panel .studio-company{display:none}.focus-panel .studio-tagline{margin:4px 0 0;color:var(--secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:10.5px}
  .focus-panel .studio-tabs{grid-template-columns:repeat(4,1fr);padding:0 7px}.focus-panel .studio-tabs button{padding:9px 0;font-size:10px}
  .focus-panel .studio-scroll{padding:13px 12px 14px;min-height:0;overflow-y:auto}.focus-panel .studio-eyebrow{font-size:9px;margin-bottom:7px}.focus-panel .studio-card{padding:12px;border-radius:12px;margin-bottom:9px}
  .focus-panel .studio-card h2{font-size:14px}.focus-panel .studio-card p{font-size:11px}.focus-panel .studio-metrics{gap:5px}.focus-panel .studio-metric{padding:8px}.focus-panel .studio-metric b{font-size:17px}
  .focus-panel .studio-foot{padding:10px 12px}.focus-panel .studio-foot small{font-size:9px;margin-top:6px}.focus-panel .studio-foot-actions button{height:35px}
  .focus-panel .studio-button{border-radius:9px}.focus-panel .studio-button.wine{background:linear-gradient(100deg,#91234b,#b23e6e)}.focus-panel.night .studio-button.wine{background:linear-gradient(100deg,#9b2b59,#ca4b7e)}
  .focus-panel .focus-title-row{display:flex;justify-content:space-between;align-items:center;gap:8px}.focus-panel .focus-title-row h2{font-size:15px;line-height:1.25;margin:0;color:var(--ink)}
  .focus-panel .focus-subtitle{font-size:11px;color:var(--secondary);margin:5px 0 12px}.focus-panel .focus-progress{display:flex;align-items:center;gap:7px;color:var(--secondary);font-size:10px;white-space:nowrap;margin-bottom:12px}.focus-panel .focus-progress i{flex:1;height:5px;background:var(--line);border-radius:10px;overflow:hidden}.focus-panel .focus-progress b{height:100%;display:block;background:var(--wine)}
  .focus-panel .focus-chips{display:flex;gap:5px;overflow:auto;margin-bottom:10px;padding-bottom:2px}.focus-panel .focus-chip{border:1px solid var(--line);background:var(--surface);color:var(--secondary);border-radius:8px;padding:7px 8px;font-size:10px;white-space:nowrap;max-width:145px;overflow:hidden;text-overflow:ellipsis;flex:none}.focus-panel .focus-chip.active{border-color:var(--wine);color:var(--wine);background:var(--soft)}
  .focus-panel .focus-question{background:var(--soft);border-color:var(--line)}.focus-panel .focus-question .studio-question{margin:7px 0 4px;font-size:12px}.focus-panel .focus-question p{margin:0;color:var(--secondary)}
  .focus-panel .studio-search,.focus-panel .studio-input{font-size:11px;min-height:38px;margin-top:5px;border-color:var(--line);background:var(--surface)}.focus-panel .studio-input{min-height:74px}
  .focus-panel .studio-scroll>label{font-size:10px;font-weight:750;color:var(--secondary)}.focus-panel .focus-hint{font-size:10px;color:var(--muted);line-height:1.45;margin:7px 0}.focus-panel .studio-checkline{margin:9px 0;font-size:10px}.focus-panel .studio-checkline input{accent-color:var(--wine)}
  .focus-panel .focus-stays{background:var(--soft);border:1px solid var(--line);border-radius:9px;color:var(--mint);font-size:10px;padding:8px;margin:11px 0}.focus-panel .focus-complete{background:var(--mintbg);color:var(--mint);border-radius:9px;padding:12px;line-height:1.5;margin:10px 0}
  .focus-panel .studio-actions{flex-wrap:wrap}.focus-panel .studio-actions button{flex:1}.focus-panel .focus-dock-body{display:flex;align-items:center;gap:8px;padding:9px 10px;min-height:49px}.focus-panel .focus-dock-status{min-width:0;flex:1}.focus-panel .focus-dock-status strong{display:block;font-size:10px;white-space:nowrap}.focus-panel .focus-dock-status small{display:block;font-size:9px;color:var(--muted);white-space:nowrap}.focus-panel .focus-dock-open{background:var(--soft);border:0;border-radius:8px;color:var(--secondary);width:30px;height:30px}
  .focus-panel .focus-compact-title{font-size:16px;font-weight:800;margin:2px 0 3px;color:var(--ink)}.focus-panel .focus-compact-copy{font-size:11px;color:var(--secondary);margin:0 0 12px}.focus-panel .focus-status{display:flex;justify-content:space-between;gap:7px;border:1px solid var(--line);background:var(--soft);border-radius:10px;padding:10px;margin:10px 0}.focus-panel .focus-status strong{font-size:11px}.focus-panel .focus-status small{display:block;font-size:10px;color:var(--secondary)}.focus-panel .focus-compact-actions{display:flex;gap:7px}.focus-panel .focus-compact-actions button{flex:1}.focus-panel .focus-utility{display:flex;justify-content:space-between;gap:7px;margin-top:12px}.focus-panel .focus-utility button{font-size:10px;background:none;border:0;color:var(--secondary);padding:3px}
  .focus-panel .focus-drag-surface{cursor:grab}.focus-panel.dragging,.focus-panel.dragging *{cursor:grabbing!important;user-select:none!important}
  @media(max-width:520px){.ace-panel.focus-panel{height:auto;max-height:calc(100dvh - 24px);border-radius:16px}.ace-panel.focus-panel.focus-review{max-height:calc(100dvh - 24px)}}
  `;
  // Geometry, colors and borders from the approved V5.1 interactive card.
  // Keep these overrides scoped to Focus Mode so the legacy fallback shell is unchanged.
  PANEL_CSS += `
  .ace-panel.focus-panel{--surface:#fffdfd;--soft:#fbf3f7;--ink:#2d1b27;--secondary:#715967;--muted:#927c89;--line:#ebdce4;--wine:#96294f;--mint:#167655;--mintbg:#eaf7f0;--amber:#975a28;--amberbg:#fff4e5;box-sizing:border-box;background:var(--surface);box-shadow:0 18px 54px rgba(54,21,36,.13),0 2px 10px rgba(54,21,36,.06);border:1px solid var(--line);border-radius:16px;font:12px/1.5 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  .ace-panel.focus-panel.night{--surface:#1b131c;--soft:#281d29;--ink:#fff5fa;--secondary:#d8c1cc;--muted:#b198a7;--line:#503848;--wine:#f07aa9;--mint:#8ad5b2;--mintbg:#19362b;--amber:#ffcc93;--amberbg:#3a2b22;background:var(--surface);box-shadow:0 16px 58px rgba(0,0,0,.4)}
  .ace-panel.focus-panel.focus-review{max-height:min(79vh,735px)}.ace-panel.focus-panel.focus-workspace{max-height:min(83vh,820px)}
  .focus-panel .studio-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 16px 10px;background:var(--surface)}.focus-panel .focus-brand{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}.focus-panel .focus-brand-top{display:flex;align-items:center;gap:9px}.focus-panel .focus-head-controls{display:flex;align-items:center;gap:3px;flex:none}
  .focus-panel .studio-logo{font-size:22px;font-weight:780;letter-spacing:-.09em}.focus-panel .studio-live{font-size:10px;font-weight:650;padding:4px 8px;border-radius:20px}
  .focus-panel .studio-icon{width:29px;height:29px;border-radius:8px;color:var(--secondary)}.focus-panel .studio-icon:hover{background:var(--soft);color:var(--wine)}.focus-panel .studio-icon svg{width:16px;height:16px;stroke-width:1.85}
  .focus-panel .focus-grip{margin-left:0}.focus-panel .focus-grip svg{width:15px;height:15px}
  .focus-panel .studio-tagline{font-size:11px;line-height:1.25;margin:0;max-width:250px}
  .focus-panel .studio-scroll{padding:16px;scrollbar-width:thin}
  .focus-panel .studio-foot{padding:9px 16px 11px;background:var(--surface)}.focus-panel .studio-foot small{display:flex;align-items:center;gap:6px;text-align:left;font-size:10.5px;line-height:1.5;margin:0;color:var(--muted)}.focus-panel .studio-foot small svg{width:14px;height:14px;stroke:var(--mint);stroke-width:1.85;fill:none;stroke-linecap:round;stroke-linejoin:round;flex:none}
  .focus-panel .studio-button{font-size:12px;line-height:1.2;font-weight:630;border-radius:9px;padding:11px 12px;background:var(--surface);border:1px solid var(--line);color:var(--ink)}.focus-panel .studio-button.wine,.focus-panel.night .studio-button.wine{background:#97294f;border-color:#95254f;color:white;font-weight:650}.focus-panel .studio-button.wine:hover{background:#842145}.focus-panel .studio-button svg{width:15px;height:15px;stroke-width:1.85;margin:0}
  .focus-panel .focus-compact-title{font-weight:690;font-size:16px;line-height:1.25;letter-spacing:-.025em;margin:0 0 4px}.focus-panel .focus-compact-copy{font-size:12px;line-height:1.5;margin:0;color:var(--secondary)}
  .focus-panel .focus-status{display:flex;align-items:center;gap:8px;background:var(--soft);border:0;border-radius:11px;padding:10px 11px;margin:14px 0}.focus-panel .focus-status svg{width:17px;height:17px;fill:none;stroke:var(--mint);stroke-width:1.85;stroke-linecap:round;stroke-linejoin:round;flex:none}.focus-panel .focus-status p{margin:0;font-size:11px;color:var(--secondary);line-height:1.4;flex:1}.focus-panel .focus-status strong{font-size:11px;color:var(--ink);font-weight:650}.focus-panel .focus-status span{font-size:10px;color:var(--wine);font-weight:690;white-space:nowrap}
  .focus-panel .focus-compact-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px}.focus-panel .focus-compact-actions button{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:39px}
  .focus-panel .focus-utility{display:flex;justify-content:space-between;gap:7px;margin-top:13px}.focus-panel .focus-utility button{display:inline-flex;align-items:center;gap:4px;font-size:11px;line-height:1.3;font-weight:620;color:var(--secondary);padding:4px 0}.focus-panel .focus-utility button:hover{color:var(--wine)}.focus-panel .focus-utility svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.85;stroke-linecap:round;stroke-linejoin:round}
  .focus-panel .focus-title-row h2{font-size:16px;font-weight:690;letter-spacing:-.025em}.focus-panel .focus-subtitle{font-size:11px;line-height:1.55;margin:4px 0 12px}.focus-panel .focus-progress{font-size:10.5px;margin-bottom:12px}.focus-panel .focus-chip{font-size:11px;padding:8px 10px;border-radius:8px}.focus-panel .focus-question{padding:13px;border-radius:11px}.focus-panel .focus-question .studio-question{font-size:13px;font-weight:680;line-height:1.45;margin:0 0 8px}.focus-panel .focus-question p{font-size:11px;line-height:1.55}.focus-panel .focus-question .studio-pill{background:none;padding:0;margin-bottom:8px;border-radius:0}
  .focus-panel .studio-search,.focus-panel .studio-input{font-size:12px;line-height:1.55;border-radius:8px;padding:10px}.focus-panel .studio-input{min-height:82px}.focus-panel .studio-scroll>label{font-size:11px;font-weight:620}.focus-panel .focus-hint{font-size:10.5px;line-height:1.55}.focus-panel .studio-checkline{font-size:11px;line-height:1.5}.focus-panel .focus-stays{font-size:10.5px;font-weight:570;padding:8px 10px}.focus-panel .studio-actions{display:flex;flex-wrap:nowrap;gap:8px}.focus-panel .studio-actions button{flex:1;min-width:0;white-space:nowrap;font-weight:600}
  .focus-panel .studio-pill{font-size:10px;font-weight:680;padding:5px 8px;border-radius:7px}
  .focus-panel .focus-dock-body{min-height:49px}.focus-panel .focus-dock-status strong{font-size:12px}.focus-panel .focus-dock-status small{font-size:11px}
  .focus-panel,.focus-panel .studio-head,.focus-panel .studio-scroll,.focus-panel .focus-question,.focus-panel .focus-status,.focus-panel .studio-foot{cursor:grab}.focus-panel button,.focus-panel input,.focus-panel textarea,.focus-panel select{cursor:pointer}.focus-panel input,.focus-panel textarea{cursor:text}
  @media(max-width:520px){.focus-panel .studio-scroll{padding:12px}.ace-panel.focus-panel.focus-review{max-height:calc(100dvh - 24px)}}
  `;

  PANEL_CSS += `
  /* Typography: the website's approved Refined scale on the V5.1 card. Type
     properties only; the approved V5.1 geometry and colours stay as they are.
     The packaged Inter face, the website's 11.5px floor and its weights. The
     job line under the wordmark keeps its approved 11px so it is not cut off. */
  .ace-panel.focus-panel{font-family:var(--font-ui);letter-spacing:var(--tracking-body)}
  .focus-panel .studio-logo{font-weight:var(--weight-wordmark);letter-spacing:var(--tracking-wordmark)}
  .focus-panel .studio-live,.focus-panel .studio-pill{font-size:var(--text-tick);font-weight:var(--weight-semibold)}
  .focus-panel .studio-tabs button,.focus-panel .studio-eyebrow,.focus-panel .studio-card p,.focus-panel .focus-subtitle,.focus-panel .focus-progress,.focus-panel .focus-chip,.focus-panel .focus-status p,.focus-panel .focus-status strong,.focus-panel .focus-question p,.focus-panel .studio-scroll>label,.focus-panel .focus-hint,.focus-panel .studio-checkline,.focus-panel .focus-stays,.focus-panel .studio-foot small,.focus-panel .focus-utility button,.focus-panel .focus-dock-status small{font-size:var(--text-tick)}
  .focus-panel .focus-status span{font-size:var(--text-tick);font-weight:var(--weight-strong)}
  .focus-panel .focus-stays{font-weight:var(--weight-medium)}
  .focus-panel .studio-button,.focus-panel .studio-button.wine,.focus-panel.night .studio-button.wine{font-weight:var(--weight-semibold)}
  .focus-panel .focus-progress,.focus-panel .focus-status span,.focus-panel .studio-pill,.focus-panel .studio-metric b,.focus-panel .studio-source-count{font-variant-numeric:tabular-nums}
  `;

  /* Inter, the face the website uses. A shadow root cannot declare its own
     font faces, so the face is added to the page's document, under a name no
     site uses, only once a panel opens. If the page refuses the file, the
     panel keeps the system face. */
  var panelFontRequested = false;
  function loadPanelFont() {
    if (panelFontRequested) return;
    panelFontRequested = true;
    try {
      if (typeof FontFace !== "function" || !document.fonts || !chrome.runtime || !chrome.runtime.getURL) return;
      var url = chrome.runtime.getURL("fonts/InterVariable.woff2");
      var face = new FontFace("ace-inter", "url(" + JSON.stringify(url) + ") format(\"woff2\")",
        { weight: "100 900", style: "normal", display: "swap" });
      document.fonts.add(face);
      face.load().catch(function () {});
    } catch (error) {
      // The system face stays; the panel works either way.
    }
  }

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
    loadPanelFont();

    root.innerHTML =
      "<style>" + PANEL_CSS + "</style>" +
      '<div class="ace-panel"></div>';

    // Listened for in here rather than on the document: an event that
    // crosses a shadow boundary is retargeted to the host, so a
    // document-level closest("[data-ace]") would find nothing.
    root.addEventListener("click", onAceClick, true);
    root.addEventListener("change", function (event) {
      var mirror = event.target.closest('[data-mirror]');
      if (!mirror) return;
      var chosen = studioFields[Number(mirror.getAttribute('data-mirror'))];
      if (!chosen || aceMemory.isEmployerMotivation(chosen.question) || !chosen.field.isConnected) return;
      if (chosen.field.tagName === 'SELECT' && chosen.field.multiple) {
        var wanted = Array.from(mirror.selectedOptions).map(function (option) { return option.value; });
        Array.from(chosen.field.options).forEach(function (option) { option.selected = wanted.indexOf(option.value) >= 0; });
        chosen.field.dispatchEvent(new Event('input', { bubbles: true }));
        chosen.field.dispatchEvent(new Event('change', { bubbles: true }));
        var selectedValues = Array.from(chosen.field.selectedOptions).map(function (option) { return option.value; });
        if (selectedValues.join('|') !== wanted.join('|')) studioError = 'The employer field did not accept these options. Choose them on the form.';
      } else if (chosen.field.tagName === 'SELECT' && mirror.value) {
        setNatively(chosen.field, mirror.value);
        if (chosen.field.value !== mirror.value) studioError = 'The employer field did not accept this option. Choose it on the form.';
      } else if (aceIsListboxButton(chosen.field) && mirror.value) {
        filling = true;
        var opened = listboxOpenedBy(chosen.field, []);
        var resultPromise;
        if (opened) {
          var exact = Array.from(opened.querySelectorAll('[role=option]')).filter(function (option) {
            return String(option.textContent || '').trim() === mirror.value;
          });
          if (exact.length === 1) press(exact[0]);
          resultPromise = Promise.resolve({ matched: exact.length === 1 && !aceIsEmpty(chosen.field) });
        } else resultPromise = fillOneListbox(chosen.field, mirror.value, []);
        resultPromise.then(function (result) {
          filling = false;
          if (!result || !result.matched) studioError = 'The employer field did not accept this option. Choose it on the form.';
          renderStudio(panel());
        }, function () {
          filling = false;
          studioError = 'The employer field did not accept this option. Choose it on the form.';
          renderStudio(panel());
        });
        return;
      } else if (aceIsChoiceControl(chosen.field) && mirror.value) {
        var members = groupMembers(chosen.field);
        var option = members.find(function (member) { return aceOptionLabel(member) === mirror.value; });
        if (option && !aceIsChosen(option)) option.click();
        if (!option || !aceIsChosen(option)) studioError = 'The employer field did not accept this option. Choose it on the form.';
      }
      renderStudio(panel());
    });
    root.addEventListener('input', function (event) {
      if (event.target && event.target.id === 'studio-answer' && event.target.tagName === 'TEXTAREA' && reviewQuestion) {
        reviewDrafts.set(reviewQuestion, event.target.value);
      }
    });
    installFocusDrag(root);

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

  /* What the panel shows never carries an em dash, as nothing in ace
     does: a form's own question can be written with one. Display only:
     the value typed into the form is exactly the saved answer. An
     unspaced en dash is a range and stays. */
  function plain(text) {
    return String(text == null ? "" : text)
      .replace(/\s*(?:[\u2014\u2015]+|\s\u2013\s)\s*/g, ", ")
      .replace(/^(?:,\s*)+|(?:,\s*)+$/g, "")
      .trim();
  }

  function shell(title, subtitle, body, footer) {
    var tag = version();

    return '<div class="ace-head">' +
        '<div class="ace-mark">ace</div>' +
        '<div><div class="ace-title">' + esc(plain(title)) + '</div>' +
        (subtitle ? '<div class="ace-sub">' + esc(plain(subtitle)) + '</div>' : "") +
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
        '<span class="k">' + esc(plain(item[0])) + '</span>' +
        '<span class="v">' + esc(plain(item[1])) + '</span>' +
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

      var name = answerNameFor(question, kindOf(field));
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
    pending = preview();
    renderStudio(host);
  }

  function collectStudioFields() {
    var seen = new Set();
    studioFields = [];
    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);
      if (!question) return;
      var kind = kindOf(field);
      var key = aceMemory.norm(question) + "|" + kind;
      if (seen.has(key)) return;
      seen.add(key);
      var group = aceIsChoiceControl(field) ? groupMembers(field) : [field];
      var answered = !group.every(aceIsEmpty);
      var name = answerNameFor(question, kind);
      if ((!name || !answers[name]) && !approvedQuestions.has(key) && !skippedQuestions.has(key)) reviewSeen.add(key);
      var explicitLabel = field.id ? document.querySelector('label[for="' + CSS.escape(field.id) + '"]') : null;
      var display = explicitLabel ? aceTextWithoutControls(explicitLabel) : field.getAttribute("aria-label") || question;
      studioFields.push({ field: field, question: question, kind: kind, key: key,
        display: display, answered: answered, name: name, protected: aceMemory.policy(question),
        source: name && name.indexOf("Memory:") === 0 ? "Answer Memory" : "Profile and answers" });
    });
    return studioFields;
  }

  function needsStudioReview(field) {
    return !approvedQuestions.has(field.key) && !skippedQuestions.has(field.key) &&
      (reviewSeen.has(field.key) || (!field.answered &&
        (!field.name || !answers[field.name] || !!(pending && pending.noOption.some(function (item) { return item[0] === field.name; })))));
  }

  function studioOverview(fields) {
    var total = fields.length;
    var completed = fields.filter(function (f) { return f.answered; }).length;
    var filled = fields.filter(function (f) { return lastFill.some(function (x) { return x.field === f.field; }); }).length;
    var needs = fields.filter(needsStudioReview).length;
    var profile = fields.filter(function (f) { return f.answered && f.name && f.source !== "Answer Memory" && lastFill.some(function (x) { return x.field === f.field; }); }).length;
    var remembered = fields.filter(function (f) { return f.answered && f.source === "Answer Memory" && lastFill.some(function (x) { return x.field === f.field; }); }).length;
    var pct = total ? Math.round(completed / total * 100) : 0;
    return '<p class="studio-eyebrow">Your application assistant</p>' +
      '<section class="studio-card studio-hero"><div class="studio-between"><h2>' + (filled ? 'Known answers filled. Review the rest.' : needs ? 'Known answers ready. Review the rest.' : 'Review your application') + '</h2><span class="studio-pill good">Live</span></div>' +
      '<p>ACE entered approved answers and protected ' + needs + ' question' + (needs === 1 ? '' : 's') + ' for your review.</p><div class="studio-progress"><i style="width:' + pct + '%"></i></div><div class="studio-between"><span>' + completed + ' of ' + total + ' fields completed</span><strong>' + pct + '%</strong></div></section>' +
      '<div class="studio-metrics"><div class="studio-metric"><b>' + filled + '</b><span>Filled by ACE</span></div><div class="studio-metric"><b>' + needs + '</b><span>Needs review</span></div><div class="studio-metric"><b>' + memory.length + '</b><span>In Memory</span></div></div>' +
      '<section class="studio-card"><h2>✓ &nbsp;Filled from trusted sources <span class="studio-source-count">' + filled + ' fields</span></h2><p>Visible answers remain editable on the employer form. ACE never touches the final submit button.</p><div class="studio-source"><span class="studio-source-icon">✓</span><span><strong>Profile</strong><small>Verified identity and saved answers</small></span><b>' + profile + ' fields</b></div><div class="studio-source"><span class="studio-source-icon">□</span><span><strong>Answer Memory</strong><small>Previously approved reusable answers</small></span><b>' + remembered + ' fields</b></div><div class="studio-source"><span class="studio-source-icon">△</span><span><strong>User review required</strong><small>No fill without enough evidence</small></span><b>' + needs + ' fields</b></div></section>' +
      '<section class="studio-card"><div class="studio-between"><h2>Answer Memory</h2><button class="studio-button small" data-ace="tab:memory">Browse memory</button></div><p>Approved reusable answers can match equivalent questions on another application.</p></section>' +
      '<section class="studio-card"><div class="studio-between"><h2>Needs your input</h2><span class="studio-pill">' + needs + ' open</span></div><p>New and protected questions stay in Review. Complete company motivation on the employer form.</p><button class="studio-button small" data-ace="tab:review">Open review</button></section>' +
      '<section class="studio-card"><h2>Current form</h2><p>' + esc(plain(document.title || location.hostname)) + '</p><p>Detected on ' + esc(location.hostname) + '. No resume attachment is claimed by ACE.</p><button class="studio-button small" data-ace="auto">Auto-fill known: ' + (autoKnown ? 'On' : 'Off') + '</button></section>';
  }

  function studioReview(fields) {
    var open = fields.filter(needsStudioReview);
    var total = reviewSeen.size;
    var done = Array.from(reviewSeen).filter(function (key) { return approvedQuestions.has(key); }).length;
    var skipped = fields.filter(function (field) { return skippedQuestions.has(field.key) && !approvedQuestions.has(field.key); }).length;
    var selected = open.find(function (f) { return f.key === reviewQuestion; }) || open[0];
    if (selected) reviewQuestion = selected.key;
    var html = '<div class="focus-title-row"><h2>' + (open.length ? 'Review questions' : skipped ? 'Review paused' : 'Review complete') + '</h2>' +
      (open.length || skipped ? '<span class="studio-pill">' + (open.length + skipped) + ' open</span>' : '') + '</div>' +
      '<p class="focus-subtitle">' + (open.length ? 'Keep answering here, or on the employer form.' : skipped ?
        'Skipped questions still need your decision on this application.' :
        'ACE\'s review queue is complete. Finish any company-motivation answer on the employer form before submitting manually.') + '</p>' +
      '<div class="focus-progress"><span>' + done + ' of ' + total + ' answered</span><i><b style="width:' + (total ? Math.round(done / total * 100) : 100) + '%"></b></i><span>' + (open.length + skipped) + ' left</span></div>';
    if (!selected && skipped) return html + '<div class="focus-complete">' + skipped + ' skipped question' + (skipped === 1 ? '' : 's') + ' remain. ACE has not submitted anything.</div>' +
      '<p class="focus-stays">✓ &nbsp;Review stays open until you minimize ACE.</p><div class="studio-actions"><button class="studio-button wine" data-ace="resume-review">Resume review</button><button class="studio-button" data-ace="show-form">Check employer form</button></div><div class="focus-utility"><button data-ace="tab:overview">Overview</button><button data-ace="workspace">Memory &amp; activity</button></div>';
    if (!selected) return html + '<div class="focus-complete">All ACE-managed review questions have been addressed. ACE has not submitted anything.</div>' +
      '<p class="focus-stays">✓ &nbsp;Review stays open until you minimize ACE.</p><div class="studio-actions"><button class="studio-button" data-ace="show-form">Check employer form</button><button class="studio-button" data-ace="minimize">Minimize when ready</button></div><div class="focus-utility"><button data-ace="tab:overview">Overview</button><button data-ace="workspace">Memory &amp; activity</button></div>';
    html += '<div class="focus-chips">' + open.slice(0, 6).map(function (f, at) {
      return '<button class="focus-chip ' + (f.key === selected.key ? 'active' : '') + '" data-ace="question:' + fields.indexOf(f) + '">' + (at + 1) + '. ' + esc(tidy(plain(f.display))) + '</button>';
    }).join('') + '</div>';
    var index = fields.indexOf(selected);
    var current = reviewValue(selected);
    var isChoice = selected.field.tagName === 'SELECT' || aceIsChoiceControl(selected.field);
    var control = '';
    if (selected.field.tagName === 'SELECT') {
      control = '<label for="studio-answer">Exact employer options</label><select id="studio-answer" class="studio-search" aria-label="Exact employer options" data-mirror="' + index + '"' + (selected.field.multiple ? ' multiple size="4"' : '') + '>' + (selected.field.multiple ? '' : '<option value=""' + (current ? '' : ' selected') + '>Choose an option</option>') +
        Array.from(selected.field.options).filter(function (option, at) { return !(at === 0 && isPlaceholderText(option.textContent)); }).map(function (option) {
          return '<option value="' + esc(option.value) + '"' + ((selected.field.multiple ? option.selected : option.value === current) ? ' selected' : '') + '>' + esc(plain(option.textContent)) + '</option>';
        }).join('') + '</select>';
    } else if (aceIsChoiceControl(selected.field)) {
      var choices = groupMembers(selected.field);
      control = '<label for="studio-answer">Exact employer options</label><select id="studio-answer" class="studio-search" aria-label="Exact employer options" data-mirror="' + index + '"><option value="">Select an option</option>' +
        choices.map(function (choice) { var option = aceOptionLabel(choice); return '<option value="' + esc(option) + '"' + (option === current ? ' selected' : '') + '>' + esc(plain(option)) + '</option>'; }).join('') + '</select>';
    } else if (aceIsListboxButton(selected.field) && customOptions.has(selected.key)) {
      control = '<label for="studio-answer">Exact employer options</label><select id="studio-answer" class="studio-search" aria-label="Exact employer options" data-mirror="' + index + '"><option value="">Choose an option</option>' +
        customOptions.get(selected.key).map(function (option) {
          return '<option value="' + esc(option) + '"' + (option === current ? ' selected' : '') + '>' + esc(plain(option)) + '</option>';
        }).join('') + '</select>';
    } else if (selected.field.tagName === 'BUTTON' || aceIsAutocomplete(selected.field)) {
      control = '<p>Choose this option on the employer form. ACE will show it here when the form reports a selected value.</p>';
    } else {
      control = '<label for="studio-answer">Your answer</label><textarea id="studio-answer" class="studio-input" aria-label="Your answer">' + esc(current || reviewDrafts.get(selected.key) || '') + '</textarea>';
    }
    var why = selected.protected === 'reusable' ? 'New question. Review this answer before saving.' :
      'Protected question. Confirm for this application only.';
    html += '<article class="studio-card focus-question"><span class="studio-pill ' + (selected.protected === 'reusable' ? 'good' : '') + '">' +
      (selected.protected === 'reusable' ? 'New question' : 'Review required') + (isChoice ? ' · Dropdown' : '') + '</span><div class="studio-question">' + esc(plain(selected.display)) + '</div><p>' + why + '</p></article>' +
      control + '<p class="focus-hint">Select here or on the employer page. ACE checks the employer control before approval.</p>' +
      (selected.protected === 'reusable' && !selected.field.multiple ? '<label class="studio-checkline"><input id="studio-reuse" type="checkbox" checked> Remember this approved answer for equivalent questions</label>' :
        '<p class="focus-hint">Used for this application only. It is not saved to Memory.</p>') +
      '<p class="focus-stays">✓ &nbsp;Review stays open until you minimize ACE.</p>' +
      '<div class="studio-actions"><button class="studio-button wine" data-ace="approve:' + index + '">Approve &amp; fill</button><button class="studio-button" data-ace="show-form">Show on form</button><button class="studio-button" data-ace="skip:' + index + '">Skip</button></div><div class="focus-utility"><button data-ace="tab:overview">Overview</button><button data-ace="workspace">Memory &amp; activity</button></div>';
    return html;
  }

  function reviewValue(item) {
    var field = item.field;
    if (!field || !field.isConnected) return '';
    if (field.tagName === 'SELECT') return field.multiple
      ? Array.from(field.selectedOptions).map(function (option) { return String(option.textContent || '').trim(); }).join(', ')
      : aceIsEmpty(field) ? '' : field.value;
    if (aceIsChoiceControl(field)) {
      var chosen = groupMembers(field).find(aceIsChosen);
      return chosen ? aceOptionLabel(chosen) : '';
    }
    if (aceIsListboxButton(field)) return aceIsEmpty(field) ? '' : String(field.textContent || '').trim();
    if (aceIsAutocomplete(field)) return aceIsEmpty(field) ? '' : String(field.value || '').trim();
    return String(field.value || '').trim();
  }

  function studioMemory() {
    var search = "";
    var input = panel().querySelector(".studio-search");
    if (input) search = input.value.toLowerCase();
    var entries = memory.filter(function (m) { return (m.question + " " + m.answer).toLowerCase().indexOf(search) >= 0; });
    return '<div class="studio-between"><h2>Answer Memory</h2><span class="studio-pill good">' + memory.length + ' approved</span></div><p>Reviewed answers available to equivalent, safe questions.</p><div class="studio-memory-status"><span class="studio-pill ' + (memoryAvailable ? 'good' : '') + '">' + (memoryAvailable ? 'Connected' : 'Unavailable') + '</span><button class="studio-button small" data-ace="retry-memory">Retry connection</button></div><input class="studio-search" type="search" placeholder="Search approved answers" value="' + esc(search) + '">' +
      (entries.length ? entries.map(function (m) {
        return '<article class="studio-card"><span class="studio-pill good">Reusable and approved</span><div class="studio-question">' + esc(plain(m.question)) + '</div><p class="studio-memory-answer">' + esc(plain(m.answer)) + '</p><p class="studio-receipt">Approved on ' + esc(m.source_host || 'an application') + '. Revision ' + m.revision + '</p>' +
          (m.last_used_at ? '<p class="studio-receipt">Last used ' + esc(new Date(m.last_used_at).toLocaleDateString()) + '</p>' : '') +
          (editConcept === m.concept ? '<textarea id="studio-memory-edit" class="studio-input" aria-label="Edit answer">' + esc(m.answer) + '</textarea><div class="studio-actions"><button class="studio-button wine" data-ace="save-edit:' + m.id + '">Save</button><button class="studio-button" data-ace="cancel-edit">Cancel</button></div>' : '<div class="studio-actions"><button class="studio-button" data-ace="edit:' + m.id + '">Edit</button><button class="studio-button" data-ace="delete:' + m.id + '">Delete</button></div>') + '</article>';
      }).join("") : '<div class="studio-empty">' + (memoryAvailable ? 'No approved answers match this search.' : 'Memory will appear here when ACE is connected and updated.') + '</div>');
  }

  function studioActivity() {
    return '<h2>Activity and evidence</h2><p>Local actions on this form. Answer values are not logged.</p>' +
      (activity.length ? activity.map(function (event) { return '<div class="studio-activity"><strong>' + esc(event.label) + '</strong><small>' + esc(event.at) + (event.count ? ' · ' + event.count + ' fields' : '') + '</small></div>'; }).join("") : '<div class="studio-empty">No activity on this form yet.</div>') +
      '<button class="studio-button small" data-ace="undo"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M9 14 4 9l5-5"/><path d="M4 9h9a6 6 0 0 1 0 12h-2"/></svg>Undo last fill</button> <button class="studio-button small" data-ace="copy">Copy field diagnostics</button><span class="ace-copied studio-receipt"></span>';
  }

  function focusCompact(fields) {
    var open = fields.filter(function (field) { return needsStudioReview(field) || skippedQuestions.has(field.key); }).length;
    var filled = lastFill.filter(function (entry) { return entry.field && entry.field.isConnected; }).length;
    return '<h2 class="focus-compact-title">You\'re in control.</h2>' +
      '<p class="focus-compact-copy">' + filled + ' known answers filled. ' + (open ? open + ' question' + (open === 1 ? ' needs' : 's need') + ' you.' : 'ACE review is clear.') + '</p>' +
      '<div class="focus-status"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg><p><strong>Ready to review</strong><br>ACE never submits the employer form.</p><span>' + open + ' open</span></div>' +
      '<div class="focus-compact-actions"><button class="studio-button wine" data-ace="fill"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>Fill</button><button class="studio-button" data-ace="tab:review">Review ' + open + '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg></button></div>' +
      '<div class="focus-utility"><button data-ace="scan"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 9V5h4M15 5h4v4M19 15v4h-4M9 19H5v-4M7 12h10"/></svg>Scan fields</button><button data-ace="workspace">Open memory &amp; activity<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg></button></div>';
  }

  function focusGrip() {
    return '<button class="studio-icon focus-grip" data-focus-grip="1" type="button" aria-label="Move ACE with pointer or arrow keys" title="Drag ACE. Double-click to reset position"><svg viewBox="0 0 18 24" aria-hidden="true"><circle cx="5" cy="5" r="1.5"/><circle cx="12" cy="5" r="1.5"/><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="5" cy="19" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg></button>';
  }

  function positionFocus(host) {
    var x = focusPosition ? focusPosition.x * Math.max(0, innerWidth - host.offsetWidth) : Math.max(12, innerWidth - host.offsetWidth - 18);
    var y = focusPosition ? focusPosition.y * Math.max(0, innerHeight - host.offsetHeight) : 18;
    host.style.left = Math.max(0, Math.min(x, innerWidth - host.offsetWidth)) + 'px';
    host.style.top = Math.max(0, Math.min(y, innerHeight - host.offsetHeight)) + 'px';
  }

  function saveFocusPosition(host) {
    focusPosition = {
      x: Math.max(0, Math.min(1, parseFloat(host.style.left) / Math.max(1, innerWidth - host.offsetWidth))),
      y: Math.max(0, Math.min(1, parseFloat(host.style.top) / Math.max(1, innerHeight - host.offsetHeight)))
    };
    if (chrome.storage && chrome.storage.local) chrome.storage.local.set({ aceFocusPosition: focusPosition });
  }

  function installFocusDrag(root) {
    var gesture = null;
    root.addEventListener('pointerdown', function (event) {
      var host = root.querySelector('.ace-panel.focus-panel');
      if (!host || !host.contains(event.target) || event.button !== 0) return;
      var grip = event.target.closest('[data-focus-grip]');
      if (!grip && (event.target.closest('button,input,textarea,select,a,label,[contenteditable]') || event.pointerType === 'touch')) return;
      gesture = { id: event.pointerId, x: event.clientX, y: event.clientY,
        left: host.offsetLeft, top: host.offsetTop, moved: false };
    });
    root.addEventListener('pointermove', function (event) {
      if (!gesture || gesture.id !== event.pointerId) return;
      var host = root.querySelector('.ace-panel.focus-panel');
      if (!host) return;
      var dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
      if (!gesture.moved && Math.hypot(dx, dy) < 5) return;
      if (!gesture.moved) host.setPointerCapture(event.pointerId);
      gesture.moved = true;
      host.classList.add('dragging');
      host.style.left = Math.max(0, Math.min(innerWidth - host.offsetWidth, gesture.left + dx)) + 'px';
      host.style.top = Math.max(0, Math.min(innerHeight - host.offsetHeight, gesture.top + dy)) + 'px';
      event.preventDefault();
    });
    function finish(event) {
      if (!gesture || gesture.id !== event.pointerId) return;
      var host = root.querySelector('.ace-panel.focus-panel');
      if (host && gesture.moved) {
        saveFocusPosition(host);
        host.classList.remove('dragging');
      }
      gesture = null;
    }
    root.addEventListener('pointerup', finish);
    root.addEventListener('pointercancel', finish);
    root.addEventListener('dblclick', function (event) {
      if (!event.target.closest('[data-focus-grip]')) return;
      focusPosition = null;
      if (chrome.storage && chrome.storage.local) chrome.storage.local.remove('aceFocusPosition');
      positionFocus(root.querySelector('.ace-panel.focus-panel'));
    });
    root.addEventListener('keydown', function (event) {
      if (!event.target.closest('[data-focus-grip]') || !/^Arrow/.test(event.key)) return;
      var host = root.querySelector('.ace-panel.focus-panel');
      var step = event.shiftKey ? 24 : 10;
      var dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
      var dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
      host.style.left = Math.max(0, Math.min(innerWidth - host.offsetWidth, host.offsetLeft + dx)) + 'px';
      host.style.top = Math.max(0, Math.min(innerHeight - host.offsetHeight, host.offsetTop + dy)) + 'px';
      saveFocusPosition(host); event.preventDefault();
    });
    window.addEventListener('resize', function () {
      var host = root.querySelector('.ace-panel.focus-panel');
      if (host) positionFocus(host);
    });
  }

  function renderStudio(host) {
    var previous = host.querySelector(".studio-scroll");
    var scroll = previous ? previous.scrollTop : 0;
    var fields = collectStudioFields();
    var open = fields.filter(function (field) { return needsStudioReview(field) || skippedQuestions.has(field.key); }).length;
    var titleParts = document.title.split(/\s[|·]\s/);
    var employer = (titleParts.length > 1 ? titleParts[titleParts.length - 1] : location.hostname.replace(/^www\./, "")) || "Application form";
    var role = titleParts.length > 1 ? titleParts[0] : document.title || 'Application form';
    var body = focusMode === 'review' ? studioReview(fields) : focusMode === 'compact' ? focusCompact(fields) :
      studioTab === "memory" ? studioMemory() : studioTab === "activity" ? studioActivity() : studioOverview(fields);
    host.className = 'ace-panel focus-panel focus-' + focusMode + (studioTheme === 'night' ? ' night' : '');
    var legacyStatus = lastResult ? 'Filled ' + lastResult.filled.length + ' fields' : 'Fill ' + (pending ? pending.willFill.length : 0) + ' fields';
    var themeLabel = studioTheme === "day" ? "Switch to Night theme" : "Switch to Day theme";
    var themeSvg = studioTheme === "day" ? '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z"/></svg>' : '<svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>';
    if (focusMode === 'dock') {
      render(host, '<div class="focus-dock-body">' + focusGrip() + '<span class="studio-logo">ace</span><span class="focus-dock-status"><strong>' + lastFill.length + ' filled · ' + open + ' to review</strong><small>Form detected · No auto-submit</small></span><button class="focus-dock-open" data-ace="expand" aria-label="Expand ACE">⌄</button></div>');
    } else {
      render(host, '<span class="ace-title" style="display:none">' + legacyStatus + '</span><header class="studio-head"><div class="focus-brand"><div class="focus-brand-top"><span class="studio-logo">ace</span><span class="studio-live">● Form detected</span></div><p class="studio-tagline">' + esc(plain(employer)) + ' · ' + esc(plain(role)) + '</p></div><div class="focus-head-controls">' + focusGrip() + '<button class="studio-icon focus-theme" data-ace="theme" aria-label="' + themeLabel + '" title="' + themeLabel + '">' + themeSvg + '</button><button class="studio-icon" data-ace="minimize" aria-label="Minimize ACE" title="Minimize ACE"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></button></div></header>' +
        (focusMode === 'workspace' ? '<nav class="studio-tabs" aria-label="ACE sections">' + ["overview", "review", "memory", "activity"].map(function (tab) { return '<button data-ace="tab:' + tab + '" class="' + (studioTab === tab ? 'active' : '') + '">' + tab.charAt(0).toUpperCase() + tab.slice(1) + '</button>'; }).join('') + '</nav>' : '') +
        '<div class="studio-scroll">' + (studioError ? '<div class="studio-error">' + esc(studioError) + '</div>' : '') + body + '</div>' +
        '<footer class="studio-foot">' + (focusMode === 'workspace' ? '<div class="studio-foot-actions"><button class="studio-button wine" data-ace="fill">Fill</button><button class="studio-button" data-ace="scan">Scan fields</button></div>' : '') + '<small><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>ACE fills. You review. You submit.</small></footer>');
      host.querySelector(".studio-scroll").scrollTop = scroll;
    }
    positionFocus(host);
    var searchBox = host.querySelector(".studio-search[type=search]");
    if (searchBox) searchBox.addEventListener("input", function () { renderStudio(host); var next = host.querySelector(".studio-search"); next.focus(); next.setSelectionRange(searchBox.value.length, searchBox.value.length); });
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
  /* What a field calls itself when ACE cannot read a question for it.

     Attribute names only, never values: this goes on a clipboard and
     into a conversation, and the bank behind it holds a home address
     and EEO answers. An attribute *name* describes the control; an
     attribute value could be an answer. */
  function fieldSignature(field) {
    var parts = [];

    [
      "aria-label",
      "data-automation-id",
      "name",
      "id",
      "placeholder",
      "role",
      "type"
    ].forEach(function (attribute) {
      var value = field.getAttribute(attribute);

      if (value) parts.push(attribute + "=" + tidy(value).slice(0, 40));
    });

    return parts.length ? parts.join(" ") : "no identifying attributes";
  }

  function diagnostics() {
    var lines = [
      "ACE " + version() + " on " + location.host,
      ""
    ];

    // Counted rather than listed one by one: a page can hold a lot of
    // these and the useful signal is the shape, not the census.
    var unnamed = [];

    fillable().forEach(function (field) {
      var question = aceQuestionFor(field);

      // A field ACE cannot name was silently dropped from this report,
      // which made the report useless for the failure it is most often
      // opened for. A control ACE cannot read a question for is the
      // most important line here, not the one to leave out: it is why
      // the box stayed empty.
      if (!question) {
        unnamed.push(
          "- (no question found) " + field.tagName.toLowerCase() +
          ": " + fieldSignature(field) +
          ", " + (aceIsEmpty(field) ? "empty" : "has a value")
        );

        return;
      }

      var name = answerNameFor(question, kindOf(field));

      var shape = aceIsListboxButton(field)
        ? "dropdown"
        : aceIsAutocomplete(field)
        ? "combobox"
        : field.tagName === "SELECT"
          ? "select"
          : aceIsChoiceControl(field)
            ? "choice"
            : field.tagName.toLowerCase();

      // A work or education block answers its own questions, and its
      // fields deliberately reach none of the rules above -- the bank's
      // single "University" must not be typed into every school box on
      // the page. Without saying so, those fields read here as
      // "matched: nothing", which looks like the bug rather than the
      // design.
      var owned = ownedByHistory(field);

      var line =
        "- " + question.slice(0, 90) +
        "\n    " + shape +
        ", " + (aceIsEmpty(field) ? "empty" : "has a value") +
        ", matched: " + (
          owned
            ? "history:" + (aceHistoryRole(field, question) || "unassigned")
            : (name || "nothing")
        );

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

    if (unnamed.length) {
      lines.push(
        "",
        "Fields ACE could not read a question for (" +
          unnamed.length + "):"
      );

      // Capped, because a wizard page can carry dozens of these and a
      // clipboard note nobody reads to the end helps nobody.
      lines.push.apply(lines, unnamed.slice(0, 25));

      if (unnamed.length > 25) {
        lines.push("- ... and " + (unnamed.length - 25) + " more");
      }
    }

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
    activityNote("Fields filled by ACE", result.filled.length);
    if (result.unmatched.length) activityNote("Options needing review", result.unmatched.length);
    result.filled.forEach(function (name) {
      if (name.indexOf("Memory:") !== 0) return;
      var row = memory.find(function (m) { return m.concept === name.slice(7); });
      if (!row) return;
      row.last_used_at = new Date().toISOString();
      chrome.runtime.sendMessage({ type: "memoryUsed", id: row.id }, function () {});
    });
    renderStudio(host);
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
  /* Whether the form ACE last saw has been taken off the page: at least
     half of its fields no longer connected. */
  function stepReplaced() {
    if (!lastFields.length) return false;

    var gone = lastFields.filter(function (field) {
      return !field.isConnected;
    }).length;

    return gone * 2 >= lastFields.length;
  }

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

    // Workday routes between an application and Search For Jobs without a
    // document reload. A deliberate toolbar Wake still overrides this guard.
    if (!isWorkdayListing()) manualListingOpen = false;
    if (isWorkdayListing() && !manualListingOpen) {
      var listingPanel = document.querySelector('.ace-root');
      if (listingPanel) listingPanel.remove();
      return;
    }

    // Many boards route client-side between postings without a full
    // reload -- the same DOM-mutation signal that re-triggers refresh()
    // also fires on that navigation. A new set of questions gets a new
    // preview, and the previous page's undo cannot apply to fields that
    // are no longer in the document.
    var newApplicationStep = location.href !== lastHref || stepReplaced();
    if (newApplicationStep) {
      reviewSeen.clear();
      approvedQuestions.clear();
      customOptions.clear();
      reviewDrafts.clear();
    }
    if (location.href !== lastHref || movedOn()) {
      lastResult = null;
      lastFill = [];
      skippedQuestions.clear();
      reviewQuestion = "";
    }

    // A new step of an application is a new page to the user, who asked
    // for the panel on every one of them: closing it on "My Information"
    // kept it shut through every Workday step after, and each had to be
    // started from the toolbar. A new step is the form being replaced --
    // most of the fields seen last time gone -- not merely changed: a
    // checkout that adds a field as it recalculates keeps its dismissal,
    // which is what the IKEA report was about, and so does any page that
    // is not an application.
    if (dismissed && stepReplaced() && looksLikeApplication()) {
      dismissed = false;
    }

    lastFields = fillable();

    // A dismissal, though, survives anything short of leaving the page.
    //
    // It used to be cleared by movedOn() as well, and movedOn() is a
    // form-shape comparison, not a navigation: on a page whose form
    // legitimately changes while the user works -- a checkout
    // recalculating a delivery option, say -- every change read as a
    // new page and reopened the panel that had just been closed. An
    // IKEA delivery page reopened it repeatedly, which is what made
    // this worth reporting.
    //
    // Closing the panel is the clearest instruction the user can give,
    // so the only thing that overrides it is going somewhere else.
    if (location.href !== lastHref) {
      lastHref = location.href;
      dismissed = false;
    }

    var currentSignature = formSignature();
    var signatureChanged = currentSignature !== lastSignature;
    lastSignature = currentSignature;

    if (filling) return;
    if (lastResult && !signatureChanged) return;
    if (dismissed) return;

    showPreview(panel());
  }

  function start() {
    chrome.runtime.sendMessage({ type: "answers" }, function (reply) {
      if (chrome.runtime.lastError) return;

      if (reply && !reply.ok && reply.error === "unpaired") {
        render(panel(), shell(
          "Pair ace autofill first",
          "In ace, Settings, Pair the extension. Then type the code in the toolbar icon, Connection.",
          "",
          ""
        ));
        return;
      }

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
          if (item.label === "Field of study" &&
              aceNormalise(item.value) === "computer science") {
            // Workday uses this catalogue wording for the same major.
            // The saved wording is still tried first, so an exact
            // Computer Science option wins when the form offers one.
            aliases[item.label] = aliases[item.label].concat(
              "Computer and Information Science"
            );
          }
          known += 1;
        }
      });

      var authorized = aceIntent(answers["Work authorisation"]);
      var sponsorship = aceIntent(answers["Need sponsorship in future"]);
      if (authorized && sponsorship) {
        answers["Sponsorship follow-up from answers 1 and 2"] =
          authorized === "no" || sponsorship === "yes" ? "Yes" : "No";
        aliases["Sponsorship follow-up from answers 1 and 2"] = [];
      }

      if (aceIntent(answers["At least 18 years old"]) === "yes") {
        answers["Age range from adult status"] = "18 years or older";
        aliases["Age range from adult status"] = ["18 or older", "18+"];
      }

      // Today is not something the bank can hold. A form asking you to
      // date your own acknowledgement wants the day you are signing it,
      // and a stored answer would be right once and wrong every day
      // after -- on a declaration the user is attesting to, which is
      // the worst place for a stale value.
      //
      // Written the way US forms print it, MM/DD/YYYY, which is what
      // these acknowledgements are: the date beside a US legal
      // declaration on a US application.
      answers["Today's date"] = aceTodayUS();

      aliases["Today's date"] = [];

      // "Please confirm your current city and state (for example:
      // Framingham, MA)" wants both, and the State rule alone typed
      // "WA" -- too short for the form to accept. Composed from the two
      // the bank already holds rather than stored a third time.
      if (answers["City"] && answers["State"]) {
        answers["City and state"] = answers["City"] + ", " + answers["State"];
        aliases["City and state"] = [];
      }

      if (!known) studioError = "No answers saved yet. Add answers in ACE or approve questions in Review.";

      loaded = true;
      lastHref = location.href;
      var prefsReady = !(chrome.storage && chrome.storage.local);
      if (prefsReady) autoKnown = false; // Browser fixtures without Chrome storage use explicit Fill.
      var memoryReady = false;
      var historyReady = false;
      function fillWhenReady() {
        if (prefsReady && memoryReady && historyReady && autoKnown) runFill();
      }

      if (chrome.storage && chrome.storage.local) chrome.storage.local.get({ aceStudioTheme: "day", aceAutoKnown: true, aceStudioActivity: [], aceFocusPosition: null }, function (prefs) {
        studioTheme = prefs.aceStudioTheme === "night" ? "night" : "day";
        autoKnown = !!prefs.aceAutoKnown;
        activity = Array.isArray(prefs.aceStudioActivity) ? prefs.aceStudioActivity.slice(0, 35) : [];
        focusPosition = prefs.aceFocusPosition && typeof prefs.aceFocusPosition.x === 'number' && typeof prefs.aceFocusPosition.y === 'number'
          ? prefs.aceFocusPosition : null;
        prefsReady = true;
        refresh();
        fillWhenReady();
      });

      loadMemory(function () {
        memoryReady = true;
        fillWhenReady();
      });

      // Fetched after the answers rather than in parallel: a page with
      // no repeating section is the common case, and the panel should
      // not wait on a request it will not use. refresh() is called
      // again once they land.
      chrome.runtime.sendMessage(
        { type: "history" },
        function (reply) {
          if (!chrome.runtime.lastError && reply && reply.ok) {
            histories.work = reply.work || [];
            histories.education = reply.education || [];
          }
          historyReady = true;
          refresh();
          fillWhenReady();
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

    var comboFields = fillable().filter(aceIsAutocomplete);

    if (!comboFields.length) {
      var flat = plan();
      filling = false;
      lastResult = flat;
      showResult(host, flat);
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

    var result = null;

    // A combobox that never offered options should not strand the
    // panel on "Filling..." forever, and must not cost the user the
    // plain fields either: if the first pass rejects, plan() has not
    // run yet, so it runs here.
    function finish() {
      restoreClobbered();
      filling = false;
      lastResult = result || plan();
      showResult(host, lastResult);
    }

    // Three passes, in this order for one reason: the phone widget's
    // country has to be chosen before the number is written beside it.
    fillComboboxes(gatesAPlainField).then(function (gate) {
      result = plan();
      result.filled = gate.filled.concat(result.filled);
      result.unmatched = gate.unmatched.concat(result.unmatched);

      return fillComboboxes(function (field) {
        return !gatesAPlainField(field);
      });
    }).then(function (rest) {
      result.filled = result.filled.concat(rest.filled);
      result.unmatched = result.unmatched.concat(rest.unmatched);
      finish();
    }, finish);
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

    if (action === 'minimize') { focusMode = 'dock'; renderStudio(panel()); return; }
    if (action === 'expand') { focusMode = studioTab === 'review' ? 'review' : 'compact'; renderStudio(panel()); return; }
    if (action === 'workspace') { focusMode = 'workspace'; studioTab = 'memory'; renderStudio(panel()); return; }
    if (action === 'resume-review') { skippedQuestions.clear(); renderStudio(panel()); return; }
    if (action === 'show-form') {
      var target = studioFields.find(function (f) { return f.key === reviewQuestion; });
      if (target && target.field && target.field.isConnected) {
        target.field.scrollIntoView({ behavior: 'smooth', block: 'center' });
        try { target.field.focus({ preventScroll: true }); } catch (error) { /* Employer widget may reject focus. */ }
      }
      return;
    }
    if (action.indexOf('question:') === 0) {
      var item = studioFields[Number(action.slice(9))];
      if (item) reviewQuestion = item.key;
      renderStudio(panel()); return;
    }

    if (action.indexOf("tab:") === 0) {
      studioTab = action.slice(4);
      focusMode = studioTab === 'review' ? 'review' : studioTab === 'overview' ? 'compact' : 'workspace';
      renderStudio(panel());
      return;
    }

    if (action === "retry-memory") {
      loadMemory();
      return;
    }

    if (action === "theme") {
      studioTheme = studioTheme === "day" ? "night" : "day";
      if (chrome.storage && chrome.storage.local) chrome.storage.local.set({ aceStudioTheme: studioTheme });
      renderStudio(panel());
      return;
    }

    if (action === "auto") {
      autoKnown = !autoKnown;
      if (chrome.storage && chrome.storage.local) chrome.storage.local.set({ aceAutoKnown: autoKnown });
      activityNote("Auto-fill known answers " + (autoKnown ? "enabled" : "disabled"));
      renderStudio(panel());
      return;
    }

    if (action === "scan") {
      lastResult = null;
      activityNote("Form scanned", fillable().length);
      renderStudio(panel());
      return;
    }

    if (action.indexOf("answer:") === 0) {
      var answerField = studioFields[Number(action.slice(7))];
      if (!answerField) return;
      reviewQuestion = answerField.key;
      renderStudio(panel());
      var answerBox = panel().querySelector("#studio-answer");
      if (answerBox) answerBox.focus();
      return;
    }

    if (action === "cancel-review") {
      reviewQuestion = "";
      renderStudio(panel());
      return;
    }

    if (action.indexOf("skip:") === 0) {
      var skipField = studioFields[Number(action.slice(5))];
      if (!skipField) return;
      skippedQuestions.add(skipField.key);
      activityNote("Question skipped for now");
      renderStudio(panel());
      return;
    }

    if (action.indexOf("approve:") === 0) {
      var chosen = studioFields[Number(action.slice(8))];
      var valueBox = panel().querySelector("#studio-answer");
      if (!chosen || aceMemory.isEmployerMotivation(chosen.question)) return;
      var value = valueBox && valueBox.multiple
        ? Array.from(valueBox.selectedOptions).map(function (option) { return String(option.textContent || '').trim(); }).join(', ')
        : valueBox ? valueBox.value.trim() : reviewValue(chosen);
      if (!value || !chosen.field.isConnected) { studioError = "Choose an answer here or on the employer form before approval."; renderStudio(panel()); return; }
      var save = chosen.protected === "reusable" && !chosen.field.multiple && !!panel().querySelector("#studio-reuse:checked");
      function applyApproved() {
        if (!chosen.field.isConnected) {
          studioError = "This field changed. Review the employer form before filling.";
          renderStudio(panel());
          return;
        }
        var existing = reviewValue(chosen);
        if (existing && existing !== value) {
          studioError = "The employer field has a different answer. Review it on the form.";
          renderStudio(panel()); return;
        }
        if (existing === value) { finishApproval(); return; }
        if (chosen.field.multiple) {
          studioError = "The employer field did not accept all selected options. Choose them on the form.";
          renderStudio(panel()); return;
        }
        filling = true;
        var outcome = aceIsListboxButton(chosen.field)
          ? fillOneListbox(chosen.field, value, [])
          : aceIsAutocomplete(chosen.field)
          ? fillOneCombobox(chosen.field, value, [])
          : Promise.resolve({ matched: fillOne(chosen.field, value, []) });
        outcome.then(function (result) {
          filling = false;
          if (!result || !result.matched || aceIsEmpty(chosen.field)) {
            studioError = "The employer field did not accept this answer. Fill it manually.";
            renderStudio(panel());
            return;
          }
          lastFill.push({ field: lastPicked || chosen.field, previous: "", wrote: value, ticked: aceIsChoiceControl(chosen.field) });
          finishApproval();
        }, function () {
          filling = false;
          studioError = "The employer field did not accept this answer. Fill it manually.";
          renderStudio(panel());
        });
      }
      function finishApproval() {
        approvedQuestions.add(chosen.key);
        reviewDrafts.delete(chosen.key);
        reviewQuestion = "";
        studioError = "";
        activityNote(save ? "Answer approved and saved" : "Answer approved for this form");
        renderStudio(panel());
      }
      if (!save) { applyApproved(); return; }
      var concept = aceMemory.concept(chosen.question);
      var memoryValue = chosen.field.tagName === 'SELECT'
        ? String(chosen.field.options[chosen.field.selectedIndex] && chosen.field.options[chosen.field.selectedIndex].textContent || value).trim()
        : aceIsChoiceControl(chosen.field) && chosen.field.type === 'checkbox' && groupMembers(chosen.field).length === 1
        ? 'Yes'
        : value;
      chrome.runtime.sendMessage({ type: "memorySave", item: {
        concept: concept, question: chosen.display, answer: memoryValue,
        answer_type: chosen.kind, source_host: location.hostname
      } }, function (reply) {
        if (chrome.runtime.lastError || !reply || !reply.ok) {
          studioError = memoryFailure(reply && reply.error || chrome.runtime.lastError && chrome.runtime.lastError.message) + " The field remains for review because its answer was not saved.";
          renderStudio(panel());
          return;
        }
        var old = memory.find(function (m) { return m.concept === concept; });
        if (old) { old.answer = memoryValue; old.question = chosen.display; old.revision = reply.item.revision; }
        else memory.push({ id: reply.item.id, concept: concept, question: chosen.display,
          answer: memoryValue, answer_type: chosen.kind, reuse_policy: "reusable", revision: reply.item.revision,
          source_host: location.hostname });
        answers["Memory:" + concept] = memoryValue;
        aliases["Memory:" + concept] = [];
        applyApproved();
      });
      return;
    }

    if (action.indexOf("edit:") === 0) {
      var editRow = memory.find(function (m) { return m.id === Number(action.slice(5)); });
      if (editRow) editConcept = editRow.concept;
      renderStudio(panel());
      return;
    }

    if (action === "cancel-edit") { editConcept = ""; renderStudio(panel()); return; }

    if (action.indexOf("save-edit:") === 0) {
      var row = memory.find(function (m) { return m.id === Number(action.slice(10)); });
      var editBox = panel().querySelector("#studio-memory-edit");
      if (!row || !editBox || !editBox.value.trim()) return;
      var updated = editBox.value.trim();
      chrome.runtime.sendMessage({ type: "memorySave", item: {
        concept: row.concept, question: row.question, answer: updated,
        answer_type: row.answer_type, source_host: row.source_host,
        expected_revision: row.revision
      } }, function (reply) {
        if (chrome.runtime.lastError || !reply || !reply.ok) {
          studioError = memoryFailure(reply && reply.error || chrome.runtime.lastError && chrome.runtime.lastError.message) + " The previous answer is still saved.";
        } else {
          row.answer = updated; row.revision = reply.item.revision;
          answers["Memory:" + row.concept] = updated;
          editConcept = ""; studioError = ""; activityNote("Answer Memory updated");
        }
        renderStudio(panel());
      });
      return;
    }

    if (action.indexOf("delete:") === 0) {
      var id = Number(action.slice(7));
      chrome.runtime.sendMessage({ type: "memoryDelete", id: id }, function (reply) {
        if (chrome.runtime.lastError || !reply || !reply.ok) studioError = memoryFailure(reply && reply.error || chrome.runtime.lastError && chrome.runtime.lastError.message) + " The answer was not deleted.";
        else {
          var deleted = memory.find(function (m) { return m.id === id; });
          if (deleted) delete answers["Memory:" + deleted.concept];
          memory = memory.filter(function (m) { return m.id !== id; });
          activityNote("Answer removed from Memory"); studioError = "";
        }
        renderStudio(panel());
      });
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
      activityNote("Last fill undone");
      renderStudio(panel());
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
        manualListingOpen = isWorkdayListing();

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

        if (answerNameFor(question, kindOf(field))) {
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

  // Employer-owned motivation fields are screened by label before any
  // control value can be observed. Other review controls mirror user edits.
  document.addEventListener('change', function (event) {
    var field = event.target;
    if (!loaded || filling || !field || field.closest && field.closest('.ace-root')) return;
    if (!field.matches || !field.matches('input,textarea,select,button')) return;
    if (aceMemory.isEmployerMotivation(aceQuestionFor(field))) return;
    if (focusMode === 'review') setTimeout(function () {
      var host = document.querySelector('.ace-root');
      if (host && host.shadowRoot) renderStudio(host.shadowRoot.querySelector('.ace-panel'));
    }, 60);
  }, true);

  // A Workday-style listbox may not expose options until the applicant
  // opens it. Mirror only the actual menu associated with that control.
  document.addEventListener('click', function (event) {
    var field = event.target && event.target.closest && event.target.closest('button[aria-haspopup="listbox"]');
    if (!field || !loaded) return;
    var question = aceQuestionFor(field);
    if (aceMemory.isEmployerMotivation(question)) return;
    var before = shownListboxes();
    setTimeout(function () {
      var box = listboxOpenedBy(field, before);
      if (!box) return;
      var options = Array.from(box.querySelectorAll('[role=option]')).filter(function (option) {
        return option.getAttribute('aria-disabled') !== 'true';
      }).map(function (option) { return String(option.textContent || '').trim(); }).filter(Boolean);
      if (!options.length) return;
      customOptions.set(aceMemory.norm(question) + '|' + kindOf(field), options);
      if (focusMode === 'review') {
        var host = document.querySelector('.ace-root');
        if (host && host.shadowRoot) renderStudio(host.shadowRoot.querySelector('.ace-panel'));
      }
    }, 100);
  }, true);

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
    fillComboboxes: fillComboboxes,
    gatesAPlainField: gatesAPlainField,
    fillOne: fillOne,
    restoreClobbered: restoreClobbered,
    recordFill: function (record) { lastFill.push(record); },
    panel: panel,
    shell: shell,
    onAceClick: onAceClick
  };
})();
