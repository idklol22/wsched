#!/usr/bin/env python3
import os
import sys
import time
import json
import random
import shutil
import signal
import subprocess
from datetime import datetime, timedelta

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
    (11, "update docs and final makefile polish")
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
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if process:
                kernel32.CloseHandle(process)
                return True
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

def detect_repo(preferred=None):
    if preferred and os.path.isdir(os.path.join(preferred, ".git")):
        return os.path.abspath(preferred)

    parent_dir = os.path.dirname(RUNNER_DIR)

    # Search subdirectories of parent_dir for a git repository
    try:
        entries = sorted(os.listdir(parent_dir))
        sorted_entries = sorted(entries, key=lambda x: (not (x.startswith("m26") or "project" in x), x))
        for entry in sorted_entries:
            full = os.path.join(parent_dir, entry)
            if os.path.isdir(full) and os.path.isdir(os.path.join(full, ".git")):
                return os.path.abspath(full)
    except Exception:
        pass

    # Check parent_dir itself
    if os.path.isdir(os.path.join(parent_dir, ".git")):
        return os.path.abspath(parent_dir)

    # Check current working directory
    cwd = os.path.abspath(os.getcwd())
    if os.path.isdir(os.path.join(cwd, ".git")):
        return cwd

    return None

def ensure_target_repo(state):
    repo_dir = state.get("repo_dir")
    if repo_dir and os.path.isdir(os.path.join(repo_dir, ".git")):
        return repo_dir

    detected = detect_repo()
    if detected:
        state["repo_dir"] = detected
        save_state(state)
        return detected

    # Auto-clone target repo if missing on new machine/OS
    remote_url = state.get("remote_url", "https://code.iiit.ac.in/osn/m26-mp2-2026121004.git")
    if remote_url:
        parent_dir = os.path.dirname(RUNNER_DIR)
        repo_name = remote_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        target_clone_path = os.path.join(parent_dir, repo_name)
        log(f"Target repository not found locally. Cloning from {remote_url}...")
        res = subprocess.run(["git", "clone", remote_url, target_clone_path], capture_output=True, text=True)
        if res.returncode == 0:
            log(f"Successfully cloned target repo to: {target_clone_path}")
            state["repo_dir"] = os.path.abspath(target_clone_path)
            save_state(state)
            return state["repo_dir"]
        else:
            log(f"Clone notice: {res.stderr.strip() or res.stdout.strip()}")

    return None

def sync_state_from_git(repo_dir, state):
    if not repo_dir or not os.path.isdir(os.path.join(repo_dir, ".git")):
        return state

    # Pull latest from origin if possible
    branch = get_current_branch(repo_dir)
    run_git(repo_dir, ["pull", "--ff-only", "origin", branch])

    # Inspect git log
    rc, out, _ = run_git(repo_dir, ["log", "--format=%s|%h|%aI", "-n", "50"])
    if rc != 0 or not out:
        return state

    committed_msgs = {}
    for line in out.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) == 3:
            msg, c_hash, ts = parts
            committed_msgs[msg.strip()] = (c_hash.strip(), ts.strip())

    highest_stage = 0
    completed_stages = []
    for s_idx, s_msg in STAGE_COMMITS:
        if s_msg in committed_msgs:
            highest_stage = s_idx
            c_hash, ts = committed_msgs[s_msg]
            completed_stages.append({
                "stage": s_idx,
                "commit_msg": s_msg,
                "hash": c_hash,
                "timestamp": ts
            })

    if highest_stage > state.get("current_stage", 0):
        log(f"Git history sync: Found stage {highest_stage} already committed on remote.")
        state["current_stage"] = highest_stage
        state["completed"] = completed_stages
        if highest_stage < len(STAGE_COMMITS):
            delay_mins = schedule_next_delay()
            nxt_dt = datetime.now() + timedelta(minutes=delay_mins)
            state["next_commit_time"] = nxt_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            state["next_commit_time"] = None
        save_state(state)

    return state

