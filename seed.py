"""Fill the database with demo data:  python seed.py"""
import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

import config
from app import app, init_db, run, q

random.seed(7)
PEOPLE = [
    ("Admin", "admin@reusematch.local", "admin123", "individual", 1, "Campus"),
    ("Aarav Sharma", "aarav@example.com", "demo123", "individual", 0, "Hostel Block A"),
    ("Simran Kaur", "simran@example.com", "demo123", "individual", 0, "Hostel Block C"),
    ("Hope Foundation", "hope@example.com", "demo123", "organization", 0, "Kharar"),
    ("Library Club", "library@example.com", "demo123", "organization", 0, "Campus Library"),
]
ITEMS = [
    ("Study table with drawer", "Wooden study table, small scratch on top", "furniture", "good", 1),
    ("Plastic chairs", "Set of sturdy white plastic chairs", "furniture", "good", 12),
    ("Old laptop", "Core i3, works, battery weak, charger included", "electronics", "fair", 1),
    ("Computer monitor 19 inch", "VGA monitor in working condition", "electronics", "good", 3),
    ("Semester textbooks", "MCA first semester books and notes", "books", "like_new", 15),
    ("Novels collection", "Mixed fiction paperbacks", "books", "good", 25),
    ("Wooden planks", "Offcuts from hostel renovation", "materials", "good", 10),
    ("Bucket and storage crates", "Plastic crates, stackable", "materials", "fair", 6),
    ("Table fan", "Works at all speeds", "electronics", "good", 2),
    ("Bookshelf", "Five-shelf bookcase, easy to carry", "furniture", "like_new", 1),
]
NEEDS = [
    ("Chairs for tuition room", "Need plastic or wooden chairs for children", "furniture", 15, 3, "fair"),
    ("Books for community library", "Textbooks and novels for students", "books", 40, 2, "good"),
    ("Computers for training lab", "Old laptop or monitor for digital literacy classes", "electronics", 4, 2, "fair"),
]

with app.app_context():
    init_db()
    if q("SELECT 1 FROM users LIMIT 1", one=True):
        raise SystemExit("Database already has data. Delete reusematch.db to reseed.")
    ids = []
    for name, email, pw, typ, adm, area in PEOPLE:
        ids.append(run("INSERT INTO users(name,email,password_hash,account_type,is_admin,lat,lng,area) VALUES(?,?,?,?,?,?,?,?)",
                       (name, email, generate_password_hash(pw), typ, adm,
                        config.DEFAULT_LAT + random.uniform(-.04, .04), config.DEFAULT_LNG + random.uniform(-.04, .04), area)))
    donors = ids[1:3]
    for i, (t, d, c, cond, qty) in enumerate(ITEMS):
        status = "collected" if i in (4, 6, 8) else "available"
        when = (datetime.now() - timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d %H:%M:%S")
        run("INSERT INTO items(donor_id,title,description,category,ai_category,ai_confidence,condition,quantity,unit_weight_kg,"
            "lat,lng,address,status,collected_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (random.choice(donors), t, d, c, c if i % 4 else "other", 0.6, cond, qty, config.UNIT_WEIGHT_KG[c],
             config.DEFAULT_LAT + random.uniform(-.04, .04), config.DEFAULT_LNG + random.uniform(-.04, .04),
             "Near campus gate", status, when if status == "collected" else None, when))
    for (t, d, c, qty, urg, mc), uid in zip(NEEDS, [ids[3], ids[4], ids[3]]):
        run("INSERT INTO needs(user_id,title,description,category,quantity,urgency,min_condition) VALUES(?,?,?,?,?,?,?)",
            (uid, t, d, c, qty, urg, mc))
print("Seeded. Admin: admin@reusematch.local / admin123 | Demo user: aarav@example.com / demo123 | Recipient: hope@example.com / demo123")
