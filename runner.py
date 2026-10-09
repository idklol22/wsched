#!/usr/bin/env python3
import os
import sys
import time
import json
import random
import shutil
import signal
import subprocess
from datetime import datetime, timezone, timedelta

RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
STAGES_DIR = os.path.join(RUNNER_DIR, "stages")
STATE_FILE = os.path.join(RUNNER_DIR, "state.json")
LOG_FILE = os.path.join(RUNNER_DIR, "runner.log")
PID_FILE = os.path.join(RUNNER_DIR, "daemon.pid")
DAEMON_LOG = os.path.join(RUNNER_DIR, "daemon.log")

STAGE_COMMITS = [
    (1, "initial setup and makefiles"),
    (2, "tempest url encode and http request builder"),
    (3, "tempest socket connect with poll timeout"),
    (4, "tempest handle short reads and raw flag"),
    (5, "mastermind udp peer discovery"),
    (6, "mastermind game state and feedback logic"),
    (7, "mastermind tcp mode and gameplay loop"),
    (8, "mastermind add logging with microsecond timestamps"),
    (9, "mastermind udp chunking and ack packet protocol"),
    (10, "mastermind cost cutting mode with reliable udp"),
    (11, "update docs and final makefile polish"),
    (12, "xv6 implement user-level alarms"),
    (13, "xv6 implement copy-on-write fork")
]

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def get_daemon_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip()
                return int(val) if val else None
        except Exception:
            return None
    return None

def is_pid_alive(pid):
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if process:
                exit_code = ctypes.c_ulong()
                success = kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
                kernel32.CloseHandle(process)
                # STILL_ACTIVE is 259
                return bool(success and exit_code.value == 259)
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

def kill_pid(pid):
    if not pid:
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False

def run_git(repo_dir, args, timeout=30):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env.setdefault("GIT_AUTHOR_NAME", "sanjam")
    env.setdefault("GIT_AUTHOR_EMAIL", "wadhwasanjam@gmail.com")
    env.setdefault("GIT_COMMITTER_NAME", "sanjam")
    env.setdefault("GIT_COMMITTER_EMAIL", "wadhwasanjam@gmail.com")
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", f"git {' '.join(args)} timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)

def get_current_branch(repo_dir):
    _, out, _ = run_git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    return out if out else "main"

def sync_wsched_repo(push=False, commit_msg=None):
    """Sync state.json to/from GitHub wsched repository across operating systems."""
    if not os.path.isdir(os.path.join(RUNNER_DIR, ".git")):
        return
    rc, remotes, _ = run_git(RUNNER_DIR, ["remote"])
    if rc != 0 or "origin" not in remotes:
        return

    branch = get_current_branch(RUNNER_DIR)
    # Pull latest updates (e.g. state pushed from another OS)
    run_git(RUNNER_DIR, ["pull", "--ff-only", "origin", branch], timeout=15)

    if push:
        rc, st, _ = run_git(RUNNER_DIR, ["status", "--porcelain", "state.json"])
        if rc == 0 and st:
            run_git(RUNNER_DIR, ["add", "state.json"])
            msg = commit_msg or "update scheduler state across OSs"
            run_git(RUNNER_DIR, ["commit", "-m", msg])
            rc_push, _, err = run_git(RUNNER_DIR, ["push", "origin", branch], timeout=15)
            if rc_push == 0:
                log("Synced state.json to GitHub wsched repository.")
            else:
                log(f"Notice: wsched state push: {err}")

def get_target_epoch(state):
    """Retrieve target commit time as Unix epoch seconds (timezone-independent)."""
    epoch = state.get("next_commit_epoch")
    if epoch is not None:
        try:
            return float(epoch)
        except (ValueError, TypeError):
            pass

    # Fallback to ISO UTC string
    utc_str = state.get("next_commit_utc")
    if utc_str:
        try:
            dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            pass

    # Fallback to legacy next_commit_time string
    time_str = state.get("next_commit_time")
    if time_str:
        try:
            dt = datetime.fromisoformat(time_str)
            return dt.timestamp()
        except Exception:
            pass
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp()
        except Exception:
            pass

    return None

