#!/usr/bin/env python3
"""Validate Alpha Apps baseline structure and repository-specific status metadata."""

from __future__ import annotations

import hashlib
import html
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NoReturn


BASELINE_SOURCE_TRUTH_FILES = ("docs/intent.md", "docs/requirements.md", "docs/architecture.md")
CONTROL_PLANE_REPOS = {".github", "control-plane"}
DEFINITION_ONLY_FILES = {"PROJECT.md", "AGENTS.md", "docs/glossary.md"} | set(
    BASELINE_SOURCE_TRUTH_FILES
)
GIT_ENV_OVERRIDES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")
MAX_LEADING_COMMENT_LINES = 20
MAX_FRONTMATTER_LINES = 200
MAX_DIAGNOSTIC_STATUS_LENGTH = 40
SENSITIVE_STATUS_PATTERN = re.compile(
    r"(access[-_]?token|api[-_]?key|key|password|refresh[-_]?token|secret|session|token|"
    r"AA_CANARY_SECRET|FORGINGALPHA_CANARY|DO_NOT_PERSIST|"
    r"sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|xox[baprs]-|"
    r"BE" r"GIN [A-Z ]*PRI" r"VATE KEY|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|"
    r"\b\d{3}-\d{2}-\d{4}\b|"
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b)",
    re.IGNORECASE,
)
ROOT_MARKERS = (
    Path.home() / "src/github.com/forgingalpha",
    Path.home() / "Development/work/forgingalpha",
    Path.home() / "wt",
)


@dataclass(frozen=True)
class BaselineStatus:
    path: str
    status: str | None
    problem: str | None


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV_OVERRIDES:
        env.pop(key, None)
    return env


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=git_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fail(what: str, why: str, how: str, details: str | None = None) -> NoReturn:
    print(f"✗ {what}", file=sys.stderr)
    print(f"  WHAT: {what}", file=sys.stderr)
    print(f"  WHY: {why}", file=sys.stderr)
    print(f"  HOW: {how}", file=sys.stderr)
    if details:
        print(details, file=sys.stderr)
    raise SystemExit(1)


def git_stdout(repo: Path, *args: str) -> str:
    result = run_git(repo, *args)
    if result.returncode != 0:
        fail(
            f"git {' '.join(args)} failed",
            "source-truth policy needs git history to compare the branch with its base ref.",
            "run from a valid checkout with the configured base ref fetched.",
            result.stderr.strip() or result.stdout.strip(),
        )
    return result.stdout.strip()


def repo_root() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        fail(
            "not inside a git repository",
            "source-truth policy is defined relative to a repository worktree.",
            "run this action after actions/checkout.",
            result.stderr.strip(),
        )
    return Path(result.stdout.strip())


