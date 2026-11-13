# Account verification, teacher review and password recovery

## Setup

Install dependencies and run `python -m flask --app run migrate` before deploying this version.
Migration `007_account_security.sql` adds account state, one-use token hashes and review history.
Existing accounts keep their existing roles and access; they are **not** falsely marked email-verified.
All newly registered accounts require email verification before using learning/teaching APIs.
New teacher signups receive the student role until an administrator approves their application.

Set a stable random `ZHIXING_SECRET_KEY` on every server worker. Changing this key logs everyone out.
Set `PUBLIC_BASE_URL` to the actual external origin (not a request-supplied Host header).
HTTPS origins enable Secure session cookies. Configure a trusted reverse proxy to preserve the external
scheme/host so same-origin write checks match your deployment; do not trust arbitrary forwarded headers.

## No SMTP account yet: local testing

Set `MAIL_BACKEND=file` and `PUBLIC_BASE_URL=http://127.0.0.1:5016` in a local, ignored `.env`.
Run the app on that port. Account emails are JSON files in `instance/mail-outbox/`.
Open the link from the message body in the local app. This is a local test outbox, not real email delivery.
File mode refuses non-loopback public origins. The outbox is ignored by Git and not served by Flask.
It contains credential links: restrict directory access, do not share/upload it, and delete expired test mail.
Default `MAIL_BACKEND=disabled` explains that delivery is unavailable instead of pretending to send email.
Registration still creates the account; verification can be resent from the profile when configured.

## Real SMTP

Set `MAIL_BACKEND=smtp`, `PUBLIC_BASE_URL=https://...`, `MAIL_HOST`, `MAIL_PORT`, `MAIL_FROM`,
`MAIL_USERNAME` and `MAIL_PASSWORD` via server environment variables. Use provider-specific credentials.
`MAIL_SECURITY=starttls` (normally port 587) or `ssl` (normally port 465) is required; plaintext SMTP is not supported.
SMTP transport has a 15-second timeout. Provider delivery, spam filtering and sender-domain verification
must be checked when actual SMTP credentials are available. No live SMTP delivery was tested for this PR.

## User flows

- Registration sends a verification email when delivery is available. The profile supports resending.
- Email verification links expire after 24 hours. Sending a replacement invalidates the old link.
- Forgot password is available on the login dialog. Reset links expire after 30 minutes.
- Links use a URL fragment, removed from browser history by the page, and require an explicit POST confirmation.
  GET/link-preview scanners cannot consume a token. The database stores SHA-256 token hashes, not raw links.
- Successful password changes/resets increment the account's session version and log out every previous
  session, including the current browser. The user signs in again with the new password.
- A verified student fills in teaching purpose/institution/course details in their profile.
  Administrators open account management, choose pending teacher applications, and approve or return each
  with an explanation. Approval requires a verified email and a completed application.
  Decisions are saved in `teacher_reviews`. Applicants can resubmit after rejection.
- Approval/rejection invalidates the applicant's old sessions; signing in again refreshes the role.
  Email ownership alone is not evidence of teacher identity: the administrator must check the stated context.

## Boundaries and validation

Existing pre-migration accounts remain usable but can verify their email in the profile.
Login and mail/credential endpoints have bounded per-process throttling. Multiple workers require a shared
rate limiter/gateway, and the existing AI jobs require a shared queue before multi-worker deployment.
Password-reset responses do not reveal whether an email is registered. SMTP failures are logged without
addresses, passwords or tokens; recovery returns the same generic response for known/unknown accounts.

Run `pytest tests/test_account_lifecycle.py` with `TEST_DATABASE_URL` set to a disposable PostgreSQL test
connection. Tests create a random schema and local outbox and remove the schema afterwards.
Run browser regressions with `RUN_BROWSER_TESTS=1 BROWSER_CHANNEL=chrome pytest tests/test_frontend_browser.py`.
