/* The content script cannot fetch ACE directly: an application form is
   served from Greenhouse or Ashby, and their pages get no CORS grant to
   read localhost. The service worker holds the host permission, so it
   does the fetch and hands the answers back. */

const DEFAULT_BASE = "http://localhost:8000";

chrome.runtime.onMessage.addListener(
  function (message, sender, respond) {
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
