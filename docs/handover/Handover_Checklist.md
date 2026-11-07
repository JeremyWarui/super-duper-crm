# Handover checklist

What the buyer receives with their copy of MZIGO CRM, what they must set up themselves, and
what is not part of the product. Go through it together at handover. Tick each line, and both
sides sign at the end.

Each copy is sold outright and run by the buyer's own IT person. There is no licence server,
no vendor console and no central system: once handed over, the copy is the buyer's to run
(`docs/Product_Design.md`, decision 1).

## 1. The source repository and its licence

- [ ] The full source repository, with its git history: `backend/`, `frontend/`,
      `contracts/`, `deploy/`, `tools/`, `ui-kit/` and `docs/`.
- [ ] The licence, in `LICENSE` at the root: the **MIT License**, copyright 2026 Jeremy
      Mwangi. It lets the buyer use, copy, change, merge, publish, distribute, sublicense and
      sell the software, provided the copyright and permission notice stay in every copy. The
      software comes "as is", without warranty, under that licence; the warranty in section 6
      below is the separate promise made at handover.
- [ ] The locked dependency versions: `backend/uv.lock` and `frontend/package-lock.json`.
- [ ] The buyer can build it: the root `Dockerfile` builds the app image (the website and the
      API) from the repository alone.

## 2. The self-host package

In `deploy/` (see `deploy/README.md`):

- [ ] `docker-compose.yml`: the database (`postgres:17`), a one-off `migrate` step, the `app`,
      the nightly `backup` and `caddy` serving HTTPS. Every image is pinned to a digest.
- [ ] `.env.example`: every setting the app reads, with the required ones at the top
      (`DOMAIN`, `ACME_EMAIL`, `PUBLIC_URL`, `SECRET_KEY` and `DB_PASSWORD`).
- [ ] `caddy/Caddyfile`: HTTPS for `DOMAIN`, with certificates renewed automatically.
- [ ] `nightly-backup.sh`: runs `campaign-crm backup` once a day at `BACKUP_HOUR_UTC`.
- [ ] The copy is installed on the buyer's server and answers at `https://DOMAIN`.

## 3. The guides

In `docs/handover/`:

- [ ] `IT_Operations.md`: install, first-run setup, backup and restore, moving server,
      certificates, operating-system updates, imports, adding the outside-service keys,
      troubleshooting.
- [ ] `Admin_Guide.md`: running the party office or the aspirant workspace: settings, website,
      team, exports.
- [ ] `User_Guides/`: one guide per role.
- [ ] `Developer_Guide.md`: for a developer taking over the code: layout, running it, both
      test lanes, migrations, the outside-service adapters.
- [ ] `samples/`: `boundaries.csv` and `register.csv`, sample reference-data imports covering
      Lamu County, for trying the imports safely.
- [ ] `docs/SYSTEM.md`, `docs/Product_Design.md` and the design documents in `docs/`, which
      say what the system does and why.

## 4. The first superuser and the setup token

A new copy opens on its setup page and nothing else works until setup is done. The buyer's IT
person does this, not the vendor, so only the buyer ever holds the superuser login.

- [ ] The IT person prints a setup token on the server:

      ```bash
      cd deploy
      docker compose exec app campaign-crm seed
      docker compose exec app campaign-crm setup-token
      ```

      It works once and expires after 24 hours; printing a new one stops any earlier unspent
      token working.
- [ ] They open `https://DOMAIN/setup`, paste the token and complete the six steps: the
      organisation type (party or aspirant, **fixed for good**), the name, logo and colours,
      contacts and privacy notice, the first superuser, and then the aspirant's seat and
      candidate login, or optionally the party workspace and its Workspace Manager.
- [ ] The first superuser signs in at `https://DOMAIN/signin` with their email and password.
- [ ] The superuser's email and password are kept by the buyer, in the buyer's own password
      store. The vendor does not keep a copy.
- [ ] If the superuser is ever locked out, the IT person can set a new password on the server
      with `campaign-crm reset-password`.

## 5. Outside-service accounts the buyer opens

Each service runs in a practice mode (nothing sent, no money moved) until its keys are added
to `deploy/.env`. The accounts are opened **in the buyer's name, by the buyer**, and the keys
never pass through the vendor. After adding keys, restart the app and press the test button
on the console's Health tab.

| Service | What it is for | Account | Settings in `deploy/.env` |
|---|---|---|---|
| Email (any SMTP server) | Invite links, password reset links, test emails | An SMTP sending service or mail server, with a sending address on the buyer's domain | `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` and `SMTP_FROM` |
| Africa's Talking | Texts to supporters, members and volunteers; delivery reports and STOP replies | An Africa's Talking account with bulk SMS, and a sender ID if wanted | `SMS_PROVIDER=africastalking`, `AT_USERNAME`, `AT_API_KEY` and `AT_SENDER_ID`, `SMS_CALLBACK_SECRET`; the callback addresses set in its dashboard |
| Paystack (Kenya) | M-Pesa payouts to mobilizers and agents for done assignments | A Paystack Kenya account with transfers enabled, and money added to its balance | `PAYOUT_PROVIDER=paystack`, `PAYSTACK_SECRET_KEY` and `PAYSTACK_WEBHOOK_SECRET`; the webhook pointed at `/api/payments/paystack/webhook/` |
| Google Cloud (optional) | "Sign in with Google" for existing logins | A Google Cloud project with an OAuth "Web application" client; redirect URI exactly `PUBLIC_URL` + `/api/auth/google/callback/` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |

