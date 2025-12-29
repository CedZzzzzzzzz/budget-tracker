
// DOM Elements
const setupScreen = document.getElementById('setupScreen');
const trackerScreen = document.getElementById('trackerScreen');
const allowanceInput = document.getElementById('allowanceInput');
const startBtn = document.getElementById('startBtn');
const allowanceDisplay = document.getElementById('allowanceDisplay');
const dayButtons = document.querySelectorAll('.day-btn');
const expenseInputs = document.getElementById('expenseInputs');
const fareInput = document.getElementById('fareInput');
const foodInput = document.getElementById('foodInput');
const otherInput = document.getElementById('otherInput');
const addExpenseBtn = document.getElementById('addExpenseBtn');
const selectedDayText = document.getElementById('selectedDayText');
const expenseList = document.getElementById('expenseList');
const summaryCard = document.getElementById('summaryCard');
const spentAmount = document.getElementById('spentAmount');
const percentUsed = document.getElementById('percentUsed');
const progressFill = document.getElementById('progressFill');
const remainingAmount = document.getElementById('remainingAmount');
const daysLogged = document.getElementById('daysLogged');
const warningMessage = document.getElementById('warningMessage');
const totalFare = document.getElementById('totalFare');
const totalFood = document.getElementById('totalFood');
const totalOther = document.getElementById('totalOther');
const grandTotal = document.getElementById('grandTotal');
const exportBtn = document.getElementById('exportBtn');

// Tab Navigation
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('weeklyTab').classList.toggle('active', tab.dataset.tab === 'weekly');
        document.getElementById('monthlyTab').classList.toggle('active', tab.dataset.tab === 'monthly');
        if (tab.dataset.tab === 'monthly') loadMonthlySummary();
    });
});

async function checkAuth() {
    try {
        const res = await fetch('/api/check-auth');
        const data = await res.json();
        
        if (!data.authenticated) {
            // Not logged in, redirect to login page
            window.location.href = '/';
            return false;
        }
        
        // Update user greeting
        const username = data.username;
        document.getElementById('userGreeting').textContent = `Hi, ${username}!`;
        return true;
    } catch (e) {
        console.error('Auth check failed:', e);
        window.location.href = '/';
        return false;
    }
}

// Logout function
async function handleLogout() {
    try {
        const res = await fetch('/api/logout', { method: 'POST' });
        if (res.ok) {
            window.location.href = '/';
        } else {
            alert('Logout failed. Please try again.');
        }
    } catch (e) {
        console.error('Logout failed:', e);
        alert('Connection error. Please try again.');
    }
}

// --- SAFE EVENT LISTENERS ---
const attachListener = (id, event, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, fn);
};

// --- ATTACH & NAV LISTENERS ---
attachListener('logoutBtn', 'click', handleLogout);
attachListener('themeToggle', 'click', toggleTheme);

// --- EXPORT BUTTONS ---
attachListener('exportBtn', 'click', () => {
    window.location.href = '/api/export-pdf';
});
attachListener('exportMonthlyBtn', 'click', () => {
    window.location.href = `/api/export-monthly-pdf?month=${currentMonth}&year=${currentYear}`;
});

// --- MONTH NAVIGATION ---
attachListener('prevMonth', 'click', () => { 
    currentMonth--; 
    if (currentMonth < 1) { currentMonth = 12; currentYear--; } 
    loadMonthlySummary(); 
});
attachListener('nextMonth', 'click', () => { 
    currentMonth++; 
    if (currentMonth > 12) { currentMonth = 1; currentYear++; } 
    loadMonthlySummary(); 
});

// --- DAY BUTTONS ---
dayButtons.forEach(btn => btn.addEventListener('click', () => selectDay(btn.dataset.day)));

// --- BUDGET TRACKING LISTENERS ---
attachListener('startBtn', 'click', startTracking);
attachListener('addExpenseBtn', 'click', addExpense);

// --- ALLOWANCE INPUT KEY ---
const allowanceInputEl = document.getElementById('allowanceInput');
if (allowanceInputEl) {
    allowanceInputEl.addEventListener('keypress', (e) => { 
        if (e.key === 'Enter') startTracking(); 
    });
}

