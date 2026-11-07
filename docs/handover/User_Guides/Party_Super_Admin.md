# Party Super Admin guide

You are the superuser of the party installation. You open every Party CRM page, approve the
party's text messages, publish the nominations timetable, edit the party website, and look
after logins in the console. You never join a campaign workspace.

The console's setup tasks (party settings, areas and the voter register, health, audit,
export, new campaigns) are covered in the Admin Guide. This guide covers the day-to-day work.

## Signing in

1. Open the sign-in page (`/signin`).
2. Type your **Email** and **Password**, then press **Sign in**.
3. If the installation has Google set up, you can press **Sign in with Google** instead.

You land in the **Console**.

### Forgot your password

1. On the sign-in page press **Forgot your password?**
2. Type your **Email** and press **Send the link**. The link works for an hour.
3. Choose a new password and press **Save and sign in**.

The console's **Send reset link** is greyed out on your own login; use **Forgot your
password?**.

### Signing out

Press your name at the top right, then **Sign out**.

## What you see

The Party CRM menu shows every page, in this order: **Dashboard**, **Members**,
**Volunteers**, **Data requests**, **Aspirants**, **Messages**, **Branches**, **Website**,
**Console**.

- Members, Volunteers, Data requests and Branches are the Membership Officer's pages.
- Aspirants is the Nominations Officer's page.
- Messages is the Comms Officer's page.
- Dashboard, Website and Console are yours alone.

Under your name it shows **Party super admin**. For the officer pages, see
[Membership_Officer.md](Membership_Officer.md), [Nominations_Officer.md](Nominations_Officer.md)
and [Comms_Officer.md](Comms_Officer.md). The extra things only you do are below.

## How to

### Read the party's totals

1. Open **Dashboard**.
2. Filter by **County**, **Constituency**, **Ward**, **Seat**, **Aspirant**, **From** and
   **To**. **Clear filters** resets them.
3. **Shared by campaigns** shows the counts each party-hosted campaign has chosen to share. A
   campaign that turned a share off shows **Not shared**.

### Approve a party text message

1. Open **Messages**. Drafts from the Comms Officer wait under **Waiting for approval**.
2. Read the text, the audience, the place and the recipient count.
3. Press **Approve and send**, or **Decline…**, type **Why (optional)**, and press **Decline**.
   **Keep it** goes back.

You cannot approve a draft you wrote yourself.

### Publish the nominations timetable

1. Open **Aspirants**. Under **Nominations timetable**, find the draft.
2. Press **Publish**. Members can then apply from their account. A timetable you drafted
   yourself has no **Publish** button for you.

### Set a branch's office details

1. Open **Branches** and press a county name.
2. Under **Branch office** fill **Office address**, **Office phone**, **Office email**,
   **Next meeting venue** and **Next meeting date**.
3. Tick **Show this branch on the website** to publish it.
4. Press **Save branch**.

### Edit the party website

1. Open **Website**. Pick a tab: **Homepage**, **Posts**, **Leaders**, **Candidates**,
   **About** or **Results**.
2. Press **New** followed by the item (for example **New post**, **New slide**, **New
   leader**). Fill the form and press the add button. It is saved as a draft.
3. On a row press **Publish** to put it live, **Unpublish** to take it off, **Edit** to
   change it, or **Delete** (then **Delete** again) to remove it for good.
4. Images: press **Choose file** beside an image field to upload one.
5. **Candidates** lists every approved aspirant. Press **Edit profile**, fill it from what the
   candidate sends, tick **Published on the website**, and press **Save profile**.
6. On an event post, **Aspirants at this event** names the aspirants there. Tick them and
   press **Save aspirants**.

### Look after logins (Console, Logins tab)

1. Open **Console**, then the **Logins** tab.
2. **Add a login** makes a new one. Fill **Username**, **They are a** (**Campaign manager**,
   **Mobilizer** or **Party staff (no campaign)**), **First name**, **Last name**, **Email**
   and **Phone**, then **Create the login**. The person is emailed a link to choose a password.
3. To give a staff login a party office, pick it in **Give a party office…** and press
   **Grant**. The **×** on an office takes it away.
4. A staff login holding an office must be linked to an approved party member. Type in **Link
   to a party member…** and press the member's name.
5. **Send reset link** then **Yes** emails a person a link to choose a new password. You never
   see or set their password.
6. **Disable** then **Yes** stops a login signing in. **Enable** lets it back in.

**Sign-in links** at the top of the console lists the links sent during this visit, and
whether each was emailed.

### Put someone on a campaign (Console, Campaigns tab)

1. On a campaign's card press **Add somebody**, choose the login, and press **Put them on**.
2. **Take off** then **Yes** removes someone from that campaign.

## Who to ask for help

You are the last stop for logins and passwords. For the server, backups, email and SMS keys,
ask the IT person who runs the installation.

## Notes to confirm

- The first-run setup offers **Open the party workspace now, with its first Workspace
  Manager**, and says it can be opened later from the console. No console button for opening
  the party workspace was found in the code.
