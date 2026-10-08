/* The content script cannot fetch ACE directly: an application form is
   served from Greenhouse or Ashby, and their pages get no CORS grant to
   read localhost. The service worker holds the host permission, so it
   does the fetch and hands the answers back. */

const DEFAULT_BASE = "http://localhost:8000";

/* The repeating work and study blocks, which are a list rather than a
   value and so cannot live in the answer bank. Fetched separately and
   only once a page turns out to have such a section. */
function fetchJson(path) {
  return new Promise(function (resolve) {
    chrome.storage.local.get(
      { base: DEFAULT_BASE },
      function (config) {
        const base = String(config.base || DEFAULT_BASE).replace(/\/+$/, "");

        fetch(base + path, { cache: "no-store" })
          .then(function (response) {
            if (!response.ok) throw new Error("HTTP " + response.status);
            return response.json();
          })
          .then(function (data) {
            resolve((data && data.items) || []);
          })
          .catch(function () {
            resolve([]);
          });
      }
    );
  });
}

chrome.runtime.onMessage.addListener(
  function (message, sender, respond) {
    if (message && message.type === "history") {
      Promise.all([
        fetchJson("/api/history/work"),
        fetchJson("/api/history/education"),
      ]).then(function (both) {
        respond({
          ok: true,
          work: both[0],
          education: both[1],
        });
      });

      return true;
    }

    if (message && message.type === "answers") {
      chrome.storage.local.get(
        { base: DEFAULT_BASE },
        function (config) {
          const base = String(config.base || DEFAULT_BASE).replace(/\/+$/, "");

          fetch(base + "/api/answers", { cache: "no-store" })
            .then(function (response) {
              if (!response.ok) throw new Error("HTTP " + response.status);
              return response.json();
            })
            .then(function (data) {
              respond({ ok: true, items: (data && data.items) || [] });
            })
            .catch(function (error) {
              // Reported rather than swallowed: a silent no-op looks
              // exactly like a form with nothing to fill.
              respond({ ok: false, error: String(error.message || error) });
            });
        }
      );

      return true;
    }
  }
);


/* A careers site the user turned ACE on for, from the popup.

   The manifest runs ACE only on job portals. A company that self-hosts
   its careers site is added one site at a time: the popup asks Chrome
   for that site, and once Chrome reports the grant, ACE is registered
   there and persists across restarts. Done here rather than in the
   popup, because the popup can close while Chrome's prompt is showing.
   Removing the grant removes ACE from the site. */
function siteScriptId(pattern) {
  return "site-" + pattern.replace(/[^a-z0-9]/gi, "_");
}

chrome.permissions.onAdded.addListener(function (added) {
  (added.origins || []).forEach(function (pattern) {
    // Never every site at once: that is what the user asked ACE to stop.
    if (/^https?:\/\/\*\//.test(pattern)) return;

    chrome.scripting.registerContentScripts([{
      id: siteScriptId(pattern),
      matches: [pattern],
      js: ["fields.js", "content.js"],
      runAt: "document_idle",
      allFrames: true,
      persistAcrossSessions: true
    }]).catch(function () {
      /* already registered */
    });
  });
});

chrome.permissions.onRemoved.addListener(function (removed) {
  (removed.origins || []).forEach(function (pattern) {
    chrome.scripting.unregisterContentScripts({
      ids: [siteScriptId(pattern)]
    }).catch(function () {
      /* was not registered */
    });
  });
});
