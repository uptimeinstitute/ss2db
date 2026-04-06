# ABOUTME: Tests for workspace processing functionality.
# ABOUTME: Covers sheet collection, concurrent processing, error handling, and output directory structure.

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ss2db.smartsheet.client import RateLimiter
from ss2db.smartsheet.workspace import (
    WorkspaceProcessor,
    SheetResult,
    collect_sheets_from_workspace,
)


# --- Sample workspace API responses for tests ---

WORKSPACE_FLAT = {
    "id": 1111111111111111,
    "name": "Test Workspace",
    "sheets": [
        {"id": 1001, "name": "Sheet A", "permalink": "https://app.smartsheet.com/sheets/a"},
        {"id": 1002, "name": "Sheet B", "permalink": "https://app.smartsheet.com/sheets/b"},
    ],
    "folders": [],
}

WORKSPACE_NESTED = {
    "id": 2222222222222222,
    "name": "Nested Workspace",
    "sheets": [
        {"id": 2001, "name": "Top Sheet", "permalink": "https://app.smartsheet.com/sheets/top"},
    ],
    "folders": [
        {
            "id": 3001,
            "name": "Folder A",
            "sheets": [
                {"id": 2002, "name": "Folder A Sheet", "permalink": None},
            ],
            "folders": [
                {
                    "id": 3002,
                    "name": "Sub-Folder",
                    "sheets": [
                        {"id": 2003, "name": "Deep Sheet", "permalink": None},
                    ],
                    "folders": [],
                }
            ],
        },
        {
            "id": 3003,
            "name": "Folder B",
            "sheets": [
                {"id": 2004, "name": "Folder B Sheet", "permalink": None},
            ],
            "folders": [],
        },
    ],
}

WORKSPACE_EMPTY = {
    "id": 3333333333333333,
    "name": "Empty Workspace",
    "sheets": [],
    "folders": [],
}

WORKSPACE_NO_SHEETS_IN_FOLDERS = {
    "id": 4444444444444444,
    "name": "Folders Only",
    "sheets": [],
    "folders": [
        {
            "id": 5001,
            "name": "Empty Folder",
            "sheets": [],
            "folders": [],
        }
    ],
}


class TestCollectSheetsFromWorkspace:
    """Tests for the collect_sheets_from_workspace helper function."""

    def test_flat_workspace(self):
        """Collect sheets from a workspace with no folders."""
        sheets = collect_sheets_from_workspace(WORKSPACE_FLAT)

        assert len(sheets) == 2
        assert sheets[0]["id"] == "1001"
        assert sheets[0]["name"] == "Sheet A"
        assert sheets[1]["id"] == "1002"
        assert sheets[1]["name"] == "Sheet B"

    def test_nested_workspace(self):
        """Collect sheets from a workspace with nested folders and sub-folders."""
        sheets = collect_sheets_from_workspace(WORKSPACE_NESTED)

        assert len(sheets) == 4
        ids = [s["id"] for s in sheets]
        assert "2001" in ids  # top-level
        assert "2002" in ids  # folder A
        assert "2003" in ids  # sub-folder
        assert "2004" in ids  # folder B

    def test_empty_workspace(self):
        """Empty workspace returns empty list."""
        sheets = collect_sheets_from_workspace(WORKSPACE_EMPTY)
        assert sheets == []

    def test_folders_with_no_sheets(self):
        """Workspace with folders but no sheets returns empty list."""
        sheets = collect_sheets_from_workspace(WORKSPACE_NO_SHEETS_IN_FOLDERS)
        assert sheets == []

    def test_sheet_ids_are_strings(self):
        """Sheet IDs should be converted to strings."""
        sheets = collect_sheets_from_workspace(WORKSPACE_FLAT)
        for sheet in sheets:
            assert isinstance(sheet["id"], str)

    def test_missing_name_uses_fallback(self):
        """Sheets without a name field get a fallback name."""
        workspace = {
            "id": 9999,
            "name": "Test",
            "sheets": [{"id": 5001}],
            "folders": [],
        }
        sheets = collect_sheets_from_workspace(workspace)
        assert sheets[0]["name"] == "Sheet 5001"


