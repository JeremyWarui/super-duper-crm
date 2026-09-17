"""Every sample secret here is built at runtime, so this file scans clean."""

import base64
import json
import os
import secrets
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scan.py"
sys.path.insert(0, str(HERE))

import scan  # noqa: E402

PW = "pass" + "word"
KEY_NAME = "SEC" + "RET_KEY"


def random_token(length: int = 12) -> str:
    """Upper, lower and digit in turn, the shape of a generated key."""
    pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits]
    return "".join(secrets.choice(pools[i % 3]) for i in range(length))


def alnum(length: int, pool: str = string.ascii_letters + string.digits) -> str:
    return "".join(secrets.choice(pool) for _ in range(length))


def rules(path: str, text: str) -> list[str]:
    return [finding.rule for finding in scan.scan_text(path, text)]


class KeyValue(unittest.TestCase):
    def test_a_keyword_argument(self) -> None:
        self.assertEqual(rules("t.py", f'make_user({PW}="{random_token()}")'), ["key-value"])

    def test_a_short_lowercase_value_still_counts(self) -> None:
        self.assertEqual(rules("t.py", f'login({PW}="x")'), ["key-value"])

    def test_a_lowercase_phrase_still_counts(self) -> None:
        self.assertEqual(rules("t.py", f'{PW}="blue sky"'), ["key-value"])

    def test_an_object_key(self) -> None:
        self.assertEqual(rules("t.js", f'const body = {{ {PW}: "plain" }};'), ["key-value"])

    def test_a_quoted_json_key(self) -> None:
        self.assertEqual(rules("t.json", f'{{"{PW}": "plain"}}'), ["key-value"])

    def test_a_hyphenated_header_name(self) -> None:
        key = "X-API-" + "Key"
        self.assertEqual(rules("t.py", f'headers={{"{key}": "plain"}}'), ["key-value"])

    def test_an_environment_name_passed_with_its_value(self) -> None:
        line = f'monkeypatch.setenv("DEFAULT_USER_{PW.upper()}", "plain")'
        self.assertEqual(rules("t.py", line), ["key-value"])

    def test_an_annotated_default(self) -> None:
        self.assertEqual(rules("t.py", f'def f({PW}: str = "plain"): ...'), ["key-value"])

    def test_a_subscript_assignment(self) -> None:
        self.assertEqual(rules("t.py", f'os.environ["DB_{PW.upper()}"] = "plain"'), ["key-value"])

    def test_a_comparison(self) -> None:
        self.assertEqual(rules("t.py", f'assert body["{PW}"] == "plain"'), ["key-value"])

    def test_a_camel_case_api_key(self) -> None:
        key = "api" + "Key"
        self.assertEqual(rules("t.py", f'assert headers["{key}"] == "plain"'), ["key-value"])

    def test_a_secret_key_constant(self) -> None:
        self.assertEqual(rules("t.py", f'{KEY_NAME} = "plain"'), ["key-value"])

    def test_a_short_pass_suffix(self) -> None:
        self.assertEqual(rules("t.py", "DB_" + 'PASS = "plain"'), ["key-value"])
        self.assertEqual(rules("t.py", "by" + 'pass = "plain"'), [])

    def test_an_empty_value_is_not_a_secret(self) -> None:
        self.assertEqual(rules("t.py", f'setenv("X_{PW.upper()}", "")'), [])

    def test_an_interpolated_value_is_not_a_secret(self) -> None:
        self.assertEqual(rules("t.py", f'{PW}=f"{{prefix}}x"'), [])
        self.assertEqual(rules("t.js", f"{PW}: `${{nth}}`"), [])

    def test_a_placeholder_is_not_a_secret(self) -> None:
        self.assertEqual(rules("t.md", f'{PW}="<shared-{PW}>"'), [])
        self.assertEqual(rules("t.py", f'{PW}="REDACTED-01"'), [])

    def test_a_variable_is_not_a_secret(self) -> None:
        self.assertEqual(rules("t.py", f"{PW}=TEST_{PW.upper()}"), [])

    def test_string_concatenation_is_not_a_value(self) -> None:
        self.assertEqual(rules("t.py", f'line = "DB_{PW.upper()}=" + value'), [])
        self.assertEqual(rules("t.py", f'line = "DB_{PW.upper()}=" + "<" + name + ">"'), [])

    def test_form_errors_and_labels_are_prose(self) -> None:
        self.assertEqual(rules("t.jsx", f'setErrors({{ {PW}: "Required" }})'), [])
        self.assertEqual(rules("t.py", f'errors = {{"{PW}": "Too short"}}'), [])
        self.assertEqual(rules("t.js", f'const labels = {{ {PW}: "{PW.capitalize()}" }};'), [])
        self.assertEqual(rules("t.py", f'{{"{PW}": "At least 8 characters."}}'), [])

    def test_a_label_that_mentions_the_word(self) -> None:
        flag = "show" + PW.capitalize()
        line = f'aria-label={{{flag} ? "Hide {PW}" : "Show {PW}"}}'
        self.assertEqual(rules("t.jsx", line), [])

    def test_a_name_that_only_starts_with_the_word(self) -> None:
        self.assertEqual(rules("t.py", "TOKEN" + '_SCHEME = "Token"'), [])
        self.assertEqual(rules("t.py", f'{PW}_hash="nope"'), [])

    def test_an_arrow_is_not_an_assignment(self) -> None:
        self.assertEqual(rules("t.js", f'{PW} => "plain"'), [])


