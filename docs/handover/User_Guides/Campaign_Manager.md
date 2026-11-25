# Campaign Manager guide

You run the campaign day to day. You see the whole campaign, build the team, plan events,
schedule payments for the candidate to approve, and approve the payments coordinators
schedule. The candidate adds you; only the candidate can replace you.

## Signing in

1. Open the sign-in page (`/signin`).
2. Type your **Email** and **Password**, then press **Sign in**.

Your first sign-in comes from an email link. Open it, fill **New password** and **The same
password again** (at least 8 characters), then press **Save and sign in**. That link works for
72 hours.

### Forgot your password

1. On the sign-in page press **Forgot your password?**
2. Type your **Email** and press **Send the link**. The link works for an hour.
3. Choose a new password and press **Save and sign in**.
4. If you see **This link no longer works**, press **Send a new link**.

You cannot reset a team member's password. Tell them to use **Forgot your password?**, or ask
the superuser to send them a reset link.

### Signing out

Press your name at the top right, then **Sign out**.

## What you see

- **Plan:** Overview, Strategy, Targets, Wards
- **Field:** Events, Mobilizers, Agents, Assignments, Contacts, Volunteers
- **Reach out:** Messages, Calls
- **People:** Team, Sign-ups, Personal data
- **Money:** Payments, Contributions
- **Website:** Website and Settings

**Your access** at the bottom of the menu shows **Campaign Manager** and "Full access to this
campaign."

## How to

### Build the team

1. Open **Team**. Press **Add coordinator** or **Add comms officer**.
2. Fill **Full name**, **Username**, **Email** and **Phone**, then press the add button. The
   person is emailed a link to choose a password. In practice mode no email is sent; see `Admin_Guide.md` section 9.
3. For each coordinator press **Area**, tick their wards (or centres), and press **Save**.
   A coordinator sees nothing outside their area.

### Approve mobilizers and agents who signed up

1. Open **Sign-ups**. Share the **Team sign-up link** with **Copy link**, or show the QR code.
2. Under **Waiting**, press **Approve** or **Reject**. A rejection needs a reason; press
   **Reject with this reason**.
3. **Replace link** stops the old link and QR code working.

### Add a mobilizer yourself

1. Open **Mobilizers** (or **Overview**) and press **Add mobilizer**.
2. Fill **Full name** and **Phone**, and pick the **Ward** (or **Registration centre**). You
   can leave it as **No ward yet**.
3. Tick **Give them a login, so they can record their own events and contacts.** to add a
   **Username** and **Email**.
4. Press **Save mobilizer**. Use **Edit** on a row to change it later.
5. **Coverage** at the top names the wards nobody covers. On **Wards**, press **Assign** or
   **Change** to move mobilizers between wards.

### Ready the polling agents

1. Open **Agents**. **Centres with no agent** lists the gaps.
2. On each row set the status (Applied, Vetted, Trained, Ready) and the **Training date**.
   Both save as soon as you change them.
3. Press **Export for letters** for a file of agents per centre, for appointment letters.

### Plan and record events

1. Open **Events** and press **Schedule event**.
2. Fill **Event title**, **Ward** (and **Registration centre** in an MCA race), **Venue** and
   **Date**, then press **Schedule event**.
3. After the event, press **Record** on its card. Fill **How many were reached / invited**
   and **How many attended**, then **Save & mark done**.
4. **Invite** texts contacts about the event. Write the **Message** with the candidate's
   name in it, choose who under **Send to** and the **Language**, press **Preview** to see
   the count, then **Send**. It joins the texting queue below.
5. **Sign-up QR** shows a code people scan to sign up as supporters. **Print** prints it.
   **Close sign-ups** stops it working.

### Give paid work and pay for it

1. Press **Assign work** (on **Assignments**, or on a mobilizer or agent row), or **Assign** on
   an event card.
2. Pick the **Kind**, **Who**, the **Ward** or **What**, and the **Amount (KES)**. Press
   **Assign**.
3. When the work is done, open **Assignments**, view **To mark done**, and press **Mark done**
   (or **Cancel**).
4. Open **Payments** and press **Schedule payment**. Pick the **Work done** and press
   **Schedule**. It then waits for the candidate.

### Approve coordinator payments

1. Open **Payments** and pick **Awaiting my approval**.
2. Press **Approve**, check the balance in **Release payment**, then **Release**. Or press
   **Approve all awaiting me**.
3. **Mark paid** records a payment made another way (type the **M-Pesa or bank reference**).
   **Decline** refuses it with a **Reason**.
4. A row stuck in **Sending** offers **Mark paid** or **Didn't go out** (then **It was not
   sent**) after you check with the payout provider.
5. **Differences with the payout provider** at the bottom compares the two records. Press
   **Check now** to run it.

You never approve a payment you scheduled yourself.

### Text contacts

1. Open **Messages**. Under **New SMS**, pick who in **Send to**, the **Language** (English or
   Kiswahili), and write the **Message**. The count of recipients shows below.
2. The text must carry the candidate's name as registered. Without it, sending is refused and
   the reason shows.
3. Press **Send SMS**, then the **Send to** button that names the count. **Not yet** goes
   back. **Save draft** keeps it unsent.
4. Drafts from coordinators and comms appear under **Waiting for approval**. Press **Approve
   and send**, **Decline…** or **Delete**.
5. Only contacts whose consent covers being texted receive it. Texts go out in batches between
   08:00 and 18:00 Nairobi time; outside those hours a run shows **Waiting for the window**.
6. **Bulk sends** shows each run with its counts (**Targeted**, **Sent**, **Delivered**,
   **Failed**, **No consent**, **Opted out**) and cost. Press **Pause**, **Resume**, or
   **Halt…** with a reason. **Consent evidence (CSV)** downloads each number with the consent
   it was texted on.
7. Under **Sent**, **Delivery log** shows what happened to each number.
8. **Send test SMS** texts one number straight away to check the gateway. It reaches only the
   campaign's own logins and contacts who agreed to be texted.

What you type in **New SMS** stays on this device until it is sent.

### Hold a team call

1. Open **Calls**. Fill **Title**, pick the **Call type** (**Video** or **Audio only (uses less
   data)**) and who to **Invite** (the whole campaign or one ward), then press **Start call**.
2. Everyone invited who has call alerts on gets an alert on their phone. Share the link or QR
   code with the rest, then press **Join now**. The call opens at `/meet/<id>`.
3. **Recent calls** lists each call, its minutes and who came.

### Volunteers and personal data

1. **Volunteers** lists people who offered help on the candidate's website page. Press **Make
   active** or **Make inactive**. A withdrawn volunteer can be erased with **Erase**.
2. On **Contacts**, **Withdrawal link** and **Erase** handle a supporter's request about
   their details. **Sign-up link** shares the campaign-wide supporter sign-up.
3. **Personal data** logs data requests (**Log a request**) and lists **People who left the
   team**, who you can **Erase**.

### Website

1. **Website** has tabs **Candidate page**, **News**, **Homepage** and **Media**. Use **New
   post** (or slide, issue, video, document), **Edit**, **Publish** or **Unpublish**, and
   **Delete**. The candidate page saves with **Save profile**.
2. **Settings** holds the site name, colours, contacts, **Other ways to give (shown on the
   Contribute page, below M-Pesa)** and the **Privacy notice**. Press **Save settings**.

## Who to ask for help

Press **Help** at the top: it lists the campaign's phone and email. For logins and password
resets for other people, ask the superuser (whoever runs your installation).

## What only the candidate does

- Add or replace the manager.
- Close the campaign. On **Personal data** you see **Only the candidate closes the
  campaign.**
