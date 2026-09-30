# Doodle — Desktop Digital Companion

Doodle is a small, persistent digital companion that lives on the user's screen.

## Project Structure

```text
doodle-desktop-companion/
├── src/
│   └── doodle/
│       ├── __init__.py
│       ├── main.py
│       └── app/
│           ├── __init__.py
│           ├── application.py
│           └── lifecycle.py
├── tests/
│   ├── __init__.py
│   └── test_application.py
├── pyproject.toml
├── ARCHITECTURE.md
├── DECISIONS.md
├── PROJECT_SPEC.md
├── ROADMAP.md
└── README.md
```

## Setup & Running

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Run the application:
   ```bash
   python -m doodle.main
   # or
   doodle
   ```

4. Run tests:
   ```bash
   pytest
   # or
   python -m unittest discover tests
   ```
