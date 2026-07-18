const textCases = [
    'spent', 'paid', 'bought', 'on', 'for',
    'at', 'a', 'an', 'the', 'php',
    'pesos', 'used', 'spend', 'purchase', 'purchased',
    'subscribed', 'subscription', 'to',
]

export function expensePhrase(text, {
    weekDays, todayName } = {}) { 
        if (typeof text !== "string") {
            return null;
        }
        let workingText = text.toLowerCase().trim();

        if (workingText == ''){
            return null;
        }
        const amountMatch = workingText.match(/(\d+\.?\d*)/);

        if (amountMatch === null) {
            return null;
        }

        const amount = Number(amountMatch[1]);

        if (amount <= 0) {
            return null;
        }
        workingText = workingText.replace(amountMatch[0], '').trim();

        let day;
        const days = weekDays || ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];


        const todayIdx = todayName
            ? days.findIndex((d) => d.toLowerCase() === todayName.toLowerCase())
            : -1;

        if (workingText.includes('today') && todayIdx >= 0) {
            day = days[todayIdx];
            workingText = workingText.replace('today', '').trim();
        } else if (workingText.includes('yesterday') && todayIdx >= 0) {
            day = days[(todayIdx + 6) % 7];
            workingText = workingText.replace('yesterday', '').trim();
        }  else {
            
        }


        const words = workingText.split(/\s+/).filter(Boolean);

        const name = words
        .filter((w) => !textCases.includes(w))
        .join(' ')
        .trim();

        if (!name) {
        return null;
        }

        return {
        amount,
        name,
        day: day ? day.trim() : null,
        };
    }
