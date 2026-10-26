# Windows install: what actually went wrong

Notes from setting up a working Windows machine from scratch (Harry's, the
Nightshift host), on 2026-10-25. Everything here was hit for real, not guessed.
Juan: these are meant to be folded into `docs/TEAM_SETUP.md`.

A full re-install was not attempted two days before the demo, because losing the
working environment would cost more than the test is worth. Every item below was
observed while bringing this machine up the first time.

## Before you start

`winget` installs that need administrator rights fail silently when nobody is at
the keyboard: the UAC prompt times out and winget reports exit code 1602,
"You cancelled the installation". Install the admin-level packages while you are
sitting in front of the machine.

| Package | Scope | Notes |
| --- | --- | --- |
| `Python.Python.3.12` | `--scope user` | No admin needed |
| `Anysphere.Cursor` | `--scope user` | No admin needed |
| `Tailscale.Tailscale` | machine | Needs admin (installs a service) |
| `GitHub.cli` | machine | Needs admin |

## Python

The machine already had Python 3.10 and 3.14. Neither works for this project:
3.10 is below the 3.12 the repo targets, and 3.14 is ahead of some wheels. `py -3.12`
fails with no useful message when 3.12 is simply absent — check with `py --list-paths`
before blaming the virtual environment.

```powershell
winget install --id Python.Python.3.12 --exact --source winget --scope user
py --list-paths          # confirm -V:3.12 appears
py -3.12 -m venv .venv
```

## Node and the World Model service

Node 20 via `nvm` worked unchanged. One trap: `npm install --prefix world_service`
does **not** work from the repo root — npm looks for `package.json` in the root and
fails with `ENOENT`. Change into the directory instead:

```powershell
cd world_service
npm install
npm run conformance      # expect 8/8
npm start                # leave this running in its own terminal
```

The service must be running whenever the agent runs. If it is down, `execute()` now
returns an escalated result naming the World Model instead of raising, so the symptom
is "every plan escalates", not a crash.

## Tailscale: the part that cost the most time

**Signing in with GitHub creates your own, separate tailnet.** The machine connects,
`tailscale status` shows your own device, and nothing else — no teammates, no Zetaris.
It looks like a connection problem and it is not.

Being *invited* to the team's tailnet and having *this machine* join it are two
different steps. The invitation link may well say "You are already a member of the
<owner> Tailscale network" while the machine is still on your own one.

Diagnose it properly before touching anything else:

```powershell
tailscale status --json | ConvertFrom-Json | ForEach-Object { $_.CurrentTailnet.Name }
tailscale switch --list      # lists the tailnets this machine has profiles for
```

If `CurrentTailnet.Name` is your own account and `switch --list` shows only one row,
the machine never joined. Fix it by logging in again and picking the team's tailnet
in the browser page that opens:

```powershell
tailscale login             # prints a URL; open it and choose the team's tailnet
```

After that, `tailscale status` lists the other machines and the IP of this machine
changes, because it is now a node in a different tailnet.

To publish Nightshift to the team (run on the Nightshift host):

```powershell
tailscale serve --bg --tcp 8088 tcp://127.0.0.1:8088
tailscale serve status
```

## Nightshift

It is **not** in winget. Download it from the directory listing at
`https://meterless.ai/Nightshift/WIN/` and check it against `SHA256SUMS` in the same
folder before running it. The current build is `Nightshift_1.2.3_x64-setup.exe`
(624 MB); it installs silently with `/S` and needs no admin.

Contrary to the current setup guide, **it did not ask for email verification**.

Two things to know:

**The window can come up black.** It happened on first launch and again after a close
and reopen. WebView2 was installed and the services were running — the services listen
on 8088 (the OpenAI-compatible API), 8089 (the phone pairing view) and 11435. Restarting
only the `meterless-runtime.exe` process fixed it once; on a later occasion it did not,
and neither did disabling GPU acceleration nor clearing the WebView profile. Opening the
app yourself from the Start menu is worth trying before anything else.

**The token on disk goes stale.** `%LOCALAPPDATA%\ai.meterless.runtime\proxy-token`
holds a token that works for the session that created it. After a restart the file is
unchanged but the API answers 401 to it. Take the token from the Console inside the app
(the gear, top right) rather than from the file, and expect to update `.env` after a
Nightshift restart.

## Models

`nvidia/nemotron-3-super-120b-a12b` — the deep lane model the plan names — returns
**404 "Function not found"** for both of our accounts, through Nightshift and through
direct NVIDIA. So do `llama-3.1-nemotron-ultra-253b-v1` (404) and
`llama-3.3-nemotron-super-49b-v1.5` (410, retired).

The large Nemotron that does answer is **`nvidia/nemotron-3-ultra-550b-a55b`**.

A free NVIDIA API key runs out of inference credits quickly: ours lasted two heavy
batteries (about 80 graph turns) plus a few demos. The symptom is confusing — the key
still authorizes and `GET /v1/models` lists 85 models, but every `chat/completions`
call returns **403 Forbidden**. If the catalogue works and inference does not, it is
credits, not the key and not the model.

## .env traps

- Paste values with no quotes and no spaces around `=`.
- Do not leave placeholder angle brackets in: `http://<1.2.3.4>:8888` resolves the
  brackets as part of the host name and fails with a name resolution error, which
  reads like a network problem.
- `LANE_FAST_MODEL` and `LANE_DEEP_MODEL` override `NEMOTRON_MODEL`. Leave them empty
  unless you mean to pin a lane.
- Keep the whole `logs/` folder out of git. It used to ignore only `*.log` and
  `*.jsonl`, so the heavy test's `.json` results would have been committed.

## Sanity check, in order

```powershell
py --list-paths                                   # 3.12 present
.\.venv\Scripts\python.exe -m pytest -q           # offline, no services needed
cd world_service; npm run conformance             # 8/8
tailscale status                                  # teammates visible
.\.venv\Scripts\python.exe smoke_test.py          # 3 PASS
.\.venv\Scripts\python.exe -m resq.run --question "How should we distribute aid right now?"
```

`pytest` passing while `smoke_test.py` fails means the code is fine and a service or a
credential is not — the tests run entirely offline on purpose.