// State
let allowance = 0, expenses = {}, selectedDay = '', weekInfo = null;
let currentMonth = new Date().getMonth() + 1, currentYear = new Date().getFullYear();
let darkMode = localStorage.getItem('darkMode') !== 'false';

// Dark Mode & Light Mode
function applyTheme(isDark) {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = isDark ? '☀️' : '🌙';
}
applyTheme(darkMode);

// Theme Toggle
function toggleTheme() {
    darkMode = !darkMode;
    localStorage.setItem('darkMode', darkMode);
    applyTheme(darkMode);
}

// PDF Export
function exportWeeklyPDF() { window.location.href = '/api/export-pdf'; }
function exportMonthlyPDF() { window.location.href = `/api/export-monthly-pdf?month=${currentMonth}&year=${currentYear}`; }

// Week Info
async function loadWeekInfo() {
    try {
        const res = await fetch('/api/current-week-info');
        const data = await res.json();
        if (res.ok) {
            weekInfo = data;
            document.getElementById('weekRange').textContent = `${data.week_start_formatted} - ${data.week_end_formatted}`;
            document.getElementById('weekDates').textContent = `${data.week_start_formatted} - ${data.week_end_formatted}`;
            document.getElementById('daysRemaining').textContent = data.days_remaining;
            document.getElementById('currentDay').textContent = data.current_day;
        }
    } catch (e) { console.error(e); }
}

// Start Tracking
async function startTracking() {
    const value = parseFloat(allowanceInput.value);
    if (!value || value <= 0) return alert('Enter valid allowance');
    
    try {
        const res = await fetch('/api/set-allowance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ allowance: value })
        });
        if (res.ok) {
            allowance = value;
            allowanceDisplay.textContent = `₱${allowance.toFixed(2)}`;
            setupScreen.classList.remove('active');
            trackerScreen.classList.add('active');
            exportBtn.classList.remove('hidden');
            updateDisplay();
        }
    } catch (e) { alert('Server error'); }
}

// Select Day
function selectDay(day) {
    if (expenses[day]) return;
    selectedDay = day;
    selectedDayText.textContent = day;
    dayButtons.forEach(btn => btn.classList.toggle('selected', btn.dataset.day === day));
    expenseInputs.classList.remove('hidden');
    fareInput.value = foodInput.value = otherInput.value = '';
}

// Add Expense
async function addExpense() {
    if (!selectedDay) return;
    const fare = parseFloat(fareInput.value) || 0;
    const food = parseFloat(foodInput.value) || 0;
    const other = parseFloat(otherInput.value) || 0;
    if (fare === 0 && food === 0 && other === 0) return alert('Enter at least one expense');
    
    try {
        const res = await fetch('/api/add-expense', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ day: selectedDay, fare, food, other })
        });
        if (res.ok) {
            const data = await res.json();
            expenses[data.day] = data.expense;
            updateDayButtons();
            dayButtons.forEach(btn => btn.classList.remove('selected'));
            selectedDay = '';
            expenseInputs.classList.add('hidden');
            await fetchBudgetData();
        }
    } catch (e) { alert('Server error'); }
}

// Delete Expense
async function deleteExpense(day) {
    if (!confirm(`Delete ${day}?`)) return;
    try {
        const res = await fetch(`/api/delete-expense/${day}`, { method: 'DELETE' });
        if (res.ok) {
            delete expenses[day];
            dayButtons.forEach(btn => { if (btn.dataset.day === day) btn.disabled = false; });
            await fetchBudgetData();
        }
    } catch (e) { alert('Server error'); }
}

// Fetch Budget
async function fetchBudgetData() {
    try {
        const res = await fetch('/api/get-budget');
        if (res.ok) {
            const data = await res.json();
            allowance = data.allowance;
            expenses = data.expenses;
            updateDisplay(data.totals);
            renderExpenseList();
            updateDayButtons();
        }
    } catch (e) { console.error(e); }
}

