from datetime import datetime
from app.database import SessionLocal
from app.models import Car


def test_car_can_be_inserted_and_queried():
    db = SessionLocal()
    try:
        db.query(Car).delete()
        car = Car(
            title="VW Golf", brand="volkswagen", model="golf", year=2018,
            price=65000, currency="PLN", mileage=120000, fuel_type="petrol",
            transmission="manual", location="Warszawa", source="otomoto",
            url="https://otomoto.pl/x", image_url="https://img/x.jpg",
        )
        db.add(car); db.commit(); db.refresh(car)
        assert car.id is not None
        assert isinstance(car.created_at, datetime)
        rows = db.query(Car).all()
        assert len(rows) == 1
        assert rows[0].brand == "volkswagen"
    finally:
        db.close()
