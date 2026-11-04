# الشامي | Elshamii — Desktop

Windows desktop management interface built with CustomTkinter. The customer-facing application name is **الشامي | Elshamii**. `PPMarket` is retained only as an internal data-folder/project identifier.

## Current implementation stage

- Staff login through the existing Django token endpoint.
- Dashboard cards backed by `/api/admin/dashboard/`.
- Persistent first-owner setup and staff login backed by Django users and the local database. The owner can sign out, close the app, reopen it, and sign in again; the one-time bootstrap is locked after account creation.
- Dashboard cards backed by live database counts.
- Product catalog: search, add, edit, and deactivate products. Existing order history is preserved when a product is deactivated.
- Category creation and category assignment to products.
- Inventory adjustment actions (restock, correction, damage) recorded as stock movements; direct stock edits are blocked by the API.
- Orders list/search/status filtering and order status actions backed by the API.
- Wallet payment confirmation.
- Operational report snapshot, local backend/database health page, and settings for store logo, Instagram URL, and Arabic/English language preference.
- Local settings are stored in `%APPDATA%\PPMarket\desktop_config.json`; the auth token is kept in memory only.

## Development

```bat
cd desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The desktop currently expects the Django API at `http://127.0.0.1:8000`. Run the project-root `Start_Elshamii.bat` to start both components. If the API is unavailable, the app displays a dedicated connection screen rather than incorrectly opening Login. The report page currently shows live operational totals, not date-range financial statements. Dedicated staff/role management, detailed sales analytics, a production-grade server supervisor, and an installer remain later work.

Made By PeterParker 🕷️

## First launch

When the backend reports that no owner account exists, the desktop opens the first-owner setup screen. The developer code is checked by the backend against `ELSHAMII_DEVELOPER_CODE_HASH`; the desktop does not contain the plain code. After the first owner is created, this setup endpoint is permanently locked for that database.

Application resources belong in the root `assets/` directory. Resolve them with `resources.asset_path(...)` rather than absolute paths.
