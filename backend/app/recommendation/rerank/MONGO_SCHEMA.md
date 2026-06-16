# Mongo Schema

## User Profiles

Collection: `Users`

Lookup:

```python
{"user_id": user_id}
```

Preference maps must use count-based values:

```json
{
  "Ryokan": {
    "count": 27,
    "last_interaction": "2026-06-09"
  }
}
```

Decimal score maps are not used.

## Session Context

`Users` should not store `session_context`. Session/search intent fields such as `destination`, `number_of_guests`, `session_price_range`, `session_trip_types`, and `session_room_views` are passed in the rerank request through `options.session_context`.

## Bookings

Collection: `Booking`

```json
{
  "booking_id": "bk_0001",
  "user_id": "user_004",
  "hotel_id": 47218637,
  "hotel_name": "Nhà Sun (The Sun House)",
  "booked_at": "2025-05-23T09:56:00Z"
}
```

Trend counts prefer `booked_at` and also accept legacy `booking_date`. If `status` is absent, the booking is treated as usable history.
