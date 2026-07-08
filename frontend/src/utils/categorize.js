export const CATEGORIES = [
  'fare',
  'food',
  'groceries',
  'bills',
  'shopping',
  'entertainment',
  'health',
  'other',
];

export const CATEGORY_LABELS = {
  fare: 'Transport',
  food: 'Food',
  groceries: 'Groceries',
  bills: 'Bills & Utilities',
  shopping: 'Shopping',
  entertainment: 'Entertainment',
  health: 'Health',
  other: 'Other',
};

export const CATEGORY_ICONS = {
  fare: '→',
  food: '◆',
  groceries: '▤',
  bills: '▮',
  shopping: '◈',
  entertainment: '★',
  health: '✚',
  other: '○',
};

export const CATEGORY_COLORS = {
  fare: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  food: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/20',
  groceries: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  bills: 'bg-amber-500/15 text-amber-300 border-amber-500/20',
  shopping: 'bg-sky-500/15 text-sky-300 border-sky-500/20',
  entertainment: 'bg-pink-500/15 text-pink-300 border-pink-500/20',
  health: 'bg-rose-500/15 text-rose-300 border-rose-500/20',
  other: 'bg-purple-500/15 text-purple-300 border-purple-500/20',
};

const CATEGORY_KEYWORDS = {
  fare: [
    'jeep', 'jeepney', 'bus', 'grab', 'taxi', 'uber', 'fare', 'transport',
    'transpo', 'tricycle', 'trisikad', 'pedicab', 'mrt', 'lrt', 'train',
    'gas', 'gasoline', 'diesel', 'petrol', 'fuel', 'parking', 'toll',
    'angkas', 'joyride', 'commute', 'ride', 'terminal', 'station',
    'multicab', 'vhire', 'fx', 'habal', 'boat', 'ferry', 'plane', 'flight',
    'airfare', 'carwash', 'toda', 'pamasahe', 'lrt', 'mrt',
    'v-hire', 'habal-habal', 'car wash', 'gas station', 'grab car',
  ],
  food: [
    'food', 'meal', 'lunch', 'dinner', 'breakfast', 'snack', 'merienda',
    'coffee', 'rice', 'ulam', 'drink', 'softdrink', 'soda', 'juice',
    'jollibee', 'mcdo', 'mcdonalds', 'kfc', 'chowking', 'restaurant',
    'cafe', 'burger', 'pizza', 'milktea', 'tea', 'bread', 'turon', 'siomai',
    'shawarma', 'fries', 'chicken', 'fishball', 'kwek', 'isaw', 'buffet',
    'samgyup', 'samgyupsal', 'carinderia', 'eatery', 'canteen', 'pancit',
    'lugaw', 'adobo', 'water',
    'mang inasal', 'street food', 'turo-turo', 'fast food', 'milk tea',
  ],
  groceries: [
    'groceries', 'grocery', 'supermarket', 'mart', 'minimart', 'palengke',
    'market', 'puregold', 'savemore', 'robinsons', 'waltermart', 'sari',
    'eggs', 'vegetables', 'veggies', 'meat', 'toiletries', 'soap',
    'shampoo', 'detergent', 'tissue', 'fruits', '711',
    'sari-sari', '7-eleven', 'seven eleven', 'wet market', 'canned goods',
    'cooking oil', 'dish soap', 'grocery store',
  ],
  bills: [
    'bill', 'bills', 'electric', 'electricity', 'meralco', 'internet',
    'wifi', 'load', 'prepaid', 'postpaid', 'globe', 'smart', 'tnt', 'dito',
    'pldt', 'converge', 'rent', 'utilities', 'cable', 'tuition',
    'kuryente', 'tubig',
    'electric bill', 'water bill', 'phone bill', 'internet bill',
    'cable bill', 'monthly rent',
  ],
  shopping: [
    'shopping', 'clothes', 'clothing', 'shirt', 'tshirt', 'pants', 'jeans',
    'shoes', 'sandals', 'slippers', 'bag', 'dress', 'jacket', 'uniqlo',
    'penshoppe', 'bench', 'shopee', 'lazada', 'tiktok', 'mall',
    'accessories', 'makeup', 'cosmetics', 'lipstick', 'gadget', 'charger',
    'earphones', 'headphones', 'laptop', 'keyboard', 'mouse', 'watch',
    'toys', 'souvenir',
    'phone case', 'department store',
  ],
  entertainment: [
    'movie', 'cinema', 'netflix', 'spotify', 'youtube', 'game', 'games',
    'gaming', 'steam', 'playstation', 'xbox', 'concert', 'ticket',
    'tickets', 'gacha', 'ktv', 'videoke', 'karaoke', 'bar', 'gimik',
    'arcade', 'bowling', 'billiards', 'park', 'museum', 'zoo', 'lotto',
    'valorant', 'genshin', 'roblox', 'subscription',
    'mobile legends', 'theme park', 'amusement park', 'board game',
  ],
  health: [
    'medicine', 'meds', 'drug', 'drugstore', 'pharmacy', 'mercury',
    'watsons', 'hospital', 'clinic', 'doctor', 'dentist', 'checkup',
    'consultation', 'vitamins', 'vitamin', 'supplement', 'bandage',
    'medical', 'therapy', 'dental', 'optical', 'eyeglasses', 'insurance',
    'maintenance',
    'check-up', 'first aid',
  ],
};

const CATEGORY_PRIORITY = [
  'health',
  'bills',
  'fare',
  'groceries',
  'entertainment',
  'shopping',
  'food',
];

export function categorizeItem(name) {
  const lower = (name || '').toLowerCase().trim();
  if (!lower) return 'other';

  const tokens = new Set(lower.match(/[a-z0-9]+/g) || []);
  for (const category of CATEGORY_PRIORITY) {
    for (const kw of CATEGORY_KEYWORDS[category] || []) {
      if (kw.includes(' ') || kw.includes('-')) {
        if (lower.includes(kw)) return category;
      } else if (tokens.has(kw)) {
        return category;
      }
    }
  }
  return 'other';
}
