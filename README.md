#  Budget Tracker

A modern, full-stack web application for tracking weekly and monthly expenses with user authentication, PDF export, mobile-responsive design, and dark/light mode support.

![Budget Tracker](https://img.shields.io/badge/status-live-success)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Flask](https://img.shields.io/badge/flask-3.0.0-green)
![PostgreSQL](https://img.shields.io/badge/postgresql-enabled-blue)
![Mobile](https://img.shields.io/badge/mobile-responsive-purple)

##  Live Demo

**[https://budget-tracker-production-5caa.up.railway.app](https://budget-tracker-production-5caa.up.railway.app)**

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
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/budget_tracker
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
```

**5. Run the application**
```bash
python app.py
```

Visit `http://localhost:5000`

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
