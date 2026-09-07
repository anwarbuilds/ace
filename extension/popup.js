/* The address is configurable because ACE runs wherever the user runs
   it, and a wrong address is otherwise indistinguishable from an
   extension that simply does nothing.

   The same is true of an unsupported page. "Nothing to autofill" on a
   site the extension was never loaded into looks identical to a broken
   extension, so the popup says which of the two it is. */

var COVERED = [
  "greenhouse.io", "jobs.ashbyhq.com", "jobs.lever.co",
  "smartrecruiters.com", "explore.jobs.netflix.net", "eightfold.ai",
  "myworkdayjobs.com", "myworkdaysite.com", "www.amazon.jobs",
  "ats.rippling.com"
];

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

  chrome.tabs.query(
    { active: true, currentWindow: true },
    function (tabs) {
      var url = (tabs && tabs[0] && tabs[0].url) || "";

      var covered = COVERED.some(function (host) {
        return url.indexOf(host) >= 0;
      });

      pageLine.className = covered ? "s" : "s warn";
      pageLine.textContent = covered
        ? "This page is one ACE fills."
        : "ACE does not fill this site. Tell it which one and it can be added.";
    }
  );
}

document.getElementById("save").addEventListener("click", function () {
  chrome.storage.local.set(
    { base: base.value.trim() || "http://localhost:8000" },
    check
  );
});
