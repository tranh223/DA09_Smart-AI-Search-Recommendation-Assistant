## DA10 Hotel List API

### Endpoint

GET https://supabase-ota-travel.onrender.com/api/hotels

### Purpose

Retrieve hotel list from DA10 PostgreSQL API.  
This endpoint supports optional filters and pagination.  
If no filter is provided, call with `page` and `limit` to crawl hotels page by page.

### Auth

All endpoints except `/health` require header:

X-API-Key: <token>

### Query Parameters

| Param | Type | Required | Description |
|---|---|---|---|
| city | string | No | Filter by city, e.g. `Da Nang` |
| area | string | No | Filter by area |
| country | string | No | Filter by country |
| property_type | string | No | Filter by property type |
| accommodation_type | string | No | Filter by accommodation type |
| star_rating_min | number | No | Minimum star rating, 0–5 |
| star_rating_max | number | No | Maximum star rating, 0–5 |
| review_score_min | number | No | Minimum review score, 0–10 |
| is_luxury | boolean | No | Filter luxury hotels |
| price_min | number | No | Minimum price |
| price_max | number | No | Maximum price |
| amenities | string | No | Comma-separated amenities, e.g. `pool,wifi,kids_club` |
| suitable_for | string | No | Comma-separated tags, e.g. `family,couple` |
| nearby_place_name | string | No | Nearby place name |
| distance_max_km | number | No | Max distance in km |
| sort_by | string | No | One of: `id:asc`, `review_score:desc`, `star_rating:desc`, `price:asc`, `price:desc`, `distance:asc` |
| page | integer | Yes | Page number, starts from 1 |
| limit | integer | Yes | Page size, 1–100 |

### Example Request

GET /api/hotels?is_luxury=true&page=1&limit=5

### Full Crawl Logic

To load all hotels:

1. Start with `page=1`, `limit=100`.
2. Call `/api/hotels?page={page}&limit=100`.
3. Save raw response.
4. Increase page until response has no items.

Pseudo:

```python
page = 1
limit = 100

while True:
    data = client.get("/api/hotels", params={"page": page, "limit": limit})

    items = data.get("items", data if isinstance(data, list) else [])

    if not items:
        break

    save_raw(items)
    page += 1