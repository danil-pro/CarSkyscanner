CLAUDE CODE PROMPT — Car Aggregator MVP (Poland)
ROLE

You are a senior full-stack engineer. Build a production-ready MVP backend + frontend for a car listing aggregator.

GOAL

Build a minimal working product that:

Lets users search cars via filters
Aggregates listings from multiple sources (Otomoto, OLX, Facebook Marketplace partial)
Displays unified results in one interface
STRICT MVP SCOPE

Do NOT add anything beyond this scope.

Required features:
1. Frontend (Web App)
Simple search form with filters:
brand
model
year_min / year_max
price_min / price_max
mileage_max
fuel_type
transmission
Results page:
list of cars
image
price
year
mileage
source badge (Otomoto / OLX / FB)
button → open original listing

No authentication.

2. Backend API (FastAPI)

Implement:

POST /search → returns filtered cars
GET /cars → returns all cars from DB
POST /scrape/run → triggers scraping manually (for dev)
3. Database (PostgreSQL)

Create table:

cars:

id (uuid)
title
brand
model
year
price
currency
mileage
fuel_type
transmission
location
source
url
image_url
created_at

Add indexes for:

brand
model
price
year
4. Scrapers (IMPORTANT)

Create modular scrapers:

scrapers/otomoto.py
scrapers/olx.py
scrapers/facebook.py (stub if blocked)

Each scraper must return normalized JSON in this format:

{
  "title": "",
  "brand": "",
  "model": "",
  "year": 0,
  "price": 0,
  "mileage": 0,
  "fuel_type": "",
  "transmission": "",
  "location": "",
  "source": "",
  "url": "",
  "image_url": ""
}

Use Playwright for scraping.

5. Data Pipeline

Flow:

SCRAPER → NORMALIZER → DATABASE → API → FRONTEND

6. Search Logic

Implement simple filtering in SQL:

price range
year range
mileage
brand/model exact match or LIKE

NO ML, NO AI, NO ranking.

7. Tech Stack

Backend:

Python 3.11
FastAPI
SQLAlchemy
PostgreSQL
Playwright

Frontend:

Next.js (React)
TailwindCSS
8. Architecture Constraints
Keep monorepo structure:
/backend
/frontend
/scrapers
/docker
Must run with docker-compose
9. Docker

Provide:

backend container
frontend container
postgres container

One command startup:

docker-compose up --build
10. Output Requirements

After generating project:

Provide full file structure
Ensure backend runs without errors
Ensure frontend connects to API
Provide sample seed data script
Provide scraping demo script
IMPORTANT CONSTRAINTS
No authentication system
No payments
No AI features
No recommendations
No complex architecture
MVP only
SUCCESS CRITERIA

System is successful if:

user can open frontend
set filters
see cars from DB
run scraper manually
see new listings appear
END

Build the simplest working version possible that satisfies the above requirements.

