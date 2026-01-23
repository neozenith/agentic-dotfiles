---
name: playwright-mcp-auth
description: Inject captured OAuth/Firebase auth state into Playwright MCP browser sessions. Use when testing authenticated pages with Playwright MCP, debugging Firebase auth issues, or setting up E2E auth capture workflows for Google OAuth.
---

# Playwright MCP Authentication Injection

Inject captured OAuth/Firebase auth state into Playwright MCP browser sessions for authenticated testing and debugging.

## The Problem

Google OAuth blocks automated browsers with "This browser or app may not be secure" errors. Playwright's Chromium cannot complete Google sign-in flows. The solution: capture auth from a real Chrome browser, then inject it into Playwright.

## Quick Reference: Injecting Auth into Playwright MCP

When you need to test an authenticated page using Playwright MCP tools:

### 1. Read the Captured Auth File

```bash
# Auth is stored at:
frontend/playwright/.auth/firebase-auth.json
```

### 2. Navigate and Inject

```javascript
// Step 1: Navigate to the app
browser_navigate → http://localhost:5173

// Step 2: Inject localStorage auth
browser_evaluate → (async () => {
  // Firebase auth (the key includes your Firebase API key)
  localStorage.setItem(
    'firebase:authUser:YOUR_FIREBASE_API_KEY:[DEFAULT]',
    '{"uid":"...","email":"...","displayName":"...","stsTokenManager":{...}}'
  );

  // Google OAuth access token (for API calls)
  sessionStorage.setItem('google_access_token', 'ya29.a0...');
})()

// Step 3: Reload to apply auth
browser_navigate → http://localhost:5173

// Step 4: Wait for auth to initialize
browser_wait_for → 2 seconds

// Step 5: Now navigate to protected pages
browser_navigate → http://localhost:5173/dashboard
```

### Simplified Injection Script

For Firebase with `browserLocalPersistence`, use this pattern:

```javascript
// Read the JSON from frontend/playwright/.auth/firebase-auth.json
// Then inject:

browser_evaluate → (async () => {
  // Inject all localStorage entries
  const localStorageData = /* paste localStorage object from firebase-auth.json */;
  for (const [key, value] of Object.entries(localStorageData)) {
    localStorage.setItem(key, value);
  }

  // Inject sessionStorage (Google OAuth token)
  const sessionStorageData = /* paste sessionStorage object from firebase-auth.json */;
  for (const [key, value] of Object.entries(sessionStorageData)) {
    sessionStorage.setItem(key, value);
  }
})()
```

---

## Full Setup Guide (For New Projects)

### Prerequisites

- Node.js project with Playwright installed
- Firebase Authentication configured
- Real Chrome browser available

### Step 1: Install Dependencies

```json
// package.json devDependencies
{
  "@playwright/test": "^1.57.0",
  "tsx": "^4.21.0"
}
```

```json
// package.json scripts
{
  "e2e": "playwright test --project=chromium",
  "e2e:capture": "npx tsx e2e/capture-from-chrome.ts",
  "e2e:ui": "playwright test --project=chromium --ui",
  "e2e:headed": "playwright test --project=chromium --headed"
}
```

### Step 2: Add Makefile Targets

```makefile
e2e:
	npm --prefix frontend run e2e

e2e-chrome:
	@echo "Launching real Chrome with remote debugging..."
	@echo "1. Sign in with Google in Chrome"
	@echo "2. Navigate to http://localhost:5173 and verify /dashboard"
	@echo "3. Run 'make e2e-capture' in another terminal"
	@if [ "$$(uname)" = "Darwin" ]; then \
		"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
			--remote-debugging-port=9222 \
			--user-data-dir=/tmp/playwright-chrome-profile \
			"http://localhost:5173"; \
	else \
		google-chrome \
			--remote-debugging-port=9222 \
			--user-data-dir=/tmp/playwright-chrome-profile \
			"http://localhost:5173"; \
	fi

e2e-capture:
	@echo "Capturing auth state from Chrome..."
	npm --prefix frontend run e2e:capture
```

### Step 3: Create Auth Capture Script

Create `e2e/capture-from-chrome.ts`:

