"""Builds a packing list for a trip."""

from dataclasses import dataclass, field


@dataclass
class Trip:
    destination: str
    days: int
    items: list[str] = field(default_factory=list)

    def add(self, item: str) -> None:
        self.items.append(item)

    def summary(self) -> str:
        return f"{self.destination}: {self.days} days, {len(self.items)} items"


def plan(destination: str, days: int) -> Trip:
    trip = Trip(destination, days)
    for item in ("boots", "rain jacket", "headlamp"):
        trip.add(item)
    if days > 2:
        trip.add("stove")
    return trip