def format_time_left(diff_seconds):
    """Format remaining duration nicely."""
    if diff_seconds <= 0:
        return "DUE NOW (scheduled time reached)"
    diff_int = int(diff_seconds)
    hours = diff_int // 3600
    mins = (diff_int % 3600) // 60
    secs = diff_int % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0 or hours > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return f"{' '.join(parts)} ({diff_seconds / 60.0:.1f} mins remaining)"

def set_next_schedule(state, delay_mins, base_epoch=None):
    """Set next commit timestamp using epoch seconds, UTC, and local time."""
    base = base_epoch if base_epoch is not None else time.time()
    target_epoch = base + (delay_mins * 60)
    dt_utc = datetime.fromtimestamp(target_epoch, timezone.utc)
    dt_loc = datetime.fromtimestamp(target_epoch).astimezone()

    state["next_commit_epoch"] = round(target_epoch, 1)
    state["next_commit_utc"] = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    state["next_commit_local"] = dt_loc.strftime("%Y-%m-%d %H:%M:%S %Z")
    state["next_commit_time"] = dt_loc.strftime("%Y-%m-%d %H:%M:%S")
    return target_epoch

def is_valid_target_repo(path):
    if not path:
        return False
    try:
        abs_p = os.path.abspath(path)
        # Never match wsched itself
        if abs_p == RUNNER_DIR:
            return False
        if not os.path.isdir(os.path.join(abs_p, ".git")):
            return False
        # Do not match if this directory contains wsched's own files
        if os.path.isfile(os.path.join(abs_p, "build_stages.py")) and os.path.isdir(os.path.join(abs_p, "stages")):
            return False
        return True
    except Exception:
        return False

def detect_repo(preferred=None):
    if preferred and is_valid_target_repo(preferred):
        return os.path.abspath(preferred)

    parent_dir = os.path.dirname(RUNNER_DIR)
    user_home = os.path.expanduser("~")

    # 1. Search sibling directories in parent (prioritize m26 or project)
    try:
        entries = sorted(os.listdir(parent_dir))
        sorted_entries = sorted(entries, key=lambda x: (not (x.startswith("m26") or "project" in x), x))
        for entry in sorted_entries:
            full = os.path.join(parent_dir, entry)
            if is_valid_target_repo(full):
                return os.path.abspath(full)
    except Exception:
        pass

    # 2. Check user's home directory (e.g. C:\Users\wadhw\m26-mp2-2026121004 or ~/m26-mp2-2026121004)
    home_target = os.path.join(user_home, "m26-mp2-2026121004")
    if is_valid_target_repo(home_target):
        return os.path.abspath(home_target)

    try:
        home_entries = sorted(os.listdir(user_home))
        sorted_home = sorted(home_entries, key=lambda x: (not (x.startswith("m26") or "project" in x), x))
        for entry in sorted_home:
            if entry.startswith("m26") or "project" in entry:
                full = os.path.join(user_home, entry)
                if is_valid_target_repo(full):
                    return os.path.abspath(full)
    except Exception:
        pass

    # 3. Check current working directory if not wsched
    cwd = os.path.abspath(os.getcwd())
    if is_valid_target_repo(cwd):
        return cwd

    return None

