# Deploying South Dumdum Enclave Portal to Vercel

This guide walks you through deploying the **South Dumdum Enclave Residents' Association (SDDRA)** web portal on **Vercel**.

---

## 📦 1. Pre-Configured Vercel Files

All necessary Vercel configuration files have already been created in your project folder:
- **`vercel.json`**: Configures serverless routing and static assets handling.
- **`requirements.txt`**: Lists all Python dependencies (`flask`, `pymysql`, `cryptography`, `bcrypt`, etc.).
- **`api/index.py`**: The serverless WSGI entrypoint for Vercel.
- **`sddra_billing_dump.sql`**: Full MySQL database dump with all 44 flats, 190 receipts, and 81 expenses.

---

## 🗄️ 2. Cloud Database Setup (Required for Vercel)

Because Vercel serverless functions run in the cloud, they cannot connect to `localhost:3306` on your personal computer. You need to host your database on a cloud MySQL provider.

### Recommended Free MySQL Cloud Providers:
1. **TiDB Cloud (Serverless)** — *Recommended (100% Free, MySQL compatible)*:
   - Sign up at: [https://tidbcloud.com](https://tidbcloud.com)
   - Create a free **Serverless Cluster**.
   - In the TiDB Cloud web console, open the **SQL Editor** and paste/import the contents of `sddra_billing_dump.sql`.
   - Copy your connection details: `Host`, `Port` (usually 4000), `User`, `Password`, and `Database`.

2. **Aiven for MySQL** / **Clever Cloud** / **Railway**:
   - Sign up and create a free MySQL instance.
   - Import `sddra_billing_dump.sql`.

---

## 🚀 3. Deploying to Vercel via GitHub

### Step 1: Push your project to GitHub
Open PowerShell in the project directory (`C:\Users\Swapnadeep\.gemini\antigravity-ide\scratch\south-dumdum-enclave`) and run:

```bash
git init
git add .
git commit -m "Initial commit for SDDRA Portal on Vercel"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/sddra-portal.git
git push -u origin main
```

### Step 2: Import into Vercel
1. Go to [https://vercel.com](https://vercel.com) and log in.
2. Click **"Add New..."** &rarr; **"Project"**.
3. Select your `sddra-portal` GitHub repository and click **Import**.

### Step 3: Configure Environment Variables in Vercel
Under the **Environment Variables** section in Vercel before clicking Deploy, add:

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `DB_HOST` | `gateway01.ap-southeast-1.prod.aws.tidbcloud.com` | Cloud MySQL host |
| `DB_PORT` | `4000` (or `3306`) | Cloud MySQL port |
| `DB_USER` | `xxxxxx.root` | Cloud MySQL username |
| `DB_PASSWORD` | `your_cloud_db_password` | Cloud MySQL password |
| `DB_NAME` | `sddra_billing` | Cloud database name |
| `DB_SSL` | `True` | Enable SSL for cloud connections |
| `SECRET_KEY` | `sddra-secret-key-2026` | Flask session secret key |
| `SMTP_USERNAME` | `your_email@gmail.com` | (Optional) Gmail for sending receipts |
| `SMTP_PASSWORD` | `your_16_char_app_password` | (Optional) Gmail App Password |

### Step 4: Click Deploy!
Vercel will automatically build the Python serverless bundle and deploy your website to a live URL (e.g. `https://sddra-portal.vercel.app`).
