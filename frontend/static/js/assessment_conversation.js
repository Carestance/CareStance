(function (root) {
  const END_CHAT_DELAY_MS = 5 * 60 * 1000;

  function isEndChatAvailable(startedAt, now = Date.now()) {
    return Number.isFinite(startedAt)
      && Number.isFinite(now)
      && now - startedAt >= END_CHAT_DELAY_MS;
  }

  function createEndChatTimer(button, storageKey) {
    let startedAt = null;
    let timerId = null;

    function readStoredStart() {
      try {
        const storedStart = Number(root.sessionStorage.getItem(storageKey));
        if (Number.isFinite(storedStart) && storedStart > 0 && storedStart <= Date.now()) {
          return storedStart;
        }
      } catch (error) {
        return null;
      }
      return null;
    }

    function setVisible(visible) {
      button.hidden = !visible;
      if (button.classList) {
        button.classList.toggle("hidden", !visible);
      }
    }

    function clearScheduledUpdate() {
      if (timerId !== null) {
        root.clearTimeout(timerId);
        timerId = null;
      }
    }

    function refresh() {
      clearScheduledUpdate();
      if (startedAt === null) {
        setVisible(false);
        return;
      }

      const remaining = Math.max(0, END_CHAT_DELAY_MS - (Date.now() - startedAt));
      setVisible(remaining === 0);
      if (remaining > 0) {
        timerId = root.setTimeout(refresh, remaining);
      }
    }

    function start() {
      if (startedAt === null) {
        startedAt = readStoredStart();
        if (startedAt === null) {
          startedAt = Date.now();
          try {
            root.sessionStorage.setItem(storageKey, String(startedAt));
          } catch (error) {
            // The in-memory timer still works when storage is unavailable.
          }
        }
      }
      refresh();
    }

    function resume() {
      if (startedAt === null) startedAt = readStoredStart();
      refresh();
    }

    function clear() {
      clearScheduledUpdate();
      startedAt = null;
      try {
        root.sessionStorage.removeItem(storageKey);
      } catch (error) {
        // Clearing the in-memory timer is sufficient when storage is unavailable.
      }
      setVisible(false);
    }

    setVisible(false);
    return { start, resume, refresh, clear };
  }

  const api = { END_CHAT_DELAY_MS, isEndChatAvailable, createEndChatTimer };
  root.AssessmentConversationTimer = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
