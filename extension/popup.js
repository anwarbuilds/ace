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
  chrome.tabs.query(
    { active: true, currentWindow: true },
    function (tabs) {
      var tab = tabs && tabs[0];

      if (!tab || !tab.id) {
        pageLine.className = "s warn";
        pageLine.textContent = "No page to check.";
        return;
      }

      chrome.tabs.sendMessage(
        tab.id,
        { type: "status" },
        function (reply) {
          if (chrome.runtime.lastError || !reply) {
            pageLine.className = "s warn";
            pageLine.textContent =
              "Not an application form, so ACE is staying quiet. " +
              "Reload the page if you expected it here.";
            return;
          }

          pageLine.className = reply.fields ? "s" : "s warn";
          pageLine.textContent = reply.fields
            ? "ACE recognises " + reply.fields +
              " question" + (reply.fields === 1 ? "" : "s") + " here."
            : "ACE recognises nothing to fill on this page.";
        }
      );
    }
  );
}

document.getElementById("save").addEventListener("click", function () {
  chrome.storage.local.set(
    { base: base.value.trim() || "http://localhost:8000" },
    check
  );
});