def origin_url(repo: Path) -> str | None:
    result = run_git(repo, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def repo_from_remote(url: str) -> str | None:
    match = re.search(r"github\.com[:/]forgingalpha/([^/\s]+?)(?:\.git)?$", url, re.IGNORECASE)
    return match.group(1) if match else None


def repo_from_path(repo: Path) -> str | None:
    resolved = repo.resolve()
    for root in ROOT_MARKERS:
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        if relative.parts:
            return relative.parts[0]
    marker = "/src/github.com/forgingalpha/"
    normalized = resolved.as_posix().lower()
    if marker in normalized:
        return normalized.split(marker, 1)[1].split("/", 1)[0]
    return None


def alphaapps_repo_name(repo: Path) -> str | None:
    remote = origin_url(repo)
    if remote:
        detected = repo_from_remote(remote)
        if detected:
            return detected
    return repo_from_path(repo)


def repo_kind(repo_name: str) -> str:
    configured = os.environ.get("ALPHAAPPS_POLICY_REPO_KIND", "auto")
    if configured in {"code", "control-plane"}:
        return configured
    return "control-plane" if repo_name.lower() in CONTROL_PLANE_REPOS else "code"


def default_base_ref(repo_name: str) -> str:
    configured = os.environ.get("ALPHAAPPS_POLICY_BASE_REF", "auto")
    if configured and configured != "auto":
        return configured
    return "main" if repo_kind(repo_name) == "control-plane" else "dev"


def resolve_ref(repo: Path, ref: str) -> str:
    candidates = [ref] if ref.startswith("origin/") else [f"origin/{ref}", ref]
    for candidate in candidates:
        result = run_git(repo, "rev-parse", "--verify", f"{candidate}^{{commit}}")
        if result.returncode == 0:
            return candidate
    fail(
        f"base ref not found: {ref}",
        "changed-file lifecycle policy must compare this branch with the configured base branch.",
        "fetch the base branch or pass base-ref with an available ref.",
    )


def review_head(repo: Path) -> str:
    current_head = git_stdout(repo, "rev-parse", "HEAD")
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        pr_head = run_git(repo, "rev-parse", "--verify", "HEAD^2^{commit}")
        if pr_head.returncode == 0:
            return pr_head.stdout.strip()
    return current_head


def changed_file_statuses(repo: Path, old: str, new: str) -> list[tuple[str, str, str | None]]:
    output = git_stdout(repo, "diff", "--name-status", "--diff-filter=ACMRDT", f"{old}..{new}")
    statuses: list[tuple[str, str, str | None]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        old_path = parts[1].strip()
        new_path = parts[2].strip() if status.startswith(("R", "C")) and len(parts) > 2 else None
        statuses.append((status, new_path or old_path, old_path if new_path else None))
    return statuses


def paths_from_statuses(statuses: list[tuple[str, str, str | None]]) -> list[str]:
    paths = []
    for status, path, old_path in statuses:
        paths.append(path)
        if status.startswith("R") and old_path:
            paths.append(old_path)
    return paths


def read_frontmatter(path: Path) -> tuple[list[str], str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            if first.startswith("<!--"):
                for _ in range(MAX_LEADING_COMMENT_LINES):
                    if not first or "-->" in first:
                        break
                    first = handle.readline()
                if "-->" not in first:
                    return [], "malformed leading HTML comment before YAML frontmatter"
                first = handle.readline()
                for _ in range(MAX_LEADING_COMMENT_LINES):
                    if not first or first.strip():
                        break
                    first = handle.readline()
                if first and not first.strip():
                    return [], "missing YAML frontmatter"
            if first.rstrip() != "---":
                return [], "missing YAML frontmatter"
            lines: list[str] = []
            for line in handle:
                if line.rstrip() == "---":
                    return lines, None
                lines.append(line.rstrip("\n"))
                if len(lines) > MAX_FRONTMATTER_LINES:
                    return [], "malformed YAML frontmatter: missing closing ---"
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], f"could not read file: {exc}"
    return [], "malformed YAML frontmatter: missing closing ---"


def frontmatter_values(lines: list[str]) -> dict:
    try:
        import yaml
    except ImportError:
        fail(
            "PyYAML is unavailable",
            "source-truth validation requires the shared CI YAML parser; syntax cannot be guessed.",
            "provision Python 3 with PyYAML on the runner before invoking ci-alphaapps-policy.",
        )

    class UniqueMappingLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            self.flatten_mapping(node)
            mapping = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise ValueError("duplicate YAML key")
                mapping[key] = self.construct_object(value_node, deep=deep)
            return mapping

    try:
        values = yaml.load("\n".join(lines), Loader=UniqueMappingLoader)
    except (yaml.YAMLError, ValueError, TypeError):
        # Parser diagnostics may contain sensitive source text.
        raise ValueError("malformed YAML frontmatter or duplicate keys") from None
    if not isinstance(values, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    return values


@dataclass(frozen=True)
class ReadmeIntent:
    metadata: dict
    canonical: bytes
    outside: tuple[bytes, bytes]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical).hexdigest()


def leading_metadata(lines: list[str]) -> tuple[dict, int]:
    if not lines or lines[0] != "---":
        return {}, 0
    try:
        end = lines.index("---", 1, MAX_FRONTMATTER_LINES + 2)
    except ValueError:
        raise ValueError("missing closing YAML frontmatter delimiter") from None
    return frontmatter_values(lines[1:end]), end + 1


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)")
_SETEXT = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
_THEMATIC = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_LIST = re.compile(r"^ {0,3}([-+*]|[0-9]{1,9}[.)])( +|$)")
_REFERENCE = re.compile(r"^\[((?:\\.|[^\[\]\\]){1,999})\]:[ \t]*")
_OPEN_LABEL = re.compile(r"^\[(?:\\.|[^\[\]\\])*$")
_TAG = re.compile(r"^ {0,3}</?([a-z][a-z0-9-]*)(?=[ \t>]|/>|$)", re.I | re.ASCII)
_BLOCK_TAGS = frozenset("""
    address article aside base basefont blockquote body caption center col colgroup
    dd details dialog dir div dl dt fieldset figcaption figure footer form frame
    frameset h1 h2 h3 h4 h5 h6 head header hr html iframe legend li link main menu
    menuitem nav noframes ol optgroup option p param search section summary table tbody
    td tfoot th thead title tr track ul
""".split())
_RAW_TAG = re.compile(r"^ {0,3}<(script|pre|style|textarea)(?=[ \t>]|$)", re.I | re.ASCII)
_RAW_END = re.compile(r"</(?:script|pre|style|textarea)>", re.I | re.ASCII)
_BLANK = re.compile(r"^[ \t]*$")
_HTML_DELIMITERS = (
    (re.compile(r"^ {0,3}<!--"), re.compile(r"--!?>")),
    (re.compile(r"^ {0,3}<\?"), re.compile(r"\?>")),
    (re.compile(r"^ {0,3}<!\[CDATA\["), re.compile(r"\]\]>")),
    (re.compile(r"^ {0,3}<![a-zA-Z]"), re.compile(">")),
    (_RAW_TAG, _RAW_END),
)
_ATTR_VALUE = r"""(?:[^\x00-\x20"'=<>`]+|'[^']*'|"[^"]*")"""
_ATTR = rf"(?:[ \t]+[a-zA-Z_:][a-zA-Z0-9_.:-]*(?:[ \t]*=[ \t]*{_ATTR_VALUE})?)"
_WHOLE_TAG = re.compile(
    rf"^ {{0,3}}(?:<[a-zA-Z][a-zA-Z0-9-]*{_ATTR}*[ \t]*/?>|</[a-zA-Z][a-zA-Z0-9-]*[ \t]*>)[ \t]*$"
)


def _html_end(line: str, previous_text: bool):
    for opening, closing in _HTML_DELIMITERS:
        if opening.match(line):
            return closing
    tag = _TAG.match(line)
    if tag and tag[1].lower() in _BLOCK_TAGS:
        return _BLANK
    if _WHOLE_TAG.fullmatch(line):
        # A standalone inline/custom tag can start a raw block only outside
        # a paragraph. Avoid guessing paragraph continuation across containers.
        if previous_text:
            raise ValueError("ambiguous standalone HTML tag after README text")
        return _BLANK
    return None


def _html_block_closed(closing: re.Pattern, line: str) -> bool:
    match = closing.search(line)
    if match is not None and match[0] == "--!>":
        raise ValueError("ambiguous README HTML comment terminator")
    return match is not None


def _has_prose(text: str) -> bool:
    visible = re.sub(r"<!--.*?--!?>|<[^>]*>", "", text)
    return bool(re.search(r"[^\W_]", visible))


def _reference_end(lines: list[str], index: int, text: str) -> int | None:
    """Find the end of a link reference definition, including a continued title."""
    if not text.startswith("["):
        return None
    last = index
    while len(text) <= 1000 and _OPEN_LABEL.fullmatch(text):
        if last + 1 == len(lines) or not lines[last + 1].strip():
            return None
        last += 1
        text += "\n" + lines[last].lstrip(" \t")
    label = _REFERENCE.match(text)
    if not label:
        return None
    destination = text[label.end():].rstrip(" \t")
    if not destination and last + 1 < len(lines) and lines[last + 1].strip():
        last += 1
        destination = lines[last].strip(" \t")
    # Destinations ending at whitespace can be followed by a quoted title.
    target = re.match(r"(?:<(?:\\.|[^<>\\])*>|(?:\\.|[^\s<>\\])+)(?:[ \t]+|$)", destination)
    if not target:
        return None
    title = destination[target.end():]
    if not title and last + 1 < len(lines):
        following = lines[last + 1].strip(" \t")
        if following.startswith(('"', "'", "(")):
            title = following
            last += 1
    if title:
        closer = {'"': '"', "'": "'", "(": ")"}.get(title[0])
        if closer is None:
            return None
        segment = title[1:]
        while not re.search(rf"(?<!\\){re.escape(closer)}[ \t]*$", segment):
            if last + 1 == len(lines) or not lines[last + 1].strip():
                raise ValueError("ambiguous README link reference title")
            last += 1
            segment = lines[last]
    return last


def _readme_lines(lines: list[str], first: int, containers: list[list[str]] | None = None):
    """Yield root headings and visible prose at their original line indices."""
    fence = html_end = None
    previous_text = False
    list_indent = 0
    quote = False
    definition_end = -1
    list_lines = None
    last_quote = -2
    for index in range(first, len(lines)):
        line = lines[index]
        if index <= definition_end:
            if _ATX.match(line) or _FENCE.match(line) or _SETEXT.fullmatch(line):
                raise ValueError("ambiguous Markdown block inside a README link definition")
            previous_text = False
            continue
        if html_end is not None:
            if _html_block_closed(html_end, line):
                html_end = None
            continue

        marker = _FENCE.match(line)
        if fence is not None:
            if marker and marker[1].startswith(fence) and not marker[2].strip(" \t"):
                fence = None
            continue

        expanded = line.expandtabs(4)
        content = expanded.lstrip(" ")
        indent = len(expanded) - len(content)
        if not content:
            if list_indent and list_lines is not None:
                list_lines.append("")
            previous_text = quote = False
            continue
        if list_indent and indent >= list_indent:
            # Nested fences, HTML and headings cannot govern a root boundary.
            if list_lines is not None:
                list_lines.append(expanded[list_indent:])
            previous_text = True
            continue
        if indent >= 4 or content.startswith(">"):
            quote = indent < 4 and content.startswith(">")
            if quote:
                list_indent = 0
                if containers is not None:
                    if last_quote != index - 1:
                        quote_lines = []
                        containers.append(quote_lines)
                    quote_lines.append(content[1:].removeprefix(" "))
                    last_quote = index
            previous_text = True
            continue

        if previous_text and _SETEXT.fullmatch(line):
            raise ValueError("unsupported Setext heading in README")
        if _THEMATIC.fullmatch(line):
            list_indent = 0
            previous_text = quote = False
            continue
        item = _LIST.match(expanded)
        if item and previous_text and not list_indent:
            # Only a nonempty bullet or a list starting at one can interrupt a paragraph.
            if not expanded[item.end():] or (item[1][0].isdigit() and int(item[1][:-1]) != 1):
                item = None
        if item:
            padding = len(item[2])
            list_indent = item.start(2) + (padding if 1 <= padding <= 4 else 1)
            item_text = expanded[list_indent:]
            if containers is not None:
                list_lines = [item_text]
                containers.append(list_lines)
            while nested := _LIST.match(item_text):
                item_text = item_text[nested.end():]
            if (not item_text.startswith((" ", ">", "<", "#", "`", "~"))
                    and _reference_end(lines, index, item_text) is None and _has_prose(item_text)):
                yield index, None
            previous_text = True
            quote = False
            continue
        if not previous_text:
            list_indent = 0
        if marker:
            if marker[1].startswith("`") and "`" in marker[2]:
                raise ValueError("ambiguous README backtick fence")
            fence = marker[1]
            previous_text = quote = False
            list_indent = 0
            continue

        if line.lstrip(" ").startswith("<"):
            html_end = _html_end(line, previous_text)
            if html_end is not None:
                if _html_block_closed(html_end, line):
                    html_end = None
                previous_text = quote = False
                list_indent = 0
                continue

        heading = _ATX.match(line)
        if heading:
            yield index, heading
            previous_text = quote = False
            list_indent = 0
        else:
            if not quote:
                reference_end = _reference_end(lines, index, content)
                if reference_end is not None:
                    definition_end = reference_end
                elif _has_prose(content):
                    yield index, None
            previous_text = True
    if fence is not None or html_end not in (None, _BLANK):
        raise ValueError("unterminated README example or HTML block")


# Recognize ordinary link labels without rendering their targets. Ambiguous rich
# heading syntax in the preamble must never silently take the published anchor.
_HEADING_LINK = re.compile(r"\[([^\[\]\\]*)\](?:\([^()\\]*\)|\[[^\[\]\\]*\])")


def _check_anchor_heading(title: str, name: str) -> None:
    visible = html.unescape(_HEADING_LINK.sub(r"\1", title)).strip().lower()
    if "![" in title or re.search(r":[A-Za-z0-9_+-]+:", title) or any(char in visible for char in "<>[]$"):
        raise ValueError(f"ambiguous inline markup in a README heading before {name}")
    # Emphasis, backticks and punctuation can disappear in GitHub's anchor.
    # Keep visible spaces and hyphens, which distinguish e.g. 'In tent'.
    candidate = "".join(char for char in visible if char.isalnum() or char in " -")
    if candidate.strip().replace(" ", "-") == name.lower().replace(" ", "-"):
        raise ValueError(f"another README heading can claim the {name} anchor")


def _check_earlier_anchors(preamble: list[str], name: str, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError("excessive README Markdown container nesting before selected section")
    containers = []
    for _, heading in _readme_lines(preamble, 0, containers):
        if heading:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2] or "")
            _check_anchor_heading(title, name)
    # A heading inside a quote or list can claim a rendered anchor while never
    # selecting or ending a governing section. Preserve its own fence/HTML state.
    for body in containers:
        _check_earlier_anchors(body, name, depth + 1)


