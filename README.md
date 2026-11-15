# Smart Notes Exchange System (SNES)

A production-grade, zero-cost academic study materials and lecture notes exchange platform built with Django 5.2, HTMX, Tailwind CSS, WhiteNoise, and flexible storage (Local Media Root by default, with optional S3-compatible cloud storage via Cloudflare R2 or Supabase).

---

## 🌟 Key Features

* **Multi-Format Document Uploads:** Upload lecture notes, cheat sheets, past exam papers (PYQs), and assignments in PDF (`.pdf`) and PowerPoint (`.pptx`) formats (up to 25 MB).
* **Automated Page Counting:** Server-side parsing of uploaded PDFs with `pypdf` to extract and display verified page counts automatically.
* **In-Browser Document Previews:**
  * Embedded, secure inline PDF previewer with fallback download options.
  * Cloud-integrated slide viewer (Microsoft Office Online & Google Docs Viewer) for PowerPoint presentations.
* **Controlled & Tracked Downloads:** Atomic download counter increments with sanitized attachment filenames streaming via storage-agnostic `note.file.open("rb")` and `FileResponse`.
* **HTMX-Powered Dynamic Interactions:**
  * Live upvote/downvote buttons with instant net score calculations and active user state indicators without full page refreshes.
  * 1-click personal study list bookmarking toggle.
* **Discovery Homepage & Advanced Search/Filter Directory:**
  * Hero search bar with instant filter pills (Category, Academic Year).
  * Composite quality score ranking: `(upvotes - downvotes) + (downloads * 0.2)`.
  * Multi-field search across title, subject, topic, and description with category and year dropdown filters and pagination.
* **User Dashboard:** Dedicated hub for managing uploaded materials, viewing personal statistics, and accessing bookmarked study lists.
* **Academic Review / 1-Click Moderation:** Atomic report submission mechanism flagging compromised or infringing uploads for administrative review.
* **Zero-Cost Production Hardening:** Configured for seamless deployment on **Render** (Render Web Service + Render PostgreSQL) with WhiteNoise for static assets and local `MEDIA_ROOT` serving by default (no cloud bucket required), plus optional S3/Supabase support.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Django 5.2 (Python 3.11+) |
| **Frontend & Styling** | Django Templates, Tailwind CSS (CDN), HTMX (`django-htmx`) |
| **PDF Processing** | `pypdf` |
| **Database** | SQLite (Local Dev) / PostgreSQL (`psycopg[binary]`, `dj-database-url` in Production) |
| **Static Files** | WhiteNoise (`CompressedManifestStaticFilesStorage`) |
| **Media Storage** | Local `MEDIA_ROOT` (default zero-cost) / `django-storages[s3]` + `boto3` (Optional S3/R2/Supabase) |
| **WSGI Server** | Gunicorn |
| **Deployment Target** | Render (Zero-cost Web Service + Managed PostgreSQL) |

---

## 🚀 Local Development Setup

### 1. Prerequisites
* Python 3.11 or higher
* Git

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/your-username/snes-platform.git
cd snes-platform

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```

Ensure `.env` contains:
```ini
DJANGO_SECRET_KEY=django-insecure-dev-local-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
USE_S3_STORAGE=False
```

### 5. Apply Migrations & Create Superuser
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Run the Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

### 7. Run Test Suite
```bash
python manage.py test
```

---

## 📦 Deploying to Render (Zero-Cost Setup)

### 1. Create Render PostgreSQL Database
1. In your [Render Dashboard](https://dashboard.render.com/), click **New +** &rarr; **PostgreSQL**.
2. Name your database (e.g., `snes-db`) and select the **Free** instance type.
3. Once provisioned, copy the **Internal Database URL**.

### 2. Create Render Web Service
1. Click **New +** &rarr; **Web Service** and connect your GitHub repository.
2. Select runtime: **Python**.
3. Configure build & start commands:
   * **Build Command:** `./build.sh`
   * **Start Command:** `gunicorn config.wsgi:application`
4. Choose the **Free** instance type.

### 3. Configure Production Environment Variables on Render
Under the **Environment** tab of your Render Web Service, add the following variables:

| Variable | Value / Description |
|---|---|
| `DJANGO_SECRET_KEY` | Generate a secure, random secret key (required in production) |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,.onrender.com,your-app-name.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com,https://your-app-name.onrender.com` |
| `DATABASE_URL` | Render Internal Database URL from Step 1 |
| `USE_S3_STORAGE` | `False` (default: serves media from local disk for 100% zero-cost demos) |
| `SECURE_SSL_REDIRECT` | `True` |

#### (Optional) Persistent S3 / Supabase Cloud Storage
If you wish to retain uploaded documents across Render dyno restarts or spin-downs, set `USE_S3_STORAGE=True` and configure:
* `AWS_ACCESS_KEY_ID`
* `AWS_SECRET_ACCESS_KEY`
* `AWS_STORAGE_BUCKET_NAME`
* `AWS_S3_ENDPOINT_URL` (e.g. `https://<account_id>.r2.cloudflarestorage.com` or Supabase S3 endpoint)
* `AWS_S3_REGION_NAME` (e.g. `auto` or your bucket region)
* `AWS_S3_CUSTOM_DOMAIN` (optional public CDN domain, e.g. `pub-xxxx.r2.dev`)

### 4. Deploy & Verify
* Render runs `./build.sh` to install dependencies, collect static files with WhiteNoise, and apply migrations.
* Once the service is live, create an admin user via the Render Shell:
  ```bash
  python manage.py createsuperuser
  ```
* Open `https://your-app-name.onrender.com` to explore SNES!

---

## 🔒 Production Security Hardening

* **Enforced Secret Key:** Requires `DJANGO_SECRET_KEY` when `DJANGO_DEBUG=False`, preventing unintended production deployment with default dev keys.
* **WhiteNoise Static Hosting:** Compresses and hashes static assets for cache busting and immediate CDN-ready delivery.
* **Production Media Serving:** Routes `/media/` via `document_root` when `USE_S3_STORAGE=False` so document previews and downloads function out-of-the-box on Render demos without requiring external S3 accounts.
* **Reverse Proxy Headers:** `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` ensures accurate SSL detection behind Render's reverse proxy.
* **Secure Cookie Flags:** `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True` protect session data from interception.
* **Clickjacking Protection:** `X_FRAME_OPTIONS = "SAMEORIGIN"` permits inline PDF previews while blocking third-party iframe hijacking.
* **Storage-Agnostic Downloads:** Controlled downloads use `note.file.open("rb")` and `FileResponse`, decoupling file serving from local filesystem paths.

---

## 📄 License
MIT License. Created for the student and academic developer community.
