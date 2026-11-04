# الشامي | Elshamii

A single-store supermarket ordering and management system. The customer-facing desktop application and website use the store brand **الشامي | Elshamii**. The internal repository/project identifier remains `pp-market`.

**Developer credit:** Made By PeterParker 🕷️

## Current project status

- `backend/`: Django + DRF API foundation (existing project source; runtime tests still required).
- `desktop/`: first desktop interface stage — staff login, dashboard, order management, payment confirmation, local API health, and store branding settings.
- `website/`, automated server runtime/tunnel publisher, inventory/catalog desktop screens, staff management, reports, and installer: not yet implemented in this repository snapshot.

## Quick start on Windows

Run `Start_Elshamii.bat` from the project root. It creates separate Python environments, installs the backend and desktop requirements, creates `backend/.env` from the supplied example if missing, applies migrations, starts the local API, and opens the desktop app. The first run needs an internet connection for Python package installation.

The desktop no longer falls back to Login when the API is unavailable; it displays a server connection screen with a Retry button.

## Desktop development

```bat
cd desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The desktop currently expects the Django API at `http://127.0.0.1:8000`. If you do not use the quick-start script, start the backend separately during development:

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Configure the development `.env`, then run migrations and the API using the backend README instructions. Do not distribute `.env`, database files, logs, backups, or credentials.

## Important

This is an incremental development build, not an installer or a production-ready deployment. The UI source has been syntax-checked, but a Windows GUI run against a live Django server remains to be tested.

## First owner activation (developer setup)

The first launch displays a one-time owner registration screen. The developer activation code is **not stored in source code or plain text**. Before packaging an installation, configure its hash in the private `backend/.env` file using:

```bat
cd backend
python configure_developer_code.py
```

The helper asks for the activation code without displaying it and stores only a salted PBKDF2-HMAC-SHA256 hash in `.env`. The first successful owner registration marks the installation bootstrap as complete in the database; the endpoint refuses any later first-owner registration. Keep `.env` private and never commit or distribute it as a public source file.

## Assets

Shared application assets live under `assets/` (`icons/`, `images/`, `logos/`, `fonts/`, `flags/`, `sounds/`). Desktop code should resolve them through `desktop/resources.py`, which supports both source execution and PyInstaller's bundled resource directory. Store-uploaded branding (such as the shop's logo) remains in the user's AppData folder, not in the read-only installation assets.


## Desktop Stage 3

This stage adds persistent owner authentication (first-run bootstrap, then repeatable login), product catalog management, category creation, stock adjustments with movement logging, and an operational report snapshot. It retains the orders workflow, store settings, bilingual interface, and local API health screen. The report page is an operational snapshot rather than a full date-range accounting report; dedicated staff/role management and advanced analytics are planned separately.

Store logo asset location: `assets/branding/logo.png`. You can also select a logo from Settings; the selected image is copied to the current Windows user's AppData folder.
