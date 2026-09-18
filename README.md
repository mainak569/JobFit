# JobFit
<div align="center">

# JobFit

**Checks how well a resume matches a job description — skill matching, implied skills, and TF-IDF fit scoring, all written by hand.**

<a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" /></a>
<a href="https://www.djangoproject.com"><img src="https://img.shields.io/badge/Django-5-092E20?logo=django&logoColor=white" alt="Django 5" /></a>
<a href="https://www.django-rest-framework.org"><img src="https://img.shields.io/badge/Django_REST_Framework-API-A30000?logo=django&logoColor=white" alt="Django REST Framework" /></a>
<a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL via Neon" /></a>
<a href="https://github.com/jsvine/pdfplumber"><img src="https://img.shields.io/badge/pdfplumber-PDF_extraction-8A2BE2" alt="pdfplumber" /></a>
<br />
<a href="https://www.backblaze.com/cloud-storage"><img src="https://img.shields.io/badge/Backblaze_B2-S3_API-E21E29?logo=backblaze&logoColor=white" alt="Backblaze B2" /></a>
<a href="https://react.dev"><img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React 18" /></a>
<a href="https://vitejs.dev"><img src="https://img.shields.io/badge/Vite-Bundler-646CFF?logo=vite&logoColor=white" alt="Vite" /></a>
<a href="https://render.com"><img src="https://img.shields.io/badge/Render-Hosting-46E3B7?logo=render&logoColor=white" alt="Render" /></a>
<a href="https://neon.tech"><img src="https://img.shields.io/badge/Neon-Database-00E599?logo=neon&logoColor=white" alt="Neon" /></a>
<a href="https://vercel.com"><img src="https://img.shields.io/badge/Vercel-Frontend-000000?logo=vercel&logoColor=white" alt="Vercel" /></a>

<p>
  <a href="https://jobfit-livid.vercel.app"><strong>Live Demo</strong></a> ·
  <a href="#features">Features</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#how-the-analysis-works">How It Works</a> ·
  <a href="#local-setup">Getting Started</a> ·
  <a href="#project-structure">Project Structure</a> ·
  <a href="#running-tests">Testing</a>
</p>

</div>

---

JobFit checks how well a resume matches a job description. Upload a resume PDF and paste a job post: JobFit extracts the text, finds the skills both documents mention using a 146-skill taxonomy with word-boundary matching (in a single pass, with a hand-written Aho-Corasick automaton), fills in skills the resume implies but never names, scores the overall fit with a hand-written TF-IDF similarity, and tells you which skills are missing and what to change. Every analysis is saved, so one resume can be compared against several job descriptions side by side.

![JobFit showing a match score of 45, matched skills in green with implied skills dashed, missing skills in amber, and coverage by area](docs/screenshot.png)

