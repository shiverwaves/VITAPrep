"""
FastAPI application — single process, no worker proxy.

Endpoints:
- POST /api/v1/scenarios — generate new scenario
- GET  /api/v1/scenarios/{id} — get scenario + document URLs
- POST /api/v1/scenarios/{id}/submit — submit answers for grading
- GET  /api/v1/scenarios/{id}/answer-key — get answer key
- GET  /api/v1/config/states — available states
- GET  /api/v1/progress — student history
"""

# TODO: Sprint 7 — implement FastAPI app
# Reference: HouseholdRNG/api/main.py for patterns, but simplify (no worker proxy)
