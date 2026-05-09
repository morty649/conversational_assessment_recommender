import json

from app.models.catalog import CatalogItem
from app.core.config import settings

def load_catalog() -> list[CatalogItem]:

    with open(settings.CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = []

    for row in data:
        items.append(
            CatalogItem(
                entity_id=str(row.get("entity_id")),
                name=row.get("name", ""),
                link=row.get("link", ""),
                description=row.get("description", ""),
                job_levels=row.get("job_levels", []),
                languages=row.get("languages", []),
                duration=row.get("duration", ""),
                remote=row.get("remote", ""),
                adaptive=row.get("adaptive", ""),
                keys=row.get("keys", []),
            )
        )

    return items