def load_state():
    state = {
        "current_stage": 0,
        "repo_dir": "",
        "remote_url": "https://code.iiit.ac.in/osn/m26-mp2-2026121004.git",
        "branch": "main",
        "next_commit_time": None,
        "completed": []
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state.update(json.load(f))
        except Exception as e:
            log(f"Error loading state: {e}")

    repo = ensure_target_repo(state)
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

def run_git(repo_dir, args):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    res = subprocess.run(["git"] + args, cwd=repo_dir, capture_output=True, text=True, env=env)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def get_current_branch(repo_dir):
    _, out, _ = run_git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    return out if out else "main"

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
    rc, pout, perr = run_git(repo_dir, ["push", "origin", branch])
    if rc == 0:
        log("Push successful!")
    else:
        log(f"Push warning (will retry on subsequent commits): {perr or pout}")

    return True, c_hash

def schedule_next_delay():
    return random.randint(180, 215)

def cmd_status():
    state = load_state()
    curr = state.get("current_stage", 0)
    pid = get_daemon_pid()
    running = is_pid_alive(pid) if pid else False
    daemon_str = f"RUNNING (PID: {pid})" if running else "STOPPED"

    print("=" * 60)
    print("AUTOMATED COMMIT RUNNER STATUS")
    print("=" * 60)
    print(f"Daemon Process:  {daemon_str}")
    print(f"Target Repo:     {state.get('repo_dir', 'Not configured')}")
    print(f"Current Stage:   {curr} / {len(STAGE_COMMITS)}")
    if curr > 0 and curr <= len(STAGE_COMMITS):
        print(f"Last Completed:  Stage {curr}: {STAGE_COMMITS[curr - 1][1]}")
    if curr < len(STAGE_COMMITS):
        next_s = STAGE_COMMITS[curr]
        print(f"Next Stage:      Stage {next_s[0]}: {next_s[1]}")
        nxt_time = state.get("next_commit_time")
        if nxt_time:
            print(f"Scheduled At:    {nxt_time}")
    else:
        print("Status:          ALL STAGES COMPLETED!")
    print("=" * 60)

def cmd_next(repo_dir=None):
    state = load_state()
    if not repo_dir:
        repo_dir = state.get("repo_dir") or ensure_target_repo(state)
    if not repo_dir or not os.path.isdir(os.path.join(repo_dir, ".git")):
        print(f"Error: Git repository not found at {repo_dir}")
        sys.exit(1)
    state["repo_dir"] = os.path.abspath(repo_dir)

    curr = state.get("current_stage", 0)
    if curr >= len(STAGE_COMMITS):
        print("All 11 stages already committed.")
        return

    stage_idx, msg = STAGE_COMMITS[curr]
    success, c_hash = do_commit_stage(repo_dir, stage_idx, msg)
    if success:
        state["current_stage"] = curr + 1
        state["completed"].append({
            "stage": stage_idx,
            "commit_msg": msg,
            "hash": c_hash,
            "timestamp": datetime.now().isoformat()
        })
        if state["current_stage"] < len(STAGE_COMMITS):
            delay_mins = schedule_next_delay()
            nxt_dt = datetime.now() + timedelta(minutes=delay_mins)
            state["next_commit_time"] = nxt_dt.strftime("%Y-%m-%d %H:%M:%S")
            log(f"Next commit (Stage {state['current_stage'] + 1}) scheduled at: {state['next_commit_time']} (in {delay_mins} mins)")
        else:
            state["next_commit_time"] = None
            log("All project commits completed!")
        save_state(state)

def cmd_run(repo_dir=None):
    state = load_state()
    if not repo_dir:
        repo_dir = state.get("repo_dir") or ensure_target_repo(state)
    if not repo_dir or not os.path.isdir(os.path.join(repo_dir, ".git")):
        print(f"Error: Git repository not found at '{repo_dir}'.")
        print("Please initialize or clone your repo first.")
        sys.exit(1)

    state["repo_dir"] = os.path.abspath(repo_dir)
    save_state(state)
    log(f"Starting Commit Runner Daemon for repo: {state['repo_dir']}")

    if state.get("current_stage", 0) == 0:
        log("Executing Stage 1 immediately...")
        cmd_next(state["repo_dir"])
        state = load_state()

    last_log_time = 0
    while state.get("current_stage", 0) < len(STAGE_COMMITS):
        state = load_state()
        nxt_time_str = state.get("next_commit_time")
        if not nxt_time_str:
            delay_mins = schedule_next_delay()
            nxt_dt = datetime.now() + timedelta(minutes=delay_mins)
            state["next_commit_time"] = nxt_dt.strftime("%Y-%m-%d %H:%M:%S")
            save_state(state)
            nxt_time_str = state["next_commit_time"]

        nxt_dt = datetime.strptime(nxt_time_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()

        if now >= nxt_dt:
            log(f"Scheduled time reached ({nxt_time_str}). Triggering next commit...")
            cmd_next(state["repo_dir"])
            last_log_time = 0
        else:
            wait_sec = (nxt_dt - now).total_seconds()
            wait_min = wait_sec / 60.0
            if time.time() - last_log_time >= 1800:
                log(f"Waiting for next commit scheduled at {nxt_time_str} (~{wait_min:.1f} minutes remaining)...")
                last_log_time = time.time()
            sleep_duration = min(30, max(1, wait_sec))
            time.sleep(sleep_duration)

    log("ALL 11 STAGES COMPLETED! Entire project committed and pushed successfully.")

def cmd_start(repo_dir=None):
    pid = get_daemon_pid()
    if pid and is_pid_alive(pid):
        print(f"Commit runner daemon is already running (PID: {pid}).")
        print("Check status: python3 runner.py status")
        return

    # Check/bootstrap repo before launching daemon
    state = load_state()
    target = repo_dir or state.get("repo_dir") or ensure_target_repo(state)

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
    print(f"Log file: {LOG_FILE}")
    print("Check status anytime with: python3 runner.py status")

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
        cmd_status()
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
        print("  python3 runner.py status            # Show current progress and daemon status")
        print("  python3 runner.py start [repo]      # Start daemon in background (cross-platform)")
        print("  python3 runner.py stop              # Stop running daemon")
        print("  python3 runner.py restart [repo]    # Restart running daemon")
        print("  python3 runner.py next [repo]       # Force trigger next stage now")
        print("  python3 runner.py run [repo]        # Run in foreground (blocking)")
