# Рисунок 1 — Контекстная диаграмма в нотации C4 (уровень C1)

Вставьте код ниже в онлайн-редактор PlantUML (https://www.plantuml.com/plantuml).
Полученное изображение поместите на место «Рисунка 1» в тексте ВКР.

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml

title Контекстная диаграмма системы IndiGuide (C4, уровень 1)

Person(tourist, "Турист", "Пользователь, желающий построить персональный пеший маршрут по достопримечательностям города")

System(indiguide, "IndiGuide", "Веб-сервис генерации и прохождения персонализированных пеших туристических маршрутов")

System_Ext(otm, "OpenTripMap API", "Внешний справочник достопримечательностей (POI): координаты, категории, рейтинг, описания")
System_Ext(osrm, "OSRM API", "Сервис построения пешеходных маршрутов по дорожному графу OpenStreetMap")
System_Ext(osm, "OpenStreetMap API", "Источник часов работы объектов (тег opening_hours)")
System_Ext(yandex, "Yandex Maps JS API", "Картографический сервис для отображения карты и маршрута в браузере")

Rel(tourist, indiguide, "Создаёт и проходит маршруты, оценивает места", "HTTPS")
Rel(indiguide, otm, "Запрашивает достопримечательности в радиусе", "HTTPS / REST")
Rel(indiguide, osrm, "Запрашивает пешеходные маршруты между точками", "HTTPS / REST")
Rel(indiguide, osm, "Запрашивает часы работы объектов", "HTTPS / REST")
Rel(tourist, yandex, "Отображает карту и геометрию маршрута", "HTTPS")

@enduml
```
