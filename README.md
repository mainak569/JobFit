<div align="center">

# JobFit

**Checks how well a resume matches a job description — skill matching, implied skills, and TF-IDF fit scoring, all written by hand — then runs a mock interview on what it found.**

<a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" /></a>
<a href="https://www.djangoproject.com"><img src="https://img.shields.io/badge/Django-5-092E20?logo=django&logoColor=white" alt="Django 5" /></a>
<a href="https://www.django-rest-framework.org"><img src="https://img.shields.io/badge/Django_REST_Framework-API-A30000?logo=django&logoColor=white" alt="Django REST Framework" /></a>
<a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL via Neon" /></a>
<a href="https://react.dev"><img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React 18" /></a>
<a href="https://vitejs.dev"><img src="https://img.shields.io/badge/Vite-Bundler-646CFF?logo=vite&logoColor=white" alt="Vite" /></a>
<br />
<a href="https://www.backblaze.com/cloud-storage"><img src="https://img.shields.io/badge/Backblaze_B2-S3_API-E21E29?logo=backblaze&logoColor=white" alt="Backblaze B2" /></a>
<a href="https://render.com"><img src="https://img.shields.io/badge/Render-Hosting-46E3B7?logo=render&logoColor=white" alt="Render" /></a>
<a href="https://vercel.com"><img src="https://img.shields.io/badge/Vercel-Frontend-000000?logo=vercel&logoColor=white" alt="Vercel" /></a>
<a href="https://ai.google.dev"><img src="https://img.shields.io/badge/Gemini-Interviewer-8E75B2?logo=googlegemini&logoColor=white" alt="Gemini" /></a>
<a href="https://groq.com"><img src="https://img.shields.io/badge/Groq-Fallback_%2B_Whisper-F55036" alt="Groq" /></a>

<p>
  <a href="https://jobfit-livid.vercel.app"><strong>Live Demo</strong></a> ·
  <a href="#how-the-analysis-works">How It Works</a> ·
  <a href="#local-setup">Getting Started</a>
</p>

</div>

https://github.com/user-attachments/assets/7d73b2fd-7465-4523-90ad-24f69be12706

Upload a resume PDF and paste a job post. JobFit extracts the text, finds the skills both documents mention, fills in skills the resume implies but never names, scores the fit, and tells you what's missing. Every analysis is saved, so one resume can be compared against several jobs. From any analysis you can practise a mock interview built on what it found.

> **Note:** No machine-learning libraries in the analysis — the matching, the implied-skills graph and TF-IDF are all written by hand. The mock interview is the one part that calls an LLM (Gemini, with Groq as fallback).

## Features

**Analysis**
- Match score from 0 to 100, clamped to 5-97.
- Skills in both documents, skills the job asks for that the resume lacks, and implied skills shown as "Python via Django".
- Coverage by area and 3-5 concrete suggestions.
- Click a skill to highlight every occurrence in the resume text.
- History of every analysis, and a compare table for one resume across several jobs.

**Mock interview**
- About six questions picked from the analysis: a project warm-up, depth on matched skills, an implied skill, the gaps, and one behavioural question.
- One follow-up when an answer is vague.
- Typed or spoken answers (recorded in the browser, transcribed by Groq Whisper).
- A report with a 1-5 score per question, what worked, what to improve, and an outline of a strong answer.

## Architecture

```
React (Vercel)
      │  upload PDF + JD text
      ▼
Django + DRF (Render)
      ├──> Backblaze B2    (private PDF storage, S3-compatible)
      ├──> analysis engine (pure Python, no ML libs)
      ├──> Gemini / Groq   (mock interview, speech to text)
      └──> PostgreSQL      (Neon)
```

## How the analysis works

1. **Extraction.** pdfplumber with `x_tolerance=1.5` (the default glued LaTeX resumes into `Developedamulti-agentworkflow...`), pypdf as a fallback, and a `scanned_pdf` error when there is no text layer.
2. **Skill matching.** 146 skills and 300 aliases with explicit word boundaries, so "R" never matches inside "React", "Java" inside "JavaScript" or "C" inside "C++". All aliases sit in one hand-written **Aho-Corasick** automaton (trie + failure links), so the text is scanned once instead of once per skill. It returns exactly what the regex reference matcher returns, checked on every test case and 400 random texts.
3. **Implied skills.** A directed graph (Django → Python, Next.js → React → JavaScript) walked with a multi-source breadth-first search. Implied skills count as covered but always stay marked as implied.
4. **Similarity.** Hand-written TF-IDF and cosine similarity. IDF comes from a corpus of job descriptions, not from the two documents being compared.
5. **Score.** `round(100 × (0.45 × skill coverage + 0.35 × cosine + 0.20 × category balance))`, clamped to 5-97.

