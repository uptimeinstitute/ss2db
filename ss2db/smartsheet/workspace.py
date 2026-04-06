# ABOUTME: Workspace processing module for concurrent multi-sheet extraction.
# ABOUTME: Discovers sheets in a Smartsheet workspace and processes them in parallel using ThreadPoolExecutor.

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ss2db.smartsheet.client import SmartsheetClient
from ss2db.utils.logging import get_logger


@dataclass
class SheetResult:
    """Result of processing a single sheet within a workspace."""

    sheet_id: str
    sheet_name: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0


def collect_sheets_from_workspace(workspace_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recursively collect all sheets from a workspace response.

    Walks the workspace structure including nested folders and sub-folders,
    returning a flat list of sheet metadata dicts. Only collects sheets,
    ignoring reports, dashboards, and other workspace items.

    Args:
        workspace_data: The workspace API response dict.

    Returns:
        Flat list of sheet dicts with id, name, and permalink fields.
    """
    sheets = []

    # Collect sheets at this level
    for sheet in workspace_data.get("sheets", []):
        sheets.append({
            "id": str(sheet["id"]),
            "name": sheet.get("name", f"Sheet {sheet['id']}"),
            "permalink": sheet.get("permalink"),
        })

    # Recurse into folders
    for folder in workspace_data.get("folders", []):
        sheets.extend(collect_sheets_from_workspace(folder))

    return sheets


class WorkspaceProcessor:
    """Processes all sheets in a Smartsheet workspace concurrently."""

    def __init__(
        self,
        client: SmartsheetClient,
        config_manager: Any,
        app_config: Any,
        max_workers: int,
        logger: Any = None,
    ):
        self.client = client
        self.config_manager = config_manager
        self.app_config = app_config
        self.max_workers = max_workers
        self.logger = logger or get_logger(__name__)

    def process_workspace(
        self,
        workspace_id: str,
        table_name: Optional[str] = None,
        db_type: Optional[str] = None,
        skip_extraction: bool = False,
        skip_schema: bool = False,
        skip_sql: bool = False,
        dry_run: bool = False,
    ) -> List[SheetResult]:
        """Discover and process all sheets in a workspace concurrently.

        Args:
            workspace_id: The Smartsheet workspace ID.
            table_name: Optional table name override (applied per-sheet).
            db_type: Database type override.
            skip_extraction: Skip data extraction phase.
            skip_schema: Skip schema extraction phase.
            skip_sql: Skip SQL generation phase.
            dry_run: Show what would be done without executing.

        Returns:
            List of SheetResult for each sheet processed.
        """
        # Fetch workspace contents
        self.logger.info(f"Fetching workspace {workspace_id} contents...")
        workspace_data = self.client.get_workspace(workspace_id)
        workspace_name = workspace_data.get("name", workspace_id)

        # Collect all sheets
        sheets = collect_sheets_from_workspace(workspace_data)

        if not sheets:
            self.logger.warning(f"No sheets found in workspace '{workspace_name}'")
            return []

        self.logger.info(f"Found {len(sheets)} sheets in workspace '{workspace_name}'")
        for sheet in sheets:
            self.logger.info(f"  - {sheet['name']} (ID: {sheet['id']})")

        if dry_run:
            self.logger.info(f"DRY RUN: Would process {len(sheets)} sheets with {self.max_workers} workers")
            return [
                SheetResult(sheet_id=s["id"], sheet_name=s["name"], success=True)
                for s in sheets
            ]

        # Process sheets concurrently
        results: List[SheetResult] = []
        effective_workers = min(self.max_workers, len(sheets))
        self.logger.info(f"Processing with {effective_workers} concurrent workers...")

        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            future_to_sheet = {
                executor.submit(
                    self._process_single_sheet,
                    sheet_info=sheet,
                    workspace_id=workspace_id,
                    table_name=table_name,
                    db_type=db_type,
                    skip_extraction=skip_extraction,
                    skip_schema=skip_schema,
                    skip_sql=skip_sql,
                ): sheet
                for sheet in sheets
            }

            for future in as_completed(future_to_sheet):
                sheet = future_to_sheet[future]
                try:
                    result = future.result()
                    results.append(result)
                    status = "✓" if result.success else "✗"
                    self.logger.info(
                        f"  {status} {result.sheet_name} ({result.duration:.1f}s)"
                        + (f" - {result.error}" if result.error else "")
                    )
                except Exception as e:
                    result = SheetResult(
                        sheet_id=sheet["id"],
                        sheet_name=sheet["name"],
                        success=False,
                        error=str(e),
                    )
                    results.append(result)
                    self.logger.error(f"  ✗ {sheet['name']} - {e}")

        return results

    def _process_single_sheet(
        self,
        sheet_info: Dict[str, Any],
        workspace_id: str,
        table_name: Optional[str],
        db_type: Optional[str],
        skip_extraction: bool,
        skip_schema: bool,
        skip_sql: bool,
    ) -> SheetResult:
        """Process a single sheet within the workspace.

        Calls execute_phases() with the shared client and a workspace-specific
        output directory.
        """
        # Import here to avoid circular imports
        from ss2db.main import execute_phases

        sheet_id = sheet_info["id"]
        sheet_name = sheet_info["name"]
        start_time = time.time()

        try:
            # Output goes to {output_dir}/{workspace_id}/{sheet_id}/
            output_dir = Path(self.app_config.output.directory) / workspace_id / sheet_id

            success = execute_phases(
                config_manager=self.config_manager,
                app_config=self.app_config,
                sheet_id=sheet_id,
                report_id=None,
                table_name=table_name,
                db_type=db_type,
                skip_extraction=skip_extraction,
                skip_schema=skip_schema,
                skip_sql=skip_sql,
                input_data=None,
                input_schema=None,
                dry_run=False,
                logger=self.logger,
                smartsheet_client=self.client,
                output_dir_override=output_dir,
            )

            duration = time.time() - start_time
            return SheetResult(
                sheet_id=sheet_id,
                sheet_name=sheet_name,
                success=success,
                error=None if success else "Processing returned failure",
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return SheetResult(
                sheet_id=sheet_id,
                sheet_name=sheet_name,
                success=False,
                error=str(e),
                duration=duration,
            )

    def print_summary(self, results: List[SheetResult]) -> None:
        """Print a summary table of workspace processing results."""
        if not results:
            self.logger.info("No sheets were processed.")
            return

        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        total_duration = sum(r.duration for r in results)

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("WORKSPACE PROCESSING SUMMARY")
        self.logger.info("=" * 60)

        for result in results:
            status = "OK" if result.success else "FAILED"
            line = f"  [{status:6s}] {result.sheet_name} ({result.duration:.1f}s)"
            if result.error:
                line += f" - {result.error}"
            self.logger.info(line)

        self.logger.info("-" * 60)
        self.logger.info(
            f"  Total: {len(results)} sheets | "
            f"Succeeded: {len(succeeded)} | "
            f"Failed: {len(failed)} | "
            f"Duration: {total_duration:.1f}s"
        )
        self.logger.info("=" * 60)
