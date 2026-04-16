# Survey Management

Streamlit-based survey management workspace for project operations, surveyor administration, banking setup, audit review, search/reporting, and project assignment tracking.

## What This App Includes

- Authentication with role-based navigation
- Project management and assignment builder
- Surveyor profiles and document tracking
- Bank and payout account management
- Search and report workspace
- Dashboard and audit log views
- Project overview filters and report exports (`.docx`, `.xlsx`, `.csv`, `.pdf`)

## Stack

- Python 3.13
- Streamlit
- Pandas
- SQLAlchemy
- PostgreSQL / Neon
- `python-docx` for Word export
- `reportlab` for PDF export

## Project Structure

```text
app/
  core/           configuration, auth, database, permissions
  design/         CSS, assets, reusable UI components
  models/         domain models
  pages/          Streamlit pages by role and area
  repositories/   database queries
  services/       business logic
tests/            unit and smoke tests
streamlit_app.py  application entry point
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Set the database connection.
4. Run Streamlit.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment Configuration

Copy `.env.example` and set a real database URL in your shell or environment manager.

Example:

```powershell
$env:DATABASE_URL="postgresql://username:password@host:5432/database_name"
```

Optional:

```powershell
$env:RUN_DATABASE_OPTIMIZATIONS="true"
```

The app also supports Streamlit secrets through `.streamlit/secrets.toml`, but that file should stay local and must not be committed.

Example local `.streamlit/secrets.toml`:

```toml
[connections.neon_db]
url = "env:DATABASE_URL"
```

## Run The App

```powershell
streamlit run streamlit_app.py
```

## Run Tests

```powershell
python -m unittest
```

For a smaller smoke check:

```powershell
python -m unittest tests.test_app_smoke.AppSmokeTests.test_super_admin_pages_render_without_exception
```

## GitHub Push Checklist

Before pushing this repository:

- Keep `.streamlit/secrets.toml` out of Git
- Keep `.runtime/`, local logs, and virtual environments out of Git
- Confirm `DATABASE_URL` is not hard-coded anywhere
- Run tests at least once
- Review `requirements.txt` after adding new packages

## Suggested First Commit Flow

```powershell
git init
git add .
git commit -m "Initial commit"
```

Then connect your GitHub repository and push:

```powershell
git remote add origin <your-github-repo-url>
git branch -M main
git push -u origin main
```

## Notes

- `.streamlit/config.toml` can be committed if it only contains UI/runtime preferences.
- `.streamlit/secrets.example.toml` is safe to keep in the repo as a template.
- Export reports in Project Overview are generated from the currently filtered data.
