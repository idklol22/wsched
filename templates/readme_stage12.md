# Mini-Project 2: Networking & xv6 (tempest, mastermind & alarms)

**Course**: CS3.301 Operating Systems and Networks  
**Student**: Sanjam Wadhwa (Roll Number: 2026121004)  

---

## Directory Structure

```
mini-project2/
├── Makefile
├── networking/
│   ├── Makefile
│   ├── tempest/
│   │   ├── Makefile
│   │   ├── http.h
│   │   ├── http.c
│   │   ├── net.h
│   │   ├── net.c
│   │   └── main.c
│   └── mastermind/
│       ├── Makefile
│       ├── discovery.h
│       ├── discovery.c
│       ├── game.h
│       ├── game.c
│       ├── net.h
│       ├── net.c
│       ├── udp_trans.h
│       ├── udp_trans.c
│       ├── logger.h
│       ├── logger.c
│       └── main.c
├── xv6/
│   ├── Makefile
│   ├── test-xv6.py
│   ├── kernel/
│   │   ├── defs.h
│   │   ├── kalloc.c
│   │   ├── proc.c
│   │   ├── proc.h
│   │   ├── riscv.h
│   │   ├── sysproc.c
│   │   ├── trap.c
│   │   ├── vm.c
│   │   └── ...
│   └── user/
│       ├── alarmtest.c
│       ├── cowtest.c
│       ├── usertests.c
│       └── ...
├── ai-usage.md
└── readme.md
```

---

## Build Instructions

### Networking (`tempest` & `mastermind`)

To build both `tempest` and `mastermind`, run:

```bash
cd networking
make all
```

Or from the root directory:

```bash
make all
```

To clean build artifacts:

```bash
cd networking
make clean
```

Compilation uses GCC with the required flags:
`-std=c23 -D_POSIX_C_SOURCE=200809L -D_XOPEN_SOURCE=700 -Wall -Wextra -Werror -Wno-unused-parameter -lm`

### xv6 Kernel

To build the xv6 kernel:

```bash
cd xv6
make kernel/kernel
```

To clean build artifacts:

```bash
make clean
```

---

## Run Instructions

### Part A: tempest

Run `tempest` from inside `networking/tempest` or from `networking/`:

```bash
# Basic weather query
cd networking/tempest
./tempest Hyderabad

# Weather query for cities with spaces (enclosed in quotes or escaped)
./tempest "New York"
./tempest San\ Francisco

# Raw HTTP request and response
./tempest Rotterdam --raw
```

### Part B: mastermind

Run `mastermind` from inside `networking/mastermind` or from `networking/`:

```bash
cd networking/mastermind

# Normal mode (TCP for game state)
./mastermind

# Normal mode with logging enabled
./mastermind --log

# Cost cutting mode (UDP reliable datagram transport instead of TCP)
./mastermind --cost-cutting

# Cost cutting mode with logging enabled
./mastermind --cost-cutting --log
```

### Part C: xv6 Alarms

Run alarm tests from inside `xv6/`:

```bash
cd xv6

# Test user-level alarms
python3 test-xv6.py alarmtest
```

---

## Part A: tempest

### Features and Implementation Details
- **URL Encoding**: City names with spaces or reserved characters are percent-encoded into valid URL path components (e.g. `New York` -> `New%20York`).
- **HTTP Request**: Conforms to HTTP/1.1 specification using `GET /<encoded_city>?0T HTTP/1.1` with `Host: wttr.is`, `User-Agent: curl/8.0.0`, and `Connection: close` (RFC 9112 Section 9.3) to terminate connection cleanly without persistent keep-alive.
- **Socket and Timeout Handling**: Uses non-blocking socket with POSIX `poll()` and monotonic timing (`clock_gettime(CLOCK_MONOTONIC)`).
  - The 10-second running timeout begins **before** `connect()` (as clarified in Q15).
  - Connect, sending, and receiving all respect the diminishing remaining timeout window.
  - Short reads and short writes are handled in loops until the complete payload is transmitted or connection terminates.
- **Argument and Location Validation**:
  - If no argument is provided: prints `tempest: missing city argument` and exits with code 1.
  - If more than one argument is provided (or `--raw` is in an invalid position): prints `tempest: too many arguments` and exits with code 1.
  - If server returns non-200 status or indicates unknown location:
    - Without `--raw`: prints `tempest: invalid location` to stderr and exits with code 1.
    - With `--raw`: `--raw` takes precedence (Q12), dumping the exact HTTP request sent and the raw HTTP response received.

---

## Part B: mastermind

### Features and Implementation Details

### 1. Peer Discovery (UDP Broadcast)
- Uses UDP broadcast on port `9999` (`DISC_PORT`) to discover peers across the LAN.
- **Magic identifier**: Exactly 4 bytes: `MM26`. Incoming packets without this magic header are ignored.
- **Payload**: Contains magic, player's username, listening port, and mode flag (TCP vs cost-cutting UDP).
  - In accordance with requirement 2, the player's IP address is **not** included in the payload; the peer extracts the sender's IP address directly from the socket's `recvfrom()` source address structure.
- **Broadcast interval**: Broadcast packets are transmitted once every 2 seconds.
- **Pruning**: Peers that have not broadcasted within the last 5 seconds are purged from the online table.
- **Terminal UI**: The player list is rendered with columns `ID`, `Name`, `IP Addr`, `Port`, `Last Seen`, clearing the screen (`\033[H\033[J`) upon updates.
- **Challenging**: Users type `challenge <ID>` to issue a challenge.

