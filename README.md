# KYC Document Verification Management System

A learning-focused Flask application that demonstrates a basic KYC case workflow: case intake, document upload, reviewer decisions, role-based access, pending-case follow-up, and an audit log.

> **Portfolio/demo project only.** Do not upload real identity documents or real customer data. This starter is not production-ready for regulated KYC operations. Production deployment requires a security review, stronger access controls, malware scanning, encryption/key management, retention policies, rate limiting, monitoring, and compliance review.

## Features

- Login with password hashing
- Admin and reviewer roles
- Create and search KYC cases
- Upload PDF/JPG/PNG files (5 MB max)
- Approve or reject pending cases
- Dashboard counts for pending, approved, rejected, and overdue cases
- Follow-up view showing pending cases and due dates
- Admin-only audit log
- CSRF protection for forms
- Basic automated tests

## Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux
- Internet access for installing Python packages

## Setup on Windows

Open PowerShell in this folder.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, run this in the same terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Edit `.env` and set a long random `SECRET_KEY` and new demo passwords. For a local learning demo, you can keep the default SQLite database. Never commit `.env`.

Initialize the database and demo accounts:

```powershell
flask --app app init-db
```

Run the app:

```powershell
flask --app app run
```

Open http://127.0.0.1:5000

The seed command prints the default credentials if it creates the accounts. Defaults in code are `admin / Admin123!` and `reviewer / Review123!` unless you set the environment variables before initializing. Change these before using the app beyond a local demo.

## Setup on macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# Edit .env
flask --app app init-db
flask --app app run
```

## Try the workflow

1. Sign in as `admin`.
2. Select **New case** and create a sample case. Use fictional data and a dummy document only.
3. Open the case and confirm its status is **Pending**.
4. Use the review form to approve or reject it.
5. Visit **Follow-ups** to see pending cases and their due dates. Overdue cases are highlighted.
6. Sign in as `reviewer`; confirm the audit log is not accessible.
7. Sign in as `admin` and inspect the audit log.

## Run tests

```bash
pytest -q
```

The tests use a temporary SQLite database. They check login, authentication requirements, role permissions, and case creation.

## Project structure

```text
kyc-document-verification-system/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── tests/
│   └── test_app.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── cases.html
│   ├── case_form.html
│   ├── case_detail.html
│   ├── audit.html
│   ├── reminders.html
│   └── error.html
├── static/
│   └── style.css
└── uploads/ (created automatically; ignored by Git)
```

## Database model

- **User**: username, password hash, role
- **KycCase**: fictional customer details, document type, reference, status, due date, creator/reviewer
- **AuditLog**: actor, case, action, details, timestamp

## GitHub publishing

Create an empty repository on GitHub named `kyc-document-verification-system`. In this folder:

```bash
git init
git add .
git commit -m "Build KYC document verification workflow MVP"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/kyc-document-verification-system.git
git push -u origin main
```

Check `git status` before pushing. `.env`, `kyc.db`, and `uploads/` should not be tracked. Never commit real documents or credentials.

## Resume bullet (after you run it and verify the features)

**KYC Document Verification Management System | Python, Flask, SQLAlchemy, SQLite, HTML/CSS**
- Built a role-based KYC case management web app with document uploads, approval/rejection workflows, due-date follow-ups, and an audit trail.
- Added CSRF protection, password hashing, file-type/size validation, and automated tests for core authentication and workflow behavior.

Only claim features and tests you personally run and understand. Add measured test results after running `pytest -q`; do not invent coverage numbers.
