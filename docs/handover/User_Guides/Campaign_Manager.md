# Campaign Manager guide

You run the campaign day to day. You see the whole campaign, build the team, plan events,
schedule payments for the candidate to approve, and approve the payments coordinators
schedule. The candidate adds you; only the candidate can replace you.

If you run the party's own coordination workspace, read
[Workspace_Manager.md](Workspace_Manager.md) as well: a few things differ there.

## Signing in

1. Open the sign-in page (`/signin`).
2. Type your **Email** and **Password**, then press **Sign in**.
3. If the installation has Google set up, you can press **Sign in with Google** instead. It
   works only when your Google account uses the same email as your login.

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
- **Field:** Events, Mobilizers, Agents, Assignments, Supporters, Volunteers
- **Reach out:** Messages, and **Party feed** if the party set up your workspace
- **People:** Team, Sign-ups, Personal data
- **Money:** Payments
- **Website:** Website and Settings, only on the candidate's own installation

**Your access** at the bottom of the menu shows **Campaign Manager** and "Full access to this
campaign."

## How to

### Build the team

1. Open **Team**. Press **Add coordinator** or **Add comms officer**.
2. Fill **Full name**, **Username**, **Email** and **Phone**, then press the add button. The
   person is emailed a link to choose a password. In practice mode no email is sent; see `Admin_Guide.md` section 10.
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
3. Tick **Give them a login, so they can record their own events and supporters.** to add a
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
4. **Invite** texts supporters about the event. Write the **Message**, choose who under
   **Send to**, press **Preview** to see the count, then **Send**.
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

### Text supporters

1. Open **Messages**. Under **New SMS**, pick who in **Send to**, and write the **Message**.
   The count of recipients shows below.
2. Press **Send SMS**, then the **Send to** button that names the count. **Not yet** goes
   back. **Save draft** keeps it unsent.
3. Drafts from coordinators and comms appear under **Waiting for approval**. Press **Approve
   and send**, **Decline…** or **Delete**.
4. Under **Sent**, **Delivery log** shows what happened to each number.

What you type in **New SMS** stays on this device until it is sent.

### Volunteers and personal data

1. **Volunteers** lists people who offered help on the candidate's website page. Press **Make
   active** or **Make inactive**. A withdrawn volunteer can be erased with **Erase**.
2. On **Supporters**, **Withdrawal link** and **Erase** handle a supporter's request about
   their details. **Sign-up link** shares the campaign-wide supporter sign-up.
3. **Personal data** logs data requests (**Log a request**) and lists **People who left the
   team**, who you can **Erase**.

### Website (candidate's own installation only)

1. **Website** has tabs **Candidate page**, **News**, **Homepage** and **Media**. Use **New
   post** (or slide, issue, video, document), **Edit**, **Publish** or **Unpublish**, and
   **Delete**. The candidate page saves with **Save profile**.
2. **Settings** holds the site name, colours, contacts, **How to give (shown on the Contribute
   page)** and the **Privacy notice**. Press **Save settings**.

## Who to ask for help

Press **Help** at the top: it lists the campaign's phone and email. For logins and password
resets for other people, ask the superuser (the party office, or whoever runs your
installation).

## What only the candidate does

- Add or replace the manager.
- Change what a party-hosted campaign shares (**Party feed**).
- Close the campaign. On **Personal data** you see **Only the candidate closes the
  campaign.**
