from app.database import SessionLocal
from app.crud import upsert_car, get_cars, search_cars
from app.schemas import SearchFilters


def _seed(db, **over):
    base = dict(title="VW Golf", brand="volkswagen", model="golf", year=2018,
                price=65000, currency="PLN", mileage=120000, fuel_type="petrol",
                transmission="manual", location="Warszawa", source="otomoto",
                url="u1", image_url="i")
    base.update(over)
    return upsert_car(db, base)


def test_upsert_is_idempotent_on_source_url():
    db = SessionLocal()
    try:
        _seed(db, url="dup", price=1000)
        _seed(db, url="dup", price=2000)  # same source+url -> update
        cars, total = get_cars(db)
        assert total == 1
        assert float(cars[0].price) == 2000.0
    finally:
        db.close()


def test_search_filters():
    db = SessionLocal()
    try:
        _seed(db, url="a", brand="volkswagen", price=50000, year=2020, mileage=10000)
        _seed(db, url="b", brand="audi", price=150000, year=2015, mileage=200000)
        cars, total = search_cars(db, SearchFilters(brand="volkswagen", price_max=100000))
        assert total == 1
        assert cars[0].brand == "volkswagen"
    finally:
        db.close()
