import random
from app.database import init_db, SessionLocal
from app.crud import upsert_car

BRANDS = {
    "volkswagen": ["golf", "passat", "tiguan"],
    "audi": ["a4", "a6", "q5"],
    "bmw": ["320i", "x3", "520"],
    "toyota": ["corolla", "yaris", "rav4"],
    "skoda": ["octavia", "superb", "kodiaq"],
}
FUELS = ["petrol", "diesel", "hybrid", "electric", "lpg"]
TRANS = ["manual", "automatic"]
CITIES = ["Warszawa", "Kraków", "Wrocław", "Poznań", "Gdańsk", "Łódź"]
SOURCES = ["otomoto", "olx", "facebook"]


def build_seed(n=40) -> list[dict]:
    out = []
    for i in range(n):
        brand = random.choice(list(BRANDS))
        model = random.choice(BRANDS[brand])
        source = SOURCES[i % 3]
        out.append({
            "title": f"{brand.title()} {model.title()}",
            "brand": brand, "model": model,
            "year": random.randint(2010, 2023),
            "price": random.randint(15000, 180000),
            "currency": "PLN",
            "mileage": random.randint(10000, 300000),
            "fuel_type": random.choice(FUELS),
            "transmission": random.choice(TRANS),
            "location": random.choice(CITIES),
            "source": source,
            "url": f"https://example.{source}/listing/{i}",
            "image_url": f"https://picsum.photos/seed/{brand}{i}/400/300",
        })
    return out


def main():
    init_db()
    db = SessionLocal()
    try:
        for item in build_seed():
            upsert_car(db, item)
        print(f"Seeded {len(build_seed())} cars")
    finally:
        db.close()


if __name__ == "__main__":
    main()
