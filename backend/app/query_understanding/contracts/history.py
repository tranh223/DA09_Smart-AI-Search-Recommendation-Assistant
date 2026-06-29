from dataclasses import dataclass, field


@dataclass(slots=True)
class UserHistoryRequest:
    user_id: str


@dataclass(slots=True)
class UserHistoryResponse:
    booked_hotels: list[str] = field(default_factory=list)
    liked_hotels: list[str] = field(default_factory=list)
    disliked_hotels: list[str] = field(default_factory=list)
