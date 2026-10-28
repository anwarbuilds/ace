/* The content script cannot fetch ACE directly: an application form is
   served from Greenhouse or Ashby, and their pages get no CORS grant to
   read localhost. The service worker holds the host permission, so it
   does the fetch and hands the answers back.

   ACE asks who is calling. The extension proves it with its own token,
   made once by pairing (a code shown in ACE, Settings, typed into the
   popup) and kept in chrome.storage.local. The token may read the
   answer bank and history, and manage only the separate, owner-approved
   Answer Memory resource. */

const DEFAULT_BASE = "http://localhost:8000";

function withConfig(run) {
  chrome.storage.local.get(
    { base: DEFAULT_BASE, token: "" },
    function (config) {
      run(
        String(config.base || DEFAULT_BASE).replace(/\/+$/, ""),
        String(config.token || "")
      );
    }
  );
}

function authHeaders(token) {
  return token ? { Authorization: "Bearer " + token } : {};
}

/* One GET against ACE. A 401 is reported as "unpaired" rather than as
   a bare status, because the popup has a remedy for exactly that. */
function getJson(path) {
  return new Promise(function (resolve, reject) {
    withConfig(function (base, token) {
      fetch(base + path, { cache: "no-store", headers: authHeaders(token) })
        .then(function (response) {
          if (response.status === 401) throw new Error("unpaired");
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(resolve, reject);
    });
  });
}

function memoryRequest(method, path, payload) {
  return new Promise(function (resolve, reject) {
    withConfig(function (base, token) {
      fetch(base + path, {
        method: method,
        cache: "no-store",
        headers: Object.assign({ "Content-Type": "application/json" }, authHeaders(token)),
        body: payload ? JSON.stringify(payload) : undefined,
      }).then(function (response) {
        if (response.status === 401) throw new Error("unpaired");
        if (!response.ok) throw new Error("Memory save failed (HTTP " + response.status + ")");
        return response.json();
      }).then(resolve, reject);
    });
  });
}

/* The repeating work and study blocks, which are a list rather than a
   value and so cannot live in the answer bank. Fetched separately and
   only once a page turns out to have such a section. */
function fetchItems(path) {
  return getJson(path)
    .then(function (data) {
      return (data && data.items) || [];
    })
    .catch(function () {
      return [];
    });
}

function pair(code, respond) {
  withConfig(function (base) {
    fetch(base + "/api/extension/pair", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code, name: "Chrome extension" }),
    })
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            const detail = body && body.detail;
            throw new Error(
              (detail && detail.message) || "HTTP " + response.status
            );
          }
          return body;
        });
      })
      .then(function (body) {
        chrome.storage.local.set({ token: body.token }, function () {
          respond({ ok: true });
        });
      })
      .catch(function (error) {
        respond({ ok: false, error: String(error.message || error) });
      });
  });
}

/* Keep an embedded employer's form work in its own content script, while
   displaying ACE in the outer viewport. Routes stay in this tab and in the
   extension's isolated worlds; no page postMessage or credential is involved. */
function routeFocusPanel(message, sender, respond) {
  if (!sender || sender.id !== chrome.runtime.id || !sender.tab ||
      !Number.isSafeInteger(sender.tab.id) || !Number.isSafeInteger(sender.frameId)) {
    respond({ ok: false }); return;
  }
  var target, forwarded;
  if ((message.op === 'render' || message.op === 'hide') && sender.frameId > 0) {
    target = { frameId: 0 };
    forwarded = Object.assign({}, message, { sourceFrame: sender.frameId, sourceDocument: sender.documentId });
  } else if (message.op === 'event' && sender.frameId === 0 && Number.isSafeInteger(message.sourceFrame) && message.sourceFrame > 0) {
    target = { frameId: message.sourceFrame };
    if (typeof message.sourceDocument === 'string') target.documentId = message.sourceDocument;
    forwarded = message;
  } else { respond({ ok: false }); return; }
  chrome.tabs.sendMessage(sender.tab.id, Object.assign({}, forwarded, { type: 'aceFocusDelivery' }), target, function (reply) {
    var failed = chrome.runtime.lastError;
    respond(!failed && reply ? reply : { ok: false });
  });
}

/* An extension update leaves every open tab running the previous content
   script, cut off from Chrome ("Extension context invalidated"): it can no
   longer load or save answers. The new one is injected into open pages, so
   an application in progress keeps working without a reload that could lose
   what was typed. The new copy claims the card and the old one is hidden.
   Pages ACE may not access are left alone. */
if (chrome.runtime.onInstalled) chrome.runtime.onInstalled.addListener(function (details) {
  if (!details || details.reason !== "update") return;
  chrome.tabs.query({}, function (tabs) {
    (tabs || []).forEach(function (tab) {
      if (!Number.isSafeInteger(tab.id)) return;
      chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        files: ["fields.js", "memory.js", "content.js"],
      }, function () {
        void chrome.runtime.lastError;
      });
    });
  });
});

chrome.runtime.onMessage.addListener(
  function (message, sender, respond) {
    if (message && message.type === 'aceFocusRoute') {
      routeFocusPanel(message, sender, respond);
      return true;
    }

    if (message && message.type === "memory") {
      getJson("/api/extension/memory").then(function (data) {
        respond({ ok: true, items: data.items || [] });
      }, function (error) {
        respond({ ok: false, error: String(error.message || error) });
      });
      return true;
    }

    if (message && message.type === "memorySave") {
      memoryRequest("PUT", "/api/extension/memory", message.item).then(function (data) {
        respond({ ok: true, item: data });
      }, function (error) {
        respond({ ok: false, error: String(error.message || error) });
      });
      return true;
    }

    if (message && message.type === "memoryDelete" && Number.isSafeInteger(message.id)) {
      memoryRequest("DELETE", "/api/extension/memory/" + message.id).then(function (data) {
        respond({ ok: true, item: data });
      }, function (error) {
        respond({ ok: false, error: String(error.message || error) });
      });
      return true;
    }
    if (message && message.type === "memoryUsed" && Number.isSafeInteger(message.id)) {
      memoryRequest("POST", "/api/extension/memory/" + message.id + "/used").then(function () {
        respond({ ok: true });
      }, function () {
        respond({ ok: false });
      });
      return true;
    }
    if (message && message.type === "history") {
      Promise.all([
        fetchItems("/api/history/work"),
        fetchItems("/api/history/education"),
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
      getJson("/api/answers")
        .then(function (data) {
          respond({ ok: true, items: (data && data.items) || [] });
        })
        .catch(function (error) {
          // Reported rather than swallowed: a silent no-op looks
          // exactly like a form with nothing to fill.
          respond({ ok: false, error: String(error.message || error) });
        });

      return true;
    }

    // Only the extension's own pages (the popup) may pair or unpair: a
    // content script runs inside an arbitrary page and has no business
    // touching the token. Its sender URL is that page's, not ours.
    const ownPage =
      sender.id === chrome.runtime.id &&
      String(sender.url || "").indexOf(chrome.runtime.getURL("")) === 0;

    if (message && message.type === "pair" && ownPage) {
      pair(String(message.code || ""), respond);
      return true;
    }

    if (message && message.type === "unpair" && ownPage) {
      chrome.storage.local.remove("token", function () {
        respond({ ok: true });
      });
      return true;
    }
  }
);
