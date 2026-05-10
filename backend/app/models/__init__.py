# Import all models here so Alembic and SQLAlchemy see the full metadata
from app.models.user import User
from app.models.poi import POI
from app.models.route import Route, RouteWaypoint, RouteStatus
from app.models.preferences import UserPreference, POIInteraction

__all__ = ["User", "POI", "Route", "RouteWaypoint", "RouteStatus", "UserPreference", "POIInteraction"]