class UrlCredentials(unittest.TestCase):
    def test_a_password_in_a_connection_string(self) -> None:
        line = f"postgresql://app:{random_token()}@db:5432/x"
        self.assertEqual(rules("t.py", line), ["url-credentials"])

    def test_a_percent_encoded_password(self) -> None:
        line = "postgresql://app:" + secrets.token_hex(3) + "%40" + secrets.token_hex(3) + "@db/x"
        self.assertEqual(rules("t.py", line), ["url-credentials"])

    def test_an_upper_case_password_is_not_a_placeholder(self) -> None:
        line = "postgresql://app:" + alnum(10, string.ascii_uppercase + string.digits) + "@db/x"
        self.assertEqual(rules("t.py", line), ["url-credentials"])

    def test_upper_case_placeholder_words(self) -> None:
        self.assertEqual(rules("t.md", "postgresql://USER:" + PW.upper() + "@HOST:5432/d"), [])
        self.assertEqual(rules("t.md", "postgresql://USER:DB_" + PW.upper() + "@HOST/d"), [])

    def test_interpolated_parts(self) -> None:
        self.assertEqual(rules("t.py", 'f"postgresql://{user}:{pw}@host/d"'), [])

    def test_no_password_at_all(self) -> None:
        self.assertEqual(rules("t.md", "https://user@host/x and http://localhost:5173"), [])


class EnvAssignment(unittest.TestCase):
    def test_a_value_in_a_readme(self) -> None:
        line = f"DEFAULT_USER_{PW.upper()}=plain"
        self.assertEqual(rules("README.md", line), ["env-assignment"])

    def test_mid_line_in_a_command(self) -> None:
        line = f"docker run -e POSTGRES_{PW.upper()}=plain postgres"
        self.assertEqual(rules("README.md", line), ["env-assignment"])

    def test_dockerfile_env_and_arg(self) -> None:
        self.assertEqual(rules("Dockerfile", f"ENV DB_{PW.upper()}=plain"), ["env-assignment"])
        self.assertEqual(rules("Dockerfile", f"ARG {KEY_NAME}=plain"), ["env-assignment"])
        self.assertEqual(rules("Dockerfile", f"ENV DB_{PW.upper()} plain"), ["env-assignment"])

    def test_a_short_pass_name_in_an_env_file(self) -> None:
        self.assertEqual(rules(".env", "DB_" + "PASS=plain"), ["env-assignment"])

    def test_lowercase_in_an_env_file(self) -> None:
        self.assertEqual(rules("deploy.sh", f"db_{PW}=plain"), ["env-assignment"])

    def test_a_value_in_yaml(self) -> None:
        self.assertEqual(rules("x.yaml", f"  {PW}: plain"), ["env-assignment"])

    def test_an_upper_case_colon_line_in_a_shell_heredoc(self) -> None:
        self.assertEqual(rules("x.sh", f"  {KEY_NAME}: {random_token()}"), ["env-assignment"])
        self.assertEqual(rules("x.sh", f"  {PW}: plain"), [])

    def test_an_npmrc_registry_token(self) -> None:
        line = "//registry.npmjs.org/:_auth" + "Token=" + alnum(20, string.ascii_lowercase)
        self.assertEqual(rules(".npmrc", line), ["env-assignment"])

    def test_a_netrc_password(self) -> None:
        line = f"machine github.com login jane {PW} {random_token()}"
        self.assertEqual(rules(".netrc", line), ["env-assignment"])

    def test_a_pgpass_line(self) -> None:
        line = "localhost:5432:campaign_crm:postgres:" + random_token()
        self.assertEqual(rules(".pgpass", line), ["env-assignment"])
        self.assertEqual(rules(".pgpass", "#host:port:db:user:" + PW), [])

    def test_prose_lines_that_start_with_the_word(self) -> None:
        self.assertEqual(rules("README.md", f"{PW.capitalize()}: whatever the demo printed"), [])
        self.assertEqual(
            rules("README.md", f"- {PW}: the new login's {PW}, at least 8 characters"), []
        )
        self.assertEqual(rules("README.md", "To" + "ken: never expires; sign out deletes it."), [])
        self.assertEqual(rules("README.md", "to" + "ken=abc is not accepted; use the header."), [])

    def test_an_identifier_in_code(self) -> None:
        self.assertEqual(rules("t.py", f"DEFAULT_{PW.upper()} = TEST_{PW.upper()}"), [])

    def test_blanks_placeholders_and_substitutions(self) -> None:
        self.assertEqual(rules(".env.example", f"{KEY_NAME}="), [])
        self.assertEqual(rules(".env.example", "AT_API_KEY=<gateway-key>"), [])
        self.assertEqual(rules("DEPLOY.md", f'{KEY_NAME}="$(python -c x)"'), [])
        self.assertEqual(rules("x.yaml", f"show-{PW}s: false"), [])


