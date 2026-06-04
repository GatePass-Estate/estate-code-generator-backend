#!/usr/bin/env python3
"""
Security scanner: JS-config supply-chain attack + CI/CD tampering detector.

Covers the Lazarus 'Contagious Interview' / BeaverTail campaign and broader
JS supply-chain attacks. Scans config files, GitHub Actions workflows,
lockfiles, package.json lifecycle hooks, all JS/TS source files, running
processes, and persistence mechanisms.

Reference:
  https://github.com/orgs/community/discussions/188732#discussioncomment-16368443

Cross-platform: Linux, macOS, Windows. Standard library only.

Usage:
    python3 security_scanner.py                     # scan cwd
    python3 security_scanner.py --ci                # CI mode (no procs, JSON out, exit 1 on hit)
    python3 security_scanner.py --changed-only      # scan only git-changed files
    python3 security_scanner.py --scan-home --fix   # quarantine + clean infected configs
    python3 security_scanner.py --kill              # kill suspicious processes
    python3 security_scanner.py --harden            # proactive defenses
    python3 security_scanner.py --all               # scan + fix + kill + harden
    python3 security_scanner.py --watch             # continuous monitor
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

IS_WINDOWS = os.name == "nt"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
IN_CI = (
    os.environ.get("CI") == "true"
    or os.environ.get("GITHUB_ACTIONS") == "true"
)

# ---------------------------------------------------------------------------
# Config file IOC patterns
# ---------------------------------------------------------------------------

IOC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Lazarus / BeaverTail markers
    (re.compile(r"global\[\s*['\"]!['\"]\s*\]"), "global['!'] marker"),
    (re.compile(r"_\$_1e42"), "_$_1e42 obfuscation marker"),
    (
        re.compile(r"global\[['\"]_V['\"]\]\s*=\s*['\"]A4-1928['\"]"),
        "A4-1928 campaign marker",
    ),
    # Crypto RPC endpoints (C2 infrastructure)
    (re.compile(r"api\.trongrid\.io"), "TRON RPC endpoint"),
    (re.compile(r"bsc-dataseed"), "BSC RPC endpoint"),
    (re.compile(r"data-seed-prebsc"), "BSC testnet endpoint"),
    (re.compile(r"\bTronWeb\b"), "TronWeb library reference"),
    (
        re.compile(r"ethers\.providers\.JsonRpcProvider"),
        "ethers RPC provider in config",
    ),
    # Exfil endpoints
    (
        re.compile(r"icloud\.com.*upload", re.IGNORECASE),
        "iCloud exfil endpoint",
    ),
    (
        re.compile(r"\bSolana\b.*Keypair", re.IGNORECASE),
        "Solana keypair access",
    ),
    # Credential access
    (
        re.compile(r"login\.keychain", re.IGNORECASE),
        "macOS keychain reference",
    ),
    (
        re.compile(r"\.config/google-chrome|Login Data"),
        "Chrome credentials path",
    ),
    # Supply-chain extras
    (
        re.compile(
            r"process\.env\b.{0,120}(fetch|axios|http\.request|XMLHttpRequest)",
            re.IGNORECASE | re.DOTALL,
        ),
        "process.env read + network call (possible exfil)",
    ),
    (
        re.compile(
            r"(child_process|exec|execSync|spawn)\s*\(.{0,80}(curl|wget|nc\b|netcat)",
            re.IGNORECASE,
        ),
        "child_process executing network tool",
    ),
    (
        re.compile(
            r"(writeFile|writeFileSync)\s*\(.{0,120}(\.ssh|authorized_keys|id_rsa|\.aws|credentials)",
            re.IGNORECASE,
        ),
        "fs write to credential path",
    ),
    (
        re.compile(
            r"(readFile|readFileSync)\s*\(.{0,120}(id_rsa|id_ed25519|\.pem|authorized_keys)",
            re.IGNORECASE,
        ),
        "fs read of private key",
    ),
]

WHITESPACE_RUN = re.compile(r"[ \t]{200,}")
LONG_B64 = re.compile(r"['\"][A-Za-z0-9+/=_-]{500,}['\"]")
EVAL_PATTERN = re.compile(r"\beval\s*\(")
NEW_FUNCTION_PAT = re.compile(r"\bnew\s+Function\s*\(")

# eval() and new Function() are only suspicious when paired with a large file
# or another IOC — standalone use in a Babel/Jest config is normal.
EVAL_SIZE_THRESHOLD = 20_480  # 20 KB

# ---------------------------------------------------------------------------
# package.json lifecycle hook patterns
# ---------------------------------------------------------------------------

LIFECYCLE_HOOKS = {
    "preinstall",
    "postinstall",
    "preuninstall",
    "postuninstall",
    "prepare",
}

# Hook values containing these patterns are flagged as IOCs, not just warnings.
SUSPICIOUS_SCRIPT_PAT = re.compile(
    r"(curl|wget|node\s+-e|node\s+-p|base64\b|atob\s*\(|eval\s*\(|"
    r"powershell\b|iwr\b|invoke-webrequest)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Source file scanning (long encoded blob check across all JS/TS)
# ---------------------------------------------------------------------------

SOURCE_EXTENSIONS = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
SOURCE_SIZE_LIMIT = 200_000  # skip auto-generated files > 200 KB

# ---------------------------------------------------------------------------
# Workflow file IOC patterns (.github/workflows/*.yml)
# ---------------------------------------------------------------------------

WORKFLOW_IOC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(curl|wget)\b.+\|\s*(sh|bash|python3?|node)", re.IGNORECASE
        ),
        "download-pipe-execute in workflow step",
    ),
    (
        re.compile(
            r"base64\s+-d\b.+\|\s*(sh|bash|python3?|node)", re.IGNORECASE
        ),
        "base64 decode-pipe-execute in workflow",
    ),
    (
        re.compile(r"\beval\s*\$\(", re.IGNORECASE),
        "eval-subshell in workflow run step",
    ),
    (
        re.compile(
            r"echo\s+['\"]?\$\{?\w*(SECRET|TOKEN|KEY|PASSWORD|PAT)\}?['\"]?\s*\|",
            re.IGNORECASE,
        ),
        "secret value piped to command",
    ),
    (
        re.compile(r"python3?\s+-c\s+['\"].{80,}['\"]", re.IGNORECASE),
        "long inline Python payload in workflow",
    ),
    (
        re.compile(r"node\s+-e\s+['\"].{80,}['\"]", re.IGNORECASE),
        "long inline Node payload in workflow",
    ),
    (re.compile(r"atob\s*\(", re.IGNORECASE), "atob() decode in workflow"),
    # Untrusted action pinning (SHA pins are safe; version tags are acceptable;
    # arbitrary branch refs are risky)
    (
        re.compile(r"uses:\s+\S+@(?!(v\d|[0-9a-f]{40}))", re.IGNORECASE),
        "action pinned to mutable ref (not a version tag or SHA)",
    ),
]

# ---------------------------------------------------------------------------
# Lockfile suspicious URL patterns
# ---------------------------------------------------------------------------

LOCKFILE_SUSPICIOUS = re.compile(
    r'(?:^|\s)"?resolved"?\s*[":]\s*"?'
    r'(git\+https?://|git\+ssh://|http://[^"\'}\s]+|file:\.\.)',
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Process IOC patterns
# ---------------------------------------------------------------------------

PROCESS_CMDLINE_IOCS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"trongrid", re.IGNORECASE), "TRON RPC in cmdline"),
    (re.compile(r"bsc-dataseed", re.IGNORECASE), "BSC RPC in cmdline"),
    (re.compile(r"data-seed-prebsc", re.IGNORECASE), "BSC testnet in cmdline"),
    (re.compile(r"_\$_1e42"), "obfuscation marker in cmdline"),
    (re.compile(r"\bTronWeb\b"), "TronWeb in cmdline"),
    (re.compile(r"\bSolana\b.*Keypair"), "Solana keypair in cmdline"),
]

C2_HOSTS = [
    "api.trongrid.io",
    "api.shasta.trongrid.io",
    "api.nileex.io",
    "bsc-dataseed.binance.org",
    "bsc-dataseed1.defibit.io",
    "bsc-dataseed1.ninicoin.io",
    "data-seed-prebsc-1-s1.binance.org",
    "data-seed-prebsc-2-s1.binance.org",
]

# Match *.config.{js,mjs,cjs,ts} and common non-standard config names.
CONFIG_FILE_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9_.-]+\.config\.(?:js|mjs|cjs|ts)"
    r"|gatsby-config\.[mc]?js"
    r"|gatsby-node\.[mc]?js"
    r"|\.babelrc\.(?:js|cjs|mjs)"
    r"|babel\.config\.json)$"
)

LOCKFILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}

SKIP_DIRS = {
    "node_modules",
    ".git",
    ".next",
    ".nuxt",
    ".turbo",
    ".svelte-kit",
    "dist",
    "build",
    "out",
    ".cache",
    ".venv",
    "venv",
    "__pycache__",
    ".pnpm-store",
    ".yarn",
    ".vercel",
    ".vscode-server",
    "__snapshots__",
}


# ===========================================================================
# Data classes
# ===========================================================================


@dataclass
class FileFinding:
    path: Path
    size: int
    kind: str = "config"
    indicators: list[str] = field(default_factory=list)
    backup_path: Path | None = None
    cleaned: bool = False
    clean_message: str = ""


@dataclass
class ProcessFinding:
    pid: int
    score: int
    indicators: list[str]
    cmdline: str
    cwd: str = ""
    exe: str = ""
    user: str = ""
    ppid: int = 0
    killed: bool = False
    kill_message: str = ""


# ===========================================================================
# Git-aware file discovery
# ===========================================================================


def get_git_changed_files(base_ref: str | None = None) -> list[Path] | None:
    """
    Return paths changed relative to base_ref (HEAD~1 by default).
    Returns None if git is unavailable or not in a repo.
    """
    if base_ref is None:
        gh_base = os.environ.get("GITHUB_BASE_REF")
        base_ref = f"origin/{gh_base}" if gh_base else "HEAD~1"
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=ACM",
                base_ref,
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return [Path(f) for f in result.stdout.splitlines() if f.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _walk(root: Path) -> Iterator[tuple[str, list[str], list[str]]]:
    """os.walk with SKIP_DIRS pruning."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        yield dirpath, dirnames, filenames


