# Рисунок 2 — Диаграмма контейнеров в нотации C4 (уровень C2)

Вставьте код ниже в онлайн-редактор PlantUML (https://www.plantuml.com/plantuml).

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

title Диаграмма контейнеров системы IndiGuide (C4, уровень 2)

Person(tourist, "Турист", "Пользователь сервиса")

System_Boundary(indiguide, "IndiGuide") {
    Container(spa, "Клиентское приложение", "Vue 3, TypeScript, Vite, Pinia, Tailwind CSS", "Одностраничное веб-приложение (SPA): карта, форма создания маршрута, режим прогулки, профиль предпочтений")
    Container(api, "Серверное приложение (API)", "Python 3.12, FastAPI, SQLAlchemy (async)", "REST API: аутентификация, генерация маршрута, обучение предпочтений, публикация маршрутов")
    ContainerDb(db, "База данных", "PostgreSQL 15 + PostGIS", "Учётные записи, кэш POI, маршруты, точки, предпочтения и история взаимодействий")
}

System_Ext(otm, "OpenTripMap API", "Справочник достопримечательностей")
System_Ext(osrm, "OSRM API", "Построение пеших маршрутов")
System_Ext(osm, "OpenStreetMap API", "Часы работы объектов")
System_Ext(yandex, "Yandex Maps JS API", "Отображение карты")

Rel(tourist, spa, "Работает с интерфейсом", "HTTPS")
Rel(spa, yandex, "Загружает карту и рисует маршрут", "HTTPS")
Rel(spa, api, "Вызывает методы API", "JSON / HTTPS")
Rel(api, db, "Читает и записывает данные", "asyncpg")
Rel(api, otm, "Запрашивает POI", "HTTPS")
Rel(api, osrm, "Запрашивает геометрию маршрута", "HTTPS")
Rel(api, osm, "Запрашивает часы работы", "HTTPS")

@enduml
```
