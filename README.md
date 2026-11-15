# Smart Notes Exchange System (SNES)

A zero-cost, production-grade academic study materials and lecture notes exchange platform built with Django 5.2, HTMX, Tailwind CSS, WhiteNoise, and S3-compatible cloud object storage.

---

## 🌟 Key Features

* **Multi-Format Document Uploads:** Seamlessly upload lecture notes, cheat sheets, past exam papers (PYQs), and assignments in PDF (`.pdf`) and PowerPoint (`.pptx`) formats (up to 25 MB).
* **Automated Page Counting:** Server-side parsing of uploaded PDFs with `pypdf` to extract and display verified page counts automatically.
* **In-Browser Document Previews:**
  * Embedded, secure inline PDF previewer with fallback download options.
  * Cloud-integrated slide viewer (Microsoft Office Online & Google Docs Viewer) for PowerPoint presentations without requiring desktop Office.
* **Controlled & Tracked Downloads:** Atomic download counter increments with sanitized attachment filenames streaming directly from local storage or cloud S3/R2 storage.
* **HTMX-Powered Dynamic Interactions:**
  * Live upvote/downvote buttons with instant net score calculations and active user state indicators without full page refreshes.
  * 1-click personal study list bookmarking toggle.
* **Discovery Homepage & Advanced Search/Filter Directory:**
  * Hero search bar with instant filter pills (Category, Academic Year).
  * Composite quality score ranking: `(upvotes - downvotes) + (downloads * 0.2)`.
  * Multi-field search across title, subject, topic, and description with category and year dropdown filters and pagination.
* **User Dashboard:** Dedicated hub for managing uploaded materials, viewing personal statistics, and accessing bookmarked study lists.
* **Academic Review / 1-Click Moderation:** Atomic report submission mechanism flagging compromised or infringing uploads for administrative review.
* **Production Hardened:** Configured for zero-cost hosting on **Render** (Render Web Service + Render PostgreSQL) with persistent media storage via Cloudflare R2 or Supabase Storage and static asset serving via WhiteNoise.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Django 5.2 (Python 3.11+) |
| **Frontend & Styling** | Django Templates, Tailwind CSS (CDN), HTMX (`django-htmx`) |
| **PDF Processing** | `pypdf` |
| **Database** | SQLite (Local Development) / PostgreSQL (`psycopg[binary]`, `dj-database-url` in Production) |
| **Static Files** | WhiteNoise (`CompressedManifestStaticFilesStorage`) |
| **Media & Object Storage** | `django-storages` + `boto3` (AWS S3, Cloudflare R2, or Supabase Storage) |
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

## 🌐 Cloud Storage Setup (Cloudflare R2 / Supabase Storage)

Because free-tier platform hosts like Render have ephemeral filesystems, uploaded media files (`/media/`) must be stored in persistent S3-compatible object storage.

### Option A: Cloudflare R2 (Recommended - 10 GB Free Forever)
1. Go to the **Cloudflare Dashboard** &rarr; **R2 Object Storage**.
2. Create a bucket (e.g., `snes-media-bucket`).
3. Under bucket **Settings** &rarr; **Public Access**, enable **Custom Domain** or **R2.dev subdomain** (e.g., `pub-xxxx.r2.dev`).
4. Generate an **R2 API Token** with `Object Read & Write` permissions.
5. Note down:
   * **Access Key ID**
   * **Secret Access Key**
   * **Endpoint URL** (e.g., `https://<account_id>.r2.cloudflarestorage.com`)
   * **Public Domain** (e.g., `pub-xxxx.r2.dev`)

### Option B: Supabase Storage (1 GB Free)
1. In your **Supabase Project**, go to **Storage** and create a public bucket named `snes-media-bucket`.
2. Under **Project Settings** &rarr; **Storage**, copy the S3 Connection details (Access Key, Secret Key, and S3 Endpoint).

---

## 📦 Deploying to Render (Zero-Cost Setup)

### 1. Create Render PostgreSQL Database
1. In your [Render Dashboard](https://dashboard.render.com/), click **New +** &rarr; **PostgreSQL**.
2. Choose a name (e.g., `snes-db`) and select the **Free** instance type.
3. Once provisioned, copy the **Internal Database URL** (or External URL).

### 2. Create Render Web Service
1. Click **New +** &rarr; **Web Service** and connect your GitHub repository.
2. Select runtime: **Python**.
3. Configure build & start commands:
   * **Build Command:** `./build.sh`
   * **Start Command:** `gunicorn config.wsgi:application`
4. Choose the **Free** instance type.

### 3. Configure Production Environment Variables on Render
Under the **Environment** tab of your Render Web Service, add:

| Variable | Value / Description |
|---|---|
| `DJANGO_SECRET_KEY` | Generate a long random secret key |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,.onrender.com,your-app-name.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com,https://your-app-name.onrender.com` |
| `DATABASE_URL` | Render Internal Database URL from Step 1 |
| `USE_S3_STORAGE` | `True` |
| `AWS_ACCESS_KEY_ID` | R2 / S3 Access Key ID |
| `AWS_SECRET_ACCESS_KEY` | R2 / S3 Secret Access Key |
| `AWS_STORAGE_BUCKET_NAME` | Name of your storage bucket |
| `AWS_S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `AWS_S3_CUSTOM_DOMAIN` | `pub-<hash>.r2.dev` (allows clean URLs for PPTX/PDF viewers) |
| `SECURE_SSL_REDIRECT` | `True` |

### 4. Deploy & Verify
* Render will trigger `build.sh` to install dependencies, run `collectstatic --no-input`, and execute database migrations.
* Once the service is live, create an admin user via Render Shell:
  ```bash
  python manage.py createsuperuser
  ```
* Open your `https://your-app-name.onrender.com` URL to begin uploading and sharing notes!

---

## 🔒 Security Best Practices Implemented

* `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` ensures correct HTTPS detection behind Render's reverse proxy.
* `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True` prevent transmission of auth cookies over insecure connections.
* `X_FRAME_OPTIONS = "SAMEORIGIN"` allows safe embedding of internal PDF previews while protecting against clickjacking.
* Strict upload validation enforces a 25 MB size cap and file extension / MIME type checking for `.pdf` and `.pptx` documents.
* Controlled downloads stream file bytes without revealing underlying storage directory structure.

---

## 📄 License
MIT License. Created for the student and academic developer community.
