#!/usr/bin/env bash
set -euo pipefail
# Source-only handoff. Never package a working database, .env, tokens or real-user data.
REPO="jchev21/gaming-network"
BASE_REF="launch/public-lobby-feed-integration"
DEST="$RUNNER_TEMP/perplexity-source"
rm -rf "$DEST"
mkdir -p "$DEST/baseline" "$DEST/patches" "$DEST/pr-snapshots" "$DEST/meta"
git fetch --no-tags origin "refs/heads/$BASE_REF:refs/remotes/origin/handoff-baseline"
BASE_SHA=$(git rev-parse "refs/remotes/origin/handoff-baseline")
printf '%s\n' "$BASE_SHA" > "$DEST/meta/baseline-commit.txt"
printf '%s\n' "$BASE_REF" > "$DEST/meta/baseline-branch.txt"
git archive "$BASE_SHA" x-integration .github/workflows | tar -xf - -C "$DEST/baseline"
cat > "$DEST/README.md" <<EOF
# Gaming Network — source-only Perplexity review handoff
Baseline: $BASE_REF
Commit: $BASE_SHA
The baseline/ directory contains the X backend integration and CI workflows.
Each pr-N.patch is the diff against THAT PR's actual GitHub base commit.
Each pr-snapshots/pr-N/ has full changed source files, not unmerged service data.
Review all PRs as DRAFT. Keep X_POLL_ENABLED=false; never deploy these snapshots.
No credentials, production DB, private user data, or live API calls are included.
Review the artifact before sharing it with third-party tools.
EOF
for n in 5 6 12 16 24 28 36 39 40 21 27 35; do
  echo "Source review for PR #$n"
  gh api "repos/$REPO/pulls/$n" | jq '{number, title, state, draft, base: {ref: .base.ref, sha: .base.sha}, head: {ref: .head.ref, sha: .head.sha}}' > "$DEST/meta/pr-$n.json"
  BASE=$(jq -r '.base.sha' "$DEST/meta/pr-$n.json")
  HEAD=$(jq -r '.head.sha' "$DEST/meta/pr-$n.json")
  git fetch --no-tags origin "$BASE" "+refs/pull/$n/head:refs/remotes/origin/handoff-pr-$n"
  TEST_HEAD=$(git rev-parse "refs/remotes/origin/handoff-pr-$n")
  if [[ "$TEST_HEAD" != "$HEAD" ]]; then
    echo "FAIL: PR #$n changed mid-bundle, re-run after review" >&2
    exit 1
  fi
  git diff --no-ext-diff --binary "$BASE" "$HEAD" -- x-integration .github/workflows launch tools > "$DEST/patches/pr-$n.patch"
  while IFS= read -r -d '' path; do
    case "$path" in
      x-integration/*|.github/workflows/*|launch/*|tools/*)
        case "$path" in
          *.env|*.env.*|*credentials*|*secrets*|*private-key*|*.pem|*.key|*.db|*.sqlite|*.sqlite3|*.db-*|*.sqlite-*|*.zip|*.tar|*.gz) continue ;;
        esac
        mkdir -p "$DEST/pr-snapshots/pr-$n/$(dirname "$path")"
        git show "$HEAD:$path" > "$DEST/pr-snapshots/pr-$n/$path"
        ;;
    esac
  done < <(git diff --name-only -z --diff-filter=AM "$BASE" "$HEAD" -- x-integration .github/workflows launch tools)
done
find "$DEST" -type f \( -name '*.env' -o -name '.env*' -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.pfx' -o -name '*.log' \) -delete
python3 - "$DEST" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
patterns = [
 re.compile(r'(?i)\b(?:DISCORD_TOKEN|X_API_BEARER_TOKEN|X_CLIENT_SECRET|X_ADMIN_TOKEN|DISCORD_BOT_TOKEN|X_ENCRYPTION_KEY|X_OAUTH_CLIENT_SECRET)\s*[:=]\s*["\x27]?[A-Za-z0-9_.-]{24,}'),
 re.compile(r'(?i)\bBearer\s+[A-Za-z0-9_.-]{32,}'),
 re.compile(r'\b(?:ghp_|gho_|github_pat_|xoxb-|sk_live_|AKIA)[A-Za-z0-9_-]{16,}'),
 re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
]
hits=[]
for f in root.rglob('*'):
 if not f.is_file(): continue
 try: lines=f.read_text(encoding='utf-8').splitlines()
 except UnicodeError: hits.append((str(f.relative_to(root)),'binary/non-UTF8')); continue
 for i,line in enumerate(lines,1):
  # Precisely identified synthetic credentials from checked-in regression fixtures.
  # Do not blanket-allow test files or secret variable names.
  checked = line.replace('Bearer test-server-private-encryption-key', 'Bearer [SYNTHETIC-FIXTURE]')                 .replace("X_CLIENT_SECRET: 'local-dummy-client-secret'", "X_CLIENT_SECRET: '[SYNTHETIC-FIXTURE]'")
  if any(p.search(checked) for p in patterns):
   hits.append((str(f.relative_to(root)),i))
if hits:
 for f,line in hits: print('BLOCKED possible secret',f,'line',line)
 sys.exit(1)
print('Source sanitization scan: PASS; files:',sum(f.is_file() for f in root.rglob('*')))
PY
tar -czf "$RUNNER_TEMP/gaming-network-perplexity-source-handoff.tar.gz" -C "$DEST" .
echo "Handoff safely packaged at GitHub Actions artifact location"
