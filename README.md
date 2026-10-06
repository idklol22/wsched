# wsched

Automated cross-platform commit scheduler for simulated staged commits across Linux, macOS, and Windows.

---

## 1-Command Startup on Any OS

After cloning this repo on any machine or operating system:

```bash
python3 runner.py start
```
*(On Windows: `python runner.py start` or double-click `start_daemon.bat`)*

### What it does automatically:
1. **Auto-clones target repo**: If the assignment repository (`m26-mp2-2026121004`) isn't present, it automatically clones it from `code.iiit.ac.in`.
2. **Auto-syncs state from remote**: Reads git commit history on remote so it knows exactly what stages have already been committed, even if you switched machines.
3. **Starts background daemon**: Runs completely detached in the background without needing a terminal open.

---

## Commands

| Command | Action |
| :--- | :--- |
| `python3 runner.py status` | Check current stage, scheduled time, and daemon PID |
| `python3 runner.py start` | Start the scheduler daemon in the background |
| `python3 runner.py stop` | Stop the background daemon |
| `python3 runner.py restart` | Restart the background daemon |
| `python3 runner.py next` | Force push the next stage immediately |
| `python3 runner.py run` | Run directly in foreground (blocking) |

---

## Pushing this Scheduler to a Private Git Repo

To backup or move this scheduler between machines:

```bash
cd .commit_runner
git init
git add .
git commit -m "commit scheduler and stages"
git remote add origin <YOUR_PRIVATE_GITHUB_OR_GITLAB_URL>
git push -u origin main
```
