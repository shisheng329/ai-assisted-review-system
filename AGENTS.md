# AI Coding Guidelines

This repository is a Python / Streamlit / SQLite application for AI-assisted literature screening and analysis.

## Project Rules

- Read `PROJECT_CONTEXT.md`, `TODO.md`, `README.md`, and the relevant module code before making broad changes.
- Keep changes scoped to the requested behavior. Do not perform opportunistic refactors.
- Do not add a frontend build chain. This project does not use React, Vue, Next.js, Fallow, or Sentrux.
- Do not change database schema unless the task explicitly requires a compatible migration.
- Do not submit `.env`, Streamlit secrets, databases, uploads, exports, logs, caches, or user data.
- Do not add mock data to production paths.
- Do not start or delegate work to subagents unless the user explicitly allows it.

## Validation Rules

- Prefer `ast.parse` for syntax checks. Avoid `python -m compileall app` because Windows cache writes can fail in this workspace.
- Use short, observable commands with timeouts. Stop and diagnose any command that runs abnormally long.
- Do not run unbounded BERTopic, `sentence_transformers`, `transformers`, `umap`, `hdbscan`, or model-download commands.
- BERTopic execution must remain subprocess-controlled with a timeout and clear failure reporting.
- Tests must use temporary `DATABASE_PATH`, `UPLOADS_PATH`, and `EXPORTS_PATH`; never test against the user's real local data.

## Git Rules

- Stage exact public files only. Do not use broad staging when privacy or unrelated files are in scope.
- Keep `开发记录.md` out of public commits unless the user explicitly confirms it should be included.
- If `.git/index.lock` appears, verify no real Git write process is active before removing it.
