/* The address is configurable because ACE runs wherever the user runs
   it, and a wrong address is otherwise indistinguishable from an
   extension that simply does nothing.

   The same is true of a page ACE stays quiet on. "Nothing to autofill"
   looks identical to a broken extension, so the popup says which of
   the two it is -- and it asks the page rather than guessing from the
   host. There is no host list any more: ACE runs everywhere and
   decides per page, because the list could not be made to hold. Most
   companies self-host their own board and Oracle gives every tenant a
   subdomain, so a substantial share of one real user's applications went through 19
   hosts the list did not name. */

var base = document.getElementById("base");
var answerLine = document.getElementById("answers");
var pageLine = document.getElementById("page");
var fillButton = document.getElementById("fill");

chrome.storage.local.get({ base: "http://localhost:8000" }, function (config) {
  base.value = config.base;
  check();
});

function check() {
  answerLine.textContent = "Checking ACE...";

  chrome.runtime.sendMessage({ type: "answers" }, function (reply) {
    if (!reply || !reply.ok) {
      answerLine.textContent = "Cannot reach ACE. Is it running?";
      answerLine.className = "s warn";
      return;
    }

    var filled = reply.items.filter(function (item) {
      return item.value;
    }).length;

    answerLine.className = filled ? "s" : "s warn";
    answerLine.textContent = filled
      ? filled + " of " + reply.items.length + " answers saved."
      : "Connected, but no answers are filled in yet.";
  });

  // Asked of the page itself. The content script is the only thing
  // that knows whether it recognised any questions here, and a host
  // name never did.
  withActiveTab(function (tab) {
    ask(
      tab,
      { type: "status" },
      function (reply, missing) {
        if (missing) {
          explainMissing(tab);
          return;
        }

        pageLine.className = reply.fields ? "s" : "s warn";
        pageLine.textContent = reply.fields
          ? "ACE recognises " + reply.fields +
            " question" + (reply.fields === 1 ? "" : "s") + " here."
          : "ACE recognises nothing to fill on this page.";
      }
    );
  });
}

fillButton.addEventListener("click", fillActivePage);

/* Why ACE is not on a page that was loaded after it was installed.

   Chrome lets a person set an extension to run only when its icon is
   clicked ("Site access: On click"). Then the panel never appears by
   itself, on any form, and every application has to be started from the
   toolbar -- which is what the user was doing. The page cannot tell; the
   granted permissions can. */
function explainMissing(tab) {
  var origin = null;

  try {
    origin = new URL(tab.url).origin;
  } catch (error) {
    origin = null;
  }

  pageLine.className = "s warn";

  if (!origin || !/^https?:/.test(origin)) {
    pageLine.textContent = "ACE does not run on this page.";
    return;
  }

  chrome.permissions.contains(
    { origins: [origin + "/*"] },
    function (granted) {
      pageLine.textContent = granted
        ? "ACE has not loaded into this tab yet. Reload the page, " +
          "or press Fill this page."
        : "Chrome runs ACE here only when you click it. For the panel " +
          "to appear by itself: chrome://extensions, ace autofill, " +
          "Details, Site access: On all sites.";
    }
  );
}

document.getElementById("save").addEventListener("click", function () {
  chrome.storage.local.set(
    { base: base.value.trim() || "http://localhost:8000" },
    check
  );
});

function withActiveTab(run) {
  chrome.tabs.query(
    { active: true, currentWindow: true },
    function (tabs) {
      var tab = tabs && tabs[0];

      if (!tab || !tab.id) {
        pageLine.className = "s warn";
        pageLine.textContent = "No page to check.";
        return;
      }

      run(tab);
    }
  );
}

/* Send a message to the page, reporting separately whether nobody was
   listening. That case is not an answer of "no", it is "ACE is not in
   this tab", and the two need different words and different remedies. */
function ask(tab, message, done) {
  chrome.tabs.sendMessage(
    tab.id,
    message,
    function (reply) {
      if (chrome.runtime.lastError || !reply) {
        done(null, true);
        return;
      }

      done(reply, false);
    }
  );
}

/* Put ACE into this tab, then run it.

   The manifest injects on page load, which cannot help a tab that was
   already open, or one opened before the extension was last reloaded.
   Injecting here covers both, and the user clicking Fill is a better
   signal than any heuristic about whether the page is an application
   form -- so the wake message runs it either way.

   content.js refuses to initialise twice, so injecting over a script
   that is already there is harmless. */
function fillActivePage() {
  withActiveTab(function (tab) {
    fillButton.disabled = true;
    pageLine.className = "s";
    pageLine.textContent = "Loading ACE into this page...";

    // No stylesheet to inject: the panel carries its own inside a
    // shadow root, so the page cannot restyle it and nothing has to
    // be placed in the page for it to look right.
    chrome.scripting.executeScript(
      {
        target: { tabId: tab.id },
        files: ["fields.js", "content.js"],
      },
      function () {
        fillButton.disabled = false;

        if (chrome.runtime.lastError) {
          pageLine.className = "s warn";
          pageLine.textContent =
            "Chrome will not let ACE run on this page.";
          return;
        }

        ask(
          tab,
          { type: "wake" },
          function (_reply, missing) {
            if (missing) {
              pageLine.className = "s warn";
              pageLine.textContent =
                "Injected, but the page did not answer.";
              return;
            }

            pageLine.className = "s";
            pageLine.textContent =
              "ACE is on the page. Review it there, then Fill.";

            window.close();
          }
        );
      }
    );
  });
}