class TestSheetResult:
    """Tests for SheetResult dataclass."""

    def test_successful_result(self):
        result = SheetResult(sheet_id="123", sheet_name="Test", success=True, duration=1.5)
        assert result.success is True
        assert result.error is None
        assert result.duration == 1.5

    def test_failed_result(self):
        result = SheetResult(
            sheet_id="123", sheet_name="Test", success=False, error="API error", duration=0.5
        )
        assert result.success is False
        assert result.error == "API error"


class TestWorkspaceProcessor:
    """Tests for WorkspaceProcessor class."""

    def _make_processor(self, max_workers=2):
        """Create a WorkspaceProcessor with mocked dependencies."""
        client = Mock()
        config_manager = Mock()
        app_config = Mock()
        app_config.output.directory = "/tmp/test_exports"
        logger = Mock()

        processor = WorkspaceProcessor(
            client=client,
            config_manager=config_manager,
            app_config=app_config,
            max_workers=max_workers,
            logger=logger,
        )
        return processor

    def test_process_workspace_discovers_sheets(self):
        """Workspace processor fetches and lists all sheets."""
        processor = self._make_processor()
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        with patch.object(processor, "_process_single_sheet") as mock_process:
            mock_process.return_value = SheetResult(
                sheet_id="1001", sheet_name="Sheet A", success=True, duration=1.0
            )
            results = processor.process_workspace(workspace_id="1111111111111111")

        processor.client.get_workspace.assert_called_once_with("1111111111111111")
        assert mock_process.call_count == 2

    def test_process_workspace_empty(self):
        """Empty workspace returns empty results."""
        processor = self._make_processor()
        processor.client.get_workspace.return_value = WORKSPACE_EMPTY

        results = processor.process_workspace(workspace_id="3333333333333333")

        assert results == []

    @patch("ss2db.main.execute_phases")
    def test_process_workspace_all_succeed(self, mock_execute):
        """All sheets succeed — results reflect that."""
        mock_execute.return_value = True

        processor = self._make_processor()
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        results = processor.process_workspace(workspace_id="1111111111111111")

        assert len(results) == 2
        assert all(r.success for r in results)

    @patch("ss2db.main.execute_phases")
    def test_process_workspace_partial_failure(self, mock_execute):
        """One sheet fails, others succeed — continues processing."""
        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("API exploded")
            return True

        mock_execute.side_effect = side_effect

        processor = self._make_processor(max_workers=1)
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        results = processor.process_workspace(workspace_id="1111111111111111")

        assert len(results) == 2
        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(succeeded) == 1
        assert len(failed) == 1
        assert "API exploded" in failed[0].error

    @patch("ss2db.main.execute_phases")
    def test_output_directory_structure(self, mock_execute):
        """Output directories follow {output_dir}/{workspace_id}/{sheet_id}/ pattern."""
        mock_execute.return_value = True
        captured_calls = []

        def capture_call(**kwargs):
            captured_calls.append(kwargs)
            return True

        mock_execute.side_effect = capture_call

        processor = self._make_processor()
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        results = processor.process_workspace(workspace_id="1111111111111111")

        assert len(captured_calls) == 2
        for call_kwargs in captured_calls:
            output_dir = call_kwargs["output_dir_override"]
            assert str(output_dir).startswith("/tmp/test_exports/1111111111111111/")
            # The sheet ID should be the last path component
            sheet_id = str(output_dir).split("/")[-1]
            assert sheet_id in ["1001", "1002"]

    @patch("ss2db.main.execute_phases")
    def test_shared_client_passed_to_execute_phases(self, mock_execute):
        """The shared SmartsheetClient is passed to each execute_phases call."""
        mock_execute.return_value = True
        captured_clients = []

        def capture_call(**kwargs):
            captured_clients.append(kwargs.get("smartsheet_client"))
            return True

        mock_execute.side_effect = capture_call

        processor = self._make_processor()
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        processor.process_workspace(workspace_id="1111111111111111")

        # All calls should receive the same client instance
        assert len(captured_clients) == 2
        assert all(c is processor.client for c in captured_clients)

    def test_dry_run_skips_processing(self):
        """Dry run returns results without actually processing."""
        processor = self._make_processor()
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        with patch.object(processor, "_process_single_sheet") as mock_process:
            results = processor.process_workspace(
                workspace_id="1111111111111111", dry_run=True
            )

        mock_process.assert_not_called()
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_print_summary_no_results(self):
        """Print summary handles empty results gracefully."""
        processor = self._make_processor()
        processor.print_summary([])
        processor.logger.info.assert_called()

    def test_print_summary_mixed_results(self):
        """Print summary shows correct counts for mixed results."""
        processor = self._make_processor()
        results = [
            SheetResult(sheet_id="1", sheet_name="OK Sheet", success=True, duration=1.0),
            SheetResult(
                sheet_id="2", sheet_name="Bad Sheet", success=False, error="fail", duration=0.5
            ),
        ]
        processor.print_summary(results)
        # Verify the summary line was logged with correct counts
        summary_calls = [
            str(call) for call in processor.logger.info.call_args_list
        ]
        summary_text = " ".join(summary_calls)
        assert "Succeeded: 1" in summary_text
        assert "Failed: 1" in summary_text


