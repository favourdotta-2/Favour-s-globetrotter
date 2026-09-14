from datetime import date
from typing import Any

from app.repositories.json_store import JsonStore


def list_destinations(
    store: JsonStore,
    query: str = "",
    tag: str = "",
    mood: str = "",
    max_cost: int | None = None,
    continent: str = "",
) -> list[dict[str, Any]]:
    destinations = store.read("destinations")
    q = query.strip().lower()
    wanted_tag = tag.strip().lower()
    wanted_mood = mood.strip().lower()

    results: list[dict[str, Any]] = []
    for destination in destinations:
        searchable = " ".join(
            [
                destination.get("name", ""),
                destination.get("city", ""),
                destination.get("country", ""),
                destination.get("description", ""),
            ]
        ).lower()
        tags = [item.lower() for item in destination.get("tags", [])]
        moods = [item.lower() for item in destination.get("moods", [])]

        if q and q not in searchable:
            continue
        if wanted_tag and wanted_tag not in tags:
            continue
        if wanted_mood and wanted_mood not in moods:
            continue
        if max_cost is not None and destination.get("avg_cost_per_day", 0) > max_cost:
            continue
        if continent and continent.lower() != destination.get("continent", "Africa").lower():
            continue
        results.append(destination)
    return results


def recommendations_for(
    user: dict[str, Any], store: JsonStore, trips: list[dict[str, Any]],
    popularity: dict[str, int], limit: int = 6,
) -> list[dict[str, Any]]:
    preferences = {preference.lower() for preference in user.get("preferences", [])}
    past_destinations = [
        destination for trip in trips
        if trip.get("end_date") and trip["end_date"] < date.today().isoformat()
        for destination in trip.get("destinations", [])
    ]
    past_tags = {tag.lower() for destination in past_destinations for tag in destination["tags"]}
    scored: list[tuple[int, dict[str, Any]]] = []
    for destination in store.read("destinations"):
        tags = {tag.lower() for tag in destination.get("tags", [])}
        moods = {mood.lower() for mood in destination.get("moods", [])}
        score = (
            3 * len(preferences.intersection(tags.union(moods)))
            + len(past_tags.intersection(tags))
            + min(popularity.get(destination["id"], 0), 2)
        )
        scored.append((score, destination))
    scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    return [{**destination, "match_score": score} for score, destination in scored[:limit]]


def map_locations(store: JsonStore) -> list[dict[str, Any]]:
    return [
        {
            "id": destination["id"],
            "name": destination["name"],
            "city": destination["city"],
            "lat": destination["lat"],
            "lng": destination["lng"],
            "image": destination["image"],
        }
        for destination in store.read("destinations")
    ]