Aho-Corasick against the regex matcher on a 37,639-character text (`python manage.py benchmark_matcher`, fastest of 15 runs):

| Skills | Regex matcher | Aho-Corasick | Speed-up |
|---|---|---|---|
| 146 | 71 ms | 9.6 ms | 7.4× |
| 2,146 | 1,110 ms | 10.0 ms | 111× |
| 8,146 | 4,266 ms | 10.6 ms | 403× |

## Mock interview

`interviews/planner.py` picks the topic of every question from the analysis; the LLM only phrases the questions, decides on follow-ups and grades. An interview makes at most 8 AI calls. Gemini (`gemini-flash-lite-latest`) is tried first and Groq (`openai/gpt-oss-120b`) takes over on any failure. Emails and phone numbers are removed from the resume before it is sent, and candidate text goes inside tags the model is told to treat as data. Each answer carries a `turn` number, so a double submit gets `409 turn_conflict`.

## Local setup

**Requirements:** Python 3.12+, Node.js 22+, PostgreSQL 15+.

```bash
git clone https://github.com/mainak569/JobFit.git
cd JobFit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

createdb jobfit
cp .env.example .env   # set DJANGO_DEBUG=True and DATABASE_URL=postgres:///jobfit
python manage.py migrate
python manage.py seed_demo
python manage.py runserver

# in a second terminal
cd frontend && npm ci && npm run dev
```

Without storage credentials, PDFs are saved to `./media/`. For the mock interview add `GEMINI_API_KEY` and/or `GROQ_API_KEY` to `.env`; spoken answers need the Groq key. Every variable is listed in `.env.example`.

## Running tests

```bash
pytest                                      # backend
cd frontend && npm run lint && npm run build
```

GitHub Actions runs both on every push, with the backend against PostgreSQL 16.

## API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/resumes/` | Upload a PDF (field `file`); returns its id and a text preview |
| `GET` `DELETE` | `/api/resumes/<id>/` | One resume |
| `POST` | `/api/analyze/` | `{resume_id, jd_text, title?, company?}` → the saved analysis |
| `GET` | `/api/analyses/?resume_id=` | History for one resume |
| `GET` `DELETE` | `/api/analyses/<id>/` | One analysis |
| `GET` | `/api/compare/?resume_id=` | One resume against all its job descriptions |
| `POST` | `/api/interviews/` | Start from `{analysis_id}`, or `{resume_id, jd_text \| role}` |
| `GET` `DELETE` | `/api/interviews/<id>/` | Session, transcript and report |
| `POST` | `/api/interviews/<id>/answer/` | `{text, turn}` → the next interviewer message |
| `POST` | `/api/interviews/<id>/finish/` | Grade the answered questions |
| `POST` | `/api/interviews/<id>/transcribe/` | Audio → `{"text"}`, nothing saved |

Errors always have the same shape: `{"error": {"code": "...", "message": "...", "fields": {...}}}`.

## Privacy and security

- Resume PDFs sit in a private bucket and are served through presigned links that expire after 15 minutes.
- There are no accounts and no list endpoints; a resume is only reachable by its random id.
- Uploads are checked by content (`%PDF-`), not extension, and capped at 5 MB.
- Rate limits per IP: 20 analyses, 10 interview starts, 60 answers and 60 recordings an hour.
- Recordings are never stored, and credentials and prompts never reach the logs.

## Deployment

API on Render (`render.yaml`), database on Neon, PDFs on Backblaze B2, frontend on Vercel, and the interview on the Gemini and Groq free tiers. The free API sleeps after 15 idle minutes and takes about 50 seconds to wake, so the site shows a "waking up the server" notice instead of a silent spinner.

## Known limitations

- Keyword matching, not understanding: a skill counts only if it is named or implied by the small graph.
- The 0.45 / 0.35 / 0.20 weights are chosen, not fitted to hiring outcomes.
- Scanned PDFs aren't supported (no OCR).
- Access by id is not real authentication.
- Every visitor shares the free AI quota, so interviews can return `ai_unavailable` on a busy day.
