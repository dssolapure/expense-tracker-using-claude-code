---
description: Commits and pushes the current feature branch, then opens a 
  PR link against the main branch. Optionally pass a commit message, e.g. 
  /ship-feature "add expense date filter"
allowed-tools: Bash(git status), Bash(git branch --show-current), 
  Bash(git add .), Bash(git commit), Bash(git diff), 
  Bash(git diff --staged), Bash(git log), Bash(git push), 
  Bash(git remote get-url origin), Bash(git remote show origin), 
  Bash(git rev-list), Bash(gh pr create), Bash(gh --version)
---

Ship the current feature branch: commit any pending changes, push it, 
and produce a PR link against the main branch.

Commit message (if provided): $ARGUMENTS

---

## Step 1: Safety checks

Run `git branch --show-current` to get the active branch.

- If the branch is `main` or `master`, STOP immediately and say:
  "You're on the {branch} branch. Please checkout your feature branch 
  before running /ship-feature."
- Do NOT create or switch branches yourself — the user has already 
  created the feature branch.

Run `git status --porcelain` to see what's pending.

---

## Step 2: Stage and commit (only if there are changes)

If `git status --porcelain` shows no changes, skip straight to Step 3 
— there may still be committed-but-unpushed work.

If there are changes:
- Run `git add .`
- Determine the commit message:
  - If $ARGUMENTS was provided, use it as the commit message.
  - Otherwise, run `git diff --staged` to see what changed and write a 
    concise, conventional commit message summarizing the change (what 
    and why, not a line-by-line description).
- Run `git commit -m "<message>"`

---

## Step 3: Push the branch

Run `git push -u origin <current-branch>`.

If the push fails (e.g. remote rejected, diverged history), STOP and 
report the exact git error to the user. Do NOT force-push under any 
circumstances.

---

## Step 4: Determine the base branch

Run `git remote show origin` and read the "HEAD branch" line to find 
the repo's actual default branch (it may be `main` or `master` — do 
not assume). This is the PR base branch.

---

## Step 5: Create the PR and share the link

Check if `gh` is available with `gh --version`.

- If `gh` is available and authenticated: run
  `gh pr create --base <base-branch> --head <current-branch> --fill`
  and capture the PR URL it prints.
- If `gh` is NOT available (command not found) or not authenticated: 
  fall back to building a compare URL manually:
  1. Run `git remote get-url origin` to get the remote URL.
  2. Parse the `owner/repo` out of it (handles both 
     `https://github.com/owner/repo.git` and 
     `git@github.com:owner/repo.git` forms).
  3. Build the link: 
     `https://github.com/<owner>/<repo>/compare/<base-branch>...<current-branch>?expand=1`

Present the final result to the user as:

**Shipped `<current-branch>` → `<base-branch>`**
- Commit: <short summary of what was committed, or "no new commits — branch was already up to date">
- Push: confirmed
- PR link: <the link>

---

## Rules
- Never force-push (`--force` / `-f`) under any circumstances.
- Never switch or create branches — only operate on the current branch.
- Never touch `main`/`master` directly — Step 1 must stop first.
- If there is nothing to commit AND nothing to push (branch already 
  in sync with origin), skip Step 3 and still proceed to Step 4/5 so 
  the user gets a PR link if one doesn't exist yet.
- If `gh pr create` reports a PR already exists for this branch, just 
  surface the existing PR URL it returns instead of erroring out.