> **Note:** No machine-learning libraries — the matching, the implied-skills graph and TF-IDF similarity are all written by hand.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [How the analysis works](#how-the-analysis-works)
  - [1. PDF text extraction](#1-pdf-text-extraction)
  - [2. Skill matching](#2-skill-matching)
  - [3. One-pass matching with Aho-Corasick](#3-one-pass-matching-with-aho-corasick)
  - [4. Implied skills](#4-implied-skills)
  - [5. Text similarity](#5-text-similarity)
  - [6. Scoring](#6-scoring)
- [Design decisions](#design-decisions)
- [Project structure](#project-structure)
- [Local setup](#local-setup)
- [Running tests](#running-tests)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Privacy and security](#privacy-and-security)
- [Deployment](#deployment)
- [Known limitations](#known-limitations)

---

## Features

**Analysis**
- Overall match score from 0 to 100, clamped to 5-97 (a 100 isn't credible and a 0 is almost always a bug).
- Skills found in both documents, and skills the job description asks for that the resume lacks, most-mentioned first.
- Implied skills: a resume that names Django covers Python, shown as "Python via Django" so it's never mistaken for something the resume says.
- Coverage by area: languages, frontend, backend, databases, DevOps & tools, concepts.
- 3-5 concrete suggestions, such as *"The JD mentions Docker 4 times but it doesn't appear in your resume."*
- PDF text extraction with pdfplumber, a pypdf fallback, and a clear error for scanned PDFs that need OCR.

**Website**
- Drag-and-drop upload with client-side type and size checks and a real upload progress bar.
- Animated SVG score gauge (requestAnimationFrame with ease-out; respects `prefers-reduced-motion`).
- Click a matched skill to highlight every occurrence in the resume text; click an implied skill to highlight the evidence for it.
- History page: sortable by score and date, optimistic delete with rollback on failure.
- Compare page: skills as rows, job descriptions as columns, with a sticky first column that scrolls sideways on phones.
- "Try the demo" loads precomputed sample results with nothing uploaded.
- Loading skeletons, error states with retry, and a "waking up the server" notice for free-tier cold starts.
- Usable from 320px wide.

## Architecture

```
React (Vercel)
      │  upload PDF + JD text
      ▼
Django + DRF (Render)
      ├──> Backblaze B2    (store the PDF, S3-compatible)
      ├──> analysis engine (pure Python, no ML libs)
      └──> PostgreSQL      (Neon: resumes, job descriptions, analyses, IDF corpus)
```

A request to analyze a job description goes through these layers:

```
frontend/src/hooks/useAnalysis.js         the only place the Analyze page calls the API
  └─ frontend/src/api/client.js           URLs, error format, XHR upload with progress
       └─ analysis/views.py               validation, throttling, demo read-only check
            └─ analysis/service.py        orchestration: extract, store, score, save
                 ├─ analysis/extractor.py        PDF -> text
                 ├─ storage/object_storage.py    S3-compatible storage or local media/
                 └─ analysis/scorer.py           the score
                      ├─ analysis/matcher.py         word-boundary skill matching
                      │    └─ analysis/aho_corasick.py   trie + failure links, one pass
                      ├─ analysis/implications.py    implied skills, breadth-first search
                      ├─ analysis/similarity.py      TF-IDF + cosine
                      └─ analysis/corpus.py          IDF corpus across stored JDs
```

The analysis engine (`aho_corasick`, `matcher`, `implications`, `similarity`, `scorer`) is plain Python with no Django imports, so it can be tested and reasoned about without a database.

## How the analysis works

### 1. PDF text extraction

`analysis/extractor.py` reads the PDF with pdfplumber. If that yields fewer than 50 characters it retries with pypdf, because the two libraries decode fonts differently and each succeeds on files the other doesn't. If both come back empty, the API returns a `scanned_pdf` error explaining that the file needs OCR, rather than silently scoring an empty resume.

Two details came from real resumes:

- **Glued words.** LaTeX and Overleaf resumes use tight justified spacing. At pdfplumber's default `x_tolerance` of 3, a line came out as `Developedamulti-agentworkflowwithInngest,tRPC,Prisma,andPostgreSQL`, which hid every skill in it from the matcher. A tolerance of 1.5 splits those words correctly.
- **NUL characters.** Some PDFs embed `\x00` in their text layer, and PostgreSQL rejects NUL in text columns, so extracted text is cleaned before it is saved.

### 2. Skill matching

The taxonomy (`analysis/skills.py`) has 146 skills in six categories, each with a canonical name and aliases (`"PostgreSQL": ["postgres", "postgresql", "psql"]`). A skill matches only on word boundaries, spelled out explicitly:

```
(?<![a-z0-9.&])(?:alias1|alias2|...)(?![a-z0-9+#&])
```

| Rule | Stops |
|---|---|
| No letter or digit before or after | "R" inside "React", "Go" inside "Google", "Java" inside "JavaScript", "SQL" inside "PostgreSQL" |
| No `.` before | "js" inside "node.js" |
| No `+` or `#` after | "C" inside "C++" or "C#" |
| No `&` on either side | "R" in "R&D" |

Plain `\b` isn't enough: `+`, `#` and `.` aren't word characters, so `\bc\+\+\b` can never match "C++" and `\bc\b` matches the "c" in "C#". `.` is allowed *after* an alias so "I used React." still matches, and `-` and `/` count as boundaries so "React-based" and "HTML/CSS" match. Ordinary English words are deliberately not aliases ("rest", "express", "node", "spring", "next").

Matching is case-insensitive. Aliases with a space match any run of whitespace ("rest\napi"), and hyphenated aliases survive a PDF line break ("cloud-\nbased"). The matcher returns the character offsets of every match, which the frontend uses to highlight skills in the resume text, so the highlight can never disagree with the score.

### 3. One-pass matching with Aho-Corasick

The first matcher compiled one regex per skill, so every analysis scanned the resume 146 times. The active matcher is an Aho-Corasick automaton (`analysis/aho_corasick.py`) that finds every alias of every skill in one pass.

**Build.** All 300 aliases go into one trie; aliases that share a prefix share nodes ("react" and "redux" share `r → e`). Every node then gets a *failure link*: the node for the longest proper suffix of its string that is also a prefix somewhere in the trie. Failure links are computed breadth-first, because a node's link always points to a shallower node, which is therefore already done.

```
        root
       /    \
      r      d
      |      |
      e      j
     / \     |
    a   d    a
    |   |    |
    c   u    n
    |   |    |
    t   x    g
  (react)(redux)(django)
```

**Search.** Walk the text one character at a time. Follow a trie edge if one exists; otherwise follow failure links until one does. Characters already read are never re-read. Every node knows which patterns end there, including those reached through its failure link ("she" also reports "he"). Time is O(n + m + z) for text length n, total pattern length m and z matches, instead of O(n × p) for p patterns.

**Keeping the results identical.** The automaton matches raw characters, so the regex matcher's flexible parts are applied to the text and the boundaries are checked at each hit (`AhoCorasickSkillMatcher` in `analysis/matcher.py`):

- Case is folded one character at a time, so positions still line up. Python's `re.IGNORECASE` treats four non-ASCII letters as ASCII (İ and ı as "i", ſ as "s", the Kelvin sign K as "k"), so those are folded the same way.
- Every run of whitespace becomes one space, and whitespace straight after a hyphen is dropped, matching the regex's `\s+` and `-\s*`. A position map sends every match back to its offsets in the original text.
- Each hit's neighbouring characters are checked against the same boundary rules.
- Within a skill, matches are chosen the way the regex chooses them: earliest start first, longest alias at the same start, no overlaps.

The regex matcher is kept as the reference implementation. The test suite asserts that both return identical results on every matcher test case, on every document in `samples/`, and on 400 randomly generated texts mixing aliases, fragments, punctuation, whitespace and the special case-folding letters (with a fixed seed, so a failure is reproducible). That equivalence test is what made switching safe.

**Benchmark** (`python manage.py benchmark_matcher`, fastest of 15 runs, Apple Silicon, Python 3.13):

Text length, real taxonomy (146 skills, 300 aliases, 1,813 trie nodes):

| Text | Regex matcher | Aho-Corasick | Speed-up |
|---|---|---|---|
| One resume (3,763 chars) | 7.05 ms | 0.96 ms | 7.4× |
| 10 resumes (37,639 chars) | 69.30 ms | 9.07 ms | 7.6× |
| 50 resumes (188,199 chars) | 355.22 ms | 48.59 ms | 7.3× |

Number of patterns, on the 37,639-character text (real taxonomy plus synthetic skills):

| Skills | Aliases | Regex matcher | Aho-Corasick | Speed-up | Automaton build |
|---|---|---|---|---|---|
| 146 | 300 | 71.14 ms | 9.62 ms | 7.4× | 0.9 ms |
| 646 | 1,302 | 331.61 ms | 10.03 ms | 33× | 17.6 ms |
| 2,146 | 4,303 | 1,110.18 ms | 10.02 ms | 111× | 14.4 ms |
| 8,146 | 16,265 | 4,265.94 ms | 10.57 ms | 403× | 96.1 ms |

Both grow linearly with text length, but only the regex matcher grows with the number of skills: it scans the text once per skill, while the automaton's time stays at about 10 ms from 300 aliases to 16,000. Even at today's size the single pure-Python pass beats 146 passes of the C regex engine, because each of those passes evaluates the boundary lookbehind at every position.

### 4. Implied skills

Some skills imply others: nobody writes Django without Python. `analysis/implications.py` stores these as a directed graph in a plain dict:

```
Django ──> Python
Next.js ──> React ──> JavaScript
GitHub Actions ──> GitHub ──> Git
PostgreSQL ──> SQL
```

`infer_skills()` runs a breadth-first search from every skill the resume names at once, so each implied skill is explained by the shortest chain from the nearest named skill. The visited set is seeded with the named skills, which stops a cycle from looping forever if an edge ever points back the way it came, and guarantees a skill the resume names outright is never downgraded to "inferred".

The edges are the risky part, not the traversal. An edge means "you can't realistically use A without B": React implies JavaScript, but JavaScript never implies React. Edges that are only usually true (.NET to C#, Playwright to JavaScript) are left out, because a wrong edge inflates the score. Every node is checked against the taxonomy when the app starts, so a misspelt skill name fails loudly instead of silently never matching.

An implied skill counts as covered but always stays visibly different: it is stored with `inferred_from` and the full `inference_path`, drawn as a dashed "Python via Django" chip, and marked `inferred` in the compare table. Selecting it highlights the evidence (where "Django" appears), and a suggestion recommends naming the skill anyway, because keyword filters don't infer anything.

On the demo resume, the implied skills were exactly the false gaps it used to report:

| Job description | Score before | Score after | Implied |
|---|---|---|---|
| Seed: SDE fresher | 38 | 46 | CSS (from Tailwind CSS), Git (from GitHub), SQL (from PostgreSQL) |
| Seed: full stack | 45 | 53 | CSS, Git, ORM (from Prisma), SQL |
| Seed: frontend | 24 | 30 | CSS, Git |
| Seed: backend | 16 | 22 | Git, SQL |
| Sample: SDE full stack | 34 | 39 | Git, SQL |
| Sample: Cvent intern (partial JD) | 21 | 21 | none |

### 5. Text similarity

`analysis/similarity.py` implements TF-IDF and cosine similarity by hand, using only `math` and `collections.Counter`:

```
tf(t,d)     = count(t,d) / len(d)          how often t appears in d, normalised by length
idf(t)      = log(N / (1 + df(t))) + 1     rarer across the N documents -> larger
tfidf(t,d)  = tf(t,d) * idf(t)
cosine(a,b) = dot(a,b) / (||a|| * ||b||)   angle between the two weight vectors
```

Each document becomes a sparse vector (a `dict` of term to weight). The `1 +` in the IDF denominator avoids dividing by zero, and the trailing `+ 1` keeps every weight positive, so a term in every document is weakened but never erased. The docstring works a two-document example by hand ("apple banana" against "apple cherry" gives 0.2612), and a test checks exactly that number.

**Where IDF comes from.** N and df(t) come from every stored job description plus the four seed JDs (`analysis/corpus.py`), not from the two documents being compared. Words in almost every job post ("team", "build") are weak evidence; rarer shared terms are strong evidence. Terms that appear in no job description (project names, grades) are ignored, because they can't be evidence of fit for a job. The counts are saved in one database row, cached in memory for 10 minutes, and rebuilt when older than an hour, whenever `seed_demo` runs, or with `python manage.py rebuild_corpus`. The job description being analysed counts as one more document, so its rarer terms keep their weight before the next rebuild.

**Why that changed.** The first version computed IDF over just the resume and the job description. With N = 2, a word in both gets `log(2/3) + 1 = 0.59` and a word in only one gets 1.0, so the metric down-weighted exactly the vocabulary the two documents share. On the demo resume, raw cosine sat at 0.03-0.11. Measuring each change separately showed that corpus IDF alone was only part of the fix: 239 of the resume's 310 terms appear in no job description, and those terms dominated the resume vector under either IDF.

| Similarity computed with | Mean cosine (6 JDs) |
|---|---|
| Two-document IDF, all terms (original) | 0.063 |
| Corpus IDF, all terms | 0.082 |
| No IDF, only terms some JD uses | 0.286 |
| **Corpus IDF, only terms some JD uses (shipped)** | **0.237** |

| Job description | Score before | Score after |
|---|---|---|
| Seed: full stack | 35 | 45 |
| Seed: SDE fresher | 31 | 38 |
| Sample: SDE full stack | 27 | 34 |
| Sample: Cvent intern (partial JD) | 13 | 21 |
| Seed: frontend | 21 | 24 |
| Seed: backend | 13 | 16 |

Dropping IDF entirely scores higher (0.286), but IDF stays on purpose: a matched rare skill should count for more than a matched "team", and the goal is a meaningful number, not a bigger one. These scores are from before implied skills were added.

### 6. Scoring

```
overall = round(100 * (
    0.45 * skill_coverage       # fraction of JD skills present in the resume (named or implied)
  + 0.35 * cosine_similarity    # TF-IDF similarity of the full texts
  + 0.20 * category_balance     # mean coverage across the JD's skill categories
))  then clamped to 5-97
```

The weights are a judgement call, not a fitted model. Skill coverage gets the largest share because it is the most direct signal of fit and what screening filters check. Text similarity catches overlap the taxonomy doesn't know about (responsibilities, domain words) but also rewards keyword mirroring, so it gets less. Category balance rewards breadth: a full-stack JD matched only on frontend skills should score lower than one matched across frontend, backend and databases. It averages per-category coverage, so matching one of six requested concepts scores 0.17 rather than counting the category as fully covered. Scaling happens before rounding; rounding the 0-1 blend first would only ever produce 0 or 100.

Missing skills are sorted by how often the JD mentions them. Suggestions come from templates: the most-mentioned missing skills, the weakest category, a skill that is only implied and should be named, and general advice when there are few gaps.

## Design decisions

Non-obvious decisions in the code are marked with `WHY:` comments. The main ones:

**No scikit-learn or numpy.** The whole analysis needs TF-IDF vectors for two documents and a cosine between them. scikit-learn would pull in numpy and scipy, a large dependency chain that slows every cold build on a free-tier host, for about 50 lines of standard-library Python. Writing it by hand also means every smoothing choice is visible and explainable. The trade-off is raw speed, and for documents of a few thousand words the pure-Python version finishes in milliseconds.

**Skill lists are JSONFields, not related tables.** `matched_skills`, `missing_skills`, `category_scores` and `suggestions` are always read whole: one analysis page shows the full lists, and the compare view builds its table in Python. No query filters or joins on an individual skill, so an `AnalysisSkill` table would add a join to every read and a bulk insert to every write while enabling nothing the app needs. JSON also lets each entry carry counts, highlight offsets and inference chains without extra columns. What would force a change is a question *across* analyses, such as "how many analyses were missing Docker?": JSON containment lookups can answer it, but without a real table and index they scan every row. The IDF corpus uses the same reasoning, and a vocabulary of hundreds of thousands of terms would be the point to move it to a row per term.

**The database stores object keys, not file URLs.** Resume PDFs sit in a private bucket and are only served through presigned links that expire after 15 minutes. A stored presigned URL would be dead by the next request, and a stored public URL would make a personal document readable by anyone who ever saw the link. The key (`resumes/<uuid>.pdf`) is the stable identifier and the URL is derived fresh each time. Keeping the provider out of the database paid off: storage moved from Cloudflare R2 (which needs a payment card on file) to Backblaze B2 with only environment variable changes.

**Storage fails fast and says why.** The first production uploads failed with the host's bare 502 page: boto3's default timeouts let a stuck storage call outlive gunicorn's 30-second worker timeout, so the worker died before anything was logged. The client now uses a 5-second connect timeout, a 15-second read timeout and two attempts, and a storage failure returns a JSON `storage_unavailable` (503) and logs the endpoint, bucket and provider error, never the credentials. That log line is what showed the next problem: boto3 sends `Expect: 100-continue` on uploads, and Backblaze B2's interim reply confused its HTTP client (one upload failed with "connection was closed", another stalled for 16 seconds). The header isn't part of the request signature, so the client removes it just before sending, and a test asserts uploads go out without it.

**Components never call the API directly.** Every request goes through `api/client.js` and the `useAnalysis`, `useHistory` and `useCompare` hooks. Loading, error and cold-start handling is written once, components render purely from props, and changing how the frontend talks to the API touches two folders instead of every component.

**Memoization targets the re-renders that actually happen.** The Analyze page re-renders on every keystroke in the job description box and on every upload progress event. `ResultsPanel` and `SkillChipList` are wrapped in `React.memo`, and the chip click handler in `useCallback`, so the results panel only re-renders when the analysis changes and the matched chips only when the selected skill changes. The gauge animation never needed it: its per-frame state lives inside `ScoreGauge`. Removing `memo` from `SkillChipList` and typing in the job description box shows the difference in the React DevTools Profiler.

**Uploads use XMLHttpRequest, not fetch.** `fetch` doesn't report how much of a request body has been sent; `xhr.upload.onprogress` does, and it drives the real progress bar. It also feeds the cold-start logic: the "waking up the server" timer starts only once every byte is sent, so a slow upload isn't mistaken for a sleeping server.

**Cold starts are explained, not hidden.** The free-tier API sleeps after 15 idle minutes and takes about 50 seconds to wake. Any request still pending after 3 seconds shows "Waking up the server, this takes about a minute on the free tier", and the site pings the API as soon as it loads so it is often awake by the time someone has picked their PDF. A silent 50-second spinner looks exactly like a broken site.

**Deletes are optimistic.** A deleted history row disappears immediately and goes back where it was, with a message, if the server refuses. Waiting for the server (possibly through a cold start) with a frozen row feels broken.

**The design is light-only on purpose.** The gauge, chips and coverage bars rely on specific colours. The Dark Reader browser extension rewrote them and made the score almost invisible, so the page opts out with `<meta name="darkreader-lock">`.

**Where it breaks at scale.** At around 1,000 concurrent users, CPU breaks first: PDF extraction and analysis run synchronously inside the request on a single free-tier worker, so uploads queue and time out. Close behind are rate limiting (counted in each worker's local-memory cache, so it stops being a real limit with several workers) and PostgreSQL connections (every worker holds a persistent connection). The first fix is cheap capacity: a paid instance with several gunicorn workers behind a connection pooler, plus a shared Redis cache for throttle counts. Past that, extraction should move to a background job queue, with the upload endpoint returning immediately and the client polling for the result.

## Project structure

```
JobFit/
├── jobfit_api/                   Django project: settings, URLs, error handler, health check
├── resumes/                      Resume model, upload + detail/delete endpoints
├── analysis/
│   ├── skills.py                 skills taxonomy
│   ├── aho_corasick.py           trie, failure links and one-pass search
│   ├── matcher.py                word-boundary skill matching (Aho-Corasick active, regex reference)
│   ├── implications.py           implied-skills graph and breadth-first inference
│   ├── similarity.py             TF-IDF + cosine
│   ├── corpus.py                 IDF corpus: term counts across stored job descriptions
│   ├── scorer.py                 score, gaps, suggestions
│   ├── extractor.py              PDF -> text (pdfplumber, pypdf fallback)
│   ├── service.py                orchestration shared by the API and commands
│   ├── demo.py                   fixed ids and seed files of the read-only demo
│   ├── models.py                 JobDescription, Analysis, CorpusSnapshot
│   ├── views.py, serializers.py, urls.py
│   ├── management/commands/      demo_analyze, seed_demo, rebuild_corpus, benchmark_matcher
│   └── tests/
├── storage/object_storage.py     S3-compatible storage (Backblaze B2) via boto3, local fallback
├── samples/
│   ├── jd_sde_fullstack.txt      sample JD for demo_analyze
│   └── seed/                     demo resume text + four sample JDs for seed_demo
├── frontend/
│   ├── vercel.json               SPA routing for Vercel
│   └── src/
│       ├── api/                  API client, cold-start notice
│       ├── hooks/                useAnalysis, useHistory, useCompare
│       ├── components/           UploadZone, ScoreGauge, SkillChips, ResumeText, ...
│       ├── pages/                Analyze, History, Compare
│       ├── lib/                  limits, formatting, remembered resumes
│       └── styles/
├── docs/screenshot.png
├── .github/workflows/ci.yml      pytest + frontend lint/build on every push
├── render.yaml                   Render web service definition (API)
└── requirements.txt
```

## Local setup

**Requirements:** Python 3.12+, Node.js 22+, PostgreSQL 15+.

Run these in order from the repository root.

```bash
# 1. Get the code
git clone https://github.com/mainak569/JobFit.git
cd JobFit

# 2. Backend dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Database and local settings
createdb jobfit
cp .env.example .env
# Edit .env and set at least:
#   DJANGO_DEBUG=True
#   DATABASE_URL=postgres:///jobfit

# 4. Tables and demo data
python manage.py migrate
python manage.py seed_demo

# 5. Start the API on http://localhost:8000
python manage.py runserver
```

In a second terminal:

```bash
# 6. Frontend on http://localhost:5173
cd frontend
npm ci
npm run dev
```

Without storage credentials, uploaded PDFs are saved to `./media/` and the API logs a warning. Nothing else is needed to run locally.

### Management commands

| Command | What it does |
|---|---|
| `python manage.py demo_analyze <resume.pdf> <jd.txt> [--title ...] [--company ...]` | Extracts, stores and analyses a resume from the terminal, and prints the full analysis. |
| `python manage.py seed_demo` | Loads the demo resume and four sample job descriptions with precomputed analyses, and rebuilds the IDF corpus. Safe to run repeatedly. |
| `python manage.py rebuild_corpus` | Recounts how many stored job descriptions contain each term (the IDF corpus) and prints the most common terms. |
| `python manage.py benchmark_matcher [--repeat N]` | Checks that the regex and Aho-Corasick matchers agree, then times them by text length and by number of patterns. |

Example:

```bash
python manage.py demo_analyze path/to/resume.pdf samples/jd_sde_fullstack.txt --title "SDE I" --company "Example"
```

## Running tests

```bash
# Backend
pytest

# Frontend
cd frontend
npm run lint
npm run build
```

The backend suite covers:

- **Matching:** the word-boundary cases (R/React, Go/Google, Java/JavaScript, SQL/PostgreSQL, C/C++, R&D), highlight offsets, and the Aho-Corasick automaton itself (shared prefixes, failure links, overlapping patterns).
- **Matcher equivalence:** the Aho-Corasick and regex matchers must return identical results on every edge case, every sample document and 400 random texts.
- **Implied skills:** chains, one-way edges, cycles terminating, and every graph node being a real skill.
- **TF-IDF:** hand-calculated values, the original two-document bug, and corpus weights (common words weak, rare words strong).
- **Scoring:** clamping at both ends, category balance, missing-skill order and suggestions.
- **Extraction and storage:** the scanned-PDF error, the local storage fallback, fast failure when storage is unreachable, and uploads without the `Expect` header.
- **API:** every endpoint, the JSON error shape, rate limiting, CORS, the read-only demo, and the seed and corpus commands.

Tests refuse to run if `DATABASE_URL` points at a remote server, because pytest-django creates and drops a test database on whatever server it is given. GitHub Actions runs the whole suite against a PostgreSQL 16 service on every push, plus the frontend lint and build.

## Environment variables

`.env.example` in the root and in `frontend/` lists every key with no values.

### Backend

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | none | Required when `DJANGO_DEBUG` is False. Generate a new one; never reuse the dev one. |
| `DJANGO_DEBUG` | `False` | `True` for local development only. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames, e.g. `your-api.onrender.com`. |
| `DATABASE_URL` | `postgres://localhost:5432/jobfit` | PostgreSQL connection URL. |
| `DJANGO_SECURE_SSL` | on when `DJANGO_DEBUG` is False | Forces HTTPS and secure cookies. Only CI turns it off. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated origins allowed to call the API. Never `*`. |
| `CSRF_TRUSTED_ORIGINS` | none | Comma-separated trusted origins, e.g. the Vercel URL. |
| `NUM_PROXIES` | unset | Set to `1` behind Render's proxy, so rate limiting uses the real client IP. |
| `STORAGE_ENDPOINT` | none | S3 endpoint, e.g. `https://s3.us-west-004.backblazeb2.com`. |
| `STORAGE_REGION` | none | Region matching the endpoint, e.g. `us-west-004`. |
| `STORAGE_BUCKET` | none | Private bucket name, e.g. `jobfit-resumes`. |
| `STORAGE_ACCESS_KEY_ID` | none | Application key id (B2 "keyID"). |
| `STORAGE_SECRET_ACCESS_KEY` | none | Application key secret (B2 "applicationKey"). |

If any `STORAGE_*` variable is missing, files are stored in `./media/` with a warning instead of crashing. On Render, `RENDER_EXTERNAL_HOSTNAME` is added to the allowed hosts automatically.

### Frontend

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Base URL of the API, e.g. `https://your-api.onrender.com/api`. |

## API reference

All endpoints are under `/api/`. `GET /` returns `{"status": "ok", "service": "jobfit-api", "api": "/api/"}`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/resumes/` | Multipart PDF upload (field `file`). Extracts text, stores the file, returns id and a text preview. |
| `GET` | `/api/resumes/<id>/` | One resume, including its full extracted text. |
| `DELETE` | `/api/resumes/<id>/` | Deletes the resume, its analyses, and the stored file. |
| `POST` | `/api/analyze/` | `{resume_id, jd_text, title?, company?}` → the full saved analysis. Rate limited to 20/hour. |
| `GET` | `/api/analyses/?resume_id=` | History for one resume, newest first, 20 per page. |
| `GET` | `/api/analyses/<id>/` | One analysis in full. |
| `DELETE` | `/api/analyses/<id>/` | Deletes one analysis. |
| `GET` | `/api/compare/?resume_id=` | One resume against all its job descriptions, shaped as a table. |
| `GET` | `/api/health/` | `{"status": "ok"}` for uptime pings. |

**Upload rules:** PDF only, checked by the file's first bytes (`%PDF-`) rather than its extension; 5 MB maximum.

**Job description rules:** 50-20,000 characters.

**Analysis shape** (abridged):

```json
{
  "id": "8a384fdd-...",
  "resume_id": "1d481871-...",
  "job_description": { "id": "...", "title": "Frontend Engineer", "company": "Example", "raw_text": "...", "created_at": "..." },
  "overall_score": 61,
  "similarity_score": 0.3182,
  "matched_skills": [
    { "name": "React", "category": "frontend", "jd_count": 2, "resume_count": 1, "resume_spans": [[27, 32]], "inferred_from": null, "inference_path": null },
    { "name": "JavaScript", "category": "languages", "jd_count": 1, "resume_count": 1, "resume_spans": [[40, 47]], "inferred_from": "Next.js", "inference_path": ["Next.js", "React", "JavaScript"] }
  ],
  "missing_skills": [{ "name": "Docker", "category": "devops", "jd_count": 3 }],
  "category_scores": { "frontend": { "label": "Frontend", "matched": 3, "required": 5, "coverage": 0.6 } },
  "suggestions": ["The JD mentions Docker 3 times but it doesn't appear in your resume — consider adding it if you've used it."],
  "created_at": "2026-09-15T00:00:00Z"
}
```

For an inferred skill, `resume_count` and `resume_spans` describe the evidence: where the skill that implies it appears in the resume.

**Compare shape:** `columns` has one entry per analysis; `rows` has one entry per skill; `rows[i].cells[j]` is `"present"`, `"inferred"` (implied by another skill on the resume), `"absent"`, or `null` when job description *j* didn't ask for skill *i*.

**Errors** always have the same shape:

```json
{ "error": { "code": "validation_error", "message": "file: The file is not a PDF.", "fields": { "file": ["The file is not a PDF."] } } }
```

| Code | Status | When |
|---|---|---|
| `validation_error` | 400 | Invalid input (`fields` has per-field messages). |
| `demo_read_only` | 403 | Trying to change the shared demo resume. |
| `not_found` | 404 | Unknown id or endpoint. |
| `method_not_allowed` | 405 | Wrong HTTP method. |
| `scanned_pdf` | 422 | The PDF has no selectable text and needs OCR. |
| `unreadable_pdf` | 422 | The file can't be parsed as a PDF. |
| `throttled` | 429 | More than 20 analyses in an hour. |
| `server_error` | 500 | Unexpected failure (details go to logs, never to the client). |
| `storage_unavailable` | 503 | The file storage service couldn't be reached or refused the upload. |

## Privacy and security

- **No public list of resumes.** There are no accounts, so a list endpoint would show everyone's uploads to everyone. A resume is only reachable by its random UUID, which the uploading browser remembers in `localStorage`.
- **Files are private.** The bucket is private and the database stores the object key, never a URL. Links are presigned on demand and expire after 15 minutes.
- **The demo is read-only.** Every visitor shares the demo resume, so its analyses can't be deleted and new job descriptions can't be analysed against it.
- **Uploads are checked by content**, not by extension or Content-Type, and capped at 5 MB.
- **Rate limiting** on `/api/analyze/`: 20 per hour per client IP.
- **CORS** is an explicit allow-list read from the environment.
- **Credentials never reach logs.** Storage errors log the endpoint, bucket and provider message only.
- The demo resume text has phone numbers and email addresses removed.

## Deployment

Everything runs on free plans that don't need a payment card.

| Part | Service | Config |
|---|---|---|
| API | Render web service, Singapore region | `render.yaml` |
| Database | Neon PostgreSQL | `DATABASE_URL` |
| Resume PDFs | Backblaze B2, private bucket (S3-compatible) | `STORAGE_*` |
| Frontend | Vercel | `frontend/vercel.json`, `VITE_API_BASE_URL` |

**Steps**

1. **Neon:** create a project and copy the connection string with connection pooling turned off (it includes `sslmode=require`). This is `DATABASE_URL`. Django keeps its own persistent connections, which don't mix well with a transaction-mode pooler.
2. **Backblaze B2:** create a *private* bucket, then an application key restricted to that bucket with read and write access. Note the keyID, the applicationKey, and the bucket's S3 endpoint (e.g. `s3.us-west-004.backblazeb2.com`, whose region is `us-west-004`). The keyID and applicationKey must come from the same key.
3. **Render:** New → Blueprint → select this repository. Fill in the variables marked `sync: false`. Every build runs `collectstatic`, `migrate` and `seed_demo` (idempotent), because the free plan has no shell to run them afterwards.
4. **Vercel:** import the repository with root directory `frontend`, framework Vite, and set `VITE_API_BASE_URL` to `https://<your-service>.onrender.com/api`.
5. **Render again:** set `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to the Vercel URL and redeploy.

**Production settings:** `DEBUG` off, a generated `SECRET_KEY`, HTTPS redirect with Render's proxy header trusted, secure session and CSRF cookies, a short HSTS header, whitenoise for static files, gunicorn as the server, and logs to stdout.

**Free-tier reality:** the Render API sleeps after 15 minutes without traffic and takes roughly 50 seconds to wake. The site shows a "waking up the server" notice when a request takes longer than 3 seconds, and pings the API as soon as the page opens.

## Known limitations

- **Keyword matching, not understanding.** A skill counts only if it is named, or implied by a named skill through a small hand-written graph. "Go" can match the English verb ("ready to go live").
- **Implications trust the evidence they are given.** "GitHub" implies Git whether it appears in a project description or only as a profile link in the header.
- **IDF is only as good as the corpus.** With a handful of stored job descriptions, generic words that happen to appear in only one of them ("time", "world") still count as rare. The weights improve as more job descriptions are analysed.
- **The score is a heuristic.** The 0.45 / 0.35 / 0.20 weights are chosen, not fitted to hiring outcomes.
- **English-centric taxonomy**, weighted toward Indian SDE and frontend roles; skills outside the 146 are invisible to the skill score.
- **Scanned PDFs aren't supported.** There is no OCR; the API explains this instead of returning empty text.
- **Access by id is not real authentication.** Anyone given a resume's id can read it.
- **Rate limits are per server process**, so they loosen if the API runs several workers.
- **Remembered resumes live in one browser.** Clearing site data or switching devices loses the list (the data stays on the server).
- **Analyses keep the scoring they were saved with.** Older analyses don't pick up later scoring changes; the demo is re-seeded on every deploy.
- **Cold starts** on the free tier, as described above.