```typescript
/**
 * Capture Firebase auth state from a real Chrome browser via CDP.
 */
import { chromium } from '@playwright/test';
import type { CDPSession } from '@playwright/test';
import * as fs from 'fs';

const AUTH_DIR = 'playwright/.auth';
const FIREBASE_AUTH_FILE = `${AUTH_DIR}/firebase-auth.json`;
const CDP_URL = 'http://localhost:9222';

async function readLocalStorageViaCDP(cdp: CDPSession): Promise<Record<string, string>> {
  const { entries } = await cdp.send('DOMStorage.getDOMStorageItems', {
    storageId: {
      securityOrigin: 'http://localhost:5173',
      isLocalStorage: true,
    },
  });
  const data: Record<string, string> = {};
  for (const [key, value] of entries) {
    data[key] = value;
  }
  return data;
}

async function readSessionStorageViaCDP(cdp: CDPSession): Promise<Record<string, string>> {
  const { entries } = await cdp.send('DOMStorage.getDOMStorageItems', {
    storageId: {
      securityOrigin: 'http://localhost:5173',
      isLocalStorage: false,
    },
  });
  const data: Record<string, string> = {};
  for (const [key, value] of entries) {
    data[key] = value;
  }
  return data;
}

async function captureAuthState() {
  console.log('Connecting to Chrome at', CDP_URL);

  const browser = await chromium.connectOverCDP(CDP_URL);
  const contexts = browser.contexts();
  const context = contexts[0];
  const pages = context.pages();
  const page = pages.find((p) => p.url().includes('localhost:5173')) ?? pages[0];

  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }

  const cdp = await context.newCDPSession(page);
  await cdp.send('DOMStorage.enable');

  const localStorageData = await readLocalStorageViaCDP(cdp);
  const sessionStorageData = await readSessionStorageViaCDP(cdp);

  const authData = {
    localStorage: localStorageData,
    sessionStorage: sessionStorageData,
    capturedAt: new Date().toISOString(),
    capturedFrom: page.url(),
  };

  fs.writeFileSync(FIREBASE_AUTH_FILE, JSON.stringify(authData, null, 2));
  console.log(`✓ Auth saved to: ${FIREBASE_AUTH_FILE}`);

  await browser.close();
}

void captureAuthState();
```

### Step 4: Create Test Fixtures

Create `e2e/fixtures.ts`:

```typescript
import { test as base, expect } from '@playwright/test';
import * as fs from 'fs';

const FIREBASE_AUTH_FILE = 'playwright/.auth/firebase-auth.json';

interface FirebaseAuthData {
  localStorage: Record<string, string>;
  sessionStorage?: Record<string, string>;
  capturedAt: string;
}

function loadFirebaseAuth(): FirebaseAuthData | null {
  if (!fs.existsSync(FIREBASE_AUTH_FILE)) return null;
  return JSON.parse(fs.readFileSync(FIREBASE_AUTH_FILE, 'utf-8'));
}

function generateAuthInjectionScript(authData: FirebaseAuthData): string {
  return `
    (async () => {
      const localStorageData = ${JSON.stringify(authData.localStorage)};
      for (const [key, value] of Object.entries(localStorageData)) {
        localStorage.setItem(key, value);
      }

      const sessionStorageData = ${JSON.stringify(authData.sessionStorage ?? {})};
      for (const [key, value] of Object.entries(sessionStorageData)) {
        sessionStorage.setItem(key, value);
      }
    })();
  `;
}

export const test = base.extend<{ firebaseAuth: undefined }>({
  firebaseAuth: [
    async ({ page }, use) => {
      const authData = loadFirebaseAuth();
      if (!authData) {
        throw new Error('Run "make e2e-chrome" then "make e2e-capture" first.');
      }
      await page.addInitScript(generateAuthInjectionScript(authData));
      await use(undefined);
    },
    { auto: true },
  ],
});

export { expect };
```

### Step 5: Write Tests

```typescript
// e2e/auth.spec.ts
import { test, expect } from './fixtures';

test('authenticated user sees dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});
```

---

## Capture Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  Terminal 1                   Terminal 2                    │
├─────────────────────────────────────────────────────────────┤
│  1. make dev                                                │
│     (start dev server)                                      │
│                                                             │
│  2. make e2e-chrome                                         │
│     (launches Chrome with                                   │
│      --remote-debugging-port=9222)                          │
│                                                             │
│  3. Sign in with Google                                     │
│     in the Chrome window                                    │
│                                                             │
│  4. Verify you're on                 5. make e2e-capture    │
│     /dashboard                          (extracts auth      │
│                                          via CDP)           │
│                                                             │
│                                      6. make e2e            │
│                                         (run tests)         │
└─────────────────────────────────────────────────────────────┘
```

---

## Auth File Structure

The captured `firebase-auth.json` contains:

```json
{
  "localStorage": {
    "firebase:authUser:API_KEY:[DEFAULT]": "{...user object with tokens...}"
  },
  "sessionStorage": {
    "google_access_token": "ya29.a0..."
  },
  "capturedAt": "2026-01-23T02:15:55.812Z",
  "capturedFrom": "http://localhost:5173/dashboard"
}
```

**Key fields in the Firebase auth user object:**
- `uid` - Firebase user ID
- `email` - User email
- `displayName` - User display name
- `stsTokenManager.accessToken` - Firebase ID token (for Firebase services)
- `stsTokenManager.refreshToken` - Refresh token

**Session storage:**
- `google_access_token` - OAuth token for Google APIs (Sheets, Calendar, Drive)

---

## Troubleshooting

### "ECONNREFUSED" when capturing
Chrome isn't running with remote debugging. Run `make e2e-chrome` first.

### Auth not working after injection
1. Check token expiration - tokens expire after ~1 hour
2. Re-capture: `make e2e-chrome` → sign in → `make e2e-capture`

### "This browser or app may not be secure"
This is why we use real Chrome. Never try to automate Google sign-in directly.

### Tests pass but Playwright MCP shows unauthenticated
You need to inject auth BEFORE the page loads Firebase. Either:
1. Inject at `about:blank` first, then navigate
2. Use `browser_evaluate` immediately after `browser_navigate`

---

## Files to Add to .gitignore

```gitignore
# E2E auth state (contains tokens - DO NOT COMMIT)
playwright/.auth/
```
