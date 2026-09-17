# secret-scan

Stops passwords, keys and tokens from being committed. Python 3.10+, standard
library only.

## Run it

```bash
python tools/secret-scan/scan.py --staged          # what the next commit holds
python tools/secret-scan/scan.py --all             # every tracked file
python tools/secret-scan/scan.py --history         # every line any commit ever added
python tools/secret-scan/scan.py --history A..B    # the lines commits after A up to B added
python -m unittest discover -s tools/secret-scan   # its own tests
```

It exits 1 when it finds anything. A finding prints the path, line, rule and the
value's length, never the value. Binary files are skipped and named on stderr;
UTF-16 files, files over any size, and text holding a stray NUL are read.

## Turn on the hook

Once per clone:

```bash
git config core.hooksPath .githooks
```

`.github/workflows/secret-scan.yml` runs the tests, scans every tracked file, and
scans every commit a push or pull request adds, so a clone without the hook is
still caught, including a value added in one commit and removed in the next.

## What it flags

| Rule | Catches |
|---|---|
| `private-key` | a PEM private key header |
| `provider-key` | AWS, GitHub, Slack, Stripe, Google, SendGrid, npm, Anthropic, OpenAI and Fly key shapes |
| `jwt` | a JSON web token |
| `auth-header` | an `Authorization` header carrying a Bearer, Token or Basic value |
| `url-credentials` | a password inside a connection string |
| `key-value` | a sensitive name (password, pass, secret, API key, access key, private key, token) given a string literal |
| `cli-flag` | `--password <value>`, `["--password", "<value>"]`, `curl -u user:<value>`, `mysql -p<value>` |
| `env-assignment` | `SOME_PASSWORD=<value>` in docs, env files, shell and Dockerfiles; `password: <value>` in YAML, TOML and INI; `.npmrc`, `.netrc` and `.pgpass` passwords |
| `named-slug` | a hyphenated string naming itself a password or secret, led by a word such as a, my, test or fake, or four parts or longer |
| `random-token` | 9 to 64 letters and digits whose case and class change at least six times |
| `word-digits` | a lowercase word and four or more digits, or a word like pass, admin or login and two or more digits |

Not flagged: empty values, `<placeholders>`, anything holding `REDACTED`,
`${template}` and `{f-string}` interpolation, `$VARIABLES`, upper-case URL
placeholders such as `USER:PASSWORD@HOST`, and values that read as prose (a
capitalised word such as a form error, or a capitalised phrase).

## Writing tests that pass it

Generate the value. `backend/tests/factories.py` has `TEST_PASSWORD` and
`fresh_password()`; `frontend/tests/helpers.jsx` has `fakeSecret()` and
`TEST_TOKEN`.

## Skipping a path

Add a glob to `allow.txt`, with a comment saying why that file can never hold a
value.

## Known gaps

- A password passed positionally with no sensitive name beside it, and no shape
  of its own, is not caught: a function argument, a tuple, a value typed into a
  form in a test.
- A base64 blob under a name that is not sensitive, such as `auth=`, is not
  caught.
- A value that reads as prose (a capitalised word or phrase) given to a
  sensitive name is treated as a label.
- A hyphenated password with no qualifier word and fewer than four parts, or one
  ending in a year, is not recognised.
- A value split across lines or built by concatenation is not reassembled.
- CI on a new branch, or after history is rewritten, has no earlier commit to
  compare with; it scans the tip only.
- The hook runs only in clones that turned it on; `--no-verify` skips it. CI does
  not.