// Update Display
function updateDisplay(totals = null) {
    if (!totals) {
        let f = 0, fd = 0, o = 0;
        Object.values(expenses).forEach(e => { f += e.fare; fd += e.food; o += e.other; });
        totals = { fare: f, food: fd, other: o, spent: f + fd + o, remaining: allowance - (f + fd + o) };
    }
    
    spentAmount.textContent = `₱${totals.spent.toFixed(2)}`;
    const pct = (totals.spent / allowance) * 100;
    percentUsed.textContent = `${pct.toFixed(0)}%`;
    progressFill.style.width = `${Math.min(pct, 100)}%`;
    progressFill.className = 'progress-fill' + (pct > 100 ? ' danger' : pct > 80 ? ' warning' : '');
    remainingAmount.textContent = `₱${totals.remaining.toFixed(2)}`;
    remainingAmount.classList.toggle('negative', totals.remaining < 0);
    daysLogged.textContent = `${Object.keys(expenses).length}/7`;
    warningMessage.classList.toggle('hidden', totals.remaining >= 0);
    totalFare.textContent = `₱${totals.fare.toFixed(2)}`;
    totalFood.textContent = `₱${totals.food.toFixed(2)}`;
    totalOther.textContent = `₱${totals.other.toFixed(2)}`;
    grandTotal.textContent = `₱${totals.spent.toFixed(2)}`;
}

// Render Expense List
function renderExpenseList() {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const today = new Date().getDay(); 
    
    // Check if any expenses to show or any days have passed
    const hasAnyExpenses = Object.keys(expenses).length > 0;
    const hasPastDays = today > 0; 
    
    if (!hasAnyExpenses && !hasPastDays) {
        summaryCard.classList.add('hidden');
        return;
    }
    
    summaryCard.classList.remove('hidden');
    expenseList.innerHTML = '';
    
    days.forEach((day, index) => {
        const e = expenses[day];
        const hasExpense = !!e;
        const isPast = index < today; 
        const isToday = index === today;
        const isFuture = index > today;
        
        // Show past days (always) and today (only if it has expenses)
        if (isFuture || (isToday && !hasExpense)) return;
        
        const item = document.createElement('div');
        item.className = 'expense-item';
        
        if (hasExpense) {
            // Day with expenses - show breakdown
            item.innerHTML = `
                <div class="expense-item-header">
                    <span class="expense-item-day">${day}${isToday ? ' (Today)' : ''}</span>
                    <div class="expense-item-actions">
                        <span class="expense-item-total">₱${e.total.toFixed(2)}</span>
                        <button class="delete-btn" onclick="deleteExpense('${day}')">✕</button>
                    </div>
                </div>
                <div class="expense-breakdown">
                    ${e.fare > 0 ? `<span class="breakdown-tag">Fare: ₱${e.fare.toFixed(2)}</span>` : ''}
                    ${e.food > 0 ? `<span class="breakdown-tag">Food: ₱${e.food.toFixed(2)}</span>` : ''}
                    ${e.other > 0 ? `<span class="breakdown-tag">Other: ₱${e.other.toFixed(2)}</span>` : ''}
                </div>
            `;
        } else {
            item.classList.add('no-expense-day');
            item.innerHTML = `
                <span class="expense-item-day">${day}</span>
                <div><span class="expense-item-no-expense">No expenses</span></div>
            `;
        }
        expenseList.appendChild(item);
    });
}

function updateDayButtons() {
    const today = new Date().getDay(); 
    
    dayButtons.forEach(btn => {
        const dayIndex = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].indexOf(btn.dataset.day);
        const isFuture = dayIndex > today;
        const hasExpense = expenses[btn.dataset.day];
        
        // Disable if: already has expense OR is a future day
        btn.disabled = hasExpense || isFuture;
    });
}

