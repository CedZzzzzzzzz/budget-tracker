#  Budget Tracker

A modern, full-stack web application for tracking weekly and monthly expenses with user authentication, PDF export, mobile-responsive design, and dark/light mode support.

![Budget Tracker](https://img.shields.io/badge/status-live-success)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Flask](https://img.shields.io/badge/flask-3.0.0-green)
![PostgreSQL](https://img.shields.io/badge/postgresql-enabled-blue)
![Mobile](https://img.shields.io/badge/mobile-responsive-purple)

##  Live Demo

**[https://budget-trackerr.up.railway.app](https://budget-trackerr.up.railway.app)**

##  Features

###  Budget Management
- **Weekly Allowance Tracking** - Set your budget for the week (Sunday to Saturday)
- **Daily Expense Logging** - Track expenses by category: Fare, Food, Other
- **Smart Day Selection** - Only log expenses for past and current days
- **Real-time Progress** - Visual progress bar showing budget usage
- **Budget Warnings** - Alerts when you exceed your weekly allowance

### Analytics & Insights
- **Weekly Summary** - Detailed breakdown of all expenses by day
- **Monthly Overview** - Aggregate view of spending across multiple weeks
- **Category Breakdown** - See spending patterns by category
- **Savings Tracker** - Track how much you saved each week

###  Security & Authentication
- **Secure User Registration** - Email validation and strong password requirements
- **Session Management** - Secure login/logout with Flask sessions
- **Password Hashing** - Werkzeug security for password protection
- **Protected Routes** - Authentication required for budget access

###  User Experience
- **Dark/Light Mode** - Toggle between themes with persistent preference
- **Mobile Responsive** - Hamburger menu and optimized layout for phones
- **Intuitive Design** - Modern purple-themed UI with smooth animations
- **Fast & Smooth** - Optimized performance with minimal load times
- **Receipt Scanning** - Capture or upload a receipt, review extracted items, and save them atomically
- **Flexible Categories** - Classify against all built-in and user-created categories

### Export & Reports
- **Weekly PDF Export** - Download detailed reports for any week
- **Monthly PDF Export** - Comprehensive monthly summaries
- **Professional Formatting** - Clean, printable PDF documents

###  Data Management
- **PostgreSQL Database** - Reliable, persistent data storage
- **Per-User Isolation** - Each user sees only their own budget data
- **Week-based Organization** - Automatic weekly budget periods
- **Data Persistence** - Never lose your expense history

##  Tech Stack

### Frontend
- HTML, CSS, JavaScript
- Custom CSS Variables for theming
- Responsive Grid & Flexbox
- Smooth CSS animations

### Backend
- Python 3.12
- Flask 3.0.0
- PostgreSQL
- psycopg2
- Werkzeug

### Deployment
- Railway
- Gunicorn
- Git & GitHub

### Additional Libraries
- ReportLab 4.0.7
- Flask-CORS
- python-dotenv

##  Prerequisites

- Python 3.12 or higher
- PostgreSQL
- pip
- Git

##  Installation

### Local Development

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/BudgetTrackerApp.git
cd BudgetTrackerApp
```

**2. Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set up environment variables**

Create `.env` file:
```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5000/budget_tracker
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
# Optional — in-app + PDF AI insights (tries primary, then secondary)
GEMINI_AI_INSIGHT_API_KEY=your-gemini-key
GEMINI_AI_INSIGHT_API_KEY_SECONDARY=your-second-gemini-key
RECEIPT_OCR_ENABLED=true
GEMINI_RECEIPT_API_KEY=your-dedicated-receipt-key
GEMINI_RECEIPT_MODEL=gemini-3.5-flash-lite
```

Receipt scanning is disabled unless `RECEIPT_OCR_ENABLED` is true and a dedicated
receipt key is configured. Optional limits include `RECEIPT_OCR_TIMEOUT_SECONDS`,
`RECEIPT_OCR_MAX_BYTES`, `RECEIPT_OCR_MAX_PIXELS`, `RECEIPT_OCR_MAX_DIMENSION`, and
`RECEIPT_OCR_CONCURRENCY`.

**5. Run the application**
```bash
python app.py
```

Visit `http://localhost:5000`

## Testing

Install backend development dependencies:

```bash
python -m pip install --requirement requirements-dev.txt
```

Run the complete local quality gate:

```bash
npm test
```

Run either side independently:

```bash
npm run test:backend
npm run test:frontend
```

Backend tests use mocks and Flask test clients, so they do not require production
credentials, a live database, or a Brevo connection. GitHub Actions runs backend tests
and frontend lint/build checks independently for pushes to `main` and pull requests.

See [Automated Testing and Continuous Integration](docs/automated-testing-ci.md) for the
workflow, test-writing expectations, failure meanings, and troubleshooting guidance.

##  Deployment (Railway)

**1. Install Railway CLI**
```bash
npm install -g @railway/cli
```

**2. Login and initialize**
```bash
railway login
railway init
```

**3. Add PostgreSQL database**
```bash
railway add
```

**4. Deploy**
```bash
railway up
```

**5. Generate public URL**
```bash
railway domain
```

## Usage

### Registration
- Username: minimum 3 characters
- Password: 8+ characters with uppercase, number, and special character
- Email: valid email address

### Weekly Budget
- Set your weekly allowance
- Week runs Sunday to Saturday
- Click "Start Tracking"

### Daily Expenses
- Select a day
- Enter Fare, Food, or Other expenses
- Click "Add"

### Monthly Summary
- Click "Monthly Summary" tab
- Navigate between months
- Export as PDF

### Theme Toggle
- Desktop: Click sun/moon icon
- Mobile: Hamburger menu → "Toggle Theme"

### Mobile Navigation
- Tap ☰ in top-right
- Access Theme, Export, Logout
- Click outside to close

**Mobile menu not working**
- Hard refresh: `Ctrl + Shift + R`
- Clear browser cache

## Open to Contributions

1. Fork the repository
2. Create feature branch (`git checkout -b `)
3. Commit changes (`git commit -m 'message'`)
4. Push to branch (`git push origin `)
5. Open Pull Request

## License

This project is licensed under the MIT License.


---
