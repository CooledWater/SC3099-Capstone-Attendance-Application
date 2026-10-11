# PWA behavior

Run `npm run build` before `npm run start`. The build generates `public/sw-precache.js` with a unique cache name and the JavaScript/CSS files from that build. Edit `public/sw.js` for worker behavior; the generated precache list is ignored by Git. Deployment must include `public`, including this generated file, and `.next/static` alongside the Next server.

The worker registers only in production. Installation saves the public page shell, manifest, icon and build assets. It does not intercept API responses, check-in submissions, biometric files or React Server Component requests. A first successful online visit and completed installation are required before offline reopening works.

After an authenticated session fetch, the browser saves a minimal session snapshot in IndexedDB under that student's ID. The local account ID allows read-only viewing after an offline reload; it does not authenticate the student. Tokens, face frames and coordinates are not part of the snapshot. Snapshots expire after 15 minutes, and closed session deadlines are filtered out. Signing out clears all snapshots and the account marker. Old unscoped snapshots are discarded when the IndexedDB schema upgrades.

Losing connectivity shows a separate **Saved sessions** view, with an offline warning, saved time and retry button. Camera verification stops; there is no attendance submission or background queue in this view. Reconnecting restores authentication when needed and fetches current sessions. Permission errors show errors instead of saved sessions.

A waiting worker shows **Update and reload**. It is disabled while offline or during check-in. Close other SAIV windows before applying an update. Activation removes previous SAIV shell caches while leaving unrelated caches alone. Registration checks again on reconnection and when the app returns to the foreground.

PNG icons are provided at 192 × 192 and 512 × 512 for the manifest, with a 180 × 180 Apple touch icon. They are exported from `public/icon.svg`; regenerate these PNGs whenever the SVG changes. Installation controls are available before and after sign-in. When the browser offers an installation event, Install app opens its confirmation prompt. Otherwise How to install shows mobile and desktop browser instructions. Controls are hidden in standalone launches and disabled during check-in. An accepted prompt is reported as installation requested; the appinstalled event confirms completion. Real-device installation testing remains pending.

## Regression checks

From the repository root:

```sh
npm install --prefix /private/tmp/saiv-pwa-tests playwright-core fake-indexeddb react-test-renderer@18.3.1
node --test new-tests/pwa/unit.test.mjs new-tests/pwa/geolocation.test.mjs new-tests/pwa/install.test.mjs
```

For the browser checks, build the frontend and run its production server on port 13010, then:

```sh
node new-tests/pwa/browser.mjs
```

The browser checks use a new Chrome profile and mocked API responses. They cover first-visit precaching, offline reload, reconnect, permission errors, update activation, camera update blocking and offline logout. Set `PWA_TEST_URL`, `PWA_BROWSER_PATH` or `PWA_TEST_DEPENDENCIES` to override the defaults. The update test temporarily changes the generated precache version and restores it afterward; run it against an isolated local server.

Real-device camera/location behavior and installation on iOS/Android still need device testing over HTTPS.

Run `npm run typecheck` in the frontend to check both React/TypeScript and the worker. `public/jsconfig.json` uses service-worker types separately from the app DOM types; `public/sw-env.d.ts` describes the values supplied by the generated precache script. Location resets invalidate pending GPS callbacks, including when going offline or switching sessions.

Installation controls are in the signed-in Profile screen. The installation event listener stays mounted so browser prompts are retained before opening Profile. Login, registration and dashboard use the shared CCDS SVG logo. Update actions check already-completed activation and time out after 15 seconds with retry guidance rather than staying disabled indefinitely. Each production build creates a new service-worker cache version, so rebuilding can trigger an update banner for returning browsers.
