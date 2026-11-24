# Admin guide

This guide is for the person who runs the system every day once the IT person has
installed it. It covers signing in, the console, the campaign workspace, the team,
payments, texts, calls and personal data. You do not need to know anything about the
code.

Words in **bold** are the exact names of pages, tabs, buttons and fields as they
appear on screen.

Installing, backups, email, SMS, calls and payout accounts are the IT person's job.
They are covered in `docs/handover/IT_Operations.md`.

---

## 1. The installation

Each installation runs one candidate's campaign for one seat: MCA, MP, Women Rep,
Senator, Governor or President. The IT person sets the seat, the area and the
candidate's login on the first-run setup screen.

| Part | Address | Who uses it |
|---|---|---|
| Public website | `/` | Visitors: the candidate's home page, news, events, volunteer sign-up, contribute and privacy pages |
| Console | `/console` | The superuser |
| Campaign workspace | `/campaign` | The candidate and the campaign team |
| Team calls | `/meet/<id>` | The campaign's own logins |

The candidate, the manager and the comms officer edit the website from the workspace
**Website** and **Settings** pages.

### Who the superuser is

The superuser is the login made on the first-run setup screen. The superuser:

- runs the console at `/console`
- is the only person who can send someone else a password reset link
- never sits on the campaign workspace, so never appears on the Team page

### Who goes where after signing in

| Login | Lands on |
|---|---|
| Superuser | The console, `/console` |
| Anyone on the campaign | The workspace, `/campaign` |

---

## 2. Signing in and passwords

### Signing in

1. Open the site and go to **Sign in** (the last link in the website menu, or `/signin`).
2. Type your **Email** and **Password**.
3. Press **Sign in**.

The eye button beside the password shows or hides what you typed.

A wrong email, a wrong password and an account that is not allowed in all get the same
answer, on purpose. One device gets 10 tries an hour.

**Sign in with Google** appears under the form only when the IT person has set Google
sign-in up. It works only for a Google account whose email already belongs to a login
here. It does not create a login.

### Forgotten password (anyone)

1. On the sign-in page, press **Forgot your password?**
2. Type the **Email** you sign in with and press **Send the link**.
3. Open the email and follow the link within one hour.
4. Type the **New password** (at least 8 characters) and **The same password again**.
5. Press **Save and sign in**.

The page gives the same answer whether or not the email has a login, so nobody can use
it to check who is registered. A new link cancels any older one. If the link has
expired the page says **This link no longer works** and offers **Send a new link**.
Choosing a new password signs the person out everywhere else.

### Resetting someone else's password (superuser only)

Nobody else can reset another person's password: not the candidate, not the manager.
The superuser never sees or sets the password; the system emails the person a link and
they choose their own. The one exception is off the website: the IT person can set a
password from the server as a last resort (IT guide section 10).

1. In the console, open the **Logins** tab.
2. Find the person. The role filters **Everyone**, **Managers**, **Candidates** and
   **Mobilizers** narrow the list.
3. On their row press **Send reset link**, then **Yes**.
4. A **Sign-in links** box at the top shows **Link emailed**, or
   **No email: nothing sent** if the login has no email address.

The button is greyed out on your own row. For your own password, use
**Forgot your password?** on the sign-in page. Every reset is recorded in the audit
trail.

### Invite links for new logins

When anyone adds a new login (the superuser in the console, the candidate or manager
on the Team page, or an approval on the Sign-ups page), the system emails the person
an invite link. It works for 72 hours. They open it, see **Choose your password**, set
it and are signed in.

If the person has no email, nothing is sent. Ask the IT person to add one with
`campaign-crm set-email` (IT guide section 10), then send a reset link from the console.

### Alerts

After signing in on a phone, everyone on the campaign sees **Enable alerts**. Once it is
on, the phone gets an alert when the team starts a call and for each new notice:
announcements, target changes, team sign-ups and payments waiting for them. On an iPhone it works only from
the Home Screen app: tap Share, then **Add to Home Screen**, open the app from there,
and then enable alerts (iOS 16.4 or later). **Not now** hides the offer on that phone.

---

## 3. The console (`/console`)

Only the superuser sees the console. The top of the page shows totals: **Campaigns**,
**Logins**, **Places held**, **Targets**, **Mobilizers**, **Events** and
**Contacts**. A red line warns about a campaign with nobody on it, because nobody
can see such a campaign.

The console has seven tabs.

### Campaigns

