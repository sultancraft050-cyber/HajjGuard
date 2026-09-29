# Current-State Audit

The selected checkout is a Django 6.1 project with six application modules and service modules for prediction, routing, CCTV, weather, Fiqh, and external adapters. It includes SQLite `db.sqlite3`, a static benchmark artifact, and 46 discovered tests in the inherited run.

Initial execution was blocked by the inherited environment: its Python executable is ACL-protected and its NumPy binary is CPython 3.13/Windows while the available bundled interpreter is CPython 3.12. The code therefore requires a clean compatible environment before full checks and tests can be trusted.

Verified corrections in this working copy:

- Explicit consent defaults to false and its timestamp is nullable.
- Group dispersion is named as RMS dispersion in metres, not entropy.
- QR payload no longer embeds national ID, name, nationality, blood type, vulnerability, leader phone, or emergency PIN.
- Committed secret and wildcard hosts were removed from settings; runtime environment variables are required.
- Static benchmark values were removed; unavailable measurements are reported as not measured.
- Official integration wording was changed to simulated/local wording in card provisioning.
