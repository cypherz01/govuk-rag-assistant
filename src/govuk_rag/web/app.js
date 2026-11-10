// Chat page for the employee rights assistant.
//
// Everything from the server is added with textContent, never parsed as HTML, and only https
// links are rendered. The demo key can arrive in the URL fragment (/#key=...), which browsers
// never send to the server, so it stays out of request logs.
"use strict";

(() => {
  const KEY_STORAGE = "demo-key";
  const KEY_HEADER = "X-Demo-Key";

  const $ = (id) => document.getElementById(id);
  const keyPanel = $("key-panel");
  const keyForm = $("key-form");
  const keyInput = $("key-input");
  const keyMessage = $("key-message");
  const chat = $("chat");
  const log = $("log");
  const suggestions = $("suggestions");
  const askForm = $("ask-form");
  const question = $("question");
  const askButton = $("ask-button");

  // Storage can be unavailable (private browsing, blocked cookies); the page still works.
  const storage = {
    get() {
      try { return localStorage.getItem(KEY_STORAGE); } catch { return null; }
    },
    set(value) {
      try { localStorage.setItem(KEY_STORAGE, value); } catch { /* keep in memory only */ }
    },
    clear() {
      try { localStorage.removeItem(KEY_STORAGE); } catch { /* nothing stored */ }
    },
  };

  let demoKey = null;
  let answerCount = 0;

  function keyFromFragment() {
    const key = new URLSearchParams(location.hash.slice(1)).get("key");
    if (key === null) return null;
    history.replaceState(null, "", location.pathname + location.search);
    return key.trim() || null;
  }

  function showKeyPanel(message) {
    if (message) keyMessage.textContent = message;
    chat.hidden = true;
    keyPanel.hidden = false;
    keyInput.value = "";
    keyInput.focus();
  }

  function showChat() {
    keyPanel.hidden = true;
    chat.hidden = false;
    question.focus();
  }

  function useKey(key) {
    demoKey = key;
    storage.set(key);
    showChat();
  }

  function forgetKey(message) {
    demoKey = null;
    storage.clear();
    showKeyPanel(message);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function isSafeLink(url) {
    try { return new URL(url).protocol === "https:"; } catch { return false; }
  }

  function addMessage(role, text) {
    const item = el("li", `message ${role}`);
    if (text !== undefined) item.append(el("p", "body", text));
    log.append(item);
    item.scrollIntoView({ block: "end", behavior: "smooth" });
    return item;
  }

  // Answer text with each [n] marker turned into a link to the matching source.
  function answerBody(text, citationCount, prefix) {
    const body = el("div", "body");
    for (const paragraph of text.split(/\n{2,}/)) {
      const p = el("p");
      for (const part of paragraph.split(/(\[\d+\])/)) {
        const marker = /^\[(\d+)\]$/.exec(part);
        const n = marker ? Number(marker[1]) : 0;
        if (n >= 1 && n <= citationCount) {
          const sup = el("sup", "cite");
          const link = el("a", null, `[${n}]`);
          link.href = `#${prefix}-${n}`;
          link.setAttribute("aria-label", `Source ${n}`);
          sup.append(link);
          p.append(sup);
        } else if (part) {
          p.append(document.createTextNode(part));
        }
      }
      body.append(p);
    }
    return body;
  }

  function sourcesList(citations, prefix) {
    const section = el("div", "sources");
    section.append(el("h3", "sources-heading", "Sources"));
    const list = el("ol");
    citations.forEach((citation, index) => {
      const item = el("li");
      item.id = `${prefix}-${index + 1}`;
      if (isSafeLink(citation.url)) {
        const link = el("a", "source-title", citation.title);
        link.href = citation.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        item.append(link);
      } else {
        item.append(el("span", "source-title", citation.title));
      }
      item.append(el("p", "snippet", citation.snippet));
      list.append(item);
    });
    section.append(list);
    return section;
  }

  function renderAnswer(item, data) {
    const prefix = `answer${++answerCount}-source`;
    item.className = data.answered ? "message assistant" : "message assistant unanswered";
    item.replaceChildren(answerBody(data.answer, data.citations.length, prefix));
    if (data.citations.length > 0) item.append(sourcesList(data.citations, prefix));
  }

  function renderError(item, text) {
    item.className = "message assistant error";
    item.replaceChildren(el("p", "body", text));
  }

  const ERRORS = {
    422: "Please ask a question of up to 1,000 characters.",
    429: "Too many questions in a short time. Wait a minute and try again.",
    503: "The assistant isn't available right now. Try again later.",
  };

  function setBusy(busy) {
    askButton.disabled = busy;
    question.readOnly = busy;
    askButton.textContent = busy ? "Thinking…" : "Ask";
  }

  async function ask(text) {
    suggestions.hidden = true;
    setBusy(true);
    const userItem = addMessage("user", text);
    const reply = addMessage("assistant pending", "Searching the guidance…");
    question.value = "";
    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", [KEY_HEADER]: demoKey },
        body: JSON.stringify({ question: text }),
      });
      if (response.ok) {
        renderAnswer(reply, await response.json());
      } else if (response.status === 401) {
        userItem.remove();
        reply.remove();
        question.value = text;
        forgetKey("That demo key wasn't accepted. Check it and enter it again.");
        return;
      } else {
        renderError(reply, ERRORS[response.status] ??
          `Something went wrong (error ${response.status}). Try again.`);
      }
    } catch {
      renderError(reply, "Couldn't reach the assistant. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
    question.focus();
  }

  keyForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const key = keyInput.value.trim();
    if (key) useKey(key);
  });

  askForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = question.value.trim();
    if (text && !askButton.disabled) ask(text);
  });

  // Enter sends; Shift+Enter starts a new line.
  question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      askForm.requestSubmit();
    }
  });

  for (const button of document.querySelectorAll(".suggestion")) {
    button.addEventListener("click", () => {
      if (!askButton.disabled) ask(button.textContent);
    });
  }

  $("change-key").addEventListener("click", () => forgetKey("Enter the demo key to use."));

  const initialKey = keyFromFragment() ?? storage.get();
  if (initialKey) useKey(initialKey);
  else showKeyPanel();
})();
