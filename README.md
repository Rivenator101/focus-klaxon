# Focus Klaxon

CLI focus enforcer with escalation:

1. Detect distraction site in active window title
2. Warn with popup and countdown
3. Mouse chaos if ignored
4. Force-close foreground tab/window and open your focus page

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## GitHub Pages Setup (2 minutes)

This repo is prepared for Pages from `docs/`.

1. Push this folder to a GitHub repo named `focus-klaxon`
2. In GitHub: **Settings -> Pages**
3. Under **Build and deployment**, set:
   - **Source**: Deploy from a branch
   - **Branch**: `main`
   - **Folder**: `/docs`
4. Save and wait ~1 minute
5. Your URL will be:
   - `https://<your-github-username>.github.io/focus-klaxon/`
6. Put that URL into `config.json` as `work_url`

## Notes

- If macOS blocks mouse/window control, enable Accessibility permissions for your terminal app.
- `docs/index.html` is the hosted focus dashboard.
