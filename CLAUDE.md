# ISM-MICMAC (project2025)

Streamlit app. Development happens locally on Windows, and the app is deployed from GitHub to Streamlit Community Cloud. Every change must work in both environments.

Communicate with the user in Hebrew.

## Local workflow (Windows)

- `.\dev.ps1 setup`: run once. It creates the venv at `%USERPROFILE%\.venvs\project2025`, outside OneDrive and outside AppData, because Microsoft Store Python redirects writes under AppData. It also creates the local `.streamlit/secrets.toml`, which git ignores.
- `.\dev.ps1 run`: starts the app at http://localhost:8501.
- `.\dev.ps1 check`: runs a syntax check, `pip check` and `pytest`. These are the same checks GitHub Actions runs (`.github/workflows/tests.yml`).

The local database lives in `%USERPROFILE%\.ism_micmac\ism_data.db`. The location is set through `ISM_DB_PATH` in the local secrets.

## Rules for every upgrade

1. Develop and test locally. Run `.\dev.ps1 check` before every commit, and it must be green.
2. Keep cloud parity:
   - Pin every new dependency in `requirements.txt` to the exact version installed in the local venv. Streamlit Cloud installs only from that file.
   - Read every new setting through `_get_secret()`, which reads st.secrets first and falls back to environment variables. Add the key to `.streamlit/secrets.toml.example`, and tell the user to add it in Streamlit Cloud under Settings > Secrets.
   - Use only Python code, with no Windows-only paths or tools, so it also runs on Linux.
   - The Streamlit Cloud filesystem is ephemeral, so the SQLite file is wiped whenever the app restarts there.
3. Add or extend tests in `tests/` for new behavior. Pure logic goes in `ism_core.py`, persistence in `storage.py`, and full-app flows in `tests/test_app_smoke.py` (AppTest).
4. Commit on a feature branch, then push. The user's fork is `osher2002/project2025`, and PRs target `matanrauf1-lgtm/project2025` main.

## Code layout

- `project2025.py`: the UI (Streamlit) and the AI engine.
- `ism_core.py`: the math (closure, levels, MICMAC classic/Godet/Katz), with no Streamlit dependency.
- `storage.py`: SQLite persistence that all sessions share.

## Thesis

The thesis document is built from scripts in `thesis_work_bundle.tgz`. See the `BUILD.md` inside it, and build with `THESIS_PDF_ENGINE=word` on Windows. Do not hand-edit the generated .docx, because the next build overwrites it.