SECTION_NAMES = ("Intent", "Requirements", "Architecture", "Local Instructions")


@dataclass(frozen=True)
class ReadmeSections:
    metadata: dict
    sections: dict[str, bytes]
    # Keep boundary positions distinct; moving text between boundaries is an edit.
    outside: tuple[bytes, ...]
    instructions: bytes


def readme_sections(data: bytes, names: tuple[str, ...] = SECTION_NAMES) -> ReadmeSections:
    """Select exact root sections using the established README Intent grammar."""
    text = data.decode("utf-8")
    if "\r" in text or "\x00" in text or text.startswith("\ufeff"):
        raise ValueError("README must use UTF-8 without BOM and LF line endings")
    lines = text.split("\n")
    if lines[0].rstrip(" \t") == "---" and lines[0] != "---":
        raise ValueError("malformed README frontmatter delimiter")
    metadata, first = leading_metadata(lines)
    titles = {name.casefold(): name for name in names}
    spans = {}
    start = current = None
    meaningful = False

    def finish(end):
        if current is not None:
            if not meaningful:
                raise ValueError(f"missing or empty README {current} section")
            spans[current] = start, end

    for index, heading in _readme_lines(lines, first):
        if heading is None:
            meaningful = True
            continue
        title = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2] or "").strip(" \t")
        name = titles.get(title.casefold())
        if len(heading[1]) > 2:
            continue
        finish(index)
        current = None
        if name is not None and heading[1] == "##":
            if lines[index] != "## " + name or name in spans:
                raise ValueError(f"ambiguous or duplicate README {name} heading")
            _check_earlier_anchors(lines[first:index], name)
            current, start, meaningful = name, index, False
    finish(len(lines))
    if tuple(spans) != names:
        raise ValueError("missing or out-of-order README section: " + ", ".join(names))

    raw_lines = [line + "\n" for line in lines[:-1]] + [lines[-1]]
    sections, outside, instructions = {}, [], b""
    previous = first
    for name, (start, end) in spans.items():
        body = "\n".join(lines[start:end]).rstrip("\n") + "\n"
        front = "".join(raw_lines[:first]) if name == "Intent" else ""
        sections[name] = (front + body).encode()
        if name == "Local Instructions":
            instructions = "".join(raw_lines[start:end]).encode()
        else:
            outside.append("".join(raw_lines[previous:start]).encode())
            previous = end
    outside.append("".join(raw_lines[previous:]).encode())
    return ReadmeSections(metadata, sections, tuple(outside), instructions)


