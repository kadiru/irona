# Publishing

The public repository is [kadiru/irona](https://github.com/kadiru/irona), with `main`
as its default branch. It is a fresh repository, not the history of the owner's
older private project. The owner renamed that project to `irona-legacy`; it
remains private and is not a publication source for this checkout.
Publish from the canonical Ubuntu checkout, `/home/kadir/code/irona`.
The Mac's unrelated GitHub account must not supply publication credentials.

## Project-Local Authentication

`bash scripts/install-gh.sh` installs a checksummed Linux x86-64 GitHub CLI
under ignored `.runtime/gh`, with no system installation. `scripts/gh.sh`
isolates configuration under `.runtime/github` and ignores inherited account
tokens. Use this wrapper for this checkout's GitHub operations.

```bash
bash scripts/gh.sh auth login --hostname github.com --git-protocol https --web --insecure-storage
bash scripts/gh.sh api user --jq .login
```

Complete the browser authorization as **kadiru**. Stop if the identity check
returns another account. Do not paste credentials into chat or shell commands.
The explicit storage option keeps the token in a private local file rather than
a system keyring: it is plaintext, not encrypted, under a mode-700 directory
with mode-600 credential files. The directory is ignored by Git. Do not include
it in public archives or share it alongside the source.

Git author identity and the credential helper belong in this repository's local
`.git/config`, not global Git configuration. Use the account's GitHub no-reply
email for public commits. Never put a token in a remote URL.

This checkout uses Kadir Uyanik and `717445+kadiru@users.noreply.github.com`.
Its HTTPS credential helper calls `bash scripts/gh.sh auth git-credential` with
the checkout's absolute script path. No global Git configuration was changed.
The origin is `https://github.com/kadiru/irona.git`. After making and reviewing a
local commit, `git push origin main` publishes that branch. New feature branches
use the `codex/` prefix unless the owner requests another name.

The project license is still undecided and is not included in the initial
snapshot. Add it only after the owner selects one; preserve third-party notices.

## Before Each Push

```bash
.venv/bin/python -m pytest -q
git status --short
git diff
git diff --cached --check
git diff --cached --stat
bash scripts/gh.sh api user --jq .login
git remote -v
```

Stage intended source changes, then inspect the staged diff before committing.
Verify the account is `kadiru` and the remote is `kadiru/irona`. Do not use force
push for routine development. The Temi APK and hardware checks are separate from
Python tests; changes to the player should also pass
`bash scripts/build-temi.sh lintDebug` and focused robot tests.

Never publish `.env`, `.runtime`, API/OAuth tokens, ADB or signing keys, models,
generated audio, live transcripts, robot photos, serial numbers, or MAC addresses.
The first publication audit checks both known local secrets and common private
key/token patterns, but no automated scan proves that all sensitive data is absent.

Do not run live ElevenLabs tests automatically on every push. Unit tests mock
external services; manual `tts` checks spend credits and need a listener.