class CliFlag(unittest.TestCase):
    def test_a_flag_and_its_value_in_docs(self) -> None:
        line = f"uv run campaign-crm demo --{PW} {alnum(10, string.ascii_lowercase)}"
        self.assertEqual(rules("README.md", line), ["cli-flag"])

    def test_an_equals_flag_in_a_script(self) -> None:
        self.assertEqual(rules("deploy.sh", f"campaign-crm demo --{PW}=plain"), ["cli-flag"])

    def test_a_quoted_flag_value(self) -> None:
        self.assertEqual(rules("README.md", f'demo --{PW} "plain"'), ["cli-flag"])

    def test_curl_user_and_password(self) -> None:
        self.assertEqual(
            rules("README.md", f"curl -u admin:{random_token()} https://x"), ["cli-flag"]
        )

    def test_an_argument_list_in_code(self) -> None:
        self.assertEqual(rules("t.py", f'main(["demo", "--{PW}", "plain"])'), ["cli-flag"])

    def test_placeholders_variables_and_prose(self) -> None:
        self.assertEqual(rules("README.md", f"demo --{PW} <shared-{PW}>"), [])
        self.assertEqual(rules("README.md", f'demo --{PW} "$DEMO_{PW.upper()}"'), [])
        self.assertEqual(rules("README.md", f"`--{PW}` pins them"), [])
        self.assertEqual(
            rules("t.py", f'add_argument("-p", "--{PW}", help="generated when left out")'), []
        )
        self.assertEqual(rules("README.md", "curl -u admin:$TOKEN https://x"), [])
        self.assertEqual(rules("README.md", "| `curl -u user:<value>` |"), [])

    def test_a_mysql_password_flag(self) -> None:
        self.assertEqual(
            rules("README.md", f"mysql -u root -p{random_token()} campaign"), ["cli-flag"]
        )
        self.assertEqual(rules("README.md", "mysql -u root -p campaign"), [])
        self.assertEqual(rules("README.md", "uv run pytest -q -p no:cacheprovider"), [])

    def test_curl_inside_backticks(self) -> None:
        self.assertEqual(
            rules("README.md", f"run `curl -u admin:{random_token()}` once"), ["cli-flag"]
        )


