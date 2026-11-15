# RX 6700 XT YouTube Chronicles — Field Log & Episode Scripts

> **Mission:** Real-world documentation of building an offline local AI pair-programmer and personal life-planning workstation on an **AMD Radeon RX 6700 XT (12 GB GDDR6)** + **AMD Ryzen 5 5600 (64 GB DDR4)** — zero cloud hype, zero influencer fluff, verified results only.

---

## Episode 1 — The 12 GB VRAM Sweet Spot & What "Shared GPU Memory" Actually Means

- **The Hook:** Task Manager showed `99% Compute 0`, `11.8 / 12.0 GB Dedicated GPU memory`, and `0.9 / 47.9 GB Shared GPU memory` while running `Qwen3.8-27B-IQ2_M.gguf` locally. If it fits in 12 GB, why is Windows showing almost 1 GB in "Shared GPU memory"?
- **The Struggle / Confusion:** Most 12 GB card owners panic when they see any non-zero Shared GPU Memory number and assume their model spilled off the card onto slow system DDR4 RAM (~32 GB/s).
- **Root Cause:** Windows WDDM reserves a Shared GPU pool across half of system RAM (47.9 GB on a 64 GB host) and stages desktop compositor textures, pinned host-to-device Vulkan transfer buffers, and display buffers there. Meanwhile, the model weights + 64k KV cache sat inside the dedicated 12.0 GB GDDR6 (~384 GB/s) bank.
- **The Fix & Guardrail:** Keep `llama-server` sized so active weights + KV stay inside the `12.0 GB` GDDR6 envelope (`qwen27b_vram` / `IQ2_M` + MTP) and monitor dedicated vs. shared counters live side by side instead of guessing.
- **Takeaway for 6700 XT Owners:** Full 99% Compute 0 at ~76 °C with steady ~0.9 GB shared desktop overhead means you're saturating GDDR6 bandwidth cleanly—you aren't choking on PCIe transfers unless Dedicated hits 12.0/12.0 GB and Shared starts climbing fast.
- **Voice Script Beat:** *"If you own a 12-gig 6700 XT, everyone online tells you 27-billion-parameter models are out of reach. Look at Task Manager: 99% Compute, 11.8 of 12 gigs dedicated GDDR6, 76 degrees. That extra 0.9 gigs in Shared isn't a crash—it's just Windows staging buffers so the GPU can chew at 384 gigs a second."*

---

## Episode 2 — Tokens Per Second Don't Mean Bunk If You Don't Get Results

- **The Hook:** Benchmarks love to brag about tokens/sec on synthetic prompts, yet asking a local coding CLI (`pi`) a real Windows admin question (*"check the last 3 unique errors in Administrative Events and tell me what is actually broken"*) dragged on for 21 minutes and earlier runs missed every key diagnosis.
- **The Struggle / What Went Wrong:**
  - Early Q3 smoke runs (`878.2s` / 26 tool calls, and `438.4s` / 16 tool calls) failed every accuracy check (`0.0%` result score) with 5–7 tool errors.
  - When models ran raw `Get-WinEvent` without filtering, 30+ full XML/text event blocks flooded the 64k context window, burning prefill time and trapping `<think>` blocks in circles.
- **Root Cause:** Local tool-calling speed isn't bottlenecked by raw decode TPS alone—it's bottlenecked by **how much garbage stdout gets stuffed back into KV cache** and **whether the model has a local baseline notebook** instead of rediscovering your PC from scratch every prompt.
- **The Fix That Actually Worked:**
  1. **Filter inside PowerShell (`Group-Object Id, ProviderName` + `Select-Object -First 3`)** so only deduplicated summaries hit the model's context.
  2. **Local Notebook + Triage Skill:** Saved `NOTEBOOK/SYSTEM_BASELINE.md` and `windows-admin-triage/SKILL.md` so the local model starts with SANDBOX's exact baseline facts (`MapsBroker` Event 7023, `Firewall 2042`, `DCOM 10010` benign noise vs. real errors).
  3. **Practical 3-Question Smoke Harness (`bench/practical_admin_smoke.py`):** Scores *tool accuracy* + *correct diagnosis* (`resultScorePct`), not vanity TPS.
- **Result After Fix:** Q3 Event Log triage reached **100.0% result score** (all 5 expected diagnostic checks matched).
- **Takeaway for 6700 XT Owners:** Don't benchmark your 6700 XT with canned poetry prompts. Measure wall-clock time to a verified real answer, and shrink tool stdout at the source.
- **Voice Script Beat:** *"Nobody cares if your local model spits 40 tokens a second if it spends 15 minutes hallucinating over raw Windows Event Logs. Filtering inside PowerShell before it hits the LLM's context took our diagnosis accuracy from zero to 100 percent."*

---

## Episode 3 — The Reasoning Trap: Why `--no-reasoning-preserve` Backfired (33 Min vs. 21 Min)

- **The Hook:** Trying to speed up `Qwen3.8-27B`, we tested `--no-reasoning-preserve` thinking *"if we strip old `<think>` blocks between tool calls, context stays small and runs go faster!"*
- **The Struggle (What Happened):** Instead of speeding up, the exact same Q3 triage benchmark **ballooned by over 12 minutes**:
  - **Standard Thinking Preservation (`--reasoning-budget 256`):** `1262.2s` (~21.0 min), `11` turns, `19` tool calls (`3` errors / `84.2%` tool success), `34,778` peak context tokens, `100.0%` result score.
  - **With `--no-reasoning-preserve`:** `1996.1s` (~33.3 min), `36` turns, `61` tool calls (`19` errors / `68.9%` tool success), `44,672` peak context tokens, `100.0%` result score.
