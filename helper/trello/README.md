# Trello Sync

Scripts for syncing project tasks and git history to the Trello board.

## `sync_trello.py`

Pushes two things to the board:
- **`todo.txt` tasks** → *Backlog* list when `todo.txt` exists
- **Git commit history** → *Done* list (backdated to each commit's date)

Duplicate protection is built in — re-running the script will skip cards that already exist on the board.
If `todo.txt` is absent, the backlog sync step is skipped and only git history is pushed.

---

## Setup

### 1. Get your Trello credentials

| What | Where to get it |
|------|----------------|
| API Key | [trello.com/power-ups/admin](https://trello.com/power-ups/admin) → create an app → API Key tab |
| Token | Same page → click the **Token** link next to your API key and authorise |

### 2. Install dependencies

```bash
pip install requests
```

### 3. Set environment variables

```bash
export TRELLO_API_KEY=your_api_key_here
export TRELLO_TOKEN=your_token_here
```

> ⚠️ Never commit your API key or token to git.

---

## Usage

Run from the repo root:

```bash
python3 helper/trello/sync_trello.py
```

### Example output

```
Fetching existing cards...

── todo.txt → Backlog ──
  [+] Evaluation metrics and whether they change
  [+] Implement validation for determining size of dataset
  2 card(s) created.

── Git history → Done ──
  [+] Add regression layer
  [+] Isolationforest implementation
  2 card(s) created.

Done!
```

---

## Board structure

| List | What gets added |
|------|----------------|
| Backlog | Tasks from `todo.txt` when present |
| Done | Completed work from git commit history |
