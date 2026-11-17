(() => {
  const installButtons = document.querySelectorAll("[data-pwa-install]");
  const notificationButtons = document.querySelectorAll("[data-pwa-notifications]");
  const feedback = document.querySelector("#pwa-feedback");
  let installPrompt;

  function showFeedback(message, isError = false) {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.classList.toggle("pwa-feedback-error", isError);
    feedback.hidden = false;
  }

  function isInstalled() {
    return window.matchMedia("(display-mode: standalone)").matches
      || window.navigator.standalone === true;
  }

  function updateInstallButtons() {
    if (isInstalled()) {
      installButtons.forEach((button) => {
        button.hidden = true;
      });
    }
  }

  async function requestInstallation() {
    if (!installPrompt) {
      showFeedback("Use your browser menu to choose Install app or Add to Home Screen.");
      return;
    }

    const prompt = installPrompt;
    installPrompt = null;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      showFeedback(
        choice.outcome === "accepted"
          ? "CareStance is being installed."
          : "Installation was cancelled. You can try again from your browser menu."
      );
      installButtons.forEach((button) => {
        button.hidden = true;
      });
    } catch (error) {
      showFeedback(error.message || "Could not open the installation prompt.", true);
    }
  }

  async function getPushSubscription() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      throw new Error("Push notifications are not supported by this browser.");
    }
    const registration = await navigator.serviceWorker.ready;
    return { registration, subscription: await registration.pushManager.getSubscription() };
  }

  async function sendSubscriptionRequest(method, subscription) {
    const response = await fetch("/api/v1/push/subscriptions", {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription.toJSON()),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.detail || "Could not update notification settings.");
    }
  }

  async function enablePush(registration, permissionRequest) {
    if (Notification.permission === "denied") {
      throw new Error("Notifications are blocked in your browser settings.");
    }
    const permission = permissionRequest
      ? await permissionRequest
      : Notification.permission;
    if (permission !== "granted") {
      throw new Error("Allow notifications in your browser to continue.");
    }

    const keyResponse = await fetch("/api/v1/push/public-key", {
      credentials: "same-origin",
    });
    const keyInfo = await keyResponse.json().catch(() => ({}));
    if (!keyResponse.ok || !keyInfo.enabled || !keyInfo.public_key) {
      throw new Error(keyInfo.detail || "Push notifications are not configured on the CareStance server yet.");
    }

    const paddedKey = keyInfo.public_key + "=".repeat((4 - keyInfo.public_key.length % 4) % 4);
    const decodedKey = atob(paddedKey.replace(/-/g, "+").replace(/_/g, "/"));
    const applicationServerKey = Uint8Array.from(
      decodedKey,
      (character) => character.charCodeAt(0)
    );
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });
    try {
      await sendSubscriptionRequest("POST", subscription);
    } catch (error) {
      await subscription.unsubscribe();
      throw error;
    }
  }

  async function togglePush() {
    notificationButtons.forEach((button) => {
      button.disabled = true;
    });
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
        throw new Error("Push notifications are not supported by this browser.");
      }
      const permissionRequest = Notification.permission === "default"
        ? Notification.requestPermission()
        : null;
      const { registration, subscription } = await getPushSubscription();
      if (subscription) {
        await sendSubscriptionRequest("DELETE", subscription);
        await subscription.unsubscribe();
        showFeedback("CareStance notifications are off on this device.");
      } else {
        await enablePush(registration, permissionRequest);
        showFeedback("CareStance notifications are on for this device.");
      }
      await updateNotificationButtons();
    } catch (error) {
      showFeedback(error.message, true);
    } finally {
      notificationButtons.forEach((button) => {
        button.disabled = false;
      });
    }
  }

  async function updateNotificationButtons() {
    if (!notificationButtons.length) return;
    try {
      const { subscription } = await getPushSubscription();
      notificationButtons.forEach((button) => {
        button.textContent = subscription ? "Turn off notifications" : "Enable notifications";
      });
    } catch (error) {
      notificationButtons.forEach((button) => {
        button.disabled = true;
        button.textContent = "Notifications unavailable";
      });
      showFeedback(error.message, true);
    }
  }

  installButtons.forEach((button) => {
    button.addEventListener("click", requestInstallation);
  });
  notificationButtons.forEach((button) => {
    button.addEventListener("click", togglePush);
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    installButtons.forEach((button) => {
      button.hidden = false;
      button.textContent = "Install app";
    });
  });

  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    installButtons.forEach((button) => {
      button.hidden = true;
    });
    showFeedback("CareStance is installed on this device.");
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" })
      .then(() => updateNotificationButtons())
      .catch((error) => {
        console.error("CareStance service worker could not be registered:", error);
        notificationButtons.forEach((button) => {
          button.disabled = true;
          button.textContent = "Notifications unavailable";
        });
        showFeedback("Could not enable the CareStance app on this device.", true);
      });
  } else {
    notificationButtons.forEach((button) => {
      button.disabled = true;
      button.textContent = "Notifications unavailable";
    });
  }

  updateInstallButtons();
})();