def iter_config_targets(root: Path) -> Iterator[Path]:
    for dirpath, _, filenames in _walk(root):
        for fn in filenames:
            if CONFIG_FILE_PATTERN.match(fn) or fn in LOCKFILE_NAMES:
                yield Path(dirpath) / fn


def iter_package_json_targets(root: Path) -> Iterator[Path]:
    for dirpath, _, filenames in _walk(root):
        if "package.json" in filenames:
            yield Path(dirpath) / "package.json"


def iter_source_targets(root: Path) -> Iterator[Path]:
    for dirpath, _, filenames in _walk(root):
        for fn in filenames:
            if Path(fn).suffix in SOURCE_EXTENSIONS:
                yield Path(dirpath) / fn


def iter_workflow_targets(root: Path) -> Iterator[Path]:
    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        for p in wf_dir.iterdir():
            if p.suffix in {".yml", ".yaml"}:
                yield p


def collect_targets(
    roots: list[Path],
    changed_only: bool,
) -> tuple[list[Path], list[Path], list[Path], list[Path]]:
    """
    Return (config_targets, workflow_targets, source_targets, pkg_json_targets).
    When changed_only=True, restrict to files changed in git.
    """
    changed: set[str] | None = None
    if changed_only:
        changed_files = get_git_changed_files()
        if changed_files is not None:
            changed = {str(p.resolve()) for p in changed_files}

    config_paths: list[Path] = []
    workflow_paths: list[Path] = []
    source_paths: list[Path] = []
    pkg_paths: list[Path] = []
    seen: set[Path] = set()

    def _add(paths: list[Path], p: Path) -> None:
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        if changed is not None and str(rp) not in changed:
            return
        paths.append(rp)

    for root in roots:
        if not root.exists():
            continue
        for p in iter_config_targets(root):
            _add(config_paths, p)
        for p in iter_workflow_targets(root):
            _add(workflow_paths, p)
        for p in iter_source_targets(root):
            _add(source_paths, p)
        for p in iter_package_json_targets(root):
            _add(pkg_paths, p)

    return config_paths, workflow_paths, source_paths, pkg_paths