### 2. Gameplay and Board
- Roles: The player who issues the challenge is the **Mastermind** (Feena); the player who accepts is the **Codebreaker** (Tatva).
- Sequence Validation: Master sequence and attempt sequences must be exactly 5 characters long and contain only digits (`0`-`9`).
- Feedback Validation & Fairness (Q20):
  - Feedback must be exactly 5 characters composed exclusively of `x`, `o`, `-`.
  - The program validates feedback fairness against the true counts of bulls and cows with duplicate digits:
    - `x` (green): digit in exact position.
    - `o` (yellow): digit present in secret but in wrong position.
    - `-` (red): digit not present / excess count.
  - If the Mastermind inputs an unfair count, the input is rejected with an explanatory message.
- Board rendering: Matches the 12-attempt board specification with masked master sequence for the Codebreaker (`*****`) and revealed master sequence for the Mastermind. ANSI colors are applied to feedback pegs (`x` = green, `o` = yellow, `-` = red).
- Game Termination: Upon guess completion (`xxxxx`) or after 12 attempts, the Mastermind sends `OVER <master_seq>` to reveal the secret sequence on the Codebreaker's terminal.

### 3. Failure Management & Disconnection Detection
- **TCP mode**: Connection drops or process exits are detected immediately via `recv()` returning `0` (EOF) or negative error codes.
- **UDP mode**: If a message cannot be acknowledged after 15 consecutive retransmission attempts (1.5 seconds without reply), the peer is detected as disconnected.
- In both modes, the application displays:
  `<Player_name> disconnected. Press enter to go home.`
  Pressing enter returns the player to discovery mode.

### 4. Cost Cutting Mode (`--cost-cutting`)
- When launched with `--cost-cutting`, all state transfer and gameplay messages use UDP datagrams instead of TCP.
- **Chunking**: Data payloads are split into fixed-size chunks of 24 bytes.
- **Packet Structure**:
  - `struct udp_chunk`: Contains 4-byte magic (`MMCK`), monotonic `msg_id`, 16-bit sequence number `seq`, 16-bit `total` chunk count, 16-bit length `len`, and data payload.
  - `struct udp_ack`: Contains 4-byte magic (`MMAC`), `msg_id`, and `seq`.
- **Pipelined Transmission**: The sender transmits all chunks immediately without blocking for per-chunk ACKs.
- **ACK & Retransmission**: The receiver sends an ACK immediately for each chunk received. If the sender has unACKed chunks after 100 ms (0.1 seconds), it retransmits all unACKed chunks.
- **Reordering & Assembly**: The receiver stores incoming chunks in an indexed array by `seq`. When all `total` chunks are present, it concatenates them in sequence order `0` to `total - 1` to reconstitute the original message.

### 5. Logging (`--log`)
- When `--log` is provided, all network events (discovery broadcasts, connections, challenges, attempts, feedback, acknowledgments, disconnections) are appended to `log.txt` in the program's working directory.
- Timestamps include microsecond resolution generated with `gettimeofday()`:
  `[YYYY-MM-DD HH:MM:SS.uuuuuu] [LOG] <event>`

---

## Part C: xv6 User-Level Alarms (`sigalarm` and `sigreturn`)

### Features and Implementation Details
- **System Calls**:
  - `sigalarm(interval, handler)`: Registers that the user-space handler function `handler` should be invoked every `interval` CPU ticks consumed by the process. If `interval == 0`, disables the alarm.
  - `sigreturn()`: Called by the user alarm handler upon completion. Restores the user process register state to what it was right before the handler was invoked, resuming the interrupted user code seamlessly.
- **State in `struct proc`**:
  - `alarm_interval`: Interval in ticks between alarm invocations.
  - `alarm_handler`: Address of the user handler function.
  - `alarm_ticks`: Accumulated timer ticks since the last alarm invocation.
  - `alarm_running`: Reentrancy guard flag. Set to 1 when an alarm handler is actively running to prevent nested alarms until `sigreturn()` is called.
  - `alarm_tf`: A separate `struct trapframe` allocated in `allocproc()` and freed in `freeproc()`, used to snapshot the trapframe registers before vectoring into user handler code.
- **Interrupt Handling & Trapframe Restoration**:
  - In `usertrap()` (`kernel/trap.c`), on timer interrupt (`which_dev == 2`), if `alarm_interval > 0`:
    - Increment `alarm_ticks`.
    - If `alarm_ticks >= alarm_interval` and `alarm_running == 0`:
      - Reset `alarm_ticks = 0` and set `alarm_running = 1`.
      - Snapshot `*alarm_tf = *trapframe`.
      - Set `p->trapframe->epc = p->alarm_handler` so returning to user space executes the handler.
  - In `sys_sigreturn()` (`kernel/sysproc.c`):
    - Restores `*p->trapframe = *p->alarm_tf`.
    - Clears `p->alarm_running = 0`.
    - Returns `p->trapframe->a0` so that the syscall dispatcher in `syscall()` preserves the restored `a0` register without overwriting it.

---

## Assumptions Made
1. **Discovery Port**: Port 9999 was chosen for UDP discovery broadcasts.
2. **Timeout**: The 10-second request timeout in `tempest` applies from the beginning of address connection until the full response is received.
3. **Raw Flag Precedence**: If `--raw` is specified with an invalid city name, the raw HTTP request and raw HTTP error response are output to stdout, as clarified in Q12.
4. **Broadcast Loopback**: Broadcasts sent to `255.255.255.255` are processed by the network stack and received by local sockets listening on `INADDR_ANY`, allowing local testing between multiple instances.

---

## Known Bugs
- None observed during testing.