// Monthly Summary
async function loadMonthlySummary() {
    try {
        const res = await fetch(`/api/monthly-summary?month=${currentMonth}&year=${currentYear}`);
        const data = await res.json();
        if (res.ok) {
            document.getElementById('currentMonth').textContent = data.month_name;
            if (data.num_weeks === 0) {
                document.getElementById('noMonthlyData').classList.remove('hidden');
                document.querySelector('.monthly-stats').style.display = 'none';
                document.querySelector('.monthly-content').style.display = 'none';
            } else {
                document.getElementById('noMonthlyData').classList.add('hidden');
                document.querySelector('.monthly-stats').style.display = 'grid';
                document.querySelector('.monthly-content').style.display = 'grid';
                document.getElementById('monthlyAllowance').textContent = `₱${data.total_allowance.toFixed(2)}`;
                document.getElementById('monthlySpent').textContent = `₱${data.total_spent.toFixed(2)}`;
                document.getElementById('monthlySaved').textContent = `₱${data.total_saved.toFixed(2)}`;
                document.getElementById('monthlySaved').classList.toggle('negative', data.total_saved < 0);
                document.getElementById('monthlyFare').textContent = `₱${data.breakdown.fare.toFixed(2)}`;
                document.getElementById('monthlyFood').textContent = `₱${data.breakdown.food.toFixed(2)}`;
                document.getElementById('monthlyOther').textContent = `₱${data.breakdown.other.toFixed(2)}`;
                renderWeeklyBreakdown(data.weeks);
            }
        }
    } catch (e) { console.error(e); }
}

// Render Weekly Breakdown
function renderWeeklyBreakdown(weeks) {
    const weeklyList = document.getElementById('weeklyList');
    weeklyList.innerHTML = '';
    weeks.forEach((week, i) => {
        const date = new Date(week.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const item = document.createElement('div');
        item.className = 'week-item';
        item.innerHTML = `
            <div class="week-header"><h4>Week ${i + 1}</h4><span class="week-date">${date}</span></div>
            <div class="week-stats">
                <div class="week-stat"><span class="week-stat-label">Allowance</span><span class="week-stat-value">₱${week.allowance.toFixed(2)}</span></div>
                <div class="week-stat"><span class="week-stat-label">Spent</span><span class="week-stat-value">₱${week.spent.toFixed(2)}</span></div>
                <div class="week-stat ${week.saved >= 0 ? 'positive' : 'negative'}"><span class="week-stat-label">Saved</span><span class="week-stat-value">₱${week.saved.toFixed(2)}</span></div>
            </div>`;
        weeklyList.appendChild(item);
    });
}

// Global functions
window.deleteExpense = deleteExpense;
window.toggleTheme = toggleTheme;
window.exportWeeklyPDF = exportWeeklyPDF;
window.exportMonthlyPDF = exportMonthlyPDF;

// Init
window.addEventListener('DOMContentLoaded', async () => {
    console.log('=== PAGE LOAD START ===');
    
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) {
        console.log('User not authenticated, redirecting to login.');
        return;
    }
    console.log('User authenticated successfully.');
    // Disable future day buttons immediately
    updateDayButtons();
    
    await loadWeekInfo();
    
    try {
        console.log('Fetching budget from API...');
        const res = await fetch('/api/get-budget');
        console.log('Response status:', res.status);
        
        if (res.ok) {
            const data = await res.json();
            console.log('Data received:', data);
            console.log('Allowance from API:', data.allowance);
            
            // Set the data
            allowance = data.allowance || 0;
            expenses = data.expenses || {};
            
            console.log('Allowance variable set to:', allowance);
            console.log('Is allowance > 0?', allowance > 0);
            
            // Check if budget exists
            if (allowance > 0) {
                console.log('✅ SHOWING TRACKER SCREEN');
                allowanceDisplay.textContent = `₱${allowance.toFixed(2)}`;
                setupScreen.classList.remove('active');
                trackerScreen.classList.add('active');
                exportBtn.classList.remove('hidden');
                
                // Update the display
                updateDisplay(data.totals);
                renderExpenseList();
                updateDayButtons();
            } else {
                console.log('❌ SHOWING SETUP SCREEN - No allowance');
                setupScreen.classList.add('active');
                trackerScreen.classList.remove('active');
                exportBtn.classList.add('hidden');
            }
        } else {
            console.log('❌ SHOWING SETUP SCREEN - Response not OK');
            setupScreen.classList.add('active');
            trackerScreen.classList.remove('active');
            exportBtn.classList.add('hidden');
        }
    } catch (e) { 
        console.log('❌ SHOWING SETUP SCREEN - Error caught:', e);
        setupScreen.classList.add('active');
        trackerScreen.classList.remove('active');
        exportBtn.classList.add('hidden');
    }
    
    console.log('=== PAGE LOAD END ===');
    loadMonthlySummary();
});