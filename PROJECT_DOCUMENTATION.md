# 🤖 HireIQ - Comprehensive System Architecture & AI Developer Guide

## 1. Executive Summary & Purpose
**HireIQ** ("Smart Hiring, Zero Effort") is an automated, AI-driven recruitment platform. It leverages **LangGraph**, **Streamlit**, and **Gemini models** to perform end-to-end recruitment workflows:
- Conversational Job Description (JD) parsing & confirmation.
- Bulk resume parsing & qualification screening.
- Automated technical background verification using the public GitHub API.
- Multi-factor semantic scoring & candidate ranking using Chain-of-Thought (CoT) reasoning.
- Calendar availability parsing (`iCal`/Google Calendar) and rank-prioritized interview scheduling.
- Automated SMTP notification & interview invitation emails.

---

## 2. Directory & File Sitemap

```
HireIQ/
├── app.py                          # Streamlit UI, auth, session history, dashboard, page rendering
├── chat_jd_confirmation.py         # Chat-based state machine for interactive JD detail confirmation
├── orchestration.py                 # LangGraph dynamic workflow definition & node execution
├── database.py                     # SQLite database management, schemas, bcrypt auth, session queries
├── requirements.txt                # Project dependencies (Streamlit, Gemini client, LangGraph, PyPDF2, etc.)
├── config/
│   ├── workflow_config.py          # Dataclasses & enums for workflow pipeline configurations
│   ├── email_templates.json        # HTML/Text email templates for in-person and online interviews
│   ├── calendar_config.json        # iCal scheduling preferences (timezones, durations, buffer times)
│   └── smtp_config.json            # SMTP server configurations for sending emails
└── src/
   ├── agents/
   │   ├── resume_screener.py      # Resumes screening against JD criteria
   │   ├── background_analyzer.py  # GitHub API-based verification (profiles, repos, followers)
   │   ├── candidate_ranker.py     # Multi-criteria semantic scoring & candidate ranking
   │   ├── calendar_scheduling_agent.py # iCal calendar slot search & rank-based allocation
   │   └── communication_agent.py  # Real SMTP email invitation dispatcher
   └── utils/
      ├── file_parser.py          # PDF and DOCX text extraction utilities
      ├── jd_analyzer.py          # Semantic LLM JD parser & workflow reasoner
      └── llm_helper.py           # Native Gemini API helper, JSON cleaner, and prompt helpers
```

---

## 3. Technology Stack & Key Dependencies

- **Framework / UI**: Streamlit (`streamlit>=1.28.0`)
- **Orchestration**: LangGraph (`langgraph`, `langchain`)
- **LLM & Agents**: Native Gemini API (`gemini-3.8-flash`), GitHub API verification, `requests`
- **Database**: SQLite3 (`recruitment.db`), `bcrypt>=4.0.0`
- **Document Processing**: `PyPDF2`, `pdfplumber`, `python-docx`
- **Calendar & Time**: `icalendar`, `pytz`
- **Data & Charts**: `pandas`, `plotly`

---

## 4. Database Schema (`database.py`)

SQLite Database File: `recruitment.db`

### Tables
1. `users`
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `username`: TEXT UNIQUE NOT NULL
   - `email`: TEXT UNIQUE NOT NULL
   - `company_name`: TEXT
   - `password_hash`: TEXT NOT NULL
   - `role`: TEXT DEFAULT 'user'
   - `created_at`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

2. `recruitment_sessions`
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `user_id`: INTEGER NOT NULL (FK -> `users.id`)
   - `session_name`: TEXT NOT NULL
   - `job_description`: TEXT
   - `job_title`: TEXT
   - `resume_count`: INTEGER DEFAULT 0
   - `workflow_config`: TEXT (JSON)
   - `results_json`: TEXT (JSON)
   - `created_at`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

3. `candidates`
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `session_id`: INTEGER NOT NULL (FK -> `recruitment_sessions.id`)
   - `candidate_name`: TEXT NOT NULL
   - `email`: TEXT
   - `phone`: TEXT
   - `score`: REAL
   - `rank`: INTEGER
   - `interview_date`: TEXT
   - `interview_time`: TEXT
   - `status`: TEXT DEFAULT 'pending'

---

## 5. LangGraph State Machine & ReAct Pipeline (`orchestration.py`)

### `RecruitmentState` Schema
```python
class RecruitmentState(TypedDict):
    candidates: list
    screening_results: Dict[str, Any]
    background_results: Dict[str, Any]
    ranking_results: Dict[str, Any]
    scheduled_interviews: Dict[str, Any]
    communication_results: Dict[str, Any]
    current_step: str
    error: str
    workflow_config: Dict[str, Any]
    jd_analysis: Dict[str, Any]
    requires_frontend_action: bool
    frontend_action: Dict[str, Any]
    reasoning: Dict[str, str]
```

### Graph Flow & Nodes

