# wsched — Automated Commit Scheduler

Cross-platform scheduler for simulated staged commits across Linux, macOS, and Windows. Completely timezone-independent and auto-syncing across operating systems.

---

## Quickstart (When Cloning on a New OS / Machine)

### 1. Clone this Repository
```bash
git clone https://github.com/idklol22/wsched.git
cd wsched
```

### 2. Start the Scheduler (1 Command)

- **Linux / macOS**:
  ```bash
  python3 runner.py start
  ```
  *(or `./start_daemon.sh`)*

- **Windows**:
  ```cmd
  python runner.py start
  ```
  *(or double-click `start_daemon.bat`)*

That's it!

---

## What Happens Automatically

When you run `python runner.py start`:
1. **Auto-Clones Target Assignment Repo**: If `m26-mp2-2026121004` isn't cloned yet on that machine, it automatically clones it from `https://code.iiit.ac.in/osn/m26-mp2-2026121004.git` right next to this directory.
2. **Auto-Syncs with Git History**: Reads the remote git commit history on `code.iiit.ac.in` to verify which stages were already pushed, so it never desyncs even if you worked across multiple OSs.
3. **Timezone-Independent Countdown**: Uses POSIX Unix Epoch timestamps (`time.time()`). Even if Windows and Linux are in different timezones or your system clock is offset, the remaining time is calculated accurately to the second.
4. **Starts in Background**: Detaches natively into a background process (works on Linux, macOS, and Windows). You can safely close your terminal.
5. **Auto-Pushes State**: Whenever a new commit is made, the runner pushes to both the assignment repo and updates `state.json` here on GitHub.

---

## Handy Commands

All commands work identically on Linux, macOS, and Windows:

| Command | Description |
| :--- | :--- |
| `python3 runner.py status` | View current stage, remaining time countdown, and daemon PID |
| `python3 runner.py start` | Start daemon in the background |
| `python3 runner.py stop` | Stop the background daemon |
| `python3 runner.py restart` | Stop and restart the daemon |
| `python3 runner.py next` | Force push the next stage immediately |
| `python3 runner.py run` | Run in foreground (blocking / debug mode) |

---

## Workflow When Switching OSs (e.g., Linux ↔ Windows)

When you switch operating systems or move to another machine:

1. Open a terminal in your cloned `wsched` folder.
2. Pull the latest state:
   ```bash
   git pull origin main
   ```
3. Start the scheduler:
   ```bash
   python runner.py start
   ```
4. Verify status:
   ```bash
   python runner.py status
   ```

If the scheduled time passed while your computer was off or in the other OS, it will **immediately trigger the next commit**. Otherwise, it resumes the remaining countdown.

---

## One-Time Prerequisite: Git Credentials

Make sure your git credentials are saved on each OS so pushes to both remotes happen without interactive terminal prompts:

- **Linux**:
  ```bash
  git config --global credential.helper store
  ```
- **Windows / macOS**:
  ```cmd
  git config --global credential.helper manager
  ```
