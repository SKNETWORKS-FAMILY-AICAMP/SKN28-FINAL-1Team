from django.urls import path

from apps.style_calendar.views import (
    CalendarEntryByDateView,
    CalendarEntryDetailView,
    CalendarEntryListView,
    CalendarWardrobeCreateView,
)

app_name = "style_calendar"

urlpatterns = [
    path(
        "calendars/wardrobe/",
        CalendarWardrobeCreateView.as_view(),
        name="calendar-wardrobe-create",
    ),
    path("calendars/", CalendarEntryListView.as_view(), name="calendar-list"),
    path(
        "calendars/by-date/",
        CalendarEntryByDateView.as_view(),
        name="calendar-by-date",
    ),
    path(
        "calendars/<uuid:calendar_id>/",
        CalendarEntryDetailView.as_view(),
        name="calendar-detail",
    ),
]
