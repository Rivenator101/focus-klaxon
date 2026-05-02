# Focus Klaxon

CLI focus enforcer with escalation:

1. Detect distraction site in active window title
2. Warn with popup and countdown
3. Mouse chaos if ignored
4. Force-close foreground tab/window and open your focus page

# try it yourself:

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Notes

- If macOS blocks mouse/window control, enable Accessibility permissions for your terminal app.
- `docs/index.html` is the hosted focus dashboard.
