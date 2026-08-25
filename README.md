# South Dumdum Enclave Residents' Association (SDERA) Web Portal

A web portal for the **South Dumdum Enclave Residents' Association** built with Python Flask, MySQL DB integration, secure Role-Based Access Control (RBAC), expense tracking analytics, and automated email receipt dispatch.

---

## 🌟 Key Features

1. **Role-Based Access Control (RBAC)**:
   - **Regular Members**: Restricted strictly to their own flat details and maintenance receipts.
   - **Committee Officials (President, Secretary, Treasurer, Caretaker)**: Full oversight across all flats, payment collections, and receipts.
2. **Maintenance Receipts Ledger**:
   - Issue, track, view, and print official verified receipts with watermarked layouts.
   - 1-click **Email Receipt** to dispatch receipt slips directly to member inboxes.
   - 1-click **WhatsApp Receipt Share**: Instantly send formatted receipt vouchers to resident WhatsApp chats.
3. **WhatsApp Integration & Society Helpdesk**:
   - **Receipts**: 1-click WhatsApp voucher dispatch with download links and payment confirmations.
   - **Maintenance Dues & Late Penalties**: 1-click WhatsApp payment reminders with monthly arrears breakdown, late fee penalty calculations, and bank payment instructions.
   - **Notice Board Broadcasts**: 1-click formatted circular broadcasts ready for Society WhatsApp Groups.
   - **Resident Directory**: One-click WhatsApp direct chat next to any resident's mobile number.
   - **Floating WhatsApp Helpdesk Widget**: 24/7 one-touch access to Caretaker, Secretary, Treasurer, and President.
   - **Dual Engine**: Instant `wa.me` deep linking out-of-the-box, plus optional Meta WhatsApp Cloud API & Twilio support.
4. **Association Expense Transparency**:
   - Public expense ledger visible to all members for complete financial accountability.
   - Interactive Chart.js category breakdown (Electricity, Security, Lift AMC, Generator, etc.) and monthly spending trend.
5. **Member & Flat Management**:
   - Manage flat roster, square footage, dues statuses, and reset credentials.
6. **Database Dual-Mode**:
   - Connects directly to local **MySQL** (`south_dumdum_enclave` database).
   - Features seamless auto-fallback to standalone SQLite if MySQL credentials are being configured.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install flask pymysql cryptography python-dotenv
```

### 2. Run the Portal
```bash
python app.py
```
Open your browser and navigate to: **`http://localhost:5000`**

---

## 🔑 Default Demo Accounts

All test accounts use default password: **`sdera@123`**

| Role | Name | Username | Flat | Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **President** | Dr. Asit Kumar Bera | `president` | A-401 | Full Association & Financial Admin |
| **Secretary** | Somenath Halder | `secretary` | B-202 | Member & Operational Admin |
| **Treasurer** | Swapnadeep Ganguly | `treasurer` | A/4-C | Receipts & Expense Management |
| **Caretaker** | Sanjoy Chakraborty | `caretaker` | Staff (CT-01) | Roster & Payment Collection Entry |
| **Member** | Sourav Ganguly | `sourav101` | A-101 | Personal Receipts & Expense View Only |
| **Member** | Anirban Bhattacharya | `anirban201` | A-201 | Personal Receipts & Expense View Only |
| **Member** | Priya Mukherjee | `priya301` | A-301 | Personal Receipts & Expense View Only |

---

## ⚙️ MySQL Configuration

To point directly to your local MySQL server, copy `.env.example` to `.env` and set your credentials:

```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=south_dumdum_enclave
```

The application will automatically create the database and tables on startup.
