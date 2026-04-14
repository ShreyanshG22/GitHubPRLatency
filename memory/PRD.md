# PR Review Bot - Product Requirements Document

## Original Problem Statement
Create a FastAPI backend for a GitHub App that reviews pull requests with webhook handling, signature validation, PR diff fetching, AI-powered code analysis, and automated review comment posting.

## Architecture
- **Backend**: FastAPI (Python) on port 8001
- **Frontend**: React dashboard on port 3000
- **Database**: MongoDB (motor async driver)
- **AI**: OpenAI GPT-5.2 via Emergent LLM key
- **Auth**: JWT (httpOnly cookies) with bcrypt password hashing

## User Personas
- **Admin**: Manages the bot, views webhook logs and review history
- **Developer**: Configures GitHub App to point webhook at this service

## Core Requirements (Static)
1. POST /api/github-webhook - accepts GitHub webhook events
2. Validate webhook signatures (HMAC-SHA256)
3. Extract PR number and repository from payload
4. Fetch PR diff via GitHub API
5. Send diff to GPT-5.2 for performance analysis
6. Post review comments back on the PR
7. JWT auth for dashboard access

## What's Been Implemented (April 2026)
- Full JWT auth (register, login, logout, refresh, forgot/reset password, brute force protection)
- GitHub webhook endpoint with signature validation
- Background PR processing (fetch diff → analyze → post comments)
- AI code analysis via Emergent LLM integration (GPT-5.2)
- Dashboard API (stats, webhook logs, reviews, review detail)
- Monitoring frontend (login, dashboard with stats/tables, review detail page)
- Admin seeding on startup
- MongoDB indexes

## Backend Modules
- `server.py` - Main FastAPI app with auth + webhook + dashboard endpoints
- `github_client.py` - GitHub API client (fetch diffs, validate signatures)
- `analyzer.py` - Code analysis using LLM
- `comment_bot.py` - Post review comments to GitHub
- `models.py` - Pydantic models

## Prioritized Backlog
### P0 (Done)
- [x] Webhook endpoint with signature validation
- [x] PR diff fetching
- [x] AI code analysis
- [x] Comment posting
- [x] JWT auth
- [x] Monitoring dashboard

### P1
- [ ] Rate limiting on webhook endpoint
- [ ] Webhook retry handling
- [ ] Custom analysis rules/configuration
- [ ] Multi-repo support with per-repo settings

### P2
- [ ] Analysis history trends/charts
- [ ] Email notifications for critical findings
- [ ] Team management (multiple users)
- [ ] Webhook delivery replay

## Iteration 2 — Diff Parser Module (April 2026)
- Created `/app/backend/diff_parser.py` with modular functions
- Language detection: Python (.py, .pyw, .pyi) and C++ (.cpp, .cc, .cxx, .c, .hpp, .hxx, .h)
- Change classification: `added` (new code) vs `modified` (changed existing code)
- Integrated into webhook processing pipeline (parse_diff → format_blocks_for_analysis → LLM)
- Added POST /api/parse-diff endpoint for direct testing
- 19/19 backend tests passed
