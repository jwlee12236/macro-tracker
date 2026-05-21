"""
Seed script — inserts ~130 common ingredients into macro.db
Run: python3 seed.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "macro.db"

# (name, brand, category, serving_size, serving_unit, cal, pro, carb, fat, fiber, sugar, sodium)
INGREDIENTS = [
    # ── Raw Proteins ──────────────────────────────────────────────────────────
    ("Chicken Breast",          "", "raw",  100, "g",  120, 22.5, 0.0,  2.6, 0.0, 0.0,  74),
    ("Chicken Thigh",           "", "raw",  100, "g",  177, 18.0, 0.0, 11.0, 0.0, 0.0,  87),
    ("Turkey Breast",           "", "raw",  100, "g",  104, 22.0, 0.0,  1.0, 0.0, 0.0,  63),
    ("Ground Beef 80/20",       "", "raw",  100, "g",  254, 17.0, 0.0, 20.0, 0.0, 0.0,  75),
    ("Ground Beef 93/7",        "", "raw",  100, "g",  152, 21.0, 0.0,  7.0, 0.0, 0.0,  74),
    ("Beef Sirloin Steak",      "", "raw",  100, "g",  207, 26.0, 0.0, 11.0, 0.0, 0.0,  69),
    ("Beef Ribeye",             "", "raw",  100, "g",  291, 24.0, 0.0, 21.0, 0.0, 0.0,  72),
    ("Pork Tenderloin",         "", "raw",  100, "g",  109, 21.0, 0.0,  2.4, 0.0, 0.0,  53),
    ("Pork Belly",              "", "raw",  100, "g",  518, 9.3,  0.0, 53.0, 0.0, 0.0,  39),
    ("Lamb Chop",               "", "raw",  100, "g",  294, 25.0, 0.0, 21.0, 0.0, 0.0,  75),
    ("Salmon",                  "", "raw",  100, "g",  208, 20.0, 0.0, 13.0, 0.0, 0.0,  59),
    ("Tuna (yellowfin)",        "", "raw",  100, "g",  132, 28.0, 0.0,  1.3, 0.0, 0.0,  45),
    ("Tuna Canned in Water",    "", "packaged", 100, "g", 116, 26.0, 0.0, 0.8, 0.0, 0.0, 320),
    ("Cod",                     "", "raw",  100, "g",   82, 18.0, 0.0,  0.7, 0.0, 0.0,  78),
    ("Shrimp",                  "", "raw",  100, "g",   99, 24.0, 0.2,  0.3, 0.0, 0.0, 111),
    ("Tilapia",                 "", "raw",  100, "g",   96, 20.0, 0.0,  1.7, 0.0, 0.0,  56),
    ("Whole Egg",               "", "raw",    1, "piece", 78,  6.3, 0.6,  5.3, 0.0, 0.6,  62),
    ("Egg White",               "", "raw",  100, "g",   52, 10.9, 0.7,  0.2, 0.0, 0.7, 166),
    ("Egg Yolk",                "", "raw",    1, "piece", 55,  2.7, 0.6,  4.5, 0.0, 0.1,   8),
    # ── Dairy ─────────────────────────────────────────────────────────────────
    ("Whole Milk",              "", "dairy", 100, "ml",  61,  3.2, 4.8,  3.3, 0.0, 5.1,  44),
    ("2% Milk",                 "", "dairy", 100, "ml",  50,  3.4, 4.8,  2.0, 0.0, 5.1,  44),
    ("Skim Milk",               "", "dairy", 100, "ml",  34,  3.4, 5.0,  0.1, 0.0, 5.1,  44),
    ("Greek Yogurt Full Fat",   "", "dairy", 100, "g",   97,  9.0, 3.6,  5.0, 0.0, 3.2,  36),
    ("Greek Yogurt 0%",         "", "dairy", 100, "g",   59, 10.0, 3.6,  0.4, 0.0, 3.2,  36),
    ("Cottage Cheese 2%",       "", "dairy", 100, "g",   84, 11.0, 3.4,  2.3, 0.0, 2.7, 321),
    ("Cheddar Cheese",          "", "dairy", 100, "g",  402, 25.0, 1.3, 33.0, 0.0, 0.5, 621),
    ("Mozzarella",              "", "dairy", 100, "g",  280, 28.0, 3.1, 17.0, 0.0, 1.0, 627),
    ("Parmesan",                "", "dairy", 100, "g",  431, 38.0, 4.0, 29.0, 0.0, 0.9, 1529),
    ("Ricotta",                 "", "dairy", 100, "g",  174, 11.0, 3.0, 13.0, 0.0, 0.3, 100),
    ("Butter",                  "", "dairy", 100, "g",  717,  0.9, 0.1, 81.0, 0.0, 0.1, 714),
    ("Heavy Cream",             "", "dairy", 100, "ml", 340,  2.8, 2.8, 36.0, 0.0, 2.8,  38),
    ("Cream Cheese",            "", "dairy", 100, "g",  342,  6.0, 4.1, 34.0, 0.0, 3.2, 321),
    ("Whipping Cream",          "", "dairy", 100, "ml", 257,  2.0, 2.8, 27.0, 0.0, 2.8,  27),
    # ── Plant Milks & Drinks ──────────────────────────────────────────────────
    ("Oat Milk",                "Oatly",      "drink", 100, "ml",  45,  1.0, 6.5,  1.5, 0.8, 4.0,  80),
    ("Oat Milk Barista",        "Oatly",      "drink", 100, "ml",  65,  1.0, 9.0,  2.5, 0.5, 3.5,  90),
    ("Almond Milk Unsweetened", "",           "drink", 100, "ml",  15,  0.6, 0.3,  1.2, 0.3, 0.2, 115),
    ("Soy Milk Unsweetened",    "",           "drink", 100, "ml",  43,  3.3, 2.8,  1.8, 0.4, 1.8, 115),
    ("Coconut Milk Full Fat",   "",           "drink", 100, "ml", 230,  2.3, 5.5, 24.0, 0.0, 3.3,  15),
    ("Coconut Milk Light",      "",           "drink", 100, "ml",  75,  0.7, 3.5,  7.0, 0.0, 1.5,  18),
    ("Rice Milk",               "",           "drink", 100, "ml",  47,  0.3, 9.2,  1.0, 0.0, 4.2,  39),
    ("Nespresso Capsule",       "Nespresso",  "drink",  30, "ml",   3,  0.1, 0.5,  0.0, 0.0, 0.0,   0),
    ("Espresso",                "",           "drink",  30, "ml",   3,  0.1, 0.4,  0.0, 0.0, 0.0,   1),
    ("Black Coffee",            "",           "drink", 240, "ml",   2,  0.3, 0.0,  0.0, 0.0, 0.0,   5),
    # ── Grains & Carbs ────────────────────────────────────────────────────────
    ("Rolled Oats",             "", "raw",    100, "g", 389, 17.0, 66.0,  7.0,  10.6, 1.1,  2),
    ("White Rice",              "", "raw",    100, "g", 365,  7.1, 80.0,  0.7,  1.3,  0.1,  5),
    ("White Rice Cooked",       "", "raw",    100, "g", 130,  2.7, 28.0,  0.3,  0.4,  0.0,  1),
    ("Brown Rice",              "", "raw",    100, "g", 370,  7.9, 77.0,  2.9,  3.5,  0.8,  4),
    ("Brown Rice Cooked",       "", "raw",    100, "g", 122,  2.6, 26.0,  0.9,  1.8,  0.3,  1),
    ("Pasta Dry",               "", "raw",    100, "g", 371, 13.0, 74.0,  1.5,  3.2,  2.7,  6),
    ("Pasta Cooked",            "", "raw",    100, "g", 131,  5.0, 25.0,  1.1,  1.8,  0.6,  1),
    ("Whole Wheat Bread",       "", "packaged", 100, "g", 247, 11.0, 43.0,  3.5,  7.0, 5.0, 450),
    ("White Bread",             "", "packaged", 100, "g", 265,  9.0, 49.0,  3.2,  2.7, 5.1, 490),
    ("Sourdough Bread",         "", "packaged", 100, "g", 274,  8.8, 51.0,  2.7,  2.2, 3.2, 517),
    ("Quinoa Cooked",           "", "raw",    100, "g", 120,  4.4, 22.0,  1.9,  2.8,  0.9, 13),
    ("Sweet Potato Cooked",     "", "raw",    100, "g",  86,  1.6, 20.0,  0.1,  3.3,  4.2, 27),
    ("White Potato Cooked",     "", "raw",    100, "g",  87,  1.9, 20.0,  0.1,  1.8,  0.9,  5),
    ("Corn Tortilla",           "", "packaged",  1, "piece", 52,  1.4, 10.7,  0.7,  1.5, 0.2, 11),
    ("Flour Tortilla",          "", "packaged",  1, "piece", 146, 4.0, 25.0,  3.5,  1.5, 0.9, 217),
    ("Granola",                 "", "packaged", 100, "g", 471, 11.0, 64.0, 20.0,  5.9, 25.0, 66),
    ("Bagel",                   "", "packaged",  1, "piece", 270, 10.0, 53.0,  1.5,  2.3, 7.0, 430),
    # ── Legumes ───────────────────────────────────────────────────────────────
    ("Black Beans Cooked",      "", "raw",  100, "g", 132,  8.9, 24.0,  0.5,  8.7,  0.3,  1),
    ("Chickpeas Cooked",        "", "raw",  100, "g", 164,  8.9, 27.0,  2.6,  7.6,  4.8, 24),
    ("Lentils Cooked",          "", "raw",  100, "g", 116,  9.0, 20.0,  0.4,  7.9,  1.8,  2),
    ("Kidney Beans Cooked",     "", "raw",  100, "g", 127,  8.7, 23.0,  0.5,  6.4,  0.3,  2),
    ("Edamame",                 "", "raw",  100, "g", 122, 10.6,  8.9,  5.2,  5.2,  2.2,  6),
    ("Tofu Firm",               "", "raw",  100, "g",  76,  8.1,  1.9,  4.8,  0.3,  0.5,  7),
    ("Tofu Silken",             "", "raw",  100, "g",  55,  5.3,  2.0,  2.7,  0.0,  0.8,  9),
    ("Tempeh",                  "", "raw",  100, "g", 193, 19.0,  9.4, 11.0,  0.0,  0.0, 14),
    # ── Vegetables ───────────────────────────────────────────────────────────
    ("Broccoli",                "", "raw",  100, "g",  34,  2.8,  7.0,  0.4,  2.6,  1.7, 33),
    ("Spinach",                 "", "raw",  100, "g",  23,  2.9,  3.6,  0.4,  2.2,  0.4, 79),
    ("Kale",                    "", "raw",  100, "g",  49,  4.3,  9.0,  0.9,  2.0,  0.0, 38),
    ("Carrots",                 "", "raw",  100, "g",  41,  0.9, 10.0,  0.2,  2.8,  4.7, 69),
    ("Bell Pepper Red",         "", "raw",  100, "g",  31,  1.0,  6.0,  0.3,  2.1,  4.2,  4),
    ("Bell Pepper Green",       "", "raw",  100, "g",  20,  0.9,  4.6,  0.2,  1.7,  2.4,  3),
    ("Cucumber",                "", "raw",  100, "g",  15,  0.7,  3.6,  0.1,  0.5,  1.7,  2),
    ("Tomato",                  "", "raw",  100, "g",  18,  0.9,  3.9,  0.2,  1.2,  2.6,  5),
    ("Cherry Tomatoes",         "", "raw",  100, "g",  18,  0.9,  3.9,  0.2,  1.2,  2.6,  5),
    ("Onion",                   "", "raw",  100, "g",  40,  1.1,  9.3,  0.1,  1.7,  4.2,  4),
    ("Garlic",                  "", "raw",  100, "g", 149,  6.4, 33.0,  0.5,  2.1,  1.0,  17),
    ("Mushrooms White",         "", "raw",  100, "g",  22,  3.1,  3.3,  0.3,  1.0,  2.0,  5),
    ("Avocado",                 "", "raw",  100, "g", 160,  2.0,  9.0, 15.0,  7.0,  0.7,  7),
    ("Zucchini",                "", "raw",  100, "g",  17,  1.2,  3.1,  0.3,  1.0,  2.5,  8),
    ("Brussels Sprouts",        "", "raw",  100, "g",  43,  3.4,  9.0,  0.3,  3.8,  2.2, 25),
    ("Asparagus",               "", "raw",  100, "g",  20,  2.2,  3.9,  0.1,  2.1,  1.9,  2),
    ("Celery",                  "", "raw",  100, "g",  16,  0.7,  3.0,  0.2,  1.6,  1.3, 80),
    ("Green Beans",             "", "raw",  100, "g",  31,  1.8,  7.0,  0.2,  2.7,  3.3,  6),
    ("Cauliflower",             "", "raw",  100, "g",  25,  1.9,  5.0,  0.3,  2.0,  1.9, 30),
    ("Romaine Lettuce",         "", "raw",  100, "g",  17,  1.2,  3.3,  0.3,  2.1,  1.2,  8),
    ("Arugula",                 "", "raw",  100, "g",  25,  2.6,  3.7,  0.7,  1.6,  2.1, 27),
    ("Sweet Corn",              "", "raw",  100, "g",  86,  3.3, 19.0,  1.4,  2.7,  3.2, 15),
    ("Cabbage",                 "", "raw",  100, "g",  25,  1.3,  5.8,  0.1,  2.5,  3.2, 18),
    ("Eggplant",                "", "raw",  100, "g",  25,  1.0,  5.9,  0.2,  3.0,  3.5,  2),
    ("Beetroot",                "", "raw",  100, "g",  43,  1.6,  9.6,  0.2,  2.8,  6.8, 78),
    # ── Fruits ───────────────────────────────────────────────────────────────
    ("Banana",                  "", "raw",  100, "g",  89,  1.1, 23.0,  0.3,  2.6, 12.2,  1),
    ("Apple",                   "", "raw",  100, "g",  52,  0.3, 14.0,  0.2,  2.4, 10.4,  1),
    ("Strawberries",            "", "raw",  100, "g",  32,  0.7,  7.7,  0.3,  2.0,  4.9,  1),
    ("Blueberries",             "", "raw",  100, "g",  57,  0.7, 14.0,  0.3,  2.4,  9.9,  1),
    ("Raspberries",             "", "raw",  100, "g",  52,  1.2, 12.0,  0.7,  6.5,  4.4,  1),
    ("Orange",                  "", "raw",  100, "g",  47,  0.9, 12.0,  0.1,  2.4,  9.4,  0),
    ("Mango",                   "", "raw",  100, "g",  60,  0.8, 15.0,  0.4,  1.6, 13.7,  1),
    ("Pineapple",               "", "raw",  100, "g",  50,  0.5, 13.0,  0.1,  1.4,  9.9,  1),
    ("Grapes",                  "", "raw",  100, "g",  69,  0.7, 18.0,  0.2,  0.9, 15.5,  2),
    ("Watermelon",              "", "raw",  100, "g",  30,  0.6,  7.6,  0.2,  0.4,  6.2,  1),
    ("Peach",                   "", "raw",  100, "g",  39,  0.9,  9.5,  0.3,  1.5,  8.4,  0),
    ("Pear",                    "", "raw",  100, "g",  57,  0.4, 15.0,  0.1,  3.1,  9.8,  1),
    ("Cherries",                "", "raw",  100, "g",  50,  1.0, 12.0,  0.3,  1.6,  8.5,  0),
    # ── Nuts, Seeds & Oils ────────────────────────────────────────────────────
    ("Almonds",                 "", "raw",  100, "g", 579, 21.0, 22.0, 50.0, 12.5,  4.4,  1),
    ("Walnuts",                 "", "raw",  100, "g", 654, 15.0, 14.0, 65.0,  6.7,  2.6,  2),
    ("Cashews",                 "", "raw",  100, "g", 553, 18.0, 30.0, 44.0,  3.3,  5.9, 12),
    ("Peanuts",                 "", "raw",  100, "g", 567, 26.0, 16.0, 49.0,  8.5,  4.7, 18),
    ("Macadamia Nuts",          "", "raw",  100, "g", 718,  7.9, 14.0, 76.0,  8.6,  4.6,  5),
    ("Pecans",                  "", "raw",  100, "g", 691,  9.2, 14.0, 72.0,  9.6,  3.9,  0),
    ("Pistachios",              "", "raw",  100, "g", 562, 20.0, 28.0, 45.0, 10.3,  7.7,  1),
    ("Peanut Butter",           "", "raw",  100, "g", 588, 25.0, 20.0, 50.0,  6.0,  9.0, 426),
    ("Almond Butter",           "", "raw",  100, "g", 614, 21.0, 19.0, 55.0, 10.0,  4.4,  7),
    ("Chia Seeds",              "", "raw",  100, "g", 486, 17.0, 42.0, 31.0, 34.0,  0.0,  16),
    ("Flaxseeds",               "", "raw",  100, "g", 534, 18.0, 29.0, 42.0, 27.0,  1.6,  30),
    ("Hemp Seeds",              "", "raw",  100, "g", 553, 32.0,  8.7, 49.0,  4.0,  1.5,   5),
    ("Sunflower Seeds",         "", "raw",  100, "g", 584, 21.0, 20.0, 51.0,  8.6,  2.6,   9),
    ("Pumpkin Seeds",           "", "raw",  100, "g", 559, 30.0, 11.0, 49.0,  6.0,  1.4,  18),
    ("Olive Oil",               "", "other",  15, "ml", 133,  0.0,  0.0, 15.0,  0.0,  0.0,   0),
    ("Coconut Oil",             "", "other",  14, "g",  121,  0.0,  0.0, 14.0,  0.0,  0.0,   0),
    ("Avocado Oil",             "", "other",  14, "ml", 124,  0.0,  0.0, 14.0,  0.0,  0.0,   0),
    # ── Supplements ──────────────────────────────────────────────────────────
    ("Whey Protein Powder",     "", "supplement", 30, "g", 120, 24.0,  3.0,  2.0, 0.0,  2.0, 130),
    ("Casein Protein Powder",   "", "supplement", 30, "g", 110, 24.0,  4.0,  0.5, 0.0,  1.0, 220),
    ("Plant Protein Powder",    "", "supplement", 30, "g", 110, 20.0,  5.0,  2.5, 2.0,  1.0, 190),
    ("Creatine Monohydrate",    "", "supplement",  5, "g",   0,  0.0,  0.0,  0.0, 0.0,  0.0,   0),
    ("Collagen Peptides",       "", "supplement", 11, "g",  40, 10.0,  0.0,  0.0, 0.0,  0.0,  20),
    # ── Condiments & Sauces ──────────────────────────────────────────────────
    ("Honey",                   "", "other", 21, "g",  64,  0.1, 17.0,  0.0, 0.0, 17.0,  1),
    ("Maple Syrup",             "", "other", 20, "ml",  52,  0.0, 13.0,  0.0, 0.0, 12.0,  2),
    ("Soy Sauce",               "", "other", 15, "ml",   9,  1.5,  0.8,  0.0, 0.0,  0.4, 902),
    ("Ketchup",                 "", "other", 17, "g",  20,  0.2,  4.8,  0.0, 0.0,  3.5, 190),
    ("Sriracha",                "", "other",  5, "g",   5,  0.1,  0.9,  0.1, 0.0,  0.6,  80),
    ("Hot Sauce (Tabasco)",     "", "other",  5, "ml",   1,  0.0,  0.2,  0.0, 0.0,  0.0,  35),
    ("Mustard",                 "", "other",  5, "g",   5,  0.3,  0.4,  0.3, 0.2,  0.1,  57),
    ("Mayonnaise",              "", "other", 15, "g",  99,  0.1,  0.3, 11.0, 0.0,  0.1,  88),
    ("Salsa",                   "", "other", 30, "g",  10,  0.4,  2.0,  0.1, 0.5,  1.2, 115),
    ("Hummus",                  "", "other", 30, "g",  66,  1.9,  5.8,  4.3, 1.4,  0.6, 152),
    ("Balsamic Vinegar",        "", "other", 15, "ml",  21,  0.1,  4.3,  0.0, 0.0,  3.8,   4),
    ("Apple Cider Vinegar",     "", "other", 15, "ml",   3,  0.0,  0.1,  0.0, 0.0,  0.1,   1),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    inserted = 0
    skipped = 0

    for row in INGREDIENTS:
        name, brand, category, serving_size, serving_unit, cal, pro, carb, fat, fiber, sugar, sodium = row
        existing = conn.execute("SELECT id FROM ingredients WHERE name=? AND brand=?", (name, brand)).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute("""
            INSERT INTO ingredients
              (name,brand,category,serving_size,serving_unit,calories,protein,carbs,fat,fiber,sugar,sodium)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (name, brand, category, serving_size, serving_unit, cal, pro, carb, fat, fiber, sugar, sodium))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Done — {inserted} inserted, {skipped} already existed")

if __name__ == "__main__":
    seed()
