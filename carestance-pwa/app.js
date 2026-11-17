const API_BASE = "/api/v1";
const loginForm = document.querySelector("#login-form");
const loginMessage = document.querySelector("#login-message");
const signedInPanel = document.querySelector("#signed-in");
const welcomeMessage = document.querySelector("#welcome-message");
const overviewPanel = document.querySelector("#overview");
const signupNote = document.querySelector("#signup-note");
const notificationButton = document.querySelector("#notification-button");
const notificationMessage = document.querySelector("#notification-message");
const installButton = document.querySelector("#install-button");
const heroInstallButton = document.querySelector("#hero-install-button");
const installStatus = document.querySelector("#install-status");
const installHint = document.querySelector(".install-hint");
let installPrompt;

function showMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set("Content-Type", "application/json");
  const token = sessionStorage.getItem("carestanceAccessToken");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem("carestanceAccessToken");
      renderSignedOut();
    }
    throw new Error(payload.detail || "Something went wrong. Please try again.");
  }
  return payload;
}

function renderSignedOut() {
  loginForm.hidden = false;
  signedInPanel.hidden = true;
  signupNote.hidden = false;
  document.querySelector("#account-heading").textContent = "Sign in to CareStance";
}

function addOverviewItem(title, detail) {
  const item = document.createElement("div");
  item.className = "overview-item";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const description = document.createElement("span");
  description.textContent = detail;
  item.append(heading, description);
  overviewPanel.append(item);
}

async function renderSignedIn(user) {
  loginForm.hidden = true;
  signedInPanel.hidden = false;
  signupNote.hidden = true;
  document.querySelector("#account-heading").textContent = "Your CareStance";
  welcomeMessage.textContent = `Welcome back, ${user.full_name || user.email || "there"}.`;
  overviewPanel.replaceChildren();

  if (user.role === "student") {
    try {
      const overview = await apiRequest("/student/overview");
      const assessment = overview.assessment;
      addOverviewItem(
        "Career assessment",
        assessment.status === "completed"
          ? assessment.recommended_stream || "Your report is ready"
          : assessment.status === "in_progress"
            ? "Pick up where you left off"
            : "Start exploring your strengths"
      );
      addOverviewItem(
        "Growth profile",
        overview.growth_profile.is_ready
          ? overview.growth_profile.growth_stage_detail || overview.growth_profile.growth_stage
          : overview.growth_profile.message || "Build your profile as you explore"
      );
    } catch (error) {
      if (!sessionStorage.getItem("carestanceAccessToken")) {
        showMessage(loginMessage, error.message, true);
        return;
      }
      addOverviewItem("Career overview", "Connect to the internet to refresh your progress.");
    }
  } else {
    addOverviewItem("Your account", `${user.role || "CareStance"} account`);
    addOverviewItem("Appointments", "Open the full site to manage your sessions");
  }

  updateNotificationButton();
}

async function restoreSession() {
  const token = sessionStorage.getItem("carestanceAccessToken");
  if (!token) return;
  try {
    const user = await apiRequest("/me");
    await renderSignedIn(user);
  } catch (error) {
    if (sessionStorage.getItem("carestanceAccessToken")) {
      showMessage(loginMessage, error.message, true);
    }
  }
}

async function updateNotificationButton() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    notificationButton.disabled = true;
    notificationButton.textContent = "Notifications unavailable";
    showMessage(notificationMessage, "This browser does not support web push notifications.");
    return;
  }

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  notificationButton.textContent = subscription ? "Turn off notifications" : "Enable notifications";
}

function decodeApplicationKey(encodedKey) {
  const paddedKey = encodedKey + "=".repeat((4 - encodedKey.length % 4) % 4);
  const decoded = atob(paddedKey.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(decoded, (character) => character.charCodeAt(0));
}

async function setUpPushNotifications() {
  if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("This browser does not support web push notifications.");
  }
  if (Notification.permission === "denied") {
    throw new Error("Notifications are blocked in your browser settings.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Allow notifications in your browser to continue.");

  const keyInfo = await apiRequest("/push/public-key");
  if (!keyInfo.enabled || !keyInfo.public_key) {
    throw new Error("Push notifications are not configured on the CareStance server yet.");
  }

  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: decodeApplicationKey(keyInfo.public_key),
    });
  }
  await apiRequest("/push/subscriptions", {
    method: "POST",
    body: JSON.stringify(subscription.toJSON()),
  });
  showMessage(notificationMessage, "Notifications are on for this device.");
  await updateNotificationButton();
}

async function turnOffPushNotifications() {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    let requestError;
    try {
      await apiRequest("/push/subscriptions", {
        method: "DELETE",
        body: JSON.stringify(subscription.toJSON()),
      });
    } catch (error) {
      requestError = error;
    }
    await subscription.unsubscribe();
    if (requestError) throw requestError;
  }
  showMessage(notificationMessage, "Notifications are off for this device.");
  await updateNotificationButton();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage(loginMessage, "Signing in…");
  const formData = new FormData(loginForm);
  try {
    const result = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    sessionStorage.setItem("carestanceAccessToken", result.access_token);
    await renderSignedIn(result.user);
    showMessage(loginMessage, "");
  } catch (error) {
    showMessage(loginMessage, error.message, true);
  }
});

notificationButton.addEventListener("click", async () => {
  notificationButton.disabled = true;
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await turnOffPushNotifications();
    } else {
      await setUpPushNotifications();
    }
  } catch (error) {
    showMessage(notificationMessage, error.message, true);
  } finally {
    notificationButton.disabled = false;
  }
});

document.querySelector("#sign-out-button").addEventListener("click", async () => {
  try {
    await turnOffPushNotifications();
  } catch (error) {
    showMessage(notificationMessage, error.message, true);
  }
  sessionStorage.removeItem("carestanceAccessToken");
  renderSignedOut();
  showMessage(loginMessage, "You have been signed out.");
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  installButton.hidden = false;
  heroInstallButton.textContent = "Install CareStance";
});

async function requestInstallation() {
  if (!installPrompt) {
    installStatus.hidden = false;
    installStatus.textContent = "Use your browser menu to choose Install app or Add to Home Screen.";
    installHint.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const prompt = installPrompt;
  installPrompt = null;
  await prompt.prompt();
  const choice = await prompt.userChoice;
  installStatus.hidden = false;
  installStatus.textContent = choice.outcome === "accepted"
    ? "CareStance is being installed."
    : "Installation was cancelled. You can try again from your browser menu.";
  installButton.hidden = true;
}

installButton.addEventListener("click", requestInstallation);
heroInstallButton.addEventListener("click", requestInstallation);

window.addEventListener("appinstalled", () => {
  installButton.hidden = true;
  heroInstallButton.hidden = true;
  installPrompt = null;
  installStatus.hidden = false;
  installStatus.textContent = "CareStance is installed on this device.";
});

if (window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true) {
  installButton.hidden = true;
  heroInstallButton.hidden = true;
}

function updateOnlineStatus() {
  document.querySelector("#offline-message").hidden = navigator.onLine;
}

window.addEventListener("online", updateOnlineStatus);
window.addEventListener("offline", updateOnlineStatus);
updateOnlineStatus();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js").catch((error) => {
    console.error("CareStance service worker could not be registered:", error);
  });
}

restoreSession();
