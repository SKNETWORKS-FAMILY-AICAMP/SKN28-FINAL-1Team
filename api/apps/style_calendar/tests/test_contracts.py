from unittest import TestCase

from apps.style_calendar.contracts import (
    CALENDAR_CALLBACK_SCHEMA_VERSION,
    CALENDAR_JOB_SCHEMA_VERSION,
    CALENDAR_RESULT_SCHEMA_VERSION,
    CalendarItemInternalStatus,
    CalendarStatus,
)


class CalendarContractTests(TestCase):
    def test_calendar_status_does_not_include_partial(self) -> None:
        self.assertEqual(
            {status.value for status in CalendarStatus},
            {"REGISTERED", "PROCESSING", "COMPLETED", "FAILED"},
        )

    def test_calendar_item_status_excludes_matching_states(self) -> None:
        self.assertEqual(
            {status.value for status in CalendarItemInternalStatus},
            {"SELECTED", "EXTRACTED", "FAILED"},
        )

    def test_contract_schema_versions_are_calendar_specific(self) -> None:
        self.assertEqual(CALENDAR_JOB_SCHEMA_VERSION, "calendar-job.v1")
        self.assertEqual(CALENDAR_CALLBACK_SCHEMA_VERSION, "calendar-callback.v1")
        self.assertEqual(CALENDAR_RESULT_SCHEMA_VERSION, "calendar-result.v1")