def readme_intent(data: bytes) -> ReadmeIntent:
    selection = readme_sections(data, ("Intent",))
    return ReadmeIntent(selection.metadata, selection.sections["Intent"], selection.outside)


def canonical_control_plane(repo: Path) -> bool:
    remote = origin_url(repo) or ""
    return re.fullmatch(
        r"(?:git@github\.com:|https://github\.com/|ssh://git@github\.com/)"
        r"ForgingAlpha/control-plane(?:\.git)?",
        remote,
        re.IGNORECASE,
    ) is not None


def diagnostic_status_value(status: str | None) -> str:
    if status is None:
        return "missing"
    if len(status) > MAX_DIAGNOSTIC_STATUS_LENGTH or SENSITIVE_STATUS_PATTERN.search(status):
        return "[redacted-sensitive-status]"
    return repr(status)


def baseline_status(repo: Path, relative_path: str, *, require_status: bool = True) -> BaselineStatus:
    path = repo / relative_path
    if not path.is_file():
        return BaselineStatus(relative_path, None, "missing file")
    lines, problem = read_frontmatter(path)
    if problem:
        return BaselineStatus(relative_path, None, problem)
    try:
        values = frontmatter_values(lines)
    except ValueError as error:
        return BaselineStatus(relative_path, None, str(error))
    if "status" not in values:
        return BaselineStatus(relative_path, None, "missing status" if require_status else None)
    status = values["status"]
    if not isinstance(status, str):
        return BaselineStatus(relative_path, None, "status must be a string")
    if status not in {"approved", "provisional"}:
        return BaselineStatus(relative_path, status, f"unsupported status {diagnostic_status_value(status)}")
    return BaselineStatus(relative_path, status, None)


