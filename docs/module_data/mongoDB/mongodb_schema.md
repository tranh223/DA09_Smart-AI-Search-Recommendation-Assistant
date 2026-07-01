# MongoDB Schema

Collection: Users
{
  "user_id": "string",
  "name": "string | null",

  "long_term_profile": {
    "nationality": "vietnamese | foreign | null",
    "age_group": "under_25 | 25_35 | over_35 | null",
    "current_workplace": "string | null",
    "traveler_type": {
      "explorer": "positive decimal number",
      "comfort_seeker": "positive decimal number",
      "planner": "positive decimal number",
      "spontaneous": "positive decimal number"
    },

    "long_term_trip_types": {
      "solo": "positive decimal number",
      "tourist": "positive decimal number",
      "business": "positive decimal number",
      "family": "positive decimal number",
      "couple": "positive decimal number",
      "group": "positive decimal number"
    },
    "long_term_budget_levels": {
      "low": "positive decimal number",
      "medium": "positive decimal number",
      "high": "positive decimal number"
    },
    "long_term_price_range": {
      "min": "number | null",
      "max": "number | null",
      "currency": "VND | null"
    },
    "long_term_preference_tags": {
      "luxury": "positive decimal number",
      "comfort": "positive decimal number",
      "quiet": "positive decimal number",
      "privacy": "positive decimal number",
      "unique": "positive decimal number",
      "safe": "positive decimal number",
      "lively": "positive decimal number"
    },
    "long_term_hotel_types": {
      "hotel": "positive decimal number",
      "homestay": "positive decimal number",
      "guesthouse": "positive decimal number",
      "hostel": "positive decimal number",
      "resort": "positive decimal number",
      "villa": "positive decimal number",
      "boutique_hotel": "positive decimal number",
      "budget_hotel": "positive decimal number",
      "premium_hotel": "positive decimal number",
      "luxury_hotel": "positive decimal number"
    },
    "long_term_amenities": {
      "pool": "positive decimal number",
      "wifi": "positive decimal number",
      "spa": "positive decimal number",
      "breakfast": "positive decimal number",
      "bar": "positive decimal number",
      "parking": "positive decimal number",
      "elevator": "positive decimal number",
      "kids_club": "positive decimal number",
      "shuttle_service": "positive decimal number",
      "pet_friendly": "positive decimal number",
      "soundproof": "positive decimal number"
    },
    "long_term_negative_preferences": {
      "avoid_hotel_types": {
        "string": "negative decimal number"
      },
      "avoid_amenities": {
        "string": "negative decimal number"
      },
      "avoid_tags": {
        "string": "negative decimal number"
      },
      "avoid_nearby_places": {
        "string": "negative decimal number"
      },
      "avoid_locations": {
        "string": "negative decimal number"
      }
    }
  },

  "session_context": {
    "destination": "string | null",
    "current_location": "string | null",
    "nearby_place": "string | null",
    "number_of_guests": "number | null",
    "has_pet": "boolean | null",
    "has_children": "boolean | null",
    "check_in": "datetime | null",
    "check_out": "datetime | null",

    "session_trip_types": {
      "solo": "positive decimal number",
      "tourist": "positive decimal number",
      "business": "positive decimal number",
      "family": "positive decimal number",
      "couple": "positive decimal number",
      "group": "positive decimal number"
    },
    "session_budget_levels": {
      "low": "positive decimal number",
      "medium": "positive decimal number",
      "high": "positive decimal number"
    },
    "session_price_range": {
      "min": "number | null",
      "max": "number | null",
      "currency": "VND | null"
    },
    "session_preference_tags": {
      "luxury": "positive decimal number",
      "comfort": "positive decimal number",
      "quiet": "positive decimal number",
      "privacy": "positive decimal number",
      "unique": "positive decimal number",
      "safe": "positive decimal number",
      "lively": "positive decimal number",
      "near_attraction": "positive decimal number",
      "near_beach": "positive decimal number",
      "city_center": "positive decimal number",
      "fast_checkin": "positive decimal number",
      "pet_friendly": "positive decimal number"
    },
    "session_hotel_types": {
      "hotel": "positive decimal number",
      "homestay": "positive decimal number",
      "guesthouse": "positive decimal number",
      "hostel": "positive decimal number",
      "resort": "positive decimal number",
      "villa": "positive decimal number",
      "boutique_hotel": "positive decimal number",
      "budget_hotel": "positive decimal number",
      "premium_hotel": "positive decimal number",
      "luxury_hotel": "positive decimal number"
    },
    "session_amenities": {
      "pool": "positive decimal number",
      "wifi": "positive decimal number",
      "spa": "positive decimal number",
      "breakfast": "positive decimal number",
      "bar": "positive decimal number",
      "parking": "positive decimal number",
      "elevator": "positive decimal number",
      "kids_club": "positive decimal number",
      "shuttle_service": "positive decimal number",
      "pet_friendly": "positive decimal number",
      "soundproof": "positive decimal number",
      "smoke": "positive decimal number"
    },
    "session_negative_preferences": {
      "avoid_hotel_types": {
        "string": "negative decimal number"
      },
      "avoid_amenities": {
        "string": "negative decimal number"
      },
      "avoid_tags": {
        "string": "negative decimal number"
      },
      "avoid_nearby_places": {
        "string": "negative decimal number"
      },
      "avoid_locations": {
        "string": "negative decimal number"
      }
    }
  }
}

