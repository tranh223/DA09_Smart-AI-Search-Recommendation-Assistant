api: GET /api/hotels/{hotel_id}

purpose:
  Retrieve complete hotel information by hotel_id.
  Returns full hotel detail and all related entities linked to the hotel.

when_to_use:
  - User asks detailed information about a hotel.
  - User already has hotel_id.
  - Need raw hotel data for RAG context building.

examples:
  - Thông tin chi tiết khách sạn.
  - Khách sạn này có những tiện ích gì?
  - Khách sạn thuộc loại nào?
  - Khách sạn nằm ở đâu?

input:
  hotel_id: integer

output:
  raw hotel detail JSON