def baseline_statuses(repo: Path, *, require_status: bool = True) -> list[BaselineStatus]:
    return [baseline_status(repo, path, require_status=require_status) for path in BASELINE_SOURCE_TRUTH_FILES]


def incomplete_baseline(statuses: list[BaselineStatus], *, require_status: bool = True) -> list[BaselineStatus]:
    accepted = {"approved"} if require_status else {None, "approved"}
    return [item for item in statuses if item.problem is not None or item.status not in accepted]


def baseline_status_details(statuses: list[BaselineStatus]) -> str:
    lines: list[str] = []
    for item in statuses:
        if item.problem:
            lines.append(f"- {item.path}: {item.problem}")
        elif item.status == "provisional":
            lines.append(f"- {item.path}: status is provisional")
    return "\n".join(lines)


def definition_only_work_allowed(incomplete: list[BaselineStatus]) -> bool:
    return all(item.problem in (None, "missing file") for item in incomplete)


def definition_only_path(path: str) -> bool:
    if path in DEFINITION_ONLY_FILES:
        return True
    parts = PurePosixPath(path).parts
    return len(parts) >= 3 and parts[0] == "docs" and parts[1] == "architecture"


def deleted_baseline_from_statuses(statuses: list[tuple[str, str, str | None]]) -> list[str]:
    return sorted(
        old_path or path
        for status, path, old_path in statuses
        if (status.startswith("D") and path in BASELINE_SOURCE_TRUTH_FILES)
        or (status.startswith("R") and old_path in BASELINE_SOURCE_TRUTH_FILES)
    )