class TestOrganizeByDate:
    """Tests for --organize-by-date directory structure."""

    def _make_processor(self, date_prefix=None, max_workers=1):
        """Create a WorkspaceProcessor with optional date prefix."""
        client = Mock()
        config_manager = Mock()
        app_config = Mock()
        app_config.output.directory = "/tmp/test_exports"
        logger = Mock()

        processor = WorkspaceProcessor(
            client=client,
            config_manager=config_manager,
            app_config=app_config,
            max_workers=max_workers,
            logger=logger,
            date_prefix=date_prefix,
        )
        return processor

    @patch("ss2db.main.execute_phases")
    def test_workspace_output_with_date_prefix(self, mock_execute):
        """Workspace mode with date prefix: {output_dir}/{date}/{workspace_id}/{sheet_id}/"""
        mock_execute.return_value = True
        captured_calls = []

        def capture_call(**kwargs):
            captured_calls.append(kwargs)
            return True

        mock_execute.side_effect = capture_call

        processor = self._make_processor(date_prefix="2026-04-06")
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        processor.process_workspace(workspace_id="1111111111111111")

        assert len(captured_calls) == 2
        for call_kwargs in captured_calls:
            output_dir = str(call_kwargs["output_dir_override"])
            assert output_dir.startswith("/tmp/test_exports/2026-04-06/1111111111111111/")
            sheet_id = output_dir.split("/")[-1]
            assert sheet_id in ["1001", "1002"]

    @patch("ss2db.main.execute_phases")
    def test_workspace_output_without_date_prefix(self, mock_execute):
        """Workspace mode without date prefix: {output_dir}/{workspace_id}/{sheet_id}/"""
        mock_execute.return_value = True
        captured_calls = []

        def capture_call(**kwargs):
            captured_calls.append(kwargs)
            return True

        mock_execute.side_effect = capture_call

        processor = self._make_processor(date_prefix=None)
        processor.client.get_workspace.return_value = WORKSPACE_FLAT

        processor.process_workspace(workspace_id="1111111111111111")

        assert len(captured_calls) == 2
        for call_kwargs in captured_calls:
            output_dir = str(call_kwargs["output_dir_override"])
            # No date component in path
            assert "/2026-" not in output_dir
            assert output_dir.startswith("/tmp/test_exports/1111111111111111/")

    def test_date_prefix_stored_on_processor(self):
        """date_prefix is stored and accessible on the processor."""
        processor = self._make_processor(date_prefix="2026-04-06")
        assert processor.date_prefix == "2026-04-06"

        processor_none = self._make_processor(date_prefix=None)
        assert processor_none.date_prefix is None