def ensure_target_repo(state, auto_clone=False):
    repo_dir = state.get("repo_dir")
    if repo_dir:
        abs_repo = os.path.abspath(os.path.join(RUNNER_DIR, repo_dir)) if not os.path.isabs(repo_dir) else repo_dir
        if is_valid_target_repo(abs_repo):
            return abs_repo

    detected = detect_repo()
    if detected:
        state["repo_dir"] = detected
        save_state(state)
        return detected

    remote_url = state.get("remote_url", "https://code.iiit.ac.in/osn/m26-mp2-2026121004.git")
    if remote_url:
        parent_dir = os.path.dirname(RUNNER_DIR)
        repo_name = remote_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        target_clone_path = os.path.join(parent_dir, repo_name)
        if is_valid_target_repo(target_clone_path):
            state["repo_dir"] = os.path.abspath(target_clone_path)
            save_state(state)
            return state["repo_dir"]

        if auto_clone:
            log(f"Target repository not found locally. Cloning from {remote_url}...")
            try:
                env = os.environ.copy()
                env["GIT_TERMINAL_PROMPT"] = "0"
                env["GCM_INTERACTIVE"] = "never"
                res = subprocess.run(
                    ["git", "clone", remote_url, target_clone_path],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=60
                )
                if res.returncode == 0:
                    log(f"Successfully cloned target repo to: {target_clone_path}")
                    state["repo_dir"] = os.path.abspath(target_clone_path)
                    save_state(state)
                    return state["repo_dir"]
                else:
                    err_msg = res.stderr.strip() or res.stdout.strip()
                    log(f"Clone notice: {err_msg}")
            except Exception as e:
                log(f"Clone error: {e}")

    return None

def sync_state_from_git(repo_dir, state):
    """Sync state against remote git history using commit epoch timestamps."""
    if not repo_dir or not os.path.isdir(os.path.join(repo_dir, ".git")):
        return state

    branch = get_current_branch(repo_dir)
    run_git(repo_dir, ["pull", "--ff-only", "origin", branch], timeout=20)

    # %s = subject, %h = short hash, %ct = commit timestamp (epoch seconds), %cI = strict ISO timestamp
    rc, out, _ = run_git(repo_dir, ["log", "--format=%s|%h|%ct|%cI", "-n", "50"])
    if rc != 0 or not out:
        return state

    committed_msgs = {}
    for line in out.splitlines():
        parts = line.strip().split("|", 3)
        if len(parts) == 4:
            msg, c_hash, c_epoch, c_iso = parts
            try:
                ep = int(c_epoch.strip())
            except ValueError:
                ep = int(time.time())
            committed_msgs[msg.strip()] = (c_hash.strip(), ep, c_iso.strip())

    highest_stage = 0
    highest_epoch = 0
    completed_stages = []
    for s_idx, s_msg in STAGE_COMMITS:
        if s_msg in committed_msgs:
            highest_stage = s_idx
            c_hash, c_epoch, c_iso = committed_msgs[s_msg]
            if c_epoch > highest_epoch:
                highest_epoch = c_epoch
            dt_utc = datetime.fromtimestamp(c_epoch, timezone.utc)
            completed_stages.append({
                "stage": s_idx,
                "commit_msg": s_msg,
                "hash": c_hash,
                "timestamp_epoch": c_epoch,
                "timestamp_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "timestamp_local": c_iso
            })

    if highest_stage > state.get("current_stage", 0):
        log(f"Git history sync: Found stage {highest_stage} already committed on remote.")
        state["current_stage"] = highest_stage
        state["completed"] = completed_stages
        if highest_stage < len(STAGE_COMMITS):
            delay_mins = schedule_next_delay()
            set_next_schedule(state, delay_mins, highest_epoch)
        else:
            state["next_commit_epoch"] = None
            state["next_commit_utc"] = None
            state["next_commit_local"] = None
            state["next_commit_time"] = None
        save_state(state)
        sync_wsched_repo(push=True, commit_msg=f"sync state from git log: stage {highest_stage}")

    return state

def load_state():
    state = {
        "current_stage": 0,
        "repo_dir": "",
        "remote_url": "https://code.iiit.ac.in/osn/m26-mp2-2026121004.git",
        "branch": "main",
        "next_commit_epoch": None,
        "next_commit_utc": None,
        "next_commit_local": None,
        "next_commit_time": None,
        "completed": []
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state.update(json.load(f))
        except Exception as e:
            log(f"Error loading state: {e}")

    repo = ensure_target_repo(state, auto_clone=False)
    if repo:
        sync_state_from_git(repo, state)

    return state

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"Error saving state: {e}")

