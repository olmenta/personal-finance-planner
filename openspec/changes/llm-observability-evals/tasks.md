# Tasks — LLM Observability & Evals

## 1. Telemetry wiring

- [ ] 1.1 `uv add --group dev deepeval`; confirm prod dependency set unchanged
- [ ] 1.2 `Settings`: add `confident_api_key`, `app_env` (or reuse existing signal), `llm_telemetry_enabled` (default False); document both keys in `backend/.env.example`
- [ ] 1.3 `app/telemetry.py`: `configure_llm_telemetry()` registering LiteLLM success/failure callbacks per design D2 gate; call it from `app/main.py` startup
- [ ] 1.4 Enrich failure logs in both `_call_model` sites with error class + cause chain (no prompt/message content)

## 2. Eval suites

- [ ] 2.1 `backend/evals/` package with `README.md` documenting the run command and the prompt-version-bump workflow (design D5)
- [ ] 2.2 Onboarding fixtures: ≥6 `(conversation, expected_extraction)` pairs covering chips, checkboxes, free text ("fully electric, no gas"), money, and skip-ahead answers
- [ ] 2.3 `evals/test_onboarding_evals.py`: extraction exact-field accuracy + G-Eval proposal-quality rubric over fixture-completed interviews
- [ ] 2.4 Category-suggestion fixtures: ≥10 labeled Spanish bank rows (category id + clean payee expected) against a fixture tree
- [ ] 2.5 `evals/test_category_suggestion_evals.py`: categorization accuracy + payee-cleaning checks
- [ ] 2.6 Confirm `uv run pytest` still excludes `evals/` and runs at current speed

## 3. Verification

- [ ] 3.1 `uv run pytest` green
- [ ] 3.2 With `CONFIDENT_API_KEY` set: run one onboarding turn + one eval run, confirm traces/eval results appear in Confident AI
- [ ] 3.3 With key unset: confirm no callbacks registered (no network attempts, logs clean)