The campaign has a card with its counts and its people. Setup made it; the console
makes no other.

- **Rename** changes the campaign's name.
- **Delete campaign** removes the campaign with its targets, mobilizers, events,
  contacts and the logins of everyone on it. It asks first. It cannot be undone.
- **Take off** removes one person from the campaign. It asks first.
- **Add somebody** puts an existing login with no campaign onto this one: pick it in
  **Choose a login…** and press **Put them on**.

### Logins

Every login on the installation.

- **Add a login** opens **A new login**. Fill **Username**, **They are a** (Campaign
  manager or Mobilizer), **First name**, **Last name**, **Email**, **Phone**, and for a
  mobilizer the **Campaign** and **Ward** (or **Centre** in an MCA race). Press
  **Create the login**. An email address is required.
- **Send reset link** emails a password reset link (see section 2).
- **Disable** stops a login from signing in and signs it out. **Enable** turns it
  back on.
- **change** next to a login's email opens a box: type the new address and press
  **Save email**. The login signs in with the new address from then on, and its links go
  there. Two logins cannot share an email.

Coordinators and comms officers are not added here. The candidate or manager adds them
from the workspace Team page (section 5).

### Site settings

The website's settings. See section 4.

### Areas and register

Loads the official boundary file (**Boundaries**) and the voter register
(**Voter register**) from CSV files.

1. Choose the **CSV file**.
2. Press **Check file**. This reports every change and writes nothing.
3. If the report looks right, press **Import boundaries** or **Import voter register**.

One bad row stops the whole import, so nothing is half done. **Recent imports** lists
past imports.

### Health

- **Installation**: version, database, migration and free space.
- **Outside services**: each service shows **Configured** or **Not configured**.
  Anything not configured runs in practice mode and sends nothing.
- **Send a test email** (to your own login's email), **Send a test SMS** and **Make a
  practice payout** (KES 1, practice mode only).
- **Sign-in**: whether Google sign-in is on, and **Check Google sign-in**.
- **Backups**: the last backup and a list of recent ones.

If **Migration** or **Backups** shows a warning, tell the IT person.

### Audit

A read-only list of who did what and when. Filter by **Action**, **Who**, **From** and
**To**. Every reset link, export, payment decision, text approval, erasure and sign-up
decision lands here.

### Export

**Export everything** downloads the whole installation's data as one zip file (every
table as JSON and CSV, with a list of what is inside). Press **Download export**.

- Only the superuser can export.
- Each export is recorded in the audit trail.
- Passwords and sign-in links are left out. The file holds personal data: keep it
  somewhere safe and delete copies you no longer need.

---

## 4. Settings and the website

### Site settings

Two places hold the same settings: the console **Site settings** tab (button **Save the
site settings**), and the workspace **Settings** page for the candidate, manager and
comms officer (button **Save settings**).