```
[Entry Point: jd_reasoner]
        │
        ▼
   [screening]
        │
        ├── router_after_screening
        │     ├─► "run_background" ──► [background_check] ──┐
        │     └─► "skip_background" ────────────────────────┼─► [ranking]
        │                                                   │
        └───────────────────────────────────────────────────┘
                                                              │
                                                   router_after_ranking
                                                      ├─► "run_scheduling" ──► [scheduling] ──► [communication] ──► END
                                                      └─► "skip_scheduling" ──────────────────────────────────────────► END
```

1. **`jd_reasoner`**: Runs `SemanticJDAnalyzer.reason_about_workflow()` on `job_description.txt` to detect if the role is technical, requires background verification, or requires scheduling.
2. **`screening`**: Calls `ResumeScreeningAgent.bulk_screen()`. Returns `eligible_candidates` and `ineligible_candidates`.
3. **`_router_after_screening`**: Conditional edge. If `is_technical` or user requested background check -> routes to `background_check`; else routes to `ranking`.
4. **`background_check`**: Calls `BackgroundVerifierLocalAgent.verify_candidates()`.
5. **`ranking`**: Calls `CandidateRankingAgent.rank_candidates()`. Sorts by `comprehensive_score`.
6. **`_router_after_ranking`**: Conditional edge. If scheduling is enabled -> routes to `scheduling`; else routes to `END`.
7. **`scheduling`**: Calls `CalendarSchedulingAgent.schedule_interviews()`. Allocates earliest calendar slots to highest-ranked candidates.
8. **`communication`**: Calls `CommunicationAgent.send_interview_confirmation()`. Dispatches emails.

---

## 6. Component Detailed Specifications

### A. Chat JD Confirmation (`chat_jd_confirmation.py`)
- Manages an interactive conversation loop (`ChatState` enum: `GREETING`, `EXTRACTING`, `CONFIRM_TITLE`, `CONFIRM_REQUIREMENTS`, `CONFIRM_QUALIFICATIONS`, `CONFIRM_EXPERIENCE`, `CONFIRM_LOCATION`, `FINAL_SUMMARY`, `COMPLETE`).
- Allows the user to confirm or edit extracted JD metadata prior to execution.

### B. Resume Screener Agent (`src/agents/resume_screener.py`)
- Reads raw files (`.pdf`, `.docx`) via `ResumeParser`.
- Uses `LLMHelper.screen_eligibility()` to test candidate against job requirements.
- Returns eligibility status, reason, extracted email/phone, and profile links (GitHub, LinkedIn).

### C. Background Verifier Local Agent (`src/agents/background_analyzer.py`)
- Uses the public GitHub API to verify profile activity and repository metadata.
- Extracts GitHub usernames from resumes or candidate metadata.
- Combines GitHub signals with LinkedIn presence to compute verification scores.

### D. Gemini LLM Helper (`src/utils/llm_helper.py`)
- Provides the native Gemini REST client wrapper used by screening, JD extraction, and ranking.
- Handles `.env` loading for `GEMINI_API_KEY`, `GEMINI_MODEL`, and `GEMINI_BASE_URL`.
- Converts chat-style prompts into Gemini `generateContent` requests and normalizes JSON responses.

### E. Candidate Ranker Agent (`src/agents/candidate_ranker.py`)
- Computes four weighted sub-scores:
  1. `resume_score`: Base candidate eligibility score.
  2. `verification_score`: GitHub / web audit score.
  3. `skills_semantic`: LLM semantic skill match against JD requirements.
  4. `experience_semantic`: LLM experience fit against JD expectations.
- Calculates `comprehensive_score` and sorts candidates descending to compute numerical `rank` (1 = Top Candidate).

### F. Calendar Scheduling Agent (`src/agents/calendar_scheduling_agent.py`)
- Fetches and parses iCal URLs (`.ics`).
- Respects recruiter configuration: working hours (e.g., 09:00 - 18:00), working days (Mon-Fri), timezone (e.g. `Asia/Kolkata`), interview duration (60 min), and buffer time (15 min).
- Priority Scheduling Algorithm: Candidate with Rank 1 gets the earliest available open slot on the recruiter's calendar.

### G. Communication Agent (`src/agents/communication_agent.py`)
- Connects via standard Python `smtplib` using SSL/TLS.
- Renders template variables (`{candidate_name}`, `{job_title}`, `{interview_date}`, `{interview_time}`, `{meeting_link}`).
- Supports sending both real emails and simulated dry-run tests.

---

## 7. Configuration Files Reference

### `config/calendar_config.json`
```json
{
  "timezone": "Asia/Kolkata",
  "interview_duration_minutes": 60,
  "buffer_minutes": 15,
  "work_hours_start": "09:00",
  "work_hours_end": "18:00",
  "work_days": [0, 1, 2, 3, 4]
}
```

### `config/smtp_config.json`
```json
{
  "sender_email": "recruitment@yourcompany.com",
  "sender_name": "HireIQ System",
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "use_tls": true,
  "test_mode": false
}
```

---

## 8. Execution Instructions

1. **Environment Setup**:
   Ensure `.env` contains:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-3.8-flash
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Launch Web Application**:
   ```bash
   streamlit run app.py
   ```
