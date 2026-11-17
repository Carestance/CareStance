# CareStance PWA

This folder is a standalone, installable CareStance app. It can be deployed as its own Vercel project with the project root set to `carestance-pwa`. The app proxies `/api/*` requests to the existing CareStance Railway backend.

## What it includes

- Add-to-home-screen installation on supported browsers.
- A service worker with an offline app shell; account data and API responses are never cached.
- Existing CareStance account sign-in and a compact student overview.
- Web Push subscriptions linked to the signed-in account. Existing CareStance system and appointment notifications can appear as operating-system notifications while the app is closed.

## Deploy the PWA

1. Create a Vercel project from this repository and set its **Root Directory** to `carestance-pwa`.
2. Deploy it on HTTPS. Web app installation and push require a secure origin.
3. If the CareStance backend uses a different Railway hostname, update the API destination in `vercel.json` and the full-site links in `index.html` and `app.js`.
4. Configure the backend for Web Push (below), then redeploy the backend.

## Enable push notifications

The backend uses VAPID to authenticate with browser push services. Generate a private key from the repository root:

```powershell
python carestance-pwa\generate-vapid-keys.py
```

Add the generated PEM value to the Railway backend environment as `VAPID_PRIVATE_KEY`. Also set `VAPID_SUBJECT` to a contact address or URL, for example `mailto:support@your-domain.example`. Keep the private key secret and out of source control. The backend derives the public key for the PWA from the private key.

The backend installs `pywebpush` through the root `requirements.txt`. Startup creates the push-subscription table alongside the application's existing tables. After deployment, sign in to the PWA and choose **Enable notifications**; the browser will ask for permission. Notifications are sent for existing booking and counsellor account updates. Push support and permission prompts vary by browser and operating system; iOS/iPadOS requires the app to be added to the Home Screen.

## Local checks

Serve this folder from a local HTTPS origin (or `localhost`) to test installation and service-worker behavior. For API use, either configure a local proxy for `/api/*` or deploy the Vercel project so the rewrite to Railway is active.

When releasing updated app-shell assets, increment the cache version in `service-worker.js` and the asset query versions in `index.html` so installed copies refresh cleanly.
