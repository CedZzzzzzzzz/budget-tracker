# Budget Tracker App

A full-stack web application for personal expense tracking, weekly allowance management, receipt OCR scanning, spending analytics, and PDF report generation.

[![Status](https://img.shields.io/badge/status-live-success?style=for-the-badge)](https://balaze.netlify.app)
[![Python](https://img.shields.io/badge/python-3.12-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.0.0-green?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-enabled-blue?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Mobile](https://img.shields.io/badge/mobile-responsive-purple?style=for-the-badge)](https://balaze.netlify.app)

---

## Live Demo

Live application: **[https://balaze.netlify.app](https://balaze.netlify.app)**

---

## Overview

Budget Tracker App is a web-based financial dashboard for managing weekly budgets, tracking daily expenses, scanning physical receipts, and exporting monthly PDF reports.

---

## Features

### Budget Management and Expense Logging
- **Weekly Allowance Tracking**: Set a weekly budget target for Sunday through Saturday.
- **Daily Expense Logging**: Record costs across default categories (Fare, Food, Other) or custom categories.
- **Date Validation**: Restrict logs for future dates while allowing retro-active logging for earlier days.
- **Visual Progress Indicators**: Progress bar updates dynamically as expenses accumulate relative to weekly allowance.
- **Allowance Alerts**: Receive notifications when spending exceeds the set allowance.

### Receipt OCR Scanning
- **Image Capture and Upload**: Upload receipt files or take photos directly on mobile or desktop devices.
- **Gemini OCR Processing**: Extract total amounts, merchant details, line items, and transaction dates automatically.
- **Log Review**: Review and edit parsed items before saving entries to the database.

### Analytics and Insights
- **Spending Breakdowns**: View weekly and monthly summaries grouped by category and day.
- **Automated Summary Analysis**: Generate text summaries of spending patterns via Gemini API integration.
- **Savings Calculation**: Calculate remaining allowance and total savings per week.

### PDF Exports
- **Downloadable Reports**: Generate print-ready PDF files for weekly or monthly expense history.
- **Optional Analysis**: Include financial summary text directly within the exported PDF.

### Security and Authentication
- **Per-User Isolation**: Database structure enforces isolation so each user accesses only their data.
- **Password Policies**: Enforce minimum complexity requirements using Werkzeug password hashing.
- **Session Management**: Session control with security headers and API rate limiting.
- **Email Verification and Admin CLI**: CLI commands for administrator account creation and role updates.

### User Interface
- **Theme Toggle**: Switch between Dark Mode and Light Mode with persistent browser storage.
- **Mobile Responsive**: Navigation drawer menu for mobile and tablet screens.

---

## Tech Stack

| Component | Technologies |
| :--- | :--- |
| **Frontend** | HTML5, CSS3 (Custom CSS variables), JavaScript (ES6+), FontAwesome |
| **Backend** | Python 3.12, Flask 3.0.0, Werkzeug, Flask-CORS, Flask-Limiter, Gunicorn |
| **Database** | PostgreSQL, `psycopg2` |
| **OCR & AI** | Google Gemini API (Receipt OCR and spending summaries) |
| **Reporting** | ReportLab (PDF generation) |
| **Deployment & CI** | Railway, Netlify, GitHub Actions |

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- PostgreSQL server
- Node.js and npm (for frontend checks and tests)
- Git

---

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/BudgetTrackerApp.git
   cd BudgetTrackerApp
   ```

2. **Set Up Virtual Environment**
   - **Windows:**
     ```cmd
     python -m venv venv
     venv\Scripts\activate
     ```
   - **macOS/Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**  
   Create a `.env` file in the root directory:
   ```env
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/budget_tracker
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   
   # Optional: Gemini API Keys
   GEMINI_AI_INSIGHT_API_KEY=your-gemini-key
   GEMINI_AI_INSIGHT_API_KEY_SECONDARY=your-secondary-gemini-key
   
   # Optional: Receipt OCR
   RECEIPT_OCR_ENABLED=true
   GEMINI_RECEIPT_API_KEY=your-dedicated-receipt-key
   GEMINI_RECEIPT_MODEL=gemini-2.5-flash
   ```

5. **Run the Application**
   ```bash
   python app.py
   ```
   Access the app at `http://localhost:5000`.

---

## Testing

Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

Run test suites:
```bash
# Run full test suite
npm test

# Run backend tests only
npm run test:backend

# Run frontend tests only
npm run test:frontend
```

See [Automated Testing & CI Documentation](docs/automated-testing-ci.md) for details.

---

## Deployment (Railway)

1. **Install Railway CLI and Authenticate**
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. **Initialize and Deploy**
   ```bash
   railway init
   railway add
   railway up
   ```

3. **Configure Domain**
   ```bash
   railway domain
   ```

---

## Usage

1. **Register**: Create an account with password complexity rules and complete email setup.
2. **Set Allowance**: Enter your weekly budget allowance.
3. **Log Expenses**: Add expenses manually or use the receipt scanner.
4. **View Summaries**: Monitor spending bars and weekly/monthly trends.
5. **Export PDF**: Download PDF copies of weekly or monthly statements.

---

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/name`).
3. Commit changes (`git commit -m 'Add feature'`).
4. Push to branch (`git push origin feature/name`).
5. Open a Pull Request.

---

## License

Distributed under the MIT License. See `LICENSE` for details.

