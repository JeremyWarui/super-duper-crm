# Workspace Manager guide (party workspace)

The party has one coordination workspace of its own. It has no candidate. The Workspace
Manager runs it, as the national coordinator, with a campaign login of role Campaign Manager.
Party staff logins never join this workspace: if you also hold a party office, you have a
second, separate login for that.

Everything in [Campaign_Manager.md](Campaign_Manager.md) applies, except what is listed here.

## Signing in

Same as every campaign login: **Email** and **Password** on `/signin`, then **Sign in**.
**Sign in with Google** shows only if the installation set it up. **Forgot your password?**
emails a link that works for an hour.

## What is different

### No candidate

- The workspace card shows the party name instead of a candidate.
- You hold the Manager column of the permission table. **Team** has **Add coordinator** and
  **Add comms officer**. There is no **Add manager** button for you.
- **Personal data** has no **After the election** section: the party workspace is not
  closed after an election.
- There is no **Party feed** and no **Website** or **Settings** in this workspace.

### Payments

- You do **not** schedule payments here. **Schedule payment** does not appear on
  **Payments**. Coordinators schedule.
- You approve every payment a coordinator schedules: **Payments**, **Awaiting my approval**,
  **Approve**, then **Release**. **Mark paid** and **Decline** work as for any manager.

### Coordinators recruit party members

Each coordinator in this workspace gets a **Recruitment** page with their own link to the
**Join the Party** form and a QR code. People who apply through it are counted to that
coordinator. Membership Officers still approve every application in the Party CRM.

## How to

### Set up the county coordinators

1. Open **Team** and press **Add coordinator**.
2. Fill **Full name**, **Username**, **Email** and **Phone**, then press **Add coordinator**.
   They are emailed a link to choose a password. In practice mode no email is sent; see `Admin_Guide.md` section 10.
3. Press **Area** on their row. Tick their wards and press **Save**.

### Approve coordinator payments

1. Open **Payments** and pick **Awaiting my approval**.
2. Press **Approve**, check the balance in **Release payment**, then **Release**.

## Who to ask for help

Press **Help** at the top of the workspace. For a login, a password reset or a change of
Workspace Manager, ask the Party Super Admin.

## Notes to confirm

- The Party Super Admin opens the party workspace and names its first Workspace Manager in
  the first-run setup (the box **Open the party workspace now, with its first Workspace
  Manager**). The setup screen says it can be opened
  later from the console, but no console button for this was found in the code. Confirm how a
  party workspace is opened after setup.
- No screen was found for replacing the Workspace Manager (**Add manager** is for a
  candidate, and this workspace has none). Confirm the route with the Party Super Admin.
- The design gives coordinators in this workspace a read-only view of the party member
  register for their area. The server supports it, but no menu item opens it yet.