class WellKnownShapes(unittest.TestCase):
    def test_a_private_key_block(self) -> None:
        header = "-----BEGIN " + "RSA PRIVATE KEY-----"
        self.assertEqual(rules("key.pem", header), ["private-key"])
        self.assertEqual(rules("t.py", f'KEY = """{header}'), ["private-key"])

    def test_provider_prefixes(self) -> None:
        upper_digits = string.ascii_uppercase + string.digits
        samples = {
            "aws": ".env",
            "github": "t.py",
            "slack": "t.py",
            "stripe": "t.js",
            "npm": ".npmrc",
        }
        values = {
            "aws": "AWS_ACCESS_KEY_ID=" + "AK" + "IA" + alnum(16, upper_digits),
            "github": 'Github("' + "gh" + "p_" + alnum(32) + '")',
            "slack": 'WebClient("'
            + "xo"
            + "xb-"
            + alnum(12, string.digits)
            + "-"
            + alnum(24)
            + '")',
            "stripe": 'Stripe("' + "sk" + "_live_" + alnum(24) + '")',
            "npm": "//registry.npmjs.org/:_authToken=" + "np" + "m_" + alnum(36),
        }
        for name, line in values.items():
            with self.subTest(name):
                self.assertIn("provider-key", rules(samples[name], line))

    def test_a_json_web_token(self) -> None:
        def part(obj: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

        header = part({"alg": "HS256", "typ": "JWT"})
        jwt = f"{header}.{part({'sub': secrets.token_hex(8)})}.{alnum(32)}"
        self.assertEqual(rules("notes.md", f"use {jwt} to call it"), ["jwt"])

    def test_an_authorization_header(self) -> None:
        line = 'headers: { Authorization: "' + "Token " + secrets.token_hex(20) + '" }'
        self.assertEqual(rules("t.js", line), ["auth-header"])

    def test_an_interpolated_authorization_header(self) -> None:
        self.assertEqual(rules("t.py", 'headers={"Authorization": f"Bearer {token}"}'), [])
        self.assertEqual(rules("t.js", "toBe(`Token ${TEST_TOKEN}`)"), [])


class NamedSlug(unittest.TestCase):
    def test_a_qualified_made_up_password(self) -> None:
        line = f'sign_in(client, "jane", "my-own-{PW}")'
        self.assertEqual(rules("t.py", line), ["named-slug"])

    def test_a_made_up_secret_with_a_qualifier(self) -> None:
        line = 'KEY = "a-' + "sec" + "ret-" + secrets.token_hex(3) + '"'
        self.assertEqual(rules("t.py", line), ["named-slug"])

    def test_four_or_more_parts(self) -> None:
        self.assertEqual(rules("t.py", f'x = "one-two-three-{PW}"'), ["named-slug"])

    def test_interface_names_and_routes(self) -> None:
        names = [
            f'<input id="confirm-{PW}" />',
            f'screen.getByTestId("{PW}-toggle")',
            f'className="{PW}-field"',
            f'navigate({{ name: "forgot-{PW}" }})',
            f'form.fields["{PW}2"]',
            f'COMMANDS = ["change-{PW}"]',
            f'parser.parse_args(["reset-{PW}", "-u", "jane"])',
            f'add_argument("-p", "--{PW}")',
            f"api(`/admin/users/${{id}}/reset-{PW}/`)",
            f'autoComplete="current-{PW}"',
            f'column("{PW}_hash")',
        ]
        for line in names:
            with self.subTest(line):
                self.assertEqual(rules("t.jsx", line), [])
        self.assertEqual(rules("package.json", '"sec' + 'ret-scan": "python tools/scan.py"'), [])
        self.assertEqual(
            rules("README.md", f"Auth uses OAuth2{PW.capitalize()}Bearer from FastAPI."), []
        )


class RandomToken(unittest.TestCase):
    def test_quoted_in_code(self) -> None:
        line = f'expect(await screen.findByText("{random_token()}"));'
        self.assertEqual(rules("t.jsx", line), ["random-token"])

    def test_a_bare_word_in_docs(self) -> None:
        line = f"  aspirant     {random_token()}   Candidate"
        self.assertEqual(rules("README.md", line), ["random-token"])

    def test_a_bare_identifier_in_code(self) -> None:
        self.assertEqual(rules("t.py", f"x = {random_token()}"), [])

    def test_names_with_a_digit_in_them(self) -> None:
        self.assertEqual(rules("README.md", "Returns an IPv4Address or an IPv6Address."), [])
        self.assertEqual(rules("README.md", "It runs on Ubuntu2204 images."), [])
        self.assertEqual(rules("t.jsx", 'getByText("Election2027")'), [])
        self.assertEqual(rules("t.jsx", 'data-testid="step2Button"'), [])

    def test_short_names_words_and_hex(self) -> None:
        self.assertEqual(rules("README.md", "Hashes are " + "Argon" + "2id."), [])
        self.assertEqual(rules("t.js", 'expect(x).toBeInTheDocument("toBeInTheDocument")'), [])
        self.assertEqual(rules("t.py", f'x = "{secrets.token_hex(8)}"'), [])


class WordDigits(unittest.TestCase):
    def test_a_word_then_four_digits(self) -> None:
        word = "zulu" + str(1000 + secrets.randbelow(9000))
        self.assertEqual(rules("t.jsx", f'await user.type(field(), "{word}");'), ["word-digits"])

    def test_a_password_word_then_digits(self) -> None:
        self.assertEqual(rules("t.py", f'login("amina", "{PW}12")'), ["word-digits"])

    def test_codes_names_and_short_numbers(self) -> None:
        self.assertEqual(rules("t.py", 'hashlib.new("sha' + '256")'), [])
        self.assertEqual(rules("t.py", 'Ward(name="Githurai", code="WRD001")'), [])
        self.assertEqual(rules("t.py", 'County(code="NRB047")'), [])
        self.assertEqual(rules("t.js", 'toBe("error404")'), [])


class Decoding(unittest.TestCase):
    def test_utf16_with_a_byte_order_mark(self) -> None:
        text = scan.decode(f'{PW}="plain"\n'.encode("utf-16"))
        self.assertEqual(rules(".env.local", text), ["key-value"])

    def test_utf16_without_a_byte_order_mark(self) -> None:
        text = scan.decode(f"DB_{PW.upper()}=plain\n".encode("utf-16-le"))
        self.assertEqual(rules(".env.local", text), ["env-assignment"])

    def test_a_stray_nul_in_text_does_not_hide_the_file(self) -> None:
        text = scan.decode(f'X\0\n{PW}="plain"\n'.encode())
        self.assertEqual(rules("t.py", text), ["key-value"])

    def test_a_large_file_is_read(self) -> None:
        body = "# filler\n" * 400_000 + f'{PW}="plain"\n'
        self.assertEqual(rules("t.py", scan.decode(body.encode())), ["key-value"])

    def test_binary_is_skipped(self) -> None:
        self.assertIsNone(scan.decode(b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + bytes(range(256))))


class Reporting(unittest.TestCase):
    def test_no_part_of_the_value_prints(self) -> None:
        (finding,) = scan.scan_text("t.py", f'{PW}="{random_token(20)}"')
        self.assertEqual(finding.render(), "t.py:1: key-value: ****** (20 chars)")

    def test_one_value_is_reported_once(self) -> None:
        self.assertEqual(len(scan.scan_text("t.js", f'{PW}: "{random_token()}"')), 1)

    def test_the_line_number_is_the_line_the_value_is_on(self) -> None:
        (finding,) = scan.scan_text("t.py", f'x = 1\n{PW}="plain"\n')
        self.assertEqual(finding.line, 2)

    def test_allowed_paths_match_as_globs(self) -> None:
        self.assertTrue(scan.allowed("backend/evals/schema.json", ["backend/evals/*.json"]))
        self.assertFalse(scan.allowed("backend/tests/x.py", ["backend/evals/*.json"]))

    def test_the_allow_file_skips_comments_and_blanks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "allow.txt"
            file.write_text("# why\n\nfrontend/package-lock.json\n", encoding="utf-8")
            self.assertEqual(scan.load_allow(file), ["frontend/package-lock.json"])

    def test_a_quoted_diff_path_is_unquoted(self) -> None:
        self.assertEqual(scan._diff_path('+++ "b/caf\\303\\251 \\"q\\".md"'), 'café "q".md')
        self.assertEqual(scan._diff_path("+++ b/doc notes.md\t"), "doc notes.md")
        self.assertEqual(scan._diff_path("+++ /dev/null"), "")


class GitModes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.git("init", "-q")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )

    def scan(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        env = env or {**os.environ, "PYTHONIOENCODING": "utf-8"}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def write(self, name: str, text: str) -> None:
        (self.repo / name).write_text(text, encoding="utf-8")

    def commit(self, name: str, text: str, message: str) -> None:
        self.write(name, text)
        self.git("add", name)
        self.git("commit", "-q", "-m", message)

    def test_staged_reads_the_index_not_the_working_tree(self) -> None:
        value = random_token()
        self.write("a.py", f'{PW}="{value}"\n')
        self.git("add", "a.py")
        self.write("a.py", "clean = True\n")

        result = self.scan("--staged")

        self.assertEqual(result.returncode, 1)
        self.assertIn("a.py:1: key-value", result.stdout)
        self.assertNotIn(value, result.stdout + result.stderr)

    def test_staged_passes_a_clean_index_under_a_dirty_tree(self) -> None:
        self.write("a.py", "clean = True\n")
        self.git("add", "a.py")
        self.write("a.py", f'{PW}="{random_token()}"\n')

        self.assertEqual(self.scan("--staged").returncode, 0)

    def test_staged_utf16_env_file_is_blocked(self) -> None:
        (self.repo / ".env.local").write_bytes(
            f"DB_{PW.upper()}={random_token()}\n".encode("utf-16")
        )
        self.git("add", "-f", ".env.local")

        self.assertEqual(self.scan("--staged").returncode, 1)

    def test_staged_binary_is_named_on_stderr(self) -> None:
        (self.repo / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + bytes(range(256)))
        self.git("add", "img.png")

        result = self.scan("--staged")

        self.assertEqual(result.returncode, 0)
        self.assertIn("img.png", result.stderr)

    def test_all_reads_tracked_files_only(self) -> None:
        self.write("untracked.py", f'{PW}="{random_token()}"\n')
        self.assertEqual(self.scan("--all").returncode, 0)

        self.git("add", "untracked.py")
        self.assertEqual(self.scan("--all").returncode, 1)

    def test_history_finds_a_value_a_later_commit_removed(self) -> None:
        self.commit("a.py", f'x = 1\n{PW}="{random_token()}"\n', "add")
        self.commit("a.py", "x = 1\n", "remove")

        self.assertEqual(self.scan("--all").returncode, 0)
        result = self.scan("--history")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"^[0-9a-f]{7,}:a\.py:2: key-value")

    def test_history_on_a_range_skips_older_commits(self) -> None:
        self.commit("a.py", f'{PW}="{random_token()}"\n', "old")
        self.commit("b.py", "clean = True\n", "new")

        self.assertEqual(self.scan("--history", "HEAD~1..HEAD").returncode, 0)

    def test_history_keeps_doc_rules_for_a_path_with_a_space(self) -> None:
        token_name = "API_" + "TOKEN"
        self.commit("doc notes.md", f'x\n{PW}="{random_token()}"\n{token_name}=plain\n', "doc")

        result = self.scan("--history")

        self.assertIn(":doc notes.md:2: key-value", result.stdout)
        self.assertIn(":doc notes.md:3: env-assignment", result.stdout)

    def test_history_ignores_a_no_prefix_diff_setting(self) -> None:
        self.git("config", "diff.noprefix", "true")
        self.commit("a.py", f'{PW}="{random_token()}"\n', "add")

        self.assertEqual(self.scan("--history").returncode, 1)

    def test_history_reads_a_merge_commit(self) -> None:
        self.commit("a.py", "x = 1\n", "base")
        self.git("checkout", "-q", "-b", "side")
        self.commit("b.py", "y = 2\n", "side")
        self.git("checkout", "-q", "-")
        self.commit("c.py", "z = 3\n", "main")
        self.git("merge", "--no-ff", "--no-commit", "side")
        self.write("evil.py", f'{PW}="{random_token()}"\n')
        self.git("add", "evil.py")
        self.git("commit", "-q", "-m", "merge")

        result = self.scan("--history")

        self.assertEqual(result.returncode, 1)
        self.assertIn("evil.py:1: key-value", result.stdout)

    def test_a_non_ascii_path_prints_readably_without_an_encoding_setting(self) -> None:
        self.write("café.py", f'{PW}="{random_token()}"\n')
        self.git("add", "café.py")
        env = {k: v for k, v in os.environ.items() if k != "PYTHONIOENCODING"}

        result = self.scan("--staged", env=env)

        self.assertIn("café.py:1: key-value", result.stdout)

    def test_exactly_one_mode(self) -> None:
        self.assertEqual(self.scan().returncode, 2)
        self.assertEqual(self.scan("--all", "--staged").returncode, 2)


class TheRepository(unittest.TestCase):
    def test_no_tracked_file_carries_a_secret(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--all"],
            cwd=HERE,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
