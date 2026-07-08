import re

CATEGORIES = [
    "fare",
    "food",
    "groceries",
    "bills",
    "shopping",
    "entertainment",
    "health",
    "other",
]

CATEGORY_LABELS = {
    "fare": "Transport",
    "food": "Food",
    "groceries": "Groceries",
    "bills": "Bills & Utilities",
    "shopping": "Shopping",
    "entertainment": "Entertainment",
    "health": "Health",
    "other": "Other",
}

CATEGORY_KEYWORDS = {
    "fare": [
        "jeep", "jeepney", "bus", "grab", "taxi", "uber", "fare", "transport",
        "transpo", "tricycle", "trisikad", "pedicab", "mrt", "lrt", "train",
        "gas", "gasoline", "diesel", "petrol", "fuel", "parking", "toll",
        "angkas", "joyride", "commute", "ride", "terminal", "station",
        "multicab", "vhire", "fx", "habal", "boat", "ferry", "plane", "flight",
        "airfare", "carwash", "toda", "pamasahe",
        "v-hire", "habal-habal", "car wash", "gas station", "grab car",
    ],
    "food": [
        "food", "meal", "lunch", "dinner", "breakfast", "snack", "merienda",
        "coffee", "rice", "ulam", "drink", "softdrink", "soda", "juice",
        "jollibee", "mcdo", "mcdonalds", "kfc", "chowking", "restaurant",
        "cafe", "burger", "pizza", "milktea", "tea", "bread", "turon", "siomai",
        "shawarma", "fries", "chicken", "fishball", "kwek", "isaw", "buffet",
        "samgyup", "samgyupsal", "carinderia", "eatery", "canteen", "pancit",
        "lugaw", "adobo", "water",
        "mang inasal", "street food", "turo-turo", "fast food", "milk tea",
    ],
    "groceries": [
        "groceries", "grocery", "supermarket", "mart", "minimart", "palengke",
        "market", "puregold", "savemore", "robinsons", "waltermart", "sari",
        "eggs", "vegetables", "veggies", "meat", "toiletries", "soap",
        "shampoo", "detergent", "tissue", "fruits", "711",
        "sari-sari", "7-eleven", "seven eleven", "wet market", "canned goods",
        "cooking oil", "dish soap", "grocery store",
    ],
    "bills": [
        "bill", "bills", "electric", "electricity", "meralco", "internet",
        "wifi", "load", "prepaid", "postpaid", "globe", "smart", "tnt", "dito",
        "pldt", "converge", "rent", "utilities", "cable", "tuition",
        "kuryente", "tubig",
        "electric bill", "water bill", "phone bill", "internet bill",
        "cable bill", "monthly rent",
    ],
    "shopping": [
        "shopping", "clothes", "clothing", "shirt", "tshirt", "pants", "jeans",
        "shoes", "sandals", "slippers", "bag", "dress", "jacket", "uniqlo",
        "penshoppe", "bench", "shopee", "lazada", "tiktok", "mall",
        "accessories", "makeup", "cosmetics", "lipstick", "gadget", "charger",
        "earphones", "headphones", "laptop", "keyboard", "mouse", "watch",
        "toys", "souvenir",
        "phone case", "department store",
    ],
    "entertainment": [
        "movie", "cinema", "netflix", "spotify", "youtube", "game", "games",
        "gaming", "steam", "playstation", "xbox", "concert", "ticket",
        "tickets", "gacha", "ktv", "videoke", "karaoke", "bar", "gimik",
        "arcade", "bowling", "billiards", "park", "museum", "zoo", "lotto",
        "valorant", "genshin", "roblox", "subscription",
        "mobile legends", "theme park", "amusement park", "board game",
    ],
    "health": [
        "medicine", "meds", "drug", "drugstore", "pharmacy", "mercury",
        "watsons", "hospital", "clinic", "doctor", "dentist", "checkup",
        "consultation", "vitamins", "vitamin", "supplement", "bandage",
        "medical", "therapy", "dental", "optical", "eyeglasses", "insurance",
        "maintenance",
        "check-up", "first aid",
    ],
}

CATEGORY_PRIORITY = [
    "health",
    "bills",
    "fare",
    "groceries",
    "entertainment",
    "shopping",
    "food",
]


def categorize_item(name: str) -> str:
    lower = (name or "").lower().strip()
    if not lower:
        return "other"

    tokens = set(re.findall(r"[a-z0-9]+", lower))
    for category in CATEGORY_PRIORITY:
        for kw in CATEGORY_KEYWORDS.get(category, []):
            if " " in kw or "-" in kw:
                if kw in lower:
                    return category
            elif kw in tokens:
                return category
    return "other"