# ===========================================================================
# File scanning
# ===========================================================================


def scan_config_file(path: Path) -> FileFinding | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        size = path.stat().st_size
    except OSError:
        return None

    indicators: list[str] = []

    if path.name in LOCKFILE_NAMES:
        for m in LOCKFILE_SUSPICIOUS.finditer(text):
            indicators.append(f"suspicious resolved URL: {m.group(1)[:80]}")
        return (
            FileFinding(
                path=path, size=size, kind="lockfile", indicators=indicators
            )
            if indicators
            else None
        )

    for pat, label in IOC_PATTERNS:
        if pat.search(text):
            indicators.append(f"IOC: {label}")

    if WHITESPACE_RUN.search(text):
        indicators.append("hidden payload: whitespace run >200 chars")

    if LONG_B64.search(text):
        indicators.append("long encoded blob (>=500 chars)")

    has_eval = bool(EVAL_PATTERN.search(text))
    if has_eval and (size > EVAL_SIZE_THRESHOLD or indicators):
        indicators.append(
            f"eval() in {'large ' if size > EVAL_SIZE_THRESHOLD else ''}config ({size}B)"
        )

    has_new_fn = bool(NEW_FUNCTION_PAT.search(text))
    if has_new_fn and (size > EVAL_SIZE_THRESHOLD or indicators):
        indicators.append(
            f"new Function() in {'large ' if size > EVAL_SIZE_THRESHOLD else ''}config ({size}B)"
        )

    return (
        FileFinding(path=path, size=size, kind="config", indicators=indicators)
        if indicators
        else None
    )


