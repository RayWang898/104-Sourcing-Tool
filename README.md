# 104 Sourcing Tool

Internal recruiter tool for sourcing and filtering candidates on [vip.104.com.tw](https://vip.104.com.tw).
Runs as a local web app — no cloud, no external servers, all data stays on your machine.

---

## Features

- **104 Candidate Search** — search via your recruiter account with filters (keyword, age, experience, gender, etc.)
- **Local Boolean Filter** — AND / OR / NOT keyword filtering applied locally on downloaded results, bypassing 104's fuzzy ranking
- **Full Profile View** — click any candidate to load their complete profile (工作經歷, 個人資料, 求職條件, 語文能力, 技能專長, 認證資格, 自傳)
- **Keyword Highlighting** — active filter keywords highlighted across all profile sections
- **Keywords Database** — build a curated database of useful sourcing keywords organised by Industry → Position
- **Projects** — create sourcing projects (Company + Industry + Position) and save candidates into them
- **Demo Mode** — test the full UI without a 104 account

---

## Requirements

- Python 3.9+
- A 104 VIP recruiter account ([vip.104.com.tw](https://vip.104.com.tw))

---

## Setup

### 1. Clone the repo

```bash
git clone git@github.com:RayWang898/104-Sourcing-Tool.git
cd 104-Sourcing-Tool
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python main.py
```

Open your browser at **http://localhost:8000**

---

## Connecting your 104 account

### Get your session cookies

1. Log into [vip.104.com.tw](https://vip.104.com.tw) in Chrome or Edge
2. Open DevTools → **F12** → **Network** tab → filter **Fetch/XHR**
3. Run any candidate search
4. Click the search request → **Headers** → copy the full `Cookie:` value

### Get your autono and ec values

From the same request URL, copy:
- `autono=XXXXXXXXXXXXXXXXXX` → your recruiter account ID
- `ec=XXX` → your company code

### Save to the tool

1. Go to **http://localhost:8000** → **⚙️ Settings**
2. Paste cookies into **Session Cookies**
3. Paste `autono` and `ec` values into their fields
4. Click **Save Cookies** → **Test Connection**

> ⚠️ **Cookies expire** — typically within hours to days. Repeat the above when the connection shows red.

> 🔒 Cookies are stored **only in your local `data/sourcing.db`** — they never leave your machine.

---

## Usage

### Search
1. Enter a keyword (supports `"exact phrase"` with quotes)
2. Set API filters (age range, experience, gender, etc.)
3. Click **Search 104** to fetch the first page
4. Click **Fetch All Pages** to download all results locally
5. Use the **Local Filter** panel to apply precise AND/OR/NOT boolean logic

### Local Filter
- Each row: `AND/OR` + checkbox (checked = active, unchecked = NOT/exclude) + keyword + field scope
- Click **+ Add** to add more conditions
- Click **Apply** to filter, **Clear** to reset

### Projects
- Create a project with Company + Industry + Position
- Select it in the Search view **Save to** dropdown
- Click 💾 on any candidate card to save them to the project

### Keywords Database
- Add industries, positions, and useful sourcing keywords
- Keywords auto-appear as quick-add chips when a project is selected in Search

---

## Notes

- This tool accesses 104's internal web API using your own account credentials — the same data your browser loads
- Each team member should use their own 104 account and cookies
- The local database (`data/sourcing.db`) is excluded from git — each person has their own
- Do not use for bulk mass-downloading of resumes