| Field | What it is |
|---|---|
| **Name** | The name across the site |
| **Short name (3 letters or fewer go on the logo tile)** | Letters used where there is no logo |
| **Logo address (https://)** | A web address of the logo image |
| **Contact email**, **Contact phone**, **Address** | Shown in the footer and contact spots |
| **Primary colour** | Buttons and links; white text sits on it |
| **Secondary colour** | Highlights; dark text sits on it |
| **About (shown on the About page)** | About text |
| **How to give (shown on the Contribute page)** | Payment instructions in words |
| **M-Pesa Paybill number**, **Paybill account number**, **M-Pesa Till number** | What the Contribute page offers to pay by code. Give a Paybill or a Till, not both. |
| **Privacy notice** | The full notice on the Privacy page |
| **Privacy notice version** | Raise it each time you change the notice |

The console form also has **Slogan**, **About page headline**, **Manifesto address
(https://)**, **Manifesto text** and **Social links** (**Add a link**).

**The colour rule.** Colours are written like `#0B5D3B`. The system refuses a colour
that would make text hard to read:

- the primary colour must be dark enough for white text on it, or you see "The
  primary colour is too light for white text; pick a darker one."
- the secondary colour must be light enough for dark text on it, or you see "The
  secondary colour is too dark for ink text; pick a lighter one."

Both use the standard 4.5 to 1 contrast level. If a colour is refused, pick a darker
(primary) or lighter (secondary) shade of the same colour.

**Logo and links** must start with `http://` or `https://`.

### Editing the website

The workspace **Website** page has the tabs **Candidate page** (the homepage profile),
**News**, **Homepage** (carousel slides and agenda issues) and **Media** (videos and
documents).

1. Open the tab and press **New** followed by the item, for example **New post** or
   **New slide**.
2. Fill the fields. Images can be chosen as a file (**Choose file**) or given as an
   `https://` address.
3. Press **Add** followed by the item (for example **Add post**). New items are saved
   as a draft: "Saved as a draft until you publish it."
4. Press **Publish** on the row to put it on the public site. **Unpublish** takes it
   off again. **Edit** changes it.
5. **Delete** removes it from the site at once and cannot be undone. It asks first.

The carousel holds up to 5 slides, turning every 6 seconds. When it is full, delete a
slide before adding another. **Order** decides the order: lower numbers come first.

---

## 5. The team

### The six workspace roles

| Role (on screen) | What they do |
|---|---|
| **Candidate** | Owns the campaign. Everything the manager can do, plus adding or replacing the manager and closing the campaign. Never schedules payments. |
| **Campaign Manager** | Runs the day to day across the whole campaign: targets, team, field work, payments, texts, calls, personal data. |
| **Coordinator** | Works only the wards (or centres) they are given. Sees and works mobilizers, agents, contacts, events, assignments and payments in that area, approves sign-ups there, drafts texts, starts ward calls, schedules payments. Never sees ID numbers. |
| **Comms officer** | Events (read only), drafts texts, starts calls, edits the website and settings. |
| **Mobilizer** | Works one ward (or one centre in an MCA race): their events, adding contacts, the contacts they added (no one else's), their payments. |
| **Agent** | A polling agent being readied for one registration centre: their centre, their events, their payments. |

What each role may do, in detail ("area" means only inside the coordinator's area,
"own" means only their own records):

| Action | Candidate | Manager | Coordinator | Comms | Mobilizer | Agent |
|---|---|---|---|---|---|---|
| Read strategy | yes | yes | area | no | no | no |
| Read targets | yes | yes | area | no | own | no |
| Refresh targets | yes | yes | no | no | no | no |
| Add or replace the manager | yes | no | no | no | no | no |
| Add coordinators and comms | yes | yes | no | no | no | no |
| Approve mobilizer and agent sign-ups | yes | yes | area | no | no | no |
| See ID numbers | yes | yes | no | no | own | own |
| Change mobilizers | yes | yes | area | no | no | no |
| Read agents / change agents | yes / yes | yes / yes | area / area | no | no | own / no |
| Contacts (read and write) | yes | yes | area | no | own | no |
| Read events | yes | yes | area | yes | own | own |
| Change events | yes | yes | area | no | own | no |
| Assign work and mark it done | yes | yes | area | no | no | no |
| Read payments | yes | yes | area | no | own | own |
| Schedule payments | no | yes | area | no | no | no |
| Approve payments | see section 6 | | | | | |
| Contributions | yes | yes | no | no | no | no |
| Volunteers | yes | yes | area | no | no | no |
| Draft texts | yes | yes | area | yes | no | no |
| Send texts | yes | yes | no | no | no | no |
| Start calls | yes | yes | area | yes | no | no |
| Join calls | yes | yes | yes | yes | yes | yes |
| Edit the website | yes | yes | no | yes | no | no |
| Export | yes | yes | no | no | no | no |
| Personal data requests and erasure | yes | yes | no | no | no | no |
| Close the campaign | yes | no | no | no | no | no |

Each role's menu shows only what it may use. The candidate and manager see **Team**,
**Sign-ups** and **Personal data** under People; a coordinator sees only **Sign-ups**.

### Add a coordinator

Done by the candidate or the manager.

1. Open the workspace and go to **Team** (under People in the menu).
2. Press **Add coordinator**.
3. Fill **Full name**, **Username** (at least 3 characters) and **Email**, and
   **Phone** if you have it. The email is required: it is how they sign in and where the
   invite goes.
4. Press **Add coordinator**.
5. The box **Coordinator added** says "We emailed *username* a link to choose their
   password." Press **Done**. In practice mode (section 9) the email is not sent: the
   link is written to the app's log, and the IT person can pass it on.
   `docker compose logs app | grep -A6 "Practice email to <their email in lower case>"`
   shows it; the link starts `https://<your domain>/invite/`.
   Or the IT person can give them a password from the server (IT guide section 10).
6. Now give them their area. A coordinator sees no wards until you do. On their row
   in the Team list, press **Area**.
7. Tick the wards (or registration centres, in an MCA race) they will work. Only
   wards that already have targets are offered.
8. Press **Save** (the button shows the count, for example **Save 3 wards**).

The coordinator gets an email titled "Your sign-in is ready". They open the link
within 72 hours, choose a password and are signed in.

If the email never arrives: check their address in the console's **Logins** tab. If it
was wrong or missing, ask the IT person to fix it with `campaign-crm set-email` (IT guide
section 10), then press **Send reset link** in the console. While the installation is in
practice mode (section 9) no email leaves the server at all.

Adding a comms officer is the same, with **Add comms officer**. Comms officers have no
area.

### Add or replace the manager

Only the candidate does this.

1. Go to **Team** and press **Add manager** (or **Replace manager** if there is one).
2. Fill **Full name**, **Username**, **Email** and **Phone**.
3. Press **Add manager** (or **Replace manager**).

There is one manager per campaign. Replacing the manager takes the old manager off the
campaign and turns their login off at once.

### Remove someone

- **Coordinator or comms officer off the campaign:** on the **Team** page the candidate
  or manager presses **Take off** on their row, then **Take off** again to confirm. Their
  login is turned off and signed out.
- **Mobilizer off a ward:** on the **Wards** page, press **Change** on the ward, then
  **Remove** followed by their name. They stay on the team with no ward.
- **Anyone off the campaign:** the superuser opens the console, **Campaigns** tab,
  finds the campaign card and presses **Take off** on the person, then **Yes**.
- **Stop someone signing in anywhere:** the superuser presses **Disable** on their
  row in the console **Logins** tab.

A person's row on the Team page shows "turned off" when their login is disabled.

### The team sign-up link (mobilizers and agents)

Mobilizers and agents sign themselves up and wait for approval.

1. Go to **Sign-ups** (under People).
2. The **Team sign-up link** card shows the link and a QR code. Press **Copy link** to
   share it, or let people scan the code.
3. The person opens it, sees **Join the campaign team**, picks Mobilizer or Agent and
   fills **First name**, **Last name**, **Phone**, **Email**, **ID number** and their
   ward (and **Registration centre** for an agent), then presses **Sign up**.
4. They now wait. They cannot sign in yet.

The candidate and manager can press **Replace link**. The old link and QR code stop
working at once; use it if a link was shared too widely.

Phone and ID number must be unique within the workspace.

### Approving sign-ups

Done by the candidate, the manager, or a coordinator for sign-ups inside their area.

1. Go to **Sign-ups**. The **Waiting** filter shows who is waiting.
2. Press **Approve** on the person, or **Reject**.
3. To reject, type a reason (at least 3 characters) and press
   **Reject with this reason**.

After approval the person's login is switched on, they join the workspace and they
are emailed an invite link. If their ward already has a mobilizer they start with no
ward; place them from the **Mobilizers** page. After rejection their login is deleted.
The filters **Approved** and **Not approved** show past decisions.

ID numbers are shown only to the candidate, the manager and the person themselves.

---

## 6. Payments

Payments go only to mobilizers and agents, and only for work that was assigned and
then marked done. No assignment, no payment.

### Step 1: assign the work

Done by the candidate, the manager, or a coordinator in their area.

1. Go to **Assignments** and press **Assign work**. (You can also press
   **Assign work** on a row of the **Mobilizers** or **Agents** page, or **Assign** on
   an event.)
2. Choose the **Kind**: **Activity (training or other)** or **Ward work** (or the
   event, when started from an event).
3. Choose **Who** (a mobilizer or agent), the **Ward** for ward work, **What** for an
   activity, and the **Amount (KES)**.
4. Press **Assign**.

### Step 2: mark it done

When the work happened, open **Assignments**, filter **To mark done**, and press
**Mark done** on the row. **Cancel** cancels work that will not happen.

### Step 3: schedule the payment

Done by a coordinator (their area) or the manager. The candidate never schedules.

1. Go to **Payments** and press **Schedule payment**.
2. Pick the item under **Work done**. Each done assignment can be paid only once.
3. Press **Schedule**.

### Step 4: approve and release

Whoever schedules a payment can never approve it. Approving releases the money.

| Scheduled by | Approved and released by |
|---|---|
| Coordinator | Manager |
| Manager | Candidate |

1. Go to **Payments** and use the filter **Awaiting my approval**.
2. Press **Approve** on one payment, or **Approve all awaiting me** for all of them.
3. The release box shows the payout balance, the payments, transfer fees and what is
   left after. Press **Release**.

Other actions on a payment:

- **Decline**: give a **Reason** and press **Decline payment**.
- **Mark paid**: when it was paid outside the system, type the
  **M-Pesa or bank reference** and press **Mark paid**.
- **Retry**: for a payment that failed (shown as **To retry**).
- **Didn't go out**: only for a payment stuck on sending when the payout provider shows
  it was not sent.

The filter **Needs attention** shows failed payments and ones stuck while sending.
Every schedule, approval and decline is recorded in the audit trail. Mobilizers and
agents see their own payments under **My payments**.

### Practice mode for payouts

Until the IT person connects a live payout account, the **Payments** page shows
**Practice mode.** "No money moves. Each released payment is marked paid under a
PRACTICE reference." Everything else works exactly as it will when live, so you can
train the team on it safely.

### Money paid in by M-Pesa

Visitors give on the website's **Contribute** page. The payment box offers:

- **Send a prompt to my phone**: an M-Pesa prompt arrives; the payer enters their PIN and the
  box says **Thank you, it is paid**. In practice mode it says "Practice mode: no money moved".
- **I paid by Paybill** (or **Till**): the box shows the number, the account and the amount;
  the payer pays on their phone and types the M-Pesa code from the confirmation text.

Set the Paybill and its account number, or a Till, in **Site settings** (console) or the
workspace **Settings** page. Give one, not both.

A code waits as **To confirm** on the workspace **Money > Contributions** page until the
candidate or the manager checks it against the M-Pesa statement. Press **Confirm** when
the code is on the statement for that amount. Otherwise press **Reject**, give the reason
and press **Reject**.

---

## 7. Messages (SMS) and calls

Texts are SMS only. Every text ends with "Reply STOP to opt out." added by the system.

### Who does what

| Who | What they can do |
|---|---|
| Comms officer, coordinator | Write a text and press **Send for approval**. A coordinator can only pick wards in their area. |
| Candidate, manager | Write and send directly (**Send SMS**, then confirm **Send to** *n* people), or **Save draft**. Approve or decline drafts from others. Run **Bulk sends** and **Send test SMS**. |

To approve a draft:

1. Go to **Messages**. Drafts sit under **Waiting for approval**.
2. Press **Approve and send**, or **Decline…**, add an optional reason under
   **Why (optional)** and press **Decline**. **Keep it** goes back.
3. **Delete** removes a draft (the person who wrote it can also delete it).

Before sending, the page counts the recipients and says how many opted out and how
many numbers are unusable. **Delivery log** on a sent message shows what the SMS
gateway reported for each number.

### The compliance queue

Every bulk text, including event invitations, goes through one queue with these rules:

- **The candidate's name.** The text must carry the candidate's name as registered.
  Without it, sending is refused with the reason, for example "The text must carry the
  candidate's name as registered: *name*."
- **Language.** Each text is marked **English** or **Kiswahili** under **Language**.
  Other languages are refused.
- **Consent.** Only contacts who ticked the separate SMS box are texted. Agreeing to have
  their details kept is not enough. Contacts without the SMS opt-in, or who opted out, are
  counted and left out.
- **Support level.** **Support levels** on **New SMS** picks who gets it. **Supporter** and
  **Undecided** are on to start; **Opposed** is off until you tap it.
- **Cost before sending.** **Send SMS** (or **Approve and send…** on a draft) shows how many
  people get it, how many SMS parts each, and the estimated cost. Nothing goes until you
  press **Send to *n* people** (or **Send now**).
- **Sending hours.** Texts go out between 08:00 and 18:00 Nairobi time, in batches. A run
  approved outside those hours shows **Waiting for the window** and the time it starts.
  When the IT person sets a campaign period, nothing is sent after it ends.

### Bulk sends

Under **Messages**, the candidate and manager see **Bulk sends**: one card per run, with
its stage (**Waiting for the window**, **Sending**, **Paused**, **Halted** or
**Completed**), the counts **Targeted**, **Sent**, **Delivered**, **Failed**, **No
consent** and **Opted out**, and the estimated and actual cost.

- **Pause** holds a run. A batch already with the gateway still lands.
- **Resume** carries on a paused run.
- **Halt…** stops a run for good. Type why under **Why halt it?** and press **Halt**.
- **Consent evidence (CSV)** downloads each number in the run with the consent it was
  texted on. Keep it with the campaign's records.

### Send test SMS

**Send test SMS** on **Messages** texts one number at once, to check the gateway. Fill
**Phone number** and **Text** and press **Send test SMS**. It goes only to the campaign's
own logins and to contacts who agreed to be texted. The log under it shows what the
gateway reported.

### Event invitations

The **Invite** button on an event opens **Invite contacts**. Write the message, pick who
under **Send to** and the **Language**, and tick **Everyone on the campaign** to reach
beyond the event's ward. Anyone who can change the event can press **Preview**; only the
candidate or manager can press **Send**. A sent invitation joins the same queue and shows
under **Bulk sends**.

### Consent and STOP

- A contact who replies STOP (or STOPALL, UNSUBSCRIBE, END, QUIT, CANCEL or ACHA)
  is opted out and never texted again by the campaign.
- Contacts also get a private withdrawal link. The candidate or manager can open it
  from the **Contacts** page with **Withdrawal link**.
- Contacts without the SMS opt-in are never texted.

### Calls

**Reach out > Calls** starts audio or video calls with the team.

1. Fill **Title**, pick the **Call type** (**Video**, or **Audio only (uses less data)**)
   and who to **Invite**: the whole campaign or one ward. A coordinator picks one of
   their wards.
2. Press **Start call**. The page says how many phones got an alert, and shows the link
   and a QR code for anyone without alerts on.
3. Press **Join now**. Everyone joins at `/meet/<id>`, signed in as a campaign login.
4. **Recent calls** lists each call: **Live** or **Ended**, the host, the minutes and who
   came. A live call has a **Join** link.

Alerts reach only phones where the person pressed **Enable alerts** (section 2).

---

## 8. Personal data

Kenya's Data Protection Act 2019 gives people the right to see, correct and erase
their details. The system keeps a log of requests and lets you erase details while
keeping the counts right.

### Data requests

On the workspace **Personal data** page (candidate and manager):

1. Press **Log a request**.
2. Choose the **Request**: **Access to their data** (due in 7 days),
   **Correction** or **Erasure** (due in 14 days).
3. Fill **Received on**, **Who asked**, **Phone or email to answer** and
   **What they asked for**. Press **Log request**.
4. When you have dealt with it, press **Answer**, write how it was answered and press
   **Mark answered**. **Reopen** opens it again.

Requests past their due date show **Overdue**.

### Erasing on request

Erasing blanks the person's name, phone and other details for good, and keeps an
empty row so totals stay right. Each erasure asks "Erase for good?" first and is
audited.

- **Contact:** **Contacts** page, **Erase** on their row (candidate, manager).
- **Campaign volunteer:** **Volunteers** page, **Erase** (candidate, manager).
- **Mobilizer or agent who left or was turned down:** **Personal data** page,
  **People who left the team**, **Erase**. This clears name, phone, email and ID
  number.

### Closing a campaign after the election

Only the candidate closes the campaign, from **Personal data**, card
**After the election**.

1. Set **Keep supporter details after closing (months)** (1 to 60; 6 by default) and
   press **Save**. This is fixed once the campaign is closed.
2. Press **Close the campaign**, then **Yes, close it**.

Closing makes the workspace read-only for everyone and stops new sign-ups. It cannot
be undone. Nothing is erased automatically. When the keeping period is over, the card
offers the candidate an **Erase** button for every contact's details; the counts stay.

### Exports

The full export (console **Export** tab) is for the superuser only and is audited
(section 3). Inside the workspace, the candidate and manager can download
**Export for letters** on the **Agents** page, a list of agents per centre for
appointment letters, and **Consent evidence (CSV)** for each bulk send. Treat every
export as personal data.

---

## 9. Practice mode and going live

Out of the box every outside service runs in practice mode, so you can demonstrate the
whole system without sending anything real:

| Service | In practice mode |
|---|---|
| Email (invites, reset links) | Nothing is sent. The email, link included, is written to the server's log. The IT person can read the link from there during a demonstration. |
| SMS | Texts are logged, not sent. The **Messages** page header says "practice mode: texts are logged, not sent", and the log shows **Practice**. |
| Payouts | No money moves. Released payments are marked paid under a PRACTICE reference. |
| Google sign-in | The button is hidden. |
| Calls and call alerts | Off until the IT person sets the call service and the alert keys. |

The console **Health** tab, **Outside services**, shows which services are live
(**Configured**) and which are not (**Not configured**).

Switching a service on (email server, SMS gateway, calls, payout account, Google
sign-in) is the IT person's job. It needs keys in the server's settings file and a
restart. See `docs/handover/IT_Operations.md`.