Collection Summary:
{
    "id": "Unique identifier for each user",
    "user_id": "Unique identifier for the user, can be an email or a UUID",
    "content": "User's content preferences, including long-term profile and session context",
    "last_updated": "Timestamp of the last update to the user's profile"
}

Collection Session:
{
    "id": "Unique identifier for each session",
    "history": [
        { "user_query": "string", "llm_answer": "string" },
        { "user_query": "string", "llm_answer": "string" }
    ],
    "num_like": "number",
    "num_dislike": "number",
    "final_reaction": "T | F | N (True = satisfied, False = not satisfied, Neutral = no clear reaction)",
    "latency": ["number (ms) - latency per turn, aligned with history index"],
    "ttft": ["number (ms) - time to first token per turn, aligned with history index"]
}

Collection Eval:
{
    "id": "Unique identifier for each evaluation record",
    "date": "datetime (chi co data vao cac ngay Chu Nhat / Sunday)",
    "csat": ["number - customer satisfaction scores in the period"],
    "ragas": {
        "faithfulness": "number",
        "answer_relevance": "number",
        "context_precision": "number",
        "context_recall": "number"
    },
    "latency": ["number (ms)"],
    "ttft": ["number (ms)"]
}

Collection Booking:
{
    "booking_id": "string - Unique identifier for each booking (vd: bk_0001)",
    "user_id": "string - email hoac UUID, tham chieu Users.user_id",
    "hotel_id": "number - tham chieu hotels.hotel_id",
    "hotel_name": "string - ten khach san (denormalized de tien tra cuu)",
    "booked_at": "datetime - thoi diem dat phong"
}

---

# Mock data (vi du)

## Summary (mock)
```json
{
  "id": "sum_001",
  "user_id": "minh.ngtr.dev@gmail.com",
  "content": "Khach thich resort 5 sao gan bien o Nha Trang/Phu Quoc, di cung gia dinh co tre nho, ngan sach trung binh-cao, uu tien ho boi va kids club, tranh khach san on ao.",
  "last_updated": "2026-06-04T09:30:00Z"
}
```

## Session (mock)
```json
{
  "id": "sess_20260604_001",
  "history": [
    {
      "user_query": "resort gan bien o Nha Trang cho gia dinh co tre nho",
      "llm_answer": "Minh goi y 3 resort phu hop gia dinh gan bien Nha Trang: Vinpearl Resort & Spa Nha Trang Bay (co kids club, ho boi), Vinpearl Beachfront Nha Trang, Movenpick Resort Cam Ranh."
    },
    {
      "user_query": "cai nao co ho boi tre em",
      "llm_answer": "Trong 3 lua chon tren, Vinpearl Resort & Spa Nha Trang Bay va Movenpick Resort Cam Ranh co ho boi rieng cho tre em."
    }
  ],
  "num_like": 1,
  "num_dislike": 0,
  "final_reaction": "T",
  "latency": [820, 640],
  "ttft": [310, 240]
}
```

## Eval (mock — 2026-05-31 la Chu Nhat)
```json
{
  "id": "eval_20260531",
  "date": "2026-05-31T00:00:00Z",
  "csat": [4, 5, 3, 5, 4],
  "ragas": {
    "faithfulness": 0.92,
    "answer_relevance": 0.88,
    "context_precision": 0.85,
    "context_recall": 0.80
  },
  "latency": [780, 910, 670, 1020, 850],
  "ttft": [290, 330, 250, 360, 300]
}
```

## Booking (mock)
> Bo 50 booking mau day du o `data/bookings/bookings_mock.json`.
> user_id lay tu mock_user_profiles (user_001..user_050);
> hotel_id + hotel_name lay dung tu `public.hotels` trong data.sql.

```json
{
  "booking_id": "bk_0001",
  "user_id": "user_004",
  "hotel_id": 47218637,
  "hotel_name": "Nhà Sun (The Sun House)",
  "booked_at": "2025-05-23T09:56:00Z"
}
```

```json
{
  "booking_id": "bk_0002",
  "user_id": "user_030",
  "hotel_id": 63942689,
  "hotel_name": "Khách Sạn Đông Nam Á 2 (Khach San Đong Nam A 2)",
  "booked_at": "2025-06-05T09:56:00Z"
}
```