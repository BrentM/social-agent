# Account Creation Guide

A reproducible process for creating isolated, purpose-built accounts across platforms. The goal is to document what works manually so it can be automated later.

---

## Strategy

Each bot or project gets its own dedicated email address. This keeps accounts isolated, makes it easy to shut one down without affecting others, and creates a clear audit trail.

**Preferred email provider: Tutanota**
- Free tier available
- Strong privacy reputation (end-to-end encrypted)
- No phone number required for basic accounts
- Supports custom domains on paid plans (useful for future scaling)
- Web: https://tuta.com

---

## Step-by-Step: New Twitter Account

### 1. Create a Tutanota email address

1. Go to https://tuta.com and click **Sign Up → Free**
2. Choose a username that reflects the bot's purpose (e.g. `adhd-tips-bot@tuta.com`)
3. Set a strong, unique password — store it in your password manager under the project name
4. Skip phone verification if prompted (Tutanota does not require it)
5. Note the account credentials:

   | Field    | Value |
   |----------|-------|
   | Email    | `<chosen address>@tuta.com` |
   | Password | _(stored in password manager)_ |
   | Created  | _(date)_ |
   | Purpose  | _(e.g. ADHD bot Twitter account)_ |

### 2. Create a Twitter/X account

1. Go to https://x.com and click **Sign up**
2. Use the Tutanota email from step 1 — do **not** use a personal email
3. Choose a display name and username that fits the account's purpose
4. Twitter may ask for a phone number — use a VOIP number (e.g. Google Voice) if required; note which number was used
5. Set profile details (bio, profile picture, header) before posting anything
6. Note the account credentials:

   | Field       | Value |
   |-------------|-------|
   | Username    | `@<handle>` |
   | Email       | _(Tutanota address from step 1)_ |
   | Phone       | _(VOIP number if used)_ |
   | Created     | _(date)_ |
   | Purpose     | _(description)_ |

---

## Checking Handle Availability on X/Twitter

Use Playwright (via `playwright-cli`) to check whether a handle is already taken before creating an account.

```bash
playwright-cli open --browser=chromium https://x.com/<handle>
playwright-cli snapshot
playwright-cli close
```

If the snapshot contains `"This account doesn't exist"`, the handle is available. If it shows a profile (page title will be `Profile / X`), the handle is taken.

---

## Account Log

Track each account pair here as they are created.

| Project      | Tutanota Email | Twitter Handle | Created    | Status  |
|--------------|----------------|----------------|------------|---------|
| ADHD Bot     | TBD            | TBD            | TBD        | Planned |

---

## Notes for Automation

When this process is automated, the key friction points to solve are:
- Tutanota account creation (API or headless browser)
- Twitter sign-up (requires CAPTCHA solving or paid API access)
- Phone number provisioning (VOIP API such as Twilio or TextVerified)
- Credential storage (secrets manager or encrypted vault)
