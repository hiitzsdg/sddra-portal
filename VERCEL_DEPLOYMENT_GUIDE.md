# Deploying South Dumdum Enclave Portal to Vercel

The portal is equipped with **hybrid zero-configuration support** for Vercel:
- **Instant Deployment (Zero Config)**: Works immediately out of the box using the bundled `sddra.db` database containing all 44 flats, 190 receipts, 81 expenses, contacts, and admin logins. No cloud database setup or environment variables required!
- **Optional Cloud MySQL**: Supports connecting live to cloud MySQL providers (such as TiDB Cloud, Aiven, Railway, or AWS RDS) by simply adding environment variables in your Vercel project settings.

---

## 📦 1. Pre-Configured Vercel Files

All necessary Vercel serverless configuration files are included:
- **`vercel.json`**: Configures serverless Python runtime with asset bundle inclusions (`templates/`, `static/`, `sddra.db`).
- **`requirements.txt`**: Clean, compatible Python dependencies for serverless lambda environments.
- **`api/index.py`**: Serverless entrypoint exporting both `app` and `handler`.
- **`sddra.db`**: Pre-seeded SQLite database with complete association data.
- **`sddra_billing_dump.sql`**: Full MySQL SQL dump for importing into cloud MySQL databases.

---

## 🚀 2. Deploying to Vercel (3 Simple Steps)

### Step 1: Push project updates to your GitHub repository
Open PowerShell in the project directory (`C:\Users\Swapnadeep\.gemini\antigravity-ide\scratch\south-dumdum-enclave`) and run:

```powershell
git add .
git commit -m "Fix Vercel deployment with hybrid database engine and asset bundling"
git push
```

*(If deploying for the first time:)*
```powershell
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
3. Select your `sddra-portal` repository and click **Import**.

### Step 3: Click Deploy!
- You do **NOT** need to configure any environment variables to get started.
- Vercel will automatically build the serverless package and deploy the website.

---

## 🌐 3. (Optional) Connecting to a Cloud MySQL Database

If you want to use a shared cloud MySQL database across all serverless instances:

### Recommended Free MySQL Cloud Provider:
**TiDB Cloud (Serverless)** — *100% Free MySQL Compatible*:
1. Sign up at [https://tidbcloud.com](https://tidbcloud.com).
2. Create a free **Serverless Cluster**.
3. Open the **SQL Editor** in the TiDB console and execute the SQL from `sddra_billing_dump.sql`.
4. In your Vercel Project &rarr; **Settings** &rarr; **Environment Variables**, add:

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `DB_HOST` | `gateway01.ap-southeast-1.prod.aws.tidbcloud.com` | Cloud MySQL host |
| `DB_PORT` | `4000` | Cloud MySQL port |
| `DB_USER` | `xxxxxx.root` | Cloud MySQL username |
| `DB_PASSWORD` | `your_cloud_password` | Cloud MySQL password |
| `DB_NAME` | `sddra_billing` | Cloud database name |
| `DB_SSL` | `True` | Enable SSL for cloud connection |
| `SECRET_KEY` | `sddra-secret-key-2026` | Flask session secret key |
| `SMTP_USERNAME` | `your_email@gmail.com` | (Optional) Gmail for dispatching receipts |
| `SMTP_PASSWORD` | `your_16_char_app_password` | (Optional) Gmail App Password |

5. Click **Redeploy** on Vercel. The portal will automatically connect to your live cloud MySQL database!