def validate(repo: Path) -> int:
    # Load only the sibling shipped with this checking action, including under
    # isolated Python. Never resolve a checking module through the consumer cwd.
    import importlib.util

    module_path = Path(__file__).resolve().with_name("standalone_readme_intent.py")
    spec = importlib.util.spec_from_file_location("alphaapps_standalone_intent", module_path)
    standalone = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = standalone
    spec.loader.exec_module(standalone)
    try:
        if standalone.maybe_validate(repo, sys.modules[__name__]):
            return 0
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        fail("Protected-base README Intent validation refused", str(error),
             "preserve the protected source selection and exact source bindings; first migrations require "
             "approved definitions, and later provisional repairs must change only selected definitions.")
    repo_name = alphaapps_repo_name(repo)
    if repo_name is None:
        print("✓ Source-truth baseline validation skipped: non-ForgingAlpha repo")
        return 0

    base_ref = default_base_ref(repo_name)
    resolved_base = resolve_ref(repo, base_ref)
    current_head = review_head(repo)
    base_sha = git_stdout(repo, "merge-base", resolved_base, current_head)
    statuses = changed_file_statuses(repo, base_sha, current_head)
    changed = paths_from_statuses(statuses)
    deleted_baseline = deleted_baseline_from_statuses(statuses)

    require_status = not canonical_control_plane(repo)
    baseline = baseline_statuses(repo, require_status=require_status)
    incomplete = incomplete_baseline(baseline, require_status=require_status)
    if incomplete:
        blocked = sorted(path for path in changed if not definition_only_path(path))
        if (
            changed
            and not blocked
            and not deleted_baseline
            and definition_only_work_allowed(incomplete)
        ):
            print(
                "✓ Source-truth baseline validation passed for "
                f"definition/backfill-only work (BASE_REF={base_ref})"
            )
            return 0
        title = "Deleted baseline source truth" if deleted_baseline else "Incomplete baseline source truth"
        details = baseline_status_details(baseline)
        if deleted_baseline:
            details = f"{details}\ndeleted baseline files:\n" + "\n".join(
                f"- {path}" for path in deleted_baseline
            )
        if blocked:
            details = f"{details}\nblocked paths:\n" + "\n".join(f"- {path}" for path in blocked)
        fail(
            title,
            "every active ForgingAlpha repo requires docs/intent.md, docs/requirements.md, "
            "and docs/architecture.md with valid repository-specific metadata before ordinary planning, "
            "implementation, maintenance, release, dependency, runtime, broad refactor, or test work.",
            "repair the baseline source-truth docs and follow their owning approval process; while the baseline is "
            "missing, malformed, or provisional, keep the diff limited to definition/backfill paths.",
            details,
        )

    print(f"✓ Source-truth baseline validation passed (BASE_REF={base_ref}); approval and Currentness are separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate(repo_root()))