class TestExecutePhasesDatePrefix:
    """Tests for date prefix in execute_phases (single sheet/report mode)."""

    def test_output_dir_with_date_prefix(self):
        """Single mode with date prefix builds path: {output_dir}/{date}/{resource_id}/"""
        from ss2db.main import execute_phases
        from ss2db.config import Config

        config = Config()
        config.output.directory = "/tmp/test_exports"
        config_manager = Mock()
        logger = Mock()

        # Use dry_run=True to avoid file I/O. Check the dry-run "Would save to" log messages.
        execute_phases(
            config_manager=config_manager,
            app_config=config,
            sheet_id="9999",
            report_id=None,
            table_name=None,
            db_type="postgresql",
            skip_extraction=False,
            skip_schema=True,
            skip_sql=True,
            input_data=None,
            input_schema=None,
            dry_run=True,
            logger=logger,
            date_prefix="2026-04-06",
        )

        # dry_run logs "Would extract data" and "Would save to: {path}" which includes the output dir
        all_calls = " ".join(str(c) for c in logger.info.call_args_list)
        assert "2026-04-06" in all_calls

    def test_output_dir_without_date_prefix(self):
        """Single mode without date prefix builds path: {output_dir}/{resource_id}/"""
        from ss2db.main import execute_phases
        from ss2db.config import Config

        config = Config()
        config.output.directory = "/tmp/test_exports"
        config_manager = Mock()
        logger = Mock()

        execute_phases(
            config_manager=config_manager,
            app_config=config,
            sheet_id="9999",
            report_id=None,
            table_name=None,
            db_type="postgresql",
            skip_extraction=False,
            skip_schema=True,
            skip_sql=True,
            input_data=None,
            input_schema=None,
            dry_run=True,
            logger=logger,
            date_prefix=None,
        )

        all_calls = " ".join(str(c) for c in logger.info.call_args_list)
        assert "2026-04-06" not in all_calls