def scan_package_json(path: Path) -> FileFinding | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        size = path.stat().st_size
    except (OSError, json.JSONDecodeError):
        return None

    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return None

    indicators: list[str] = []
    for hook in LIFECYCLE_HOOKS:
        value = scripts.get(hook)
        if value is None:
            continue
        if SUSPICIOUS_SCRIPT_PAT.search(str(value)):
            indicators.append(
                f"IOC: suspicious lifecycle script '{hook}': {str(value)[:120]}"
            )
        else:
            indicators.append(
                f"lifecycle hook '{hook}' present — verify: {str(value)[:120]}"
            )

    return (
        FileFinding(
            path=path, size=size, kind="package-json", indicators=indicators
        )
        if indicators
        else None
    )


def scan_source_file(path: Path) -> FileFinding | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None

    if size > SOURCE_SIZE_LIMIT:
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    indicators: list[str] = []
    if LONG_B64.search(text):
        indicators.append("long encoded blob (>=500 chars) in source file")

    return (
        FileFinding(path=path, size=size, kind="source", indicators=indicators)
        if indicators
        else None
    )


def scan_workflow_file(path: Path) -> FileFinding | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        size = path.stat().st_size
    except OSError:
        return None

    indicators: list[str] = []
    for pat, label in WORKFLOW_IOC_PATTERNS:
        if pat.search(text):
            indicators.append(f"IOC: {label}")

    return (
        FileFinding(
            path=path, size=size, kind="workflow", indicators=indicators
        )
        if indicators
        else None
    )


def quarantine(path: Path) -> Path:
    backup = path.with_suffix(
        path.suffix + f".malware-backup-{int(time.time())}"
    )
    shutil.copy2(path, backup)
    return backup


