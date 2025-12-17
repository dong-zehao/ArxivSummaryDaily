# Repository Guidelines

## Project Structure & Module Organization
- `src/`: core logic. `arxiv_client.py` fetches and dedupes papers; `paper_summarizer.py` drives LLM calls; `site_manager.py` builds the Pages site (CLI `arxivsite`); `cli.py` wires the `arxivsummary` entry point.  
- `config/`: copy `settings.example.py` to `settings.py` for local secrets; GitHub Actions injects `LLM_API_KEY` automatically.  
- `data/`: generated summaries, metadata (`metadata.json`), and `last_run.json`; treated as build artifacts.  
- `tests/`: `unittest` suites for clients and site tools.  
- `.github/workflows/pages.yml`: scheduled build/deploy to `gh-pages`.

## Setup, Build, Test, and Run
- Install deps: `pip install -r requirements.txt` then `pip install -e .` to expose the CLIs.  
- Local run: `arxivsummary --query "cuprate" --max-results 10 --output-dir ./data` (uses `config/settings.py` defaults otherwise).  
- Site generation: `arxivsite --data-dir ./data --github-dir ./.github --days 7` to prune old outputs and refresh the Pages content.  
- Tests: `python -m unittest discover -s tests -v`. Avoid running against real LLM keys when not needed.

## Coding Style & Naming Conventions
- Python 3.9+, PEP 8, 4-space indentation; prefer f-strings and pathlib over os.path.  
- Functions and variables in `snake_case`; classes in `PascalCase`; constants and configuration in `UPPER_SNAKE_CASE`.  
- Keep CLI arguments short and documented; reuse existing patterns in `cli.py`/`site_manager.py`.  
- Avoid logging secrets; read API keys from env (`LLM_API_KEY`) rather than committing them.

## Testing Guidelines
- Favor `unittest` style consistent with current suites (`tests/test_*.py`).  
- Include minimal fixtures; when network-dependent, gate with env flags or clearly mark assumptions.  
- For new modules, add constructor/edge-case coverage and a smoke test for CLI entry points if behavior changes.

## Commit & Pull Request Guidelines
- Commit messages follow short, imperative phrases (e.g., “Update days parameter for site generation”).  
- Before opening a PR: describe the change and runtime impact, note config or secret expectations, and link any related issue.  
- Include screenshots or sample output when modifying generated site layouts or summary formatting.  
- Ensure PRs pass `python -m unittest …` and do not include real keys in `config/settings.py` or `.env`.
