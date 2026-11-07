# User guides

One short guide per role. Each one lists what you see after you sign in and how to do the
common jobs, using the names of the pages and buttons as they appear on screen.

## Campaign workspace

People who work on one campaign. Everyone signs in at `/signin` and lands in the campaign
workspace.

| Role (as shown on screen) | Guide |
|---|---|
| Candidate | [Candidate.md](Candidate.md) |
| Campaign Manager | [Campaign_Manager.md](Campaign_Manager.md) |
| Coordinator | [Coordinator.md](Coordinator.md) |
| Comms officer | [Comms.md](Comms.md) |
| Mobilizer | [Mobilizer.md](Mobilizer.md) |
| Agent | [Agent.md](Agent.md) |

The party's own coordination workspace has no candidate. Its Campaign Manager is called the
Workspace Manager: see [Workspace_Manager.md](Workspace_Manager.md).

## Party office

Party staff logins. They never join a campaign workspace; they sign in and land in the
Party CRM.

| Office | Guide |
|---|---|
| Membership Officer | [Membership_Officer.md](Membership_Officer.md) |
| Nominations Officer | [Nominations_Officer.md](Nominations_Officer.md) |
| Comms Officer | [Comms_Officer.md](Comms_Officer.md) |
| Party Super Admin | [Party_Super_Admin.md](Party_Super_Admin.md) |

One login can hold more than one office. It then sees the pages of each office it holds.

## Party members

| Who | Guide |
|---|---|
| Party member (My membership, at `/account`) | [Party_Member.md](Party_Member.md) |

This applies to a party installation only. An aspirant's own installation has no member
accounts.

## Things every guide assumes

- Everyone signs in with **email and password**. **Sign in with Google** shows on the sign-in
  page only when the installation has set it up.
- **Forgot your password?** on the sign-in page emails you a link. The link works for an
  hour. A new login's first link (an invite) works for 72 hours.
- Only the superuser (the Party Super Admin, or whoever runs the installation) can send a
  reset link to someone else. Nobody can see another person's password, and on the website
nobody can set it. The IT person can set one from the server as a last resort.
- **Sign out** clears anything a phone has kept but not yet sent. Send your entries first.