def clean_file(path: Path) -> tuple[bool, str]:
    """Attempt to strip trailing malicious payload after the last legit export."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, f"read failed: {e}"

    end_markers = [
        re.compile(r"export\s+default\s+[A-Za-z_$][\w$]*\s*;", re.MULTILINE),
        re.compile(
            r"module\.exports\s*=\s*[A-Za-z_$][\w$]*\s*;", re.MULTILINE
        ),
        re.compile(r"export\s+default\s+\{[\s\S]*?\}\s*;?", re.MULTILINE),
        re.compile(r"module\.exports\s*=\s*\{[\s\S]*?\}\s*;?", re.MULTILINE),
    ]
    cut = -1
    for pat in end_markers:
        m = pat.search(text)
        if m:
            cut = m.end() if cut < 0 else min(cut, m.end())

    if cut < 0:
        return False, "no legit end marker found — review manually"
    cleaned = text[:cut].rstrip() + "\n"
    if cleaned == text:
        return False, "no trailing payload to remove"
    removed = len(text) - len(cleaned)
    if removed < 50:
        return (
            False,
            f"trailing diff only {removed}B — too small to auto-clean",
        )
    path.write_text(cleaned, encoding="utf-8")
    return True, f"removed {removed}B of trailing content"


# ===========================================================================
# Process scanning
# ===========================================================================


def _list_processes_linux() -> list[dict[str, Any]]:
    procs: list[dict[str, Any]] = []
    proc_root = Path("/proc")
    if not proc_root.exists():
        return procs
    for pid_dir in proc_root.iterdir():
        if not pid_dir.name.isdigit():
            continue
        pid = int(pid_dir.name)
        try:
            cmdline_raw = (pid_dir / "cmdline").read_bytes()
            if not cmdline_raw:
                continue
            args = [
                a.decode("utf-8", "replace")
                for a in cmdline_raw.split(b"\0")
                if a
            ]
            cmdline = " ".join(args)
            stat = (pid_dir / "stat").read_text()
            m = re.match(r"\d+\s+\(.*\)\s+\S+\s+(\d+)", stat)
            ppid = int(m.group(1)) if m else 0
            try:
                cwd = os.readlink(pid_dir / "cwd")
            except OSError:
                cwd = ""
            try:
                exe = os.readlink(pid_dir / "exe")
            except OSError:
                exe = ""
            uid = ""
            try:
                for line in (pid_dir / "status").read_text().splitlines():
                    if line.startswith("Uid:"):
                        uid = line.split()[1]
                        break
            except OSError:
                pass
            procs.append(
                {
                    "pid": pid,
                    "ppid": ppid,
                    "user": uid,
                    "cmdline": cmdline,
                    "cwd": cwd,
                    "exe": exe,
                }
            )
        except (OSError, ValueError):
            continue
    return procs


def _list_processes_posix() -> list[dict[str, Any]]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid,user,command"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    procs: list[dict[str, Any]] = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid, ppid, user, cmd = parts
            procs.append(
                {
                    "pid": int(pid),
                    "ppid": int(ppid),
                    "user": user,
                    "cmdline": cmd,
                    "cwd": "",
                    "exe": "",
                }
            )
        except ValueError:
            continue
    return procs


def _list_processes_windows() -> list[dict[str, Any]]:
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | "
                "Select-Object ProcessId,ParentProcessId,Name,CommandLine,ExecutablePath | "
                "ConvertTo-Json -Depth 2",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    if not out.strip():
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return [
        {
            "pid": int(p.get("ProcessId") or 0),
            "ppid": int(p.get("ParentProcessId") or 0),
            "user": "",
            "cmdline": p.get("CommandLine") or p.get("Name") or "",
            "cwd": "",
            "exe": p.get("ExecutablePath") or "",
        }
        for p in data
    ]


def list_processes() -> list[dict[str, Any]]:
    if IS_LINUX:
        return _list_processes_linux()
    if IS_WINDOWS:
        return _list_processes_windows()
    return _list_processes_posix()


def score_process(p: dict[str, Any]) -> tuple[int, list[str]]:
    """Return (score, reasons). Score >= 2 is suspicious."""
    cmdline = (p.get("cmdline") or "").lower()
    cwd = (p.get("cwd") or "").lower()
    exe = (p.get("exe") or "").lower()

    if not any(
        t in (cmdline + " " + exe) for t in ("node", "electron", "bun")
    ):
        return 0, []

    score = 0
    reasons: list[str] = []

    for pat, label in PROCESS_CMDLINE_IOCS:
        if pat.search(p.get("cmdline") or ""):
            reasons.append(label)
            score += 2

    if len(cmdline) > 1500:
        reasons.append(f"very long cmdline ({len(cmdline)} chars)")
        score += 1

    sus_paths = (
        "/tmp/",
        "/var/tmp/",
        "/dev/shm/",
        "appdata\\local\\temp\\",
        "\\windows\\temp\\",
        "/private/tmp/",
    )
    for sp in sus_paths:
        if sp in cwd or sp in exe:
            reasons.append(f"runs from temp path: {sp}")
            score += 2
            break

    if p.get("ppid") == 1 and "node" in cmdline:
        reasons.append("detached node process (ppid=1)")
        score += 1

    if "eval(" in cmdline or "atob(" in cmdline:
        reasons.append("eval/atob in cmdline")
        score += 2

    if re.search(r"['\"][A-Fa-f0-9]{200,}['\"]", cmdline):
        reasons.append("hex blob in cmdline")
        score += 2

    return score, reasons


def scan_processes() -> list[ProcessFinding]:
    return [
        ProcessFinding(
            pid=p["pid"],
            score=score,
            indicators=reasons,
            cmdline=(p.get("cmdline") or "")[:500],
            cwd=p.get("cwd") or "",
            exe=p.get("exe") or "",
            user=str(p.get("user") or ""),
            ppid=p.get("ppid") or 0,
        )
        for p in list_processes()
        for score, reasons in [score_process(p)]
        if score >= 2
    ]


def kill_process(pid: int) -> tuple[bool, str]:
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        else:
            os.kill(pid, signal.SIGKILL)
        return True, f"killed pid {pid}"
    except (
        subprocess.CalledProcessError,
        ProcessLookupError,
        PermissionError,
        OSError,
    ) as e:
        return False, f"failed to kill pid {pid}: {e}"


# ===========================================================================
# Persistence checks
# ===========================================================================


def check_shell_persistence(home: Path) -> list[str]:
    notes: list[str] = []
    rc_files = [
        home / r
        for r in (
            ".bashrc",
            ".bash_profile",
            ".profile",
            ".zshrc",
            ".zprofile",
            ".config/fish/config.fish",
        )
    ]
    sus = re.compile(
        r"(curl|wget|iwr|invoke-webrequest).*\|.*(node|sh|bash|powershell)",
        re.IGNORECASE,
    )
    for rc in rc_files:
        if not rc.exists():
            continue
        try:
            text = rc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if sus.search(line):
                notes.append(f"{rc}:{n}: {line.strip()[:120]}")
    return notes


def check_ssh_authorized_keys(home: Path) -> list[str]:
    notes: list[str] = []
    ak = home / ".ssh" / "authorized_keys"
    if not ak.exists():
        return notes
    try:
        entries = [
            line.strip()
            for line in ak.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.strip() and not line.startswith("#")
        ]
    except OSError:
        return notes
    for entry in entries:
        comment = entry.split()[-1] if len(entry.split()) >= 3 else ""
        notes.append(f"authorized_keys entry: ...{entry[-40:]} ({comment})")
    if notes:
        notes.insert(
            0,
            f"~/.ssh/authorized_keys has {len(notes)} entr(ies) — verify all are expected:",
        )
    return notes


def check_cron_persistence() -> list[str]:
    if IS_WINDOWS:
        return []
    notes: list[str] = []
    try:
        out = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return notes
    sus = re.compile(r"(curl|wget|node\b)", re.IGNORECASE)
    for n, line in enumerate(out.splitlines(), 1):
        if (
            line.strip()
            and not line.lstrip().startswith("#")
            and sus.search(line)
        ):
            notes.append(f"crontab:{n}: {line.strip()[:150]}")
    return notes


def check_launchd_persistence(home: Path) -> list[str]:
    if not IS_MACOS:
        return []
    notes: list[str] = []
    for d in (home / "Library" / "LaunchAgents",):
        if not d.exists():
            continue
        for plist in d.glob("*.plist"):
            try:
                t = plist.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"(node|curl|wget)", t, re.IGNORECASE):
                notes.append(f"{plist}: contains node/curl reference — review")
    return notes


def check_windows_persistence() -> list[str]:
    if not IS_WINDOWS:
        return []
    notes: list[str] = []
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-ScheduledTask | "
                "Where-Object { $_.Actions.Execute -match 'node|curl|wget' } | "
                "Select-Object TaskName,"
                "@{N='Cmd';E={$_.Actions.Execute}},"
                "@{N='Args';E={$_.Actions.Arguments}} | ConvertTo-Json -Depth 3",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        if out.strip():
            notes.append(
                f"scheduled task references node/curl/wget:\n{out.strip()}"
            )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-ItemProperty HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run | Out-String",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        for line in out.splitlines():
            if re.search(
                r"node|curl|wget|powershell.*-enc", line, re.IGNORECASE
            ):
                notes.append(f"HKCU Run: {line.strip()}")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return notes


def all_persistence_checks(home: Path) -> list[str]:
    out: list[str] = []
    out.extend(check_shell_persistence(home))
    out.extend(check_ssh_authorized_keys(home))
    out.extend(check_cron_persistence())
    out.extend(check_launchd_persistence(home))
    out.extend(check_windows_persistence())
    return out


# ===========================================================================
# Hygiene checks
# ===========================================================================

# Patterns in .gitignore that cover .env files.
_GITIGNORE_ENV_PAT = re.compile(
    r"^(\.env[\*\s]?|\.env$|\*\.env|\*\.env\.\*)", re.MULTILINE
)


def check_gitignore_env(root: Path) -> list[str]:
    """Warn if .env is not covered by .gitignore in this root."""
    gi = root / ".gitignore"
    if not gi.exists():
        return [f"{root}/.gitignore missing — .env files may be unprotected"]
    try:
        text = gi.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if not _GITIGNORE_ENV_PAT.search(text):
        return [
            f"{gi}: .env is not covered — add '.env' to prevent secret exposure"
        ]
    return []


def all_hygiene_checks(roots: list[Path]) -> list[str]:
    out: list[str] = []
    for root in roots:
        out.extend(check_gitignore_env(root))
    return out


# ===========================================================================
# Hardening
# ===========================================================================


def harden_npm_ignore_scripts() -> tuple[bool, str]:
    try:
        cur = subprocess.run(
            ["npm", "config", "get", "ignore-scripts"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        if cur == "true":
            return True, "npm ignore-scripts already true"
        subprocess.run(
            ["npm", "config", "set", "ignore-scripts", "true"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return (
            True,
            "npm ignore-scripts=true  (revert: npm config delete ignore-scripts)",
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return False, f"npm not available or set failed: {e}"


def hosts_path() -> Path:
    if IS_WINDOWS:
        return Path(r"C:\Windows\System32\drivers\etc\hosts")
    return Path("/etc/hosts")


def check_hosts_blocked() -> tuple[set[str], set[str]]:
    p = hosts_path()
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(C2_HOSTS)
    blocked: set[str] = set()
    for h in C2_HOSTS:
        if re.search(
            rf"^\s*[\d.:a-fA-F]+\s+{re.escape(h)}\s*$", text, re.MULTILINE
        ):
            blocked.add(h)
    return blocked, set(C2_HOSTS) - blocked


def hosts_block_lines(missing: set[str]) -> list[str]:
    return [f"127.0.0.1\t{h}" for h in C2_HOSTS if h in missing]


def clear_git_credential_cache() -> tuple[bool, str]:
    try:
        subprocess.run(
            ["git", "credential-cache", "exit"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return True, "ran git credential-cache exit"
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return False, f"git unavailable: {e}"


def harden(report_lines: list[str]) -> None:
    ok, msg = harden_npm_ignore_scripts()
    report_lines.append(("OK   " if ok else "FAIL ") + msg)
    ok, msg = clear_git_credential_cache()
    report_lines.append(("OK   " if ok else "FAIL ") + msg)
    blocked, missing = check_hosts_blocked()
    if missing:
        report_lines.append(
            f"hosts file is missing {len(missing)} C2 block entries — "
            f"append to {hosts_path()} as root/admin:"
        )
        for line in hosts_block_lines(missing):
            report_lines.append(f"  {line}")
    else:
        report_lines.append("OK   all C2 hosts blocked in hosts file")


# ===========================================================================
# Core scan runner
# ===========================================================================


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        return input(f"{prompt} [y/N] ").strip().lower() == "y"
    except EOFError:
        return False


def run_once(args: argparse.Namespace, home: Path) -> dict[str, Any]:
    roots = [
        Path(p).expanduser().resolve() for p in (args.paths or [os.getcwd()])
    ]
    if args.scan_home:
        roots.append(home)

    config_targets, workflow_targets, source_targets, pkg_targets = (
        collect_targets(roots, changed_only=args.changed_only)
    )

    file_findings: list[FileFinding] = []
    for path in config_targets:
        f = scan_config_file(path)
        if f:
            file_findings.append(f)
    for path in workflow_targets:
        f = scan_workflow_file(path)
        if f:
            file_findings.append(f)
    for path in source_targets:
        f = scan_source_file(path)
        if f:
            file_findings.append(f)
    for path in pkg_targets:
        f = scan_package_json(path)
        if f:
            file_findings.append(f)

    if args.fix:
        for f in file_findings:
            if f.kind == "config":
                f.backup_path = quarantine(f.path)
                ok, msg = clean_file(f.path)
                f.cleaned = ok
                f.clean_message = msg

    proc_findings: list[ProcessFinding] = []
    if not args.no_process_check:
        proc_findings = scan_processes()

    if args.kill and proc_findings:
        for pf in proc_findings:
            preview = (
                (pf.cmdline[:80] + "…") if len(pf.cmdline) > 80 else pf.cmdline
            )
            if confirm(
                f"kill pid {pf.pid} (score {pf.score})? {preview}", args.yes
            ):
                ok, msg = kill_process(pf.pid)
                pf.killed = ok
                pf.kill_message = msg

    persistence = all_persistence_checks(home)
    hygiene = all_hygiene_checks(roots)

    harden_results: list[str] = []
    if args.harden:
        harden(harden_results)

    return {
        "timestamp": time.time(),
        "changed_only": args.changed_only,
        "scanned_config": len(config_targets),
        "scanned_workflow": len(workflow_targets),
        "scanned_source": len(source_targets),
        "scanned_packages": len(pkg_targets),
        "scanned_roots": [str(r) for r in roots],
        "file_findings": [
            {
                "path": str(f.path),
                "size": f.size,
                "kind": f.kind,
                "indicators": f.indicators,
                "backup": str(f.backup_path) if f.backup_path else None,
                "cleaned": f.cleaned,
                "clean_message": f.clean_message,
            }
            for f in file_findings
        ],
        "process_findings": [
            {
                "pid": p.pid,
                "score": p.score,
                "indicators": p.indicators,
                "cmdline": p.cmdline,
                "cwd": p.cwd,
                "exe": p.exe,
                "user": p.user,
                "ppid": p.ppid,
                "killed": p.killed,
                "kill_message": p.kill_message,
            }
            for p in proc_findings
        ],
        "persistence": persistence,
        "hygiene": hygiene,
        "harden_results": harden_results,
    }


# ===========================================================================
# Output rendering
# ===========================================================================


def render(report: dict[str, Any], args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        mode = " [changed-only]" if report.get("changed_only") else ""
        print(
            f"scanned {report['scanned_config']} config, "
            f"{report['scanned_workflow']} workflow, "
            f"{report['scanned_source']} source, "
            f"{report['scanned_packages']} package.json file(s){mode}"
        )

        ff = report["file_findings"]
        pf = report["process_findings"]
        pst = report["persistence"]
        hyg = report["hygiene"]
        hr = report["harden_results"]

        if not ff:
            print("  files:        clean")
        else:
            print(f"\n  FILE FINDINGS ({len(ff)}):")
            for f in ff:
                print(f"    [{f['kind']}] {f['path']}  [{f['size']}B]")
                for ind in f["indicators"]:
                    print(f"      - {ind}")
                if f.get("backup"):
                    print(f"      backup: {f['backup']}")
                if f.get("clean_message"):
                    s = "CLEANED" if f["cleaned"] else "skip"
                    print(f"      {s}: {f['clean_message']}")

        if args.no_process_check:
            print("  processes:    skipped (--no-process-check)")
        elif not pf:
            print("  processes:    clean")
        else:
            print(f"\n  PROCESS FINDINGS ({len(pf)}):")
            for p in pf:
                cm = (
                    (p["cmdline"][:120] + "…")
                    if len(p["cmdline"]) > 120
                    else p["cmdline"]
                )
                k = " [KILLED]" if p["killed"] else ""
                print(
                    f"    pid {p['pid']} ppid {p['ppid']} score {p['score']}{k}"
                )
                print(f"      cmd: {cm}")
                for ind in p["indicators"]:
                    print(f"      - {ind}")
                if p.get("kill_message") and not p["killed"]:
                    print(f"      kill: {p['kill_message']}")

        if pst:
            print(f"\n  PERSISTENCE ({len(pst)}):")
            for line in pst:
                print(f"    {line}")
        else:
            print("  persistence:  clean")

        if hyg:
            print(f"\n  HYGIENE ({len(hyg)}):")
            for line in hyg:
                print(f"    {line}")
        else:
            print("  hygiene:      clean")

        if hr:
            print("\n  HARDENING:")
            for line in hr:
                print(f"    {line}")

    if args.log:
        try:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            with args.log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(report, default=str) + "\n")
        except OSError as e:
            print(f"log write failed: {e}", file=sys.stderr)

    bad = bool(
        report["file_findings"]
        or report["process_findings"]
        or report["persistence"]
        or report["hygiene"]
    )
    return 1 if bad else 0


# ===========================================================================
# CLI
# ===========================================================================


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scan for JS-config supply-chain and CI/CD tampering IOCs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "paths", nargs="*", help="Directories to scan (default: cwd)"
    )
    ap.add_argument("--scan-home", action="store_true", help="Also scan $HOME")
    ap.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: skip process check, JSON output, exit 1 on any finding",
    )
    ap.add_argument(
        "--changed-only",
        action="store_true",
        help="Scan only files changed since the previous commit (git-aware)",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help="Quarantine and clean infected config files",
    )
    ap.add_argument(
        "--kill",
        action="store_true",
        help="Kill suspicious processes (with confirmation)",
    )
    ap.add_argument(
        "--harden",
        action="store_true",
        help="Apply proactive defenses (npm ignore-scripts, hosts block hint, …)",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Equivalent to --scan-home --fix --kill --harden",
    )
    ap.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompts"
    )
    ap.add_argument(
        "--watch",
        action="store_true",
        help="Continuous scan loop (Ctrl-C to stop)",
    )
    ap.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Watch interval in seconds (default 60)",
    )
    ap.add_argument(
        "--json", action="store_true", help="Machine-readable output"
    )
    ap.add_argument(
        "--no-process-check",
        action="store_true",
        help="Skip running-process inspection",
    )
    ap.add_argument(
        "--log", type=Path, help="Append JSON findings to this log file"
    )

    args = ap.parse_args()

    if args.all:
        args.scan_home = args.fix = args.kill = args.harden = True

    if args.ci or IN_CI:
        args.no_process_check = True
        args.json = True

    home = Path.home()

    if args.watch:
        print(f"watch mode (interval {args.interval}s, Ctrl-C to stop)")
        try:
            while True:
                report = run_once(args, home)
                print(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
                render(report, args)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nstopped")
            return 0
    else:
        return render(run_once(args, home), args)


if __name__ == "__main__":
    sys.exit(main())
