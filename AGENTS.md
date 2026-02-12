# Repository Guidelines

## Project Structure & Module Organization
VisionLink is a Python application for a Raspberry Pi wearable assistant. Entry point is `main.py`, with runtime settings in `config.py` and secrets in `.env` (copy from `.env.example`).

Core code lives in `src/`:
- `src/hardware/`: GPIO buttons, camera, audio I/O
- `src/ai/`: Gemini, Soniox STT stub, TTS, QR scanning
- `src/cloud/`: Supabase integration
- `src/subsystems/`: documentation and assistant workflows
- `src/utils/`: logging and email helpers

Supporting docs include `PLAN.md`, `HARDWARE_CONNECTION.md`, and `AGENT_HANDOFF.md`. Local runtime artifacts are written to `~/visionlink/logs` and `~/visionlink/sessions` (not committed).

## Build, Test, and Development Commands
Use Python 3 on Raspberry Pi/Linux.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 main.py
```

- `pip install -r requirements.txt`: installs AI/cloud/hardware dependencies.
- `python3 main.py`: starts VisionLink and initializes hardware/services.
- `python3 -m unittest discover -s tests -p "test_*.py"`: runs unit tests.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and clear, small functions. Use:
- `snake_case` for functions/variables/modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants in `config.py`

Prefer type hints and concise docstrings for public methods. Keep hardware side effects inside `setup()/cleanup()` patterns used across modules.

## Testing Guidelines
Place tests under `tests/` and name files `test_*.py`. Mirror source structure where practical (for example, `tests/test_session_manager.py` for `src/subsystems/session_manager.py`). Prioritize:
- button event handling
- session lifecycle logic
- API client failure/retry paths

Mock hardware/network calls to keep tests deterministic.

## Commit & Pull Request Guidelines
Current history has one commit (`Initial commit`), so no strict convention is established yet. Use short, imperative commit messages (for example, `audio: switch recorder to ALSA path`).

For PRs, include:
- purpose and scope
- linked issue/task
- hardware impact (GPIO/audio/camera)
- test evidence (command + result)
- logs/screenshots only when they clarify runtime behavior

## Security & Configuration Tips
Never commit `.env`, API keys, or service credentials. Keep `.env.example` updated when adding config values. Validate all new secrets are loaded through `config.py`.
