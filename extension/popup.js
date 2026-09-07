/* The address is configurable because ACE runs wherever the user runs
   it, and a wrong address is otherwise indistinguishable from an
   extension that simply does nothing. */

var base = document.getElementById("base");
var status = document.getElementById("status");

chrome.storage.local.get({ base: "http://localhost:8000" }, function (config) {
  base.value = config.base;
  check();
});

function check() {
  status.textContent = "Checking...";

  chrome.runtime.sendMessage({ type: "answers" }, function (reply) {
    if (!reply || !reply.ok) {
      status.textContent = "Cannot reach ACE. Is it running?";
      return;
    }

    var filled = reply.items.filter(function (item) {
      return item.value;
    }).length;

    status.textContent = filled
      ? filled + " of " + reply.items.length + " answers saved."
      : "Connected, but no answers are filled in yet.";
  });
}

document.getElementById("save").addEventListener("click", function () {
  chrome.storage.local.set(
    { base: base.value.trim() || "http://localhost:8000" },
    check
  );
});