- **Root Cause:** Stripping previous-turn `<think>` traces gave the model inter-turn amnesia. Every tool round, it forgot *why* it had called the previous PowerShell command, repeated work, threw 19 tool errors, and ironically pushed peak context **higher** (`44,672` vs. `34,778`).
- **The Fix:** Removed `--no-reasoning-preserve` from `start_local_server.ps1` and kept `--reasoning-budget 256` so each turn's thinking stays concise *and* preserved across multi-step tool chains.
- **Takeaway for 6700 XT Owners:** Test server flags against an actual multi-turn benchmark, not intuition—saving 200 tokens of history can cost you 25 extra tool turns.
- **Voice Script Beat:** *"Here's one we actually broke trying to be clever: stripping thinking tokens between turns looked faster on paper, and instead gave the 27B model short-term memory loss—jumping from 11 turns to 36 turns and 21 minutes to 33. Always measure the whole run."*

---

## Episode 4 — Building a Local Control Center That Doesn't Jump Around

- **The Hook:** Monitoring `llama-server` on port `8080`, switching quant modes, cleaning typo-filled prompts before sending them to `pi`, and toggling tile chart styles (`BAR`, `GAUGE`, `GRAPH`, `HIST`) in one local web app (`http://127.0.0.1:8090`).
- **The Struggle:**
  1. Clicking telemetry tiles to switch between Bar Slider, Gauge, Graph, and Histogram caused subtle text width and SVG height changes that cascaded across neighboring cards like dominoes.
  2. Wanting user-rearrangeable drag-and-drop tiles without triggering accidental drags on every click—and without blowing up a working UI.
- **The Fix:**
  1. Locked `.metric-card` height (`166px`), `.mode-badge` fixed width (`52px`), and `.viz-stage` height (`60px`) so swapping chart modes causes zero layout shift.
  2. Set the testing protocol for drag-and-drop: build on an isolated Git branch (`exp/tile-layout`) with a default-locked **Lock / Rearrange** toggle so one click reverts or disables dragging cleanly.
- **Takeaway for 6700 XT Owners:** Build your own zero-dependency Python + vanilla HTML control panel over localhost/LAN instead of fighting clunky GUIs—and lock experimental UI layout changes behind branches and lock toggles.

---

## Episode 5 — "Bottled Lightning": Turning Your Phone Into a Voice Handset for Your Local Rig

- **The Hook:** Typing prompts on a couch or away from the desk with typos—and unactivated Windows 11 making Bluetooth headphone selection confusing—when all we really want is to speak into our phone and hear the box answer back like a phone call.
- **The Struggle & Discovery:**
  1. `JLab JBuds Lux ANC` headphones were already paired in Windows (`{ff106afc-...}` Playback, `{bcd88a35-...}` Hands-Free Mic), yet invisible in active dropdowns (`DeviceState = 8` unplugged/standby) because Bluetooth headsets turn off their radio while charging.
  2. Unactivated Windows 11 hides some Settings personalization, and mobile browsers block JS `SpeechRecognition` over plain `http://LAN-IP`.
- **The Fix:**
  1. `control.exe mmsys.cpl` opens the unrestricted classic Win32 Sound dialog where Bluetooth devices appear cleanly once unplugged and powered on.
  2. Bound `dashboard/server.py` to `0.0.0.0:8090` (`http://192.168.0.185:8090`), enabled `spellcheck="true"` + phone keyboard voice dictation guidance, added **🔊 Auto-Speak: ON** via browser TTS so Pi replies out loud automatically, and opened Chrome Remote Desktop for full remote Google-login screen/voice control.
  3. **Dual-Playback Fix (`scripts/switch_audio_mode.ps1`):** When Windows routed live voice replies through HDMI monitor speakers (`1 - SyncMaster`) and the `JLab JBuds Lux ANC` Bluetooth headset at the same time, built a reusable Windows CoreAudio COM toggle script (`IPolicyConfig` + `IAudioEndpointVolume`) that disables (`State=2`) and mutes `1 - SyncMaster` (`Vol=0`) and `Realtek Digital Output`, locking `Console`, `Multimedia`, and `Communications` exclusively to `JLab JBuds Lux ANC` (reversible anytime with `-Mode Monitor`).
  4. **Voice Workflow & GitHub Change-Control Notes:** Logged `"Aye aye, captain."` as the user's preferred execution-confirmation cue, clarified that GitHub commits/pushes serve as structured change control and iteration (not "infinite undo"), and confirmed this workstation runs native Windows (`SANDBOX`).

---

## Upcoming Milestones (Logged for Future Episodes)

- **Episode 6 (Next):** Local Planner / Executor Model Routing on One 12 GB GPU (emulating frontier cloud routing between a thinking planner and fast executor locally).
- **Episode 7 (Goal Project):** 100% Offline Retirement Date Calculator (`NOTEBOOK/RETIREMENT_PLAN.md` + exact Python math engine + private local Qwen analysis).