def ensure_git_exclude(repo_dir):
    exclude_file = os.path.join(repo_dir, ".git", "info", "exclude")
    if os.path.exists(exclude_file):
        try:
            with open(exclude_file, "r", encoding="utf-8") as f:
                content = f.read()
            entries = [".commit_runner", ".commit_runner/", "runner.log", "state.json", "*.log"]
            missing = [e for e in entries if e not in content]
            if missing:
                with open(exclude_file, "a", encoding="utf-8") as f:
                    f.write("\n" + "\n".join(missing) + "\n")
        except Exception:
            pass

def apply_stage(stage_idx, repo_dir):
    src_stage = os.path.join(STAGES_DIR, f"stage_{stage_idx:02d}")
    if not os.path.isdir(src_stage):
        raise RuntimeError(f"Stage directory not found: {src_stage}")

    for root, dirs, files in os.walk(src_stage):
        rel = os.path.relpath(root, src_stage)
        dest_root = repo_dir if rel == "." else os.path.join(repo_dir, rel)
        os.makedirs(dest_root, exist_ok=True)
        for f in files:
            src_f = os.path.join(root, f)
            dest_f = os.path.join(dest_root, f)
            shutil.copy2(src_f, dest_f)

def do_commit_stage(repo_dir, stage_idx, commit_msg):
    log(f"--- Applying Stage {stage_idx:02d}: {commit_msg} ---")
    apply_stage(stage_idx, repo_dir)
    ensure_git_exclude(repo_dir)

    net_dir = os.path.join(repo_dir, "networking")
    if os.path.isdir(net_dir):
        try:
            subprocess.run(["make", "-C", net_dir, "clean"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (FileNotFoundError, OSError):
            pass

    xv6_dir = os.path.join(repo_dir, "xv6")
    if os.path.isdir(xv6_dir):
        try:
            subprocess.run(["make", "-C", xv6_dir, "clean"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (FileNotFoundError, OSError):
            pass

    run_git(repo_dir, ["add", "-A"])

    rc, out, _ = run_git(repo_dir, ["status", "--porcelain"])
    if rc == 0 and not out:
        log("No changes detected for this stage (already up to date).")
        return True, "no_changes"

    rc, out, err = run_git(repo_dir, ["commit", "-m", commit_msg])
    if rc != 0:
        log(f"Git commit failed: {err}")
        return False, err

    rc, c_hash, _ = run_git(repo_dir, ["rev-parse", "--short", "HEAD"])
    log(f"Committed successfully: [{c_hash}] {commit_msg}")

    branch = get_current_branch(repo_dir)
    log(f"Pushing to remote origin/{branch}...")
    rc, pout, perr = run_git(repo_dir, ["push", "origin", branch], timeout=30)
    if rc == 0:
        log("Push successful!")
    else:
        log(f"Push warning (will retry on subsequent commits): {perr or pout}")

    return True, c_hash

def schedule_next_delay():
    return 360  # 6 hours interval (360 minutes)

def cmd_status(repo_dir=None):
    sync_wsched_repo(push=False)
    state = load_state()
    if repo_dir and is_valid_target_repo(repo_dir):
        state["repo_dir"] = os.path.abspath(repo_dir)
        save_state(state)
        sync_state_from_git(state["repo_dir"], state)

    curr = state.get("current_stage", 0)
    pid = get_daemon_pid()
    running = is_pid_alive(pid) if pid else False
    daemon_str = f"RUNNING (PID: {pid})" if running else "STOPPED"

    repo_display = state.get("repo_dir", "")
    if not repo_display:
        repo_display = "Not configured"
    elif not is_valid_target_repo(repo_display):
        repo_display = f"{repo_display} (NOT FOUND LOCALLY)"

    print("=" * 64)
    print("AUTOMATED COMMIT RUNNER STATUS")
    print("=" * 64)
    print(f"Daemon Process:   {daemon_str}")
    print(f"Target Repo:      {repo_display}")
    print(f"Current Stage:    {curr} / {len(STAGE_COMMITS)}")
    if curr > 0 and curr <= len(STAGE_COMMITS):
        print(f"Last Completed:   Stage {curr}: {STAGE_COMMITS[curr - 1][1]}")
    if curr < len(STAGE_COMMITS):
        next_s = STAGE_COMMITS[curr]
        print(f"Next Stage:       Stage {next_s[0]}: {next_s[1]}")
        
        target_epoch = get_target_epoch(state)
        if target_epoch is not None:
            time_left = target_epoch - time.time()
            dt_utc = datetime.fromtimestamp(target_epoch, timezone.utc)
            dt_loc = datetime.fromtimestamp(target_epoch).astimezone()
            print(f"Time Remaining:   {format_time_left(time_left)}")
            print(f"Scheduled (UTC):  {dt_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"Scheduled (Local):{dt_loc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        print("Status:           ALL STAGES COMPLETED!")
    print("=" * 64)

def cmd_next(repo_dir=None):
    sync_wsched_repo(push=False)
    state = load_state()
    if not repo_dir:
        repo_dir = state.get("repo_dir") or ensure_target_repo(state, auto_clone=True)
    if not repo_dir or not is_valid_target_repo(repo_dir):
        print(f"Error: Target git repository not found at '{repo_dir}'.")
        print("Please clone the repository first:")
        print(f"  git clone {state.get('remote_url', 'https://code.iiit.ac.in/osn/m26-mp2-2026121004.git')}")
        sys.exit(1)
    state["repo_dir"] = os.path.abspath(repo_dir)

    curr = state.get("current_stage", 0)
    if curr >= len(STAGE_COMMITS):
        print(f"All {len(STAGE_COMMITS)} stages already committed.")
        return

    stage_idx, msg = STAGE_COMMITS[curr]
    success, c_hash = do_commit_stage(repo_dir, stage_idx, msg)
    if success:
        now_epoch = time.time()
        dt_utc = datetime.now(timezone.utc)
        dt_loc = datetime.now().astimezone()

        state["current_stage"] = curr + 1
        state["completed"].append({
            "stage": stage_idx,
            "commit_msg": msg,
            "hash": c_hash,
            "timestamp_epoch": round(now_epoch, 1),
            "timestamp_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp_local": dt_loc.strftime("%Y-%m-%d %H:%M:%S %Z")
        })

        if state["current_stage"] < len(STAGE_COMMITS):
            delay_mins = schedule_next_delay()
            target_epoch = set_next_schedule(state, delay_mins, now_epoch)
            log(f"Next commit (Stage {state['current_stage'] + 1}) scheduled at: {state['next_commit_local']} ({state['next_commit_utc']}) (in {delay_mins} mins)")
        else:
            state["next_commit_epoch"] = None
            state["next_commit_utc"] = None
            state["next_commit_local"] = None
            state["next_commit_time"] = None
            log("All project commits completed!")

        save_state(state)
        sync_wsched_repo(push=True, commit_msg=f"update state: stage {state['current_stage']} ({msg}) pushed")

def cmd_run(repo_dir=None):
    sync_wsched_repo(push=False)
    state = load_state()
    if not repo_dir:
        repo_dir = state.get("repo_dir") or ensure_target_repo(state, auto_clone=True)
    if not repo_dir or not is_valid_target_repo(repo_dir):
        print(f"Error: Git repository not found at '{repo_dir}'.")
        print("Please clone or specify the target repo directory.")
        sys.exit(1)

    state["repo_dir"] = os.path.abspath(repo_dir)
    save_state(state)
    log(f"Starting Commit Runner Daemon for repo: {state['repo_dir']}")

    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    try:
        if state.get("current_stage", 0) == 0:
            log("Executing Stage 1 immediately...")
            cmd_next(state["repo_dir"])
            state = load_state()

        last_log_time = 0
        while state.get("current_stage", 0) < len(STAGE_COMMITS):
            state = load_state()
            target_epoch = get_target_epoch(state)
            if target_epoch is None:
                delay_mins = schedule_next_delay()
                target_epoch = set_next_schedule(state, delay_mins)
                save_state(state)
                sync_wsched_repo(push=True)

            now_epoch = time.time()
            time_left = target_epoch - now_epoch

            if time_left <= 0:
                log(f"Scheduled time reached ({state.get('next_commit_utc', 'now')}). Triggering next commit...")
                cmd_next(state["repo_dir"])
                last_log_time = 0
            else:
                if time.time() - last_log_time >= 1800:
                    log(f"Waiting for next commit scheduled at {state.get('next_commit_local')} ({state.get('next_commit_utc')}) - {format_time_left(time_left)}...")
                    last_log_time = time.time()
                sleep_duration = min(30, max(1, time_left))
                time.sleep(sleep_duration)

        log(f"ALL {len(STAGE_COMMITS)} STAGES COMPLETED! Entire project committed and pushed successfully.")
    finally:
        try:
            if get_daemon_pid() == os.getpid() and os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except Exception:
            pass

def cmd_start(repo_dir=None):
    pid = get_daemon_pid()
    if pid and is_pid_alive(pid):
        print(f"Commit runner daemon is already running (PID: {pid}).")
        print("Check status: python runner.py status")
        return

    if pid and os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    # Check/bootstrap repo and pull latest wsched state before launching daemon
    sync_wsched_repo(push=False)
    state = load_state()
    target = repo_dir or state.get("repo_dir") or ensure_target_repo(state, auto_clone=True)
    if not target or not is_valid_target_repo(target):
        print("Error: Target repository not found locally.")
        print("Please specify path: python runner.py start <path-to-repo>")
        return

    cmd = [sys.executable, "-u", os.path.abspath(__file__), "run"]
    if target:
        cmd.append(os.path.abspath(target))

    out_file = open(DAEMON_LOG, "a", encoding="utf-8")
    if sys.platform == "win32":
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=out_file,
            stderr=out_file,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            close_fds=True
        )
    else:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=out_file,
            stderr=out_file,
            start_new_session=True,
            close_fds=True
        )

    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(proc.pid))

    print(f"Commit runner daemon started in background (PID: {proc.pid}).")
    print(f"Target Repo: {os.path.abspath(target)}")
    print(f"Log file: {LOG_FILE}")
    print("Check status anytime with: python runner.py status")

def cmd_stop():
    pid = get_daemon_pid()
    if not pid:
        print("No daemon PID file found.")
        return
    if is_pid_alive(pid):
        kill_pid(pid)
        print(f"Stopped commit runner daemon (PID: {pid}).")
    else:
        print(f"Process {pid} is not running.")
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

def cmd_restart(repo_dir=None):
    cmd_stop()
    time.sleep(1)
    cmd_start(repo_dir)

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    target_repo = sys.argv[2] if len(sys.argv) > 2 else None

    if action == "status":
        cmd_status(target_repo)
    elif action == "next":
        cmd_next(target_repo)
    elif action == "start":
        cmd_start(target_repo)
    elif action == "stop":
        cmd_stop()
    elif action == "restart":
        cmd_restart(target_repo)
    elif action == "run":
        cmd_run(target_repo)
    else:
        print("Usage:")
        print("  python runner.py status [repo]      # Show current progress, time left, and daemon status")
        print("  python runner.py start [repo]       # Start daemon in background (cross-platform)")
        print("  python runner.py stop               # Stop running daemon")
        print("  python runner.py restart [repo]     # Restart running daemon")
        print("  python runner.py next [repo]        # Force trigger next stage now")
        print("  python runner.py run [repo]         # Run in foreground (blocking)")
