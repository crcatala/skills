# Safety protocol for terminal captures

A capture is a durable, shareable copy of everything the terminal displayed, including anything you typed. Recordings (`.cast`) hold the raw stream; SVGs hold selectable text, so secrets in an SVG are trivially copyable. Apply this protocol to every capture, whatever the output format.

## Before recording

Work out what will appear on screen and make it safe:

- **Commands and arguments.** No tokens, passwords or keys in argv, URLs (`https://user:token@...`), or `-H "Authorization: ..."` headers.
- **Environment.** The recorder drops the host environment (keeps only `PATH`, locale and `TZ`, and uses an empty `HOME`). Do not defeat this with `--pass-env` for anything credential-like. Be careful with `--keep-home`: it exposes real config and dotfiles.
- **Files and data.** Point the tool at fixtures or generated mock data. Prefer clearly fake values: `EXAMPLE`, `dummy`, `fake`, `redacted`, `<your-token>`. Avoid values that merely look like real keys, as readers cannot tell them apart and scanners will (rightly) block them.
- **Commands that print secrets by nature.** Do not show `env`, `printenv`, `cat .env`, shell history, `git remote -v` with embedded tokens, `docker inspect`, `kubectl get secret`, cloud CLI identity or config output, or `curl -v`. If the demo needs one of these, use a mock.
- **Network and credentials.** Do not run against production, shared, or personal accounts to get something to screenshot. Use a local mock, fixture, or dry-run mode.
- **Identifiers.** Hostnames, usernames, home-directory paths, internal IPs, emails, org or customer names are sensitive when the artifact leaves the machine. Even `PATH` or fastfetch-style system summaries can reveal them. Use a fixture directory, a neutral `--cwd`, and generic data. If the artifact is local-only these are acceptable, but say so in the handoff.

If you cannot make the demo safe, do not record it: ask the user.

## During recording

Only the scripted steps run. Never improvise commands into a live capture. The recorder writes `.cast` files readable only by the current user (mode 0600).

## After recording

1. Run `scripts/scan_secrets.py --betterleaks <binary>` on the recording and on every rendered SVG. `scripts/capture.sh` does both automatically and also scans the scenario file first. Two engines run over the same extracted text: the built-in rules (dependency-free, tuned for terminal captures) and the pinned Betterleaks binary (hundreds of provider key formats). They miss different things, so a finding from either one blocks. If the second engine cannot run, the scan fails closed instead of silently falling back.
2. Look at the capture. The scanner knows common credential formats only: it cannot recognize names, customer data, internal URLs, non-standard tokens, or secrets shown in images or unusual encodings. A passing scan is not proof of safety.
3. For any artifact that will be shared or committed, resolve WARN findings (emails, IP addresses, home-directory paths, high-entropy strings) by changing the fixtures and re-recording.

## Scanner results

| Level | Meaning | Action |
|---|---|---|
| `BLOCK` | Credential-shaped content from either engine: provider keys and tokens, JWTs, private keys, credentials in URLs, sensitive-looking assignments (`*_TOKEN=...`, `password: ...`) with a non-placeholder value. Betterleaks findings show only the rule name and line (the engine redacts the value). | **Stop.** Follow "Stop and notify" below. |
| `WARN` | Identifiers that may be sensitive when shared | Review each. Report in the handoff. Fix before sharing. |

Line numbers for a recording refer to its extracted output text, not the raw `.cast` lines. Values containing `example`, `dummy`, `fake`, `mock`, `placeholder`, `redacted`, `changeme`, `your_`, or shell variable references are treated as placeholders. Reports show only a short prefix and the length, never the whole value.

## Stop and notify

Stop immediately, before rendering, sharing, or retrying, when any of these holds:

- the scanner reports a `BLOCK` finding (in the scenario, recording, or SVG);
- you see or suspect a real credential in the command, environment, fixtures, or output;
- the demo needs real credentials, production systems, or personal or customer data, and there is no safe substitute;
- you cannot tell whether some output is sensitive.

Then:

1. Delete the generated artifacts that contain it (`capture.sh` already removes its own on a block). Do not leave the `.cast` behind.
2. Do **not** quote the secret. Describe the type, where it appeared (file and line, or which step), and the redacted preview from the scanner.
3. Tell the user what happened and what you propose, for example: re-record with mock values, or a different command that shows the same behavior safely. Remind them to **rotate the credential if it was real** and may have been exposed (for instance in this session's transcript).
4. Wait for the user's answer. Do not edit captures to hide the secret unless the user approves; re-recording with safe data is preferable to patching a recording.

Template:

> I stopped the capture before rendering. The scan found <type> in <where> (preview `<abcd…(N chars)>`). I deleted the generated files. If this is a real credential, consider rotating it. To continue I can <safe alternative>; tell me how you'd like to proceed.