class TestRateLimiterThreadSafety:
    """Tests for thread-safe RateLimiter behavior."""

    def test_concurrent_access_no_exceptions(self):
        """Multiple threads calling wait_if_needed() concurrently should not raise."""
        limiter = RateLimiter(max_requests_per_minute=100, buffer_requests=5)
        errors = []

        def worker():
            try:
                for _ in range(5):
                    limiter.wait_if_needed()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Threads raised exceptions: {errors}"

    def test_concurrent_request_count_consistency(self):
        """After concurrent access, request_times length should be consistent."""
        limiter = RateLimiter(max_requests_per_minute=200, buffer_requests=5)
        num_threads = 10
        calls_per_thread = 5
        expected_total = num_threads * calls_per_thread

        barrier = threading.Barrier(num_threads)

        def worker():
            barrier.wait()
            for _ in range(calls_per_thread):
                limiter.wait_if_needed()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # All requests should have been recorded
        assert len(limiter.request_times) == expected_total

    def test_concurrent_usage_stats(self):
        """get_current_usage() should not raise under concurrent access."""
        limiter = RateLimiter(max_requests_per_minute=200, buffer_requests=5)
        errors = []

        def writer():
            for _ in range(20):
                limiter.wait_if_needed()

        def reader():
            for _ in range(20):
                try:
                    usage = limiter.get_current_usage()
                    assert "requests_in_last_minute" in usage
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(5)]
        threads += [threading.Thread(target=reader) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Threads raised exceptions: {errors}"


class TestWorkspaceMetadata:
    """Tests for workspace metadata in schema and JSON data files."""

    def test_schema_to_dict_includes_workspace_fields(self):
        """Schema.to_dict() includes workspace_id and workspace_name when set."""
        from ss2db.smartsheet.models import SmartsheetSchema

        schema = SmartsheetSchema(
            id=1234,
            name="Test Sheet",
            columns=[],
            workspace_id="9876543210",
            workspace_name="My Workspace",
        )

        result = schema.to_dict()
        assert result["workspace_id"] == "9876543210"
        assert result["workspace_name"] == "My Workspace"

    def test_schema_to_dict_includes_processed_at(self):
        """Schema.to_dict() includes processed_at when set."""
        from datetime import datetime
        from ss2db.smartsheet.models import SmartsheetSchema

        ts = datetime(2026, 4, 6, 14, 30, 0)
        schema = SmartsheetSchema(
            id=1234,
            name="Test Sheet",
            columns=[],
            processed_at=ts,
        )

        result = schema.to_dict()
        assert result["processed_at"] == "2026-04-06T14:30:00"

    def test_schema_to_dict_omits_processed_at_when_none(self):
        """Schema.to_dict() omits processed_at when not set."""
        from ss2db.smartsheet.models import SmartsheetSchema

        schema = SmartsheetSchema(id=1234, name="Test Sheet", columns=[])
        result = schema.to_dict()
        assert "processed_at" not in result

    def test_schema_from_dict_round_trips_processed_at(self):
        """Schema.from_dict() preserves processed_at."""
        from datetime import datetime, timezone
        from ss2db.smartsheet.models import SmartsheetSchema

        ts = datetime(2026, 4, 6, 14, 30, 0)
        original = SmartsheetSchema(
            id=1234, name="Test Sheet", columns=[], processed_at=ts,
        )
        data = original.to_dict()
        restored = SmartsheetSchema.from_dict(data)
        assert restored.processed_at == ts

    def test_schema_to_dict_omits_workspace_fields_when_none(self):
        """Schema.to_dict() omits workspace fields when not set."""
        from ss2db.smartsheet.models import SmartsheetSchema

        schema = SmartsheetSchema(
            id=1234,
            name="Test Sheet",
            columns=[],
        )

        result = schema.to_dict()
        assert "workspace_id" not in result
        assert "workspace_name" not in result

    def test_schema_from_dict_round_trips_workspace_fields(self):
        """Schema.from_dict() preserves workspace_id and workspace_name."""
        from ss2db.smartsheet.models import SmartsheetSchema

        original = SmartsheetSchema(
            id=1234,
            name="Test Sheet",
            columns=[],
            workspace_id="9876543210",
            workspace_name="My Workspace",
        )

        data = original.to_dict()
        restored = SmartsheetSchema.from_dict(data)

        assert restored.workspace_id == "9876543210"
        assert restored.workspace_name == "My Workspace"

    def test_schema_from_dict_without_workspace_fields(self):
        """Schema.from_dict() handles missing workspace fields gracefully."""
        from ss2db.smartsheet.models import SmartsheetSchema

        data = {"id": 1234, "name": "Test Sheet", "columns": []}
        restored = SmartsheetSchema.from_dict(data)

        assert restored.workspace_id is None
        assert restored.workspace_name is None

    @patch("ss2db.main.execute_phases")
    def test_workspace_processor_passes_workspace_metadata(self, mock_execute):
        """WorkspaceProcessor passes workspace_id and workspace_name to execute_phases."""
        captured_calls = []

        def capture_call(**kwargs):
            captured_calls.append(kwargs)
            return True

        mock_execute.side_effect = capture_call

        client = Mock()
        client.get_workspace.return_value = WORKSPACE_FLAT
        config_manager = Mock()
        app_config = Mock()
        app_config.output.directory = "/tmp/test_exports"
        logger = Mock()

        processor = WorkspaceProcessor(
            client=client,
            config_manager=config_manager,
            app_config=app_config,
            max_workers=1,
            logger=logger,
        )

        processor.process_workspace(workspace_id="1111111111111111")

        assert len(captured_calls) == 2
        for call_kwargs in captured_calls:
            assert call_kwargs["workspace_id"] == "1111111111111111"
            assert call_kwargs["workspace_name"] == "Test Workspace"


class TestGetWorkspace:
    """Tests for SmartsheetClient.get_workspace()."""

    def test_get_workspace_calls_correct_endpoint(self):
        """get_workspace() calls the correct API endpoint with loadAll param."""
        from ss2db.smartsheet.client import SmartsheetClient

        client = SmartsheetClient("test_token", {"request_timeout": 5, "retry_attempts": 1})

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = WORKSPACE_FLAT

        with patch.object(client, "_make_request", return_value=mock_response) as mock_req:
            result = client.get_workspace("1111111111111111")

        mock_req.assert_called_once_with(
            "GET", "/workspaces/1111111111111111", params={"loadAll": "true"}
        )
        assert result["name"] == "Test Workspace"

    def test_get_workspace_without_load_all(self):
        """get_workspace(load_all=False) does not send loadAll param."""
        from ss2db.smartsheet.client import SmartsheetClient

        client = SmartsheetClient("test_token", {"request_timeout": 5, "retry_attempts": 1})

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = WORKSPACE_FLAT

        with patch.object(client, "_make_request", return_value=mock_response) as mock_req:
            client.get_workspace("1111111111111111", load_all=False)

        mock_req.assert_called_once_with(
            "GET", "/workspaces/1111111111111111", params={}
        )
