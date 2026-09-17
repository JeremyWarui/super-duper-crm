"""Find passwords, keys and tokens in files before they reach a commit.

    python tools/secret-scan/scan.py --staged         the files about to be committed
    python tools/secret-scan/scan.py --all            every tracked file
    python tools/secret-scan/scan.py --history [REV]  every line ever added (all refs by default)
    python tools/secret-scan/scan.py PATH [PATH ...]  these files

Exits 1 when anything is found. Values never print, so a CI log cannot repeat them.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ALLOW_FILE = Path(__file__).resolve().with_name("allow.txt")

SENSITIVE = (
    r"(?:passw(?:or)?d|pwd|[_-]pass|secret(?:[_-]?key)?|api[_-]?key"
    r"|access[_-]?key(?:[_-]?id)?|private[_-]?key|token)"
)
_OP = r"(?:!==?|===?|=(?![=>]))"
_VALUE = r"""(?:[rbuf]{1,2})?(?P<q>["'`])(?P<v>(?:\\.|[^\\\n])*?)(?P=q)"""

# A sensitive name given a string literal: `password="..."`, `"api_key": "..."`,
# `setenv("DB_PASSWORD", "...")`, `env["TOKEN"] = "..."`, `password: str = "..."`.
KEY_VALUE = re.compile(
    rf"""(?ix)
    (?:
        (?P<kq>["'`])[\w.-]*?{SENSITIVE}(?P=kq)\]?\s*(?::(?!:)|{_OP})
      | (?P<eq>["'`])[A-Za-z0-9_]*?{SENSITIVE}(?P=eq)\s*,
      | (?<![\w$.-])(?:[a-z_$][\w$.-]*?)?{SENSITIVE}(?![\w$-])
        (?:\s*:\s*[a-z_][\w\[\],|.\ ]*?\s*{_OP}|\s*:(?!:)|\s*{_OP})
    )
    \s*{_VALUE}
    """
)

PRIVATE_KEY = re.compile(r"(?P<v>-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----)")

PROVIDER_KEY = re.compile(
    r"""(?x)(?P<v>
        \b(?:AKIA|ASIA)[0-9A-Z]{16}\b
      | \bgh[pousr]_[A-Za-z0-9]{30,}
      | \bgithub_pat_[A-Za-z0-9_]{22,}
      | \bxox[abprs]-[A-Za-z0-9-]{10,}
      | \b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}
      | \bAIza[0-9A-Za-z_-]{35}
      | \bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}
      | \bnpm_[A-Za-z0-9]{30,}
      | \bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}
      | \bFlyV1\ fm\d_[A-Za-z0-9+/=_-]{20,}
    )"""
)

JWT = re.compile(r"(?P<v>\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")

AUTH_HEADER = re.compile(
    r"""(?i)\b(?:proxy-)?authorization\b["'`]?\s*[:=,]\s*["'`]?\s*(?:bearer|token|basic)\s+"""
    r"""(?P<v>[A-Za-z0-9._~+/=-]{8,})"""
)

URL_CREDENTIALS = re.compile(r"""(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@"'`<>]*:(?P<v>[^\s/@"'`<>]+)@""")

# A password flag and its value, on a command line or in an argument list.
CLI_FLAG = re.compile(
    r"""(?i)(?<![\w-])--?(?:[a-z0-9]+[_-])*(?:passw(?:or)?d|pwd|pass|secret|token|api[_-]?key)"""
    r"""(?:=|[ \t]+)["']?(?P<v>[^\s"'`<>$\\{-][^\s"'`\\]*)"""
)
CLI_LIST = re.compile(
    r"""(?i)["'`]--?[\w-]*?(?:passw(?:or)?d|pwd|pass|secret|token|api[_-]?key)["'`]"""
    r"""\s*,\s*["'`](?P<v>[^"'`\n]+)["'`]"""
)
MYSQL_PASSWORD = re.compile(
    r"""\bmysql(?:dump|admin|sh)?\b.*?(?<![\w-])-p(?P<v>[^\s"'`<$-][^\s"'`]*)"""
)
CURL_USER = re.compile(
    r"""(?<![\w-])(?:-u|--user)[ \t]+["']?[^\s:"'`@]+:(?P<v>[^\s"'`@]+)["']?(?=[\s`|]|$)"""
)

# `DB_PASSWORD=value`, anywhere on the line, in docs, env files and config.
ENV_UPPER = re.compile(
    rf"""(?i)(?<![\w$.-])(?:(?:export|set|env|arg)[ \t]+)?(?P<k>[a-z0-9_]*?{SENSITIVE})"""
    r"""[ \t]*=[ \t]*["']?(?P<v>[^\s"'`#<$][^\s"'`#]*)"""
)
# `password=value` or, in config, `password: value`, at the start of a line.
ENV_LINE = re.compile(
    rf"""(?i)^[ \t]*(?:export[ \t]+|set[ \t]+|-[ \t]+)?(?P<k>[a-z0-9_.:/-]*?{SENSITIVE})"""
    r"""[ \t]*(?P<sep>[=:])[ \t]*["']?(?P<v>[^\s"'`#<$][^\s"'`#]*)"""
)
# Dockerfile `ENV DB_PASSWORD value`.
DOCKER_SPACE = re.compile(
    rf"""(?i)^[ \t]*(?:env|arg)[ \t]+[a-z0-9_]*?{SENSITIVE}[ \t]+"""
    r"""["']?(?P<v>[^\s"'`#<$=][^\s"'`#]*)"""
)
ENV_SAFE_VALUES = {"true", "false", "null", "none", "~", "|", ">"}

NETRC_PASSWORD = re.compile(r"""(?i)(?:^|\s)password[ \t]+(?P<v>\S+)""")
PGPASS_LINE = re.compile(r"""^(?!#)[^:\s]*:[^:\s]*:[^:\s]*:[^:\s]*:(?P<v>\S.*)$""")

# A made-up password that names itself: a qualifier first, or four or more parts.
NAMED_SLUG = re.compile(r"""(?=(?P<q>["'`])(?P<v>[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)+)(?P=q))""")
SLUG_WORDS = re.compile(r"(?i)passw|secret|pwd")
SLUG_QUALIFIER = re.compile(
    r"(?i)a|an|the|my|your|our|some|not|no|test|fake|dummy|sample|example|super|very|real|long"
    r"|strong|chosen|pinned|another|other|wrong|bad|good|weak|valid|invalid"
)

# Letters and digits whose case and class keep changing, like a generated key.
TOKEN_QUOTED = re.compile(r"""(?=(?P<q>["'`])(?P<v>[A-Za-z0-9]{9,64})(?P=q))""")
TOKEN_WORD = re.compile(r"""(?<![\w$./+=%-])(?P<v>[A-Za-z0-9]{9,64})(?![\w/+=%-])""")

WORD_DIGITS = re.compile(r"""(?=(?P<q>["'`])(?P<v>[A-Za-z]+[0-9]+)(?P=q))""")
WORD_DIGITS_WORDS = re.compile(r"(?i)pass|secret|admin|qwerty|welcome|login")

PROSE = re.compile(r"[A-Z][a-z]+|[A-Z][\w'’,.!?()-]*(?: +[\w'’,.!?()-]+)+")
URL_PLACEHOLDER = re.compile(
    r"(?:[A-Z]+_)*(?:USER(?:NAME)?|PASS(?:WORD)?|PWD|SECRET|TOKEN|KEY|CHANGEME|X+)"
)

PROSE_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}
CONFIG_SUFFIXES = {".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties"}
CONFIG_NAMES = {".npmrc", ".pypirc"}
ENV_SUFFIXES = {".env", ".example", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"}
ENV_NAMES = {"dockerfile", "containerfile", "makefile", ".envrc"}

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    value: str
    commit: str = ""

    def render(self) -> str:
        where = f"{self.commit}:{self.path}" if self.commit else self.path
        return f"{where}:{self.line}: {self.rule}: {mask(self.value)}"


def mask(value: str) -> str:
    return f"****** ({len(value)} chars)"


def file_kind(path: str) -> str:
    """The kind of file, which decides the rules it gets."""
    name = PurePosixPath(path).name.lower()
    suffix = PurePosixPath(name).suffix
    if name in (".netrc", "_netrc"):
        return "netrc"
    if name == ".pgpass":
        return "pgpass"
    if name.startswith((".env", "dockerfile.")) or name in ENV_NAMES or suffix in ENV_SUFFIXES:
        return "env"
    if name in CONFIG_NAMES or suffix in CONFIG_SUFFIXES:
        return "config"
    if suffix in PROSE_SUFFIXES:
        return "prose"
    return "code"


def _placeholder(value: str) -> bool:
    v = value.strip()
    return (
        "{" in v
        or v.startswith("$")
        or bool(re.fullmatch(r"<[^<>]+>", v))
        or set(v) <= set("*.+")
        or "REDACTED" in v.upper()
    )


SEGMENT = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")


def _looks_random(value: str) -> bool:
    """All three classes, changing often, in runs too short to be words."""
    kinds = ["d" if c.isdigit() else "u" if c.isupper() else "l" for c in value]
    if (
        set(kinds) != {"d", "u", "l"}
        or sum(a != b for a, b in zip(kinds, kinds[1:], strict=False)) < 6
    ):
        return False
    return len(value) / len(SEGMENT.findall(value)) < 2.5


def _word_digits(value: str) -> bool:
    letters = value.rstrip("0123456789")
    digits = len(value) - len(letters)
    if WORD_DIGITS_WORDS.search(letters):
        return digits >= 2
    return letters.islower() and len(letters) >= 4 and digits >= 4


def _named_slug(value: str) -> bool:
    parts = value.split("-")
    return bool(SLUG_WORDS.search(value)) and (
        bool(SLUG_QUALIFIER.fullmatch(parts[0])) or len(parts) >= 4
    )


Check = Callable[[re.Match[str]], bool]


def _rules(kind: str) -> list[tuple[str, re.Pattern[str], Check]]:
    doc = kind != "code"
    rules: list[tuple[str, re.Pattern[str], Check]] = [
        ("private-key", PRIVATE_KEY, lambda m: True),
        ("provider-key", PROVIDER_KEY, lambda m: True),
        ("jwt", JWT, lambda m: True),
        ("auth-header", AUTH_HEADER, lambda m: not _placeholder(m["v"])),
        (
            "url-credentials",
            URL_CREDENTIALS,
            lambda m: (
                not (_placeholder(m["v"]) or "*" in m["v"] or URL_PLACEHOLDER.fullmatch(m["v"]))
            ),
        ),
        ("key-value", KEY_VALUE, lambda m: not (_placeholder(m["v"]) or PROSE.fullmatch(m["v"]))),
        ("cli-flag", CLI_LIST, lambda m: not _placeholder(m["v"])),
    ]
    if doc:
        rules += [
            ("cli-flag", CLI_FLAG, lambda m: not _placeholder(m["v"])),
            ("cli-flag", CURL_USER, lambda m: not _placeholder(m["v"])),
            ("cli-flag", MYSQL_PASSWORD, lambda m: not _placeholder(m["v"])),
            (
                "env-assignment",
                ENV_UPPER,
                lambda m: m["k"] == m["k"].upper() and m["v"].lower() not in ENV_SAFE_VALUES,
            ),
        ]
    if kind in ("env", "config"):
        rules.append(
            (
                "env-assignment",
                ENV_LINE,
                lambda m: (
                    (kind == "config" or m["sep"] == "=" or m["k"] == m["k"].upper())
                    and m["v"].lower() not in ENV_SAFE_VALUES
                ),
            )
        )
    if kind == "env":
        rules.append(
            ("env-assignment", DOCKER_SPACE, lambda m: m["v"].lower() not in ENV_SAFE_VALUES)
        )
    if kind == "netrc":
        rules.append(("env-assignment", NETRC_PASSWORD, lambda m: not _placeholder(m["v"])))
    if kind == "pgpass":
        rules.append(("env-assignment", PGPASS_LINE, lambda m: not _placeholder(m["v"])))
    rules += [
        ("named-slug", NAMED_SLUG, lambda m: _named_slug(m["v"])),
        ("random-token", TOKEN_WORD if doc else TOKEN_QUOTED, lambda m: _looks_random(m["v"])),
        ("word-digits", WORD_DIGITS, lambda m: _word_digits(m["v"])),
    ]
    return rules


RULES = {kind: _rules(kind) for kind in ("prose", "env", "config", "netrc", "pgpass", "code")}


def scan_line(path: str, number: int, line: str, kind: str, commit: str = "") -> list[Finding]:
    """Findings on one line; a value caught by one rule is not reported again by another."""
    found: list[tuple[int, int, Finding]] = []
    for rule, pattern, check in RULES[kind]:
        for match in pattern.finditer(line):
            start, end = match.start("v"), match.end("v")
            if any(start < e and s < end for s, e, _ in found) or not check(match):
                continue
            found.append((start, end, Finding(path, number, rule, match["v"], commit)))
    return [finding for _, _, finding in sorted(found, key=lambda item: item[0])]


def scan_text(path: str, text: str) -> list[Finding]:
    kind = file_kind(path)
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        findings.extend(scan_line(path, number, line, kind))
    return findings


def decode(data: bytes) -> str | None:
    """The text of a file in UTF-8 or UTF-16, or None when it is binary."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    head = data[:4096]
    if b"\0" not in head:
        return data.decode("utf-8", errors="replace")
    quarter = len(head) // 4
    odd, even = head[1::2].count(0), head[0::2].count(0)
    if odd > quarter and even == 0:
        return data.decode("utf-16-le", errors="replace")
    if even > quarter and odd == 0:
        return data.decode("utf-16-be", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def load_allow(file: Path = ALLOW_FILE) -> list[str]:
    """Path globs to skip, one per line; `#` starts a comment."""
    if not file.exists():
        return []
    lines = (line.strip() for line in file.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def allowed(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def git(*args: str, cwd: Path) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-c", "log.showsignature=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    ).stdout


def _scan_blob(path: str, data: bytes, skipped: list[str]) -> list[Finding]:
    text = decode(data)
    if text is None:
        skipped.append(path)
        return []
    return scan_text(path, text)


def scan_paths(paths: Iterable[str], allow: list[str], skipped: list[str]) -> Iterator[Finding]:
    for path in paths:
        name = Path(path).as_posix()
        if allowed(name, allow) or not Path(path).is_file():
            continue
        yield from _scan_blob(name, Path(path).read_bytes(), skipped)


def scan_tracked(root: Path, allow: list[str], skipped: list[str]) -> Iterator[Finding]:
    for path in git("ls-files", "-z", cwd=root).decode("utf-8").split("\0"):
        file = root / path
        if not path or allowed(path, allow) or not file.is_file():
            continue
        yield from _scan_blob(path, file.read_bytes(), skipped)


def scan_staged(root: Path, allow: list[str], skipped: list[str]) -> Iterator[Finding]:
    """The index copy of each added or changed file, which is what gets committed."""
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", cwd=root)
    for path in names.decode("utf-8").split("\0"):
        if not path or allowed(path, allow):
            continue
        yield from _scan_blob(path, git("show", f":{path}", cwd=root), skipped)


def _diff_path(header: str) -> str:
    """The path on a `+++ b/...` line, unquoted, or "" for a deleted file."""
    rest = header[4:].rstrip("\t")
    if rest.startswith('"') and rest.endswith('"'):
        escaped = rest[1:-1].encode("ascii", "backslashreplace").decode("unicode_escape")
        rest = escaped.encode("latin-1").decode("utf-8", errors="replace")
    return rest[2:] if rest.startswith("b/") else ""


def scan_history(root: Path, allow: list[str], rev: str = "") -> Iterator[Finding]:
    """Every line any commit added, including ones a later commit removed."""
    log = git(
        "log",
        rev or "--all",
        "-p",
        "-U0",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--diff-merges=first-parent",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "--format=%x00%h",
        cwd=root,
    )
    commit = path = kind = ""
    number = 0
    in_header = False
    for raw in log.decode("utf-8", errors="replace").split("\n"):
        if raw.startswith("\0"):
            commit, path, in_header = raw[1:], "", False
        elif raw.startswith("diff --git "):
            path, in_header = "", True
        elif in_header and raw.startswith("+++ "):
            path = _diff_path(raw)
            kind = file_kind(path)
            if allowed(path, allow):
                path = ""
        elif hunk := HUNK.match(raw):
            number, in_header = int(hunk[1]), False
        elif not in_header and raw.startswith("+") and path:
            yield from scan_line(path, number, raw[1:], kind, commit)
            number += 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--staged", action="store_true", help="the files about to be committed")
    parser.add_argument("--all", action="store_true", help="every tracked file")
    parser.add_argument(
        "--history",
        nargs="?",
        const="",
        default=None,
        metavar="REV",
        help="every line ever added, on all refs or on REV",
    )
    parser.add_argument("paths", nargs="*", help="these files")
    args = parser.parse_args(argv)
    if sum([args.staged, args.all, args.history is not None, bool(args.paths)]) != 1:
        parser.error("pick exactly one of --staged, --all, --history or paths")

    allow = load_allow()
    skipped: list[str] = []
    if args.paths:
        findings = list(scan_paths(args.paths, allow, skipped))
    else:
        root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd()).decode("utf-8").strip())
        if args.staged:
            findings = list(scan_staged(root, allow, skipped))
        elif args.all:
            findings = list(scan_tracked(root, allow, skipped))
        else:
            findings = list(scan_history(root, allow, args.history))

    for finding in findings:
        print(finding.render())
    if skipped:
        print(f"Skipped {len(skipped)} binary file(s): {', '.join(skipped)}", file=sys.stderr)
    if findings:
        print(
            f"\n{len(findings)} possible secret(s). Generate the value at runtime, "
            "read it from the environment, or write a <placeholder>.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
