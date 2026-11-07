# IT operations guide

This guide is for the person who installs and runs the campaign platform on one Linux server.
You do not need to read any code. Every command here is typed on the server, in a terminal,
from the `deploy` folder of the package unless a step says otherwise.

Boxes marked **To confirm** are things this guide could not check before handover. Test them on
your first install and tell the supplier what you find.

Contents:

1. [What you need](#1-what-you-need)
2. [Install](#2-install)
3. [First-run setup](#3-first-run-setup)
4. [Backups](#4-backups)
5. [Restore](#5-restore)
6. [Moving to a new server](#6-moving-to-a-new-server)
7. [Updates](#7-updates)
8. [Reference data imports](#8-reference-data-imports)
9. [Switching on outside services](#9-switching-on-outside-services)
10. [Locked out](#10-locked-out)
11. [Troubleshooting](#11-troubleshooting)
12. [The hosted alternative: Fly.io and Neon](#12-the-hosted-alternative-flyio-and-neon)

---

## 1. What you need

- **One Linux server** you can reach over SSH, with `sudo`. Ubuntu LTS or Debian is the easiest.
  > **To confirm:** no minimum size has been measured. The first build compiles the website
  > and needs memory; 2 GB of RAM and 20 GB of disk is a sensible starting point.
- **Docker Engine with Compose v2.** Install it from Docker's own page for your system, for
  Ubuntu <https://docs.docker.com/engine/install/ubuntu/>. On Ubuntu the last install line is:

  ```bash
  sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  ```

  Check both are there:

  ```bash
  sudo docker run hello-world
  docker compose version
  ```

  The commands below are written without `sudo`. Either put them after `sudo`, or add your
  user to the `docker` group (`sudo usermod -aG docker $USER`, then log out and back in).
- **A domain name** (for example `crm.example.org`) whose DNS **A** record (and **AAAA**, if
  the server has IPv6) points at the server's public address. Set this up first: DNS changes
  can take a while to reach everyone.
- **Ports 80 and 443 open** to the internet, TCP, and 443 UDP as well. Open them in your cloud
  provider's firewall or security group. Keep SSH (22) open for yourself.
- **Git**, to fetch the code (`sudo apt install git`), or the package as a zip or tar file from
  the supplier.

The server runs five containers: `db` (the Postgres database), `migrate` (updates the database
layout, then stops), `app` (the website and its API), `backup` (the nightly backup) and `caddy`
(HTTPS in front of the app). Only Caddy is reachable from outside.

## 2. Install

1. Put the code on the server, for example in `/opt/campaign-crm`:

   ```bash
   sudo mkdir -p /opt/campaign-crm && sudo chown $USER /opt/campaign-crm
   git clone <the repository address the supplier gave you> /opt/campaign-crm
   cd /opt/campaign-crm/deploy
   ```

   With a zip or tar file instead, unpack it into `/opt/campaign-crm` and `cd` into its
   `deploy` folder.

2. Make your settings file from the example:

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

3. Make two long random values, one for `SECRET_KEY` and one for `DB_PASSWORD`. Run this twice
   and keep each line it prints:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Open `.env` in an editor (`nano .env`) and fill in the required lines at the top:

   | Line | What to put |
   |---|---|
   | `DOMAIN` | The web address without `https://`, for example `crm.example.org` |
   | `ACME_EMAIL` | An email address you read; the certificate authority writes to it about certificates |
   | `PUBLIC_URL` | Leave blank. Docker fills it in as `https://` plus `DOMAIN` |
   | `SECRET_KEY` | The first random value (at least 32 characters) |
   | `DB_PASSWORD` | The second random value |

   Leave every other line as it is for now. If any value contains a `$`, put it in single
   quotes, so the `$` is kept.

   > **Choose `DB_PASSWORD` once.** The database stores the password it was first started with.
   > Changing `DB_PASSWORD` later in `.env` does not change it in the database, and the app
   > then cannot connect (see [Troubleshooting](#11-troubleshooting)).

   Keep a copy of `.env` somewhere safe, away from the server. You need it to move or rebuild
   the server. Never put it in Git or email it.

5. Build and start everything:

   ```bash
   docker compose up -d --build
   ```

   The first build takes several minutes. The containers start in order: the database, then
   `migrate`, then the app, then the backup job and Caddy.

6. Check it is running:

   ```bash
   docker compose ps -a
   ```

   You want `db` and `app` showing `healthy`, `backup` and `caddy` `running`, and `migrate`
   showing `Exited (0)` (it runs once and stops; 0 means it worked). Without `-a` the stopped
   `migrate` is not listed.

7. Open `https://<your domain>/health` in a browser. An answer there means HTTPS and the app
   both work. The first visit can take up to a minute while Caddy gets the certificate.

## 3. First-run setup

A new installation sends every page to `/setup` until the setup is done.

1. **Load the map data** (counties, constituencies, wards and registration centres). An
   aspirant's setup needs it to pick the seat, and a party needs it for members and branches.
   This loads about 27,000 centres and takes a few minutes:

   ```bash
   docker compose exec app campaign-crm seed
   ```

   It prints the counts of counties, constituencies, wards and centres it loaded. Run again on
   a loaded database, it prints "Reference data is already loaded" and changes nothing.


2. **Print a setup token:**

   ```bash
   docker compose exec app campaign-crm setup-token
   ```

   It prints `Setup token, valid 24 hours and spent on use: <token>`. The token works once,
   for 24 hours. Printing a new one cancels any earlier one.

3. Open `https://<your domain>/setup`, paste the token into **Setup token** and press
   **Start setup**.

4. Go through the six steps, pressing **Next** after each (**Back** goes back):

   1. **Type.** Choose **A party** (members, branches, aspirants and the party workspace) or
      **An aspirant** (one candidate's website and campaign workspace).
      **This is fixed for good once setup finishes.** There is no switch later.
   2. **Name and colours.** The organisation's **Name**, an optional **Short name** (up to 30
      characters), an optional **Logo link** (an `https://` address of the logo image), and the
      **Primary colour** and **Secondary colour**. The page checks the colours can be read: the
      primary colour must be dark enough for white text, the secondary light enough for dark
      text.
   3. **Contacts.** **Contact email**, **Contact phone**, **Address** and the **Privacy
      notice** (shown on `/privacy` and agreed to on every sign-up form). All optional, and all
      can be changed later.
   4. **First superuser.** The first login for the console: **First name**, **Last name**,
      **Username** (3 or more characters: letters, digits, `.`, `-` or `_`), **Email**, and a
      **Password** of at least 8 characters, typed twice. The superuser signs in with this email
      and password.
   5. **Workspace.**
      - *Aspirant:* the **Campaign name**, the **Seat** (MCA, MP, Governor, Senator or Women
        Rep), the **Election date**, the area (county, then constituency, then ward, as far as
        the seat needs), and the candidate's login (first and last name, username and email).
        If the county list says "No counties loaded", go back to step 1 of this section.
      - *Party:* optionally tick **Open the party workspace now, with its first Workspace
        Manager** and give that manager's name, username and email. You can also do this later
        from the console.
   6. **Check and finish.** Read the summary and press **Finish setup**.

5. The page shows **Set up.** Press **Sign in and test** to sign in as the superuser. The
   **Outside services** list shows Email, SMS, Payouts (M-Pesa) and Google sign-in; each one
   says **Practice** until you switch it on (section 9). Press **Open the site** to see the
   public site.

6. The candidate or Workspace Manager gets a sign-in link by email. While email is still in
   practice mode nothing is sent: the whole email, link included, goes to the app's log, so pass them the link.
   `docker compose logs app | grep -A6 "Practice email to <their email in lower case>"` shows it; the link
   starts `https://<your domain>/invite/`. Or give them a password instead (section 10):

   ```bash
   docker compose exec app campaign-crm reset-password -u <their username>
   ```

From now on:

- Everyone signs in at `https://<your domain>/signin` with their **email and password**, or
  with **Sign in with Google** once Google sign-in is switched on (section 9).
- The superuser's console is at `https://<your domain>/console`. Its tabs are **Campaigns**,
  **Logins**, **Party**, **Areas and register**, **Health**, **Audit** and **Export**. This
  guide uses **Health** and **Areas and register**.

## 4. Backups

### What runs by itself

- The `backup` container runs a backup once a day at the hour set by `BACKUP_HOUR_UTC` in
  `.env` (UTC; the default `0` is 03:00 in Kenya).
- Each backup is one file named `backup-<YYYYMMDD>-<HHMMSS>.tar.gz` (UTC time). It holds the
  whole database (`database.dump`), every uploaded file (`uploads/`) and a small
  `manifest.json` with the time and version.
- Backups are kept in the Docker volume `backups`, which is the folder `/backups` inside the
  containers.
- Each run keeps the newest backup of each of the last **14 days** and of each of the last
  **8 weeks**, and deletes older ones. It only deletes files with exactly that name pattern, so
  a file you rename (for example `keep-before-election.tar.gz`) is never deleted.
- The console's **Health** tab, under **Backups**, shows **Last backup** with its time and
  status (`ok` or `failed`) and a table of recent runs with size and file path. A failed run
  shows its error there.

**Change the hour:** edit `BACKUP_HOUR_UTC` in `.env`, then `docker compose up -d`.

### A backup on demand

Take one before any update, restore or large import:

```bash
docker compose exec app campaign-crm backup
```

It prints `Backed up to /backups/backup-....tar.gz (<size> bytes).`

### Copy backups off the server every night

A backup that lives only on the server is lost with the server. Copy the folder off every
night, after the backup has run.

1. Make a folder on the server for the copies:

   ```bash
   sudo mkdir -p /srv/crm-backups && sudo chown $USER /srv/crm-backups
   ```

2. Test the copy by hand. The `/.` at the end copies the folder's contents:

   ```bash
   cd /opt/campaign-crm/deploy && docker compose cp app:/backups/. /srv/crm-backups/
   ls -l /srv/crm-backups
   ```

   To take one off the server by hand right now, copy it to another machine:

   ```bash
   scp /srv/crm-backups/<file name> you@otherhost:
   ```

3. To do this every night, add it to your user's crontab (`crontab -e`), one hour after
   the backup. Cron uses the server's own clock; check it with `date`. For a server on UTC and the default
   `BACKUP_HOUR_UTC=0`:

   ```
   0 1 * * * cd /opt/campaign-crm/deploy && docker compose cp app:/backups/. /srv/crm-backups/ && rsync -a /srv/crm-backups/ <offsite target>
   ```

   Replace `<offsite target>` with somewhere off this server: another machine
   (`backupuser@otherhost:/backups/crm/`, using an SSH key), or a cloud storage tool of your
   choice. The cron user must be able to run `docker` (see section 1).

4. `/srv/crm-backups` keeps every file ever copied. To keep it to about 60 days, add:

   ```
   0 2 * * * find /srv/crm-backups -name 'backup-*.tar.gz' -mtime +60 -delete
   ```

### Check a backup

1. See the files and their sizes:

   ```bash
   docker compose exec app ls -l /backups
   ```

   Sizes should be similar from day to day and should grow slowly. A sudden drop is worth a
   look.

2. Look inside one. You should see `database.dump`, `uploads/` and `manifest.json`:

   ```bash
   docker compose exec app tar -tzf /backups/<file name> | head
   docker compose exec app tar -xzOf /backups/<file name> manifest.json
   ```

3. The real test is a restore. Every few months, restore the newest copy onto a spare server
   (section 6) and sign in. That proves the backups work.

## 5. Restore

A restore **replaces** the database and the uploaded files with those in a backup. Anything
added after that backup was taken is lost. The command refuses to run unless you add
`--yes-erase-current-data`.

1. Take a backup of the current state first, in case you need to go back. This is the
   newest file in the list in step 2, so do not restore that one by mistake:

   ```bash
   docker compose exec app campaign-crm backup
   ```

2. Find the backup to restore:

   ```bash
   docker compose exec app ls -l /backups
   ```

   If the file is somewhere else (for example on another machine), copy it into the volume
   first. Give it a name that does not start with `backup-`, so the nightly clean-up never
   deletes it:

   ```bash
   docker compose cp ./backup-20261106-000001.tar.gz app:/backups/restore-me.tar.gz
   ```

3. Stop the app, the backup job and Caddy. Leave the database running:

   ```bash
   docker compose stop app backup caddy
   ```

   While stopped, the site does not answer. That is expected.

4. Run the restore in a one-off container:

   ```bash
   docker compose run --rm --no-deps app campaign-crm restore /backups/<file name> --yes-erase-current-data
   ```

   It should print `Restored. Restart the app so it reads the restored data.`

   What it does: it restores the database from `database.dump` in one step (if that fails,
   the database is left as it was), then copies the current uploads into the backups
   volume as `/backups/uploads.before-restore-<time>` and puts the backup's uploads in
   their place. That copy is kept until you delete it, once you are happy with the restore:
   `docker compose exec app rm -rf /backups/uploads.before-restore-<time>`. If the database step works but the
   uploads step does not, it says so plainly; fix the cause (usually a full disk) and run
   the same restore again.

   If it prints `That archive could not be read`, `No archive at` or `That archive has no
   database.dump`, nothing was changed. Pick another archive and run this step again, or
   go on to step 5 to bring the site back as it was.


5. Start everything again:

   ```bash
   docker compose up -d
   ```

   `migrate` runs first and checks the database is on the current version.

6. Sign in, open the console's **Health** tab and check the database is **Reachable**. Look at
   a few records you know. **Last backup** may say `running` until the next backup: the
   archive was made while that backup was still being recorded.

Restore a backup taken with the same version of the platform, not a newer one.

> **To confirm:** restoring a backup from an older version, then letting `migrate` bring it
> up to date, has not been tried. Tables added since that backup stay in place during the
> restore, so the update step may fail. Test it on a spare server before relying on it, for
> example to undo a bad update.

## 6. Moving to a new server

1. On the **old** server, take a fresh backup and note its name:

   ```bash
   docker compose exec app campaign-crm backup
   ```

2. Copy it out of the volume, then to the new server:

   ```bash
   docker compose cp app:/backups/<file name> ./
   scp ./<file name> <you>@<new server>:/tmp/
   ```

3. Copy your `.env` to the new server too. Use the same `SECRET_KEY`. You may keep
   `DB_PASSWORD` or make a new one: the new server's database is new, so it takes whatever is
   in `.env` the first time it starts.

4. On the **new** server, follow [section 2](#2-install) using that `.env`. Do **not** run
   the first-run setup: the backup already has it.

5. Restore the backup, as in [section 5](#5-restore):

   ```bash
   cd /opt/campaign-crm/deploy
   docker compose cp /tmp/<file name> app:/backups/restore-me.tar.gz
   docker compose stop app backup caddy
   docker compose run --rm --no-deps app campaign-crm restore /backups/restore-me.tar.gz --yes-erase-current-data
   docker compose up -d
   ```

6. Sign in on the new server by its address and check your data. Then point the domain's DNS
   at the new server. Caddy on the new server gets its certificate once DNS reaches it.

7. Stop the old server (`docker compose down` in its `deploy` folder, which keeps its data)
   only after the new one is working. Keep it for a week before deleting it.

If the domain changes as well, set the new `DOMAIN` in `.env`. Google sign-in, Africa's Talking
callbacks and the Paystack webhook all contain the address and must then be changed on the
provider's side (section 9).

## 7. Updates

### Updating the platform

1. Take a backup:

   ```bash
   docker compose exec app campaign-crm backup
   ```

2. Get the new code:

   ```bash
   cd /opt/campaign-crm && git pull && cd deploy
   ```

   (With a zip or tar file, unpack the new one over the old folder, keeping `deploy/.env`.)

3. Rebuild and restart:

   ```bash
   docker compose up -d --build
   ```

   The `migrate` container runs again and updates the database layout before the new app
   starts. If it fails, the new app does not start (see [Troubleshooting](#11-troubleshooting)).

4. Check with `docker compose ps -a` and the console's **Health** tab (**Version** and
   **Migration**).

The base images (Postgres, Python, Node and Caddy) are pinned to exact versions, so a rebuild
gives the same result each time. They move to newer versions only when the supplier ships an
update that changes them. Keep `postgres:17` in `docker-compose.yml` and `postgresql-client-17`
in the `Dockerfile` on the same major version, or backups may not restore.

### Security updates for the server

On Ubuntu and Debian, let the server install security updates by itself
(<https://ubuntu.com/server/docs/how-to/software/automatic-updates/>):

```bash
sudo apt install unattended-upgrades
cat /etc/apt/apt.conf.d/20auto-upgrades
```

The file should contain:

```
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```

If it does not, create it with those two lines (`sudo nano /etc/apt/apt.conf.d/20auto-upgrades`).
Test it with `sudo unattended-upgrade -v --dry-run`. Logs are in `/var/log/unattended-upgrades`.

Some updates (the kernel) need a reboot. The containers start again by themselves after a
reboot.

### Certificates

Caddy gets the HTTPS certificate for `DOMAIN` and renews it by itself
(<https://caddyserver.com/docs/automatic-https>). There is nothing to schedule. Renewal stops
working when:

- the domain's DNS no longer points at this server;
- port 80 or 443 is closed in a firewall;
- the `caddy-data` volume is deleted (for example by `docker compose down -v`), which also
  throws away the certificate and makes Caddy ask for a new one;
- the `caddy` container is stopped.

`docker compose logs caddy` shows certificate problems.

> **Never run `docker compose down -v`.** The `-v` deletes every volume: the database, the
> uploads, the backups and the certificates. `docker compose down` without `-v` is safe.

## 8. Reference data imports

Take a backup before a large boundaries import (section 4).

When boundaries are reviewed or a new voter register is published, load it from a CSV file.
Two kinds:

### Boundaries file

Columns, in a header row:

```
county_code,county_name,constituency_code,constituency_name,ward_code,ward_name,centre_code,centre_name
```

- One row per registration centre, or one row per ward with the two centre columns blank.
- Counties, constituencies and wards are matched by their code; a centre by its ward's code
  and its own code. A name that changes is renamed, a ward or constituency that moves is moved,
  and new areas are created.
- **A file covers whole counties.** Inside a county the file names, any constituency or ward
  the file leaves out is **retired**, and so is any centre left out of a ward whose centres are
  listed. A file with one ward in it retires the rest of that county, so always send the whole
  county.
- **Nothing is ever deleted.** A retired area keeps everything that refers to it (supporters,
  targets, history). It is hidden from pick lists and from new targets, and comes back if a
  later file names it again.
- Every row naming the same code must give the same name and parent.

### Register file

Columns:

```
county_code,ward_code,centre_code,registered_voters,turnout_pct
```

- A row with only `county_code` sets that county's registered voters and `turnout_pct`.
- A row with only `ward_code` sets that ward's registered voters.
- A row with `ward_code` and `centre_code` sets that centre's registered voters.
- Campaign targets keep their numbers until a candidate or manager presses **Refresh targets**
  in their workspace. An import changes no figure on a campaign's pages by itself.

### Samples

`docs/handover/samples/boundaries.csv` and `docs/handover/samples/register.csv` cover Lamu
County. On a database loaded with `seed`, both report no changes, so they are safe to practise
with. Save your own files as CSV in UTF-8.

### From the console

1. Sign in as the superuser and open **Areas and register** in the console.
2. In the **Boundaries** or **Voter register** box, choose the **CSV file**.
3. Press **Check file**. This writes nothing. It lists every change it would make (created,
   renamed, moved, retired, and so on), or the lines that are wrong.
4. Read the list, especially every **retired** line.
5. Press **Import boundaries** or **Import voter register** to apply it.
6. **Recent imports** lists what was loaded, when and from which file.

### From the server

The file has to be inside the container first:

```bash
docker compose cp ./boundaries.csv app:/tmp/boundaries.csv
docker compose exec app campaign-crm import-boundaries /tmp/boundaries.csv --dry-run
```

`--dry-run` prints every change and writes nothing. When it looks right, run it again without
`--dry-run`:

```bash
docker compose exec app campaign-crm import-boundaries /tmp/boundaries.csv
```

The register works the same way with `import-register`:

```bash
docker compose cp ./register.csv app:/tmp/register.csv
docker compose exec app campaign-crm import-register /tmp/register.csv --dry-run
docker compose exec app campaign-crm import-register /tmp/register.csv
```

If any row is wrong, it prints `Nothing was imported. Fix these lines and run it again:` and
the lines. One bad row and nothing at all is written. Every real import is recorded in the
**Audit** tab.


## 9. Switching on outside services

The platform talks to four outside services: email, SMS, M-Pesa payouts and Google sign-in.
Each one runs in **practice mode** until its keys are in `.env`. In practice mode the platform
works fully but nothing leaves it: emails go to the app's log (`docker compose logs app`), texts are recorded in the SMS
log without being sent, payouts are marked
paid under a `PRACTICE-` reference and move no money.

**The platform is shown to the buyer in practice mode first. A service is switched to live
only after the go-ahead, by adding its keys to `.env`. No code changes.**

For every service the steps are the same:

1. Do the provider-side steps below.
2. Add the lines to `.env`.
3. Restart with the new settings:

   ```bash
   docker compose up -d
   ```

4. Open the console's **Health** tab. Under **Outside services** the service should say
   **Configured** with its mode (for example `Configured (smtp)`) instead of **Not
   configured**. Then run its check, below.

If a required line is missing (for example `SMS_PROVIDER=africastalking` with no
`AT_API_KEY`), the app refuses to start and `docker compose logs migrate app` names the missing
setting. Fix `.env` and run `docker compose up -d` again.

To go back to practice mode, set the provider line back (`EMAIL_PROVIDER=practice`,
`SMS_PROVIDER=console`, `PAYOUT_PROVIDER=practice`, or blank the two Google lines) and run
`docker compose up -d`.

### Email (SMTP, any provider)

Any email service that offers SMTP works: your organisation's mail server, Google Workspace,
Microsoft 365, or a sending service. The platform sends sign-in links, password resets and
invitations.

1. From your email provider, get: the SMTP server name, the port, a username and password
   (often an "app password" or SMTP key), and the address you are allowed to send from.
   Many providers also ask you to add SPF and DKIM records to your domain so mail is not marked
   as spam; follow your provider's instructions for that.
2. In `.env`:

   ```
   EMAIL_PROVIDER=smtp
   SMTP_HOST=smtp.your-provider.example
   SMTP_PORT=587
   SMTP_USER=<username>
   SMTP_PASSWORD='<password>'
   SMTP_FROM=Party Name <noreply@your-domain.example>
   ```

   Port `587` uses STARTTLS. Port `465` uses TLS from the start. Both work; use what your
   provider says. `SMTP_HOST` and `SMTP_FROM` are required.
3. `docker compose up -d`, then check **Health** shows Email as `Configured (smtp)`.
4. Check it sends: on the **Health** tab press **Send a test email**. It goes to the email of
   the login you are signed in as.

   If nothing arrives, check spam, then `docker compose logs app` for the error.

### SMS (Africa's Talking)

Texts to supporters, event invitations and party messages go out through Africa's Talking.
Replies of STOP opt the number out.

> **To confirm:** Africa's Talking's developer site
> (developers.africastalking.com) refused automated reading, so the dashboard menu names below
> could not be checked against it. Follow the dashboard as it is today.

1. Create an account at Africa's Talking. In the dashboard, create (or open) your **app** and
   note its **username**. Generate an **API key** for it.
2. To send under your own name instead of the shared short code, apply for an alphanumeric
   **sender ID** (or a short code) in the dashboard. Approval can take days. Leave
   `AT_SENDER_ID` blank until it is approved.
3. Make a long random secret for the callback addresses:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. In `.env`:

   ```
   SMS_PROVIDER=africastalking
   AT_USERNAME=<your app username>
   AT_API_KEY=<your API key>
   AT_SENDER_ID=
   AT_SANDBOX=false
   SMS_CALLBACK_SECRET=<the secret from step 3>
   ```

   To try the **sandbox** first (texts go to the Africa's Talking simulator, not real phones),
   use `AT_USERNAME=sandbox`, the sandbox app's API key, and `AT_SANDBOX=true`. Africa's
   Talking's own library documents that the sandbox username is always `sandbox`
   (<https://github.com/AfricasTalkingLtd/africastalking-python>).
5. In the Africa's Talking dashboard, under the SMS callback settings, set these addresses,
   using your domain and the exact secret:

   | Callback | Address |
   |---|---|
   | Delivery reports | `https://<your domain>/api/sms/<SMS_CALLBACK_SECRET>/delivery/` |
   | Incoming messages | `https://<your domain>/api/sms/<SMS_CALLBACK_SECRET>/inbound/` |
   | Bulk SMS opt-out | `https://<your domain>/api/sms/<SMS_CALLBACK_SECRET>/opt-out/` |

   The trailing `/` is part of the address. Africa's Talking does not sign its callbacks, so
   the secret in the address is what keeps strangers out; an address with the wrong secret
   gets "Not Found". With `SMS_CALLBACK_SECRET` blank, the callbacks are off.

   > **To confirm with Africa's Talking:** replies such as STOP reach the "Incoming messages"
   > address only for a number or short code that can receive texts. Ask your account manager
   > how replies work for your sender ID.
6. `docker compose up -d`, then check **Health** shows SMS as `Configured (africastalking)`.
7. In **Health**, type your phone number under **Send a test SMS: phone number** and press
   **Send a test SMS**. It answers `Sent to <number>.` and the text arrives. In practice mode it
   says the text was recorded instead of sent.

### Payments in (Paystack, M-Pesa prompts)

Contributions and nomination fees can be paid by an M-Pesa prompt to the payer's phone, through
Paystack's Charge API (`mobile_money` with provider `mpesa`). Paying by Paybill or Till code
works without Paystack.

Checked against Paystack's documentation:
<https://paystack.com/docs/payments/payment-channels/>,
<https://paystack.com/docs/api/charge/>, <https://paystack.com/docs/payments/webhooks/>.

1. Use the same Paystack account, keys and webhook as payouts (below). The one webhook address
   takes both transfer and charge events.
2. In `.env`: `PAYIN_PROVIDER=paystack` with `PAYSTACK_SECRET_KEY` set.
3. Set the site's contact email: Paystack needs an email with every prompt, and a payer who
   leaves theirs blank is sent under the site's.
4. A prompt is marked paid only by a signed `charge.success` webhook, or by Paystack's
   `GET /charge/:reference` check when the box has waited 15 seconds, and only when the amount
   and currency (KES) match. A mismatch shows as **Failed** with the reason.

### Payouts (Paystack, M-Pesa transfers)

Approved payments to mobilizers and agents are sent as M-Pesa transfers from your Paystack
balance.

Checked against Paystack's documentation:
<https://paystack.com/docs/api/authentication/>,
<https://paystack.com/docs/payments/webhooks/>,
<https://paystack.com/docs/transfers/single-transfers/>,
<https://paystack.com/docs/transfers/creating-transfer-recipients/>.

1. Open a Paystack account for Kenya and complete its business checks; transfers need a live,
   approved business.
2. **Start with test mode.** In the Paystack dashboard, on the Developers overview page, copy
   the **test** secret key. Test keys start with `sk_test_`; live keys start with `sk_live_`.
3. In the dashboard, add the webhook address below, and copy the webhook signing secret (it
   starts with `whsec_`; Paystack's docs place it under **Developers > API configuration**).
   Paystack keeps test and live webhook settings apart, so set them in each mode. The address
   is:

   ```
   https://<your domain>/api/payments/paystack/webhook/
   ```

4. In `.env`:

   ```
   PAYOUT_PROVIDER=paystack
   PAYSTACK_SECRET_KEY=<your sk_test_ key>
   PAYSTACK_WEBHOOK_SECRET=<your whsec_ secret>
   ```

   `PAYSTACK_SECRET_KEY` is required. With `PAYSTACK_WEBHOOK_SECRET` blank, the platform falls
   back to Paystack's older signature, made with the secret key.
5. `docker compose up -d`, then check **Health** shows Payouts (M-Pesa) as
   `Configured (paystack)`. The **Make a practice payout** button is refused from now on: it
   only works in practice mode.
6. Test with a real flow in a campaign: approve a small payment to a mobilizer. In test mode
   Paystack always reports test transfers as successful and moves no real money. The payment
   should move from sending to paid once Paystack's webhook arrives. If it stays sending, the
   webhook address or secret is wrong; `docker compose logs app` then shows the webhook
   address answered with `401`.
7. For transfers sent by the platform without a person confirming each one, Paystack's
   documentation says to turn off OTP confirmation for transfers in the dashboard's transfer
   approval settings.
8. **Going live** (only after the go-ahead): replace the key with the `sk_live_` key and the
   webhook secret with the live one, set the live webhook address in the dashboard, add money
   to the Paystack balance, and run `docker compose up -d`. Every release checks the balance
   first and is refused if it does not cover the amount and Paystack's fee.

Paystack sends webhooks only from fixed addresses listed on its webhooks page. If your server
has a firewall that filters incoming traffic by address, allow them.

### Google sign-in

Lets people with a login sign in with their Google account. It never creates a login: the
Google account's email must match an existing login's email, and Google must have verified it.

Checked against Google's documentation:
<https://support.google.com/cloud/answer/15549257> and
<https://developers.google.com/identity/protocols/oauth2/openid-connect>.

1. In Google Cloud, create a project (or pick one). Open the **Branding** page of the Google
   Auth Platform (<https://console.developers.google.com/auth/branding>) and fill in the app
   name and support email that people see when they sign in.
2. Open the **Clients** page (<https://console.developers.google.com/auth/clients>), press
   **Create client**, and choose **Web application**.
3. Under **Authorized redirect URIs**, add exactly:

   ```
   https://<your domain>/api/auth/google/callback/
   ```

   That is your `PUBLIC_URL` followed by `/api/auth/google/callback/`, **with the trailing
   slash**. Google compares it character for character; any difference gives a
   `redirect_uri_mismatch` error.
4. Press **Create**. Copy the **client ID** and the **client secret** straight away: Google
   shows the full secret only once.
5. In `.env`:

   ```
   GOOGLE_CLIENT_ID=<id>.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=<secret>
   ```

6. `docker compose up -d`. **Sign in with Google** now shows on the sign-in page.
7. In **Health**, under **Sign-in**, press **Check Google sign-in**. It answers `Google
   answered. Its OAuth client must allow the redirect URI ...` with the exact address; compare
   it with the one in step 3. Then sign in with Google once yourself.

## 10. Locked out

**Someone forgot their password.** If email is live, they press **Forgot your password?** on
the sign-in page. Otherwise, or for the superuser, give them a new password from the server:

```bash
docker compose exec app campaign-crm reset-password -u <username>
```

It prints `<username> signs in with: <new password>`, shown once. Every session that login had
is signed out. To set a password you choose instead, add `-p '<password>'`.

**A login has no email, or the wrong one.** Sign-in is by email, so set it:

```bash
docker compose exec app campaign-crm set-email -u <username> --email <address>
```

It refuses an email another login already has.

**You do not know the username.** List every login:

```bash
docker compose exec app campaign-crm users
```

**A login was disabled.**

```bash
docker compose exec app campaign-crm activate -u <username>
```

**No superuser can sign in at all.** Make a new one (it asks for the password), then give it
your email:

```bash
docker compose exec app campaign-crm createuser -u <new username> --email <address> --superuser
```

Every one of these is recorded in the console's **Audit** tab.

## 11. Troubleshooting

### Where to look

- Container state: `docker compose ps -a`
- The app's log: `docker compose logs app` (add `--tail 200` for the last lines, `-f` to
  follow)
- Other logs: `docker compose logs migrate`, `docker compose logs caddy`,
  `docker compose logs backup`, `docker compose logs db`
- Is the app answering? `https://<your domain>/health`
- The console's **Health** tab: version, database, migration, outside services, last backup
  and free disk space for uploads and backups.

### Common problems

| What you see | Likely cause and fix |
|---|---|
| The site does not load at all, or the browser warns about the certificate | DNS for `DOMAIN` does not point at this server yet, or ports 80/443 are closed. Check DNS with `dig +short <your domain>` (it should print the server's address) and your cloud firewall. `docker compose logs caddy` shows certificate errors. Caddy keeps retrying, so once DNS and ports are right it fixes itself. |
| `docker compose up` stops with `set DOMAIN in .env` (or `DB_USER`, `DB_PASSWORD` and `DB_NAME`, `ACME_EMAIL`) | That line is empty in `.env`. Fill it in. Run the command from the `deploy` folder. |
| `migrate` shows `Exited (1)` and the app never starts | Read `docker compose logs migrate`. A settings error (for example `SECRET_KEY` shorter than 32 characters, or a live provider missing its keys) names the setting. A database password error is the next row. Anything else: send the log to the supplier and restore from your backup if needed. |
| `password authentication failed for user "campaign_crm"` in the logs | `DB_PASSWORD` in `.env` was changed after the first start. The database keeps the password it was first started with. Put the original value back in `.env` and run `docker compose up -d`. |
| The app keeps restarting | `docker compose logs app`. Usually a settings error, as above. |
| Every page goes to `/setup` | The first-run setup has not been done, or a restore brought back a database without it. See section 3. |
| `That setup token is wrong, spent or more than 24 hours old.` | Print a new token with `docker compose exec app campaign-crm setup-token`. |
| Health shows **Last backup** as `failed` or `never` | The error is in the backups table on the Health tab and in `docker compose logs backup`. Check free disk space (`df -h`). Run `docker compose exec app campaign-crm backup` by hand to see the message. |
| Disk is filling up | Check the Health tab's free space and `docker system df`. Old build images can be removed with `docker image prune`. Apart from an old `uploads.before-restore-<time>` copy (section 5), do not delete anything inside the volumes by hand. |
| Emails or texts do not arrive | Health should say **Configured**. Then see `docker compose logs app` for the provider's error, and section 9. |


### Restarting

```bash
docker compose restart app       # the app only
docker compose up -d             # everything, picking up .env changes
docker compose down              # stop everything (data is kept)
```

## 12. The hosted alternative: Fly.io and Neon

Instead of your own server, the platform can run on Fly.io (the app) with the database on Neon
(hosted Postgres). The supplier keeps a separate, private step-by-step file for this. In short:

1. Install `flyctl` (Fly's command-line tool) and the Neon command-line tool, and sign in to
   both.
2. Create a Fly app and a Neon database, in nearby regions.
3. Store the settings as Fly secrets, not in a file: `DATABASE_URL` (the Neon connection string,
   with `sslmode=verify-full` so the database's certificate is checked) and `SECRET_KEY` (a long
   random value), with `flyctl secrets set --stage`. The same `.env` settings from section 9
   switch on outside services there; `PUBLIC_URL` must be set to the app's address.
4. Deploy with `flyctl deploy --remote-only`. It builds the same image on Fly's machines and
   runs `alembic upgrade head` before the new version takes traffic; a failed migration leaves
   the old version running.
5. Run the one-off commands on a Fly machine with `flyctl ssh console -C "<command>"`, for
   example `campaign-crm seed` and `campaign-crm setup-token`, then finish setup at `/setup`.
   Always pass `--password` to commands that would otherwise ask for one.
6. Check it with `flyctl status`, `flyctl logs` and the `/health` address.

What is different from your own server:

- **Backups** are Neon's restore window, which on the free plan is a few hours plus one manual
  snapshot. The nightly `backup` container and its 14 daily and 8 weekly archives are part of
  the self-host package only.
- Neon's free plan pauses an idle database (the first request afterwards is slow) and caps
  compute and storage each month.
- Fly machines can be set to suspend when idle, which saves money but makes the first visit
  slower.

> **To confirm with the supplier before choosing this option:** where uploaded files are kept
> on Fly, and how they are backed up.