- [ ] Email account opened, keys added, test email received.
- [ ] Africa's Talking account opened, keys added, callbacks set, test text received.
- [ ] Paystack account opened, keys added, webhook set, balance funded. (The KES 1 practice
      payout on the Health tab runs only in practice mode; the first real payment is the
      live test.)
- [ ] Google sign-in set up, or left off on purpose: ____________________

Until a service is set up, the copy works without it: email links are written to the app's
log, texts are recorded but not sent, and payments are marked paid under a `PRACTICE-`
reference.

## 6. Backups, proven by a test restore

A backup only counts once it has been restored. Do this at handover, on the buyer's server.

- [ ] The nightly `backup` service is running and the console's Health tab shows the last
      backup.
- [ ] A backup is taken by hand:

      ```bash
      docker compose exec app campaign-crm backup
      ```

- [ ] The archives in the `backups` volume are copied off the server, to a place the buyer
      controls.
- [ ] A test restore is run from one of those archives (`campaign-crm restore <file>
      --yes-erase-current-data`, as `IT_Operations.md` describes), on a spare server or before
      real data is entered, and the restored copy signs in and shows the expected data.
- [ ] Date of the test restore: ____________ Archive restored: ______________________

## 7. Warranty

- [ ] **3 months of defect fixes** from the handover date (`docs/Product_Design.md`, decision
      9). A defect is the software not doing what `docs/SYSTEM.md` and the guides say it does.
      New features, changes of scope, and problems caused by the server, its hosting, or
      changes the buyer makes to the code are not defects.
- [ ] After the 3 months, maintenance is the buyer's: their IT person or any developer, using
      `docs/handover/Developer_Guide.md`.
- [ ] Handover date: ____________ Warranty ends: ____________
- [ ] How defects are reported during the warranty: ______________________________

## 8. Out of scope

These were drawn in the mockups or discussed and are **not** in the product
(`docs/Product_Design.md`, section 6, and decisions 22 to 31 of section 0):

- [ ] **Party primaries voting**: online, USSD and in-person voting, the control room,
      sealed counts, tallies, receipt codes, appeals, party lists and IEBC nomination
      submission. Nominations end at an approved aspirant; primary results are entered as
      website content.
- [ ] **Election-day features**: polling-day check-in, polling-station imports and result
      forms. Agents are recruited, vetted, trained and assigned to a registration centre
      during the campaign; the product does nothing on polling day itself.
- [ ] **Hosting and subscriptions**: renting workspaces, plans, a subscription ledger, grace,
      read-only and locked states. A party's nominee workspaces are free.
- [ ] **Money handling beyond payouts**: online payments in (subscriptions, contributions,
      fees), campaign spending, contributions and declarations, a party finance page, party
      payouts other than to mobilizers and agents, a rate card and a payment threshold, and
      the Finance role and Finance Officer office. The Contribute page shows payment
      instructions and records nothing.
- [ ] **SMS sign-in codes and SMS reset codes**, and password resets by the Candidate or
      Manager. On the website only the superuser resets someone else's password, by an emailed link;
      the IT person can set one from the server as a last resort.
- [ ] **A vendor console or licence server**, and **multi-party hosting**: one copy serves one
      party or one aspirant.
- [ ] **An offline mobilizer app** with full sync; drafts are kept on the device only.
- [ ] **Maps**: areas are lists and tables.
- [ ] **WhatsApp messaging** from the system (sharing a link from one's own phone stays).
- [ ] **USSD** for any purpose.
- [ ] **Two languages side by side**: website content is in the one language the buyer writes
      it in.
- [ ] **Party event management**: RSVPs, invites and door check-in. Party events are website
      posts.
- [ ] **Sub-branches** below county.
- [ ] **Appeals and nominated-seat party lists.**

## 9. Known gaps

- [ ] The buyer has been shown the known gaps listed under `## Known gaps` in
      `backend/README.md` and the `### Known gaps` lists in its sections.

## Sign-off

By signing, the buyer confirms they received everything ticked above, and the vendor confirms
it was handed over as described.

**Buyer**

Organisation: ______________________________________

Name: ______________________________________

Role: ______________________________________

Signature: ______________________________ Date: ____________

**Buyer's IT person**

Name: ______________________________________

Signature: ______________________________ Date: ____________

**Vendor**

Name: ______________________________________

Signature: ______________________________ Date: ____________
