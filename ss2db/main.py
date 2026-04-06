"""Main CLI entry point for ss2db."""

import sys
import time
from pathlib import Path
from typing import Optional

import click
import yaml

from ss2db import __version__
from ss2db.config import Config, ConfigManager, load_config
from ss2db.utils.logging import get_logger, log_operation_complete, log_operation_start, setup_logging
from ss2db.utils.files import get_file_manager, get_output_manager
from ss2db.smartsheet.client import SmartsheetClient, SmartsheetAPIError
from ss2db.smartsheet.extractors import SheetExtractor, ReportExtractor, DataExporter
from ss2db.smartsheet.workspace import WorkspaceProcessor
from ss2db.database.postgresql import generate_postgresql_script
from ss2db.database.mysql import generate_mysql_script


@click.command()
@click.option("--sheet-id", type=str, help="Smartsheet sheet ID to process")
@click.option("--report-id", type=str, help="Smartsheet report ID to process")
@click.option("--workspace-id", type=str, help="Smartsheet workspace ID to process all sheets")
@click.option("--max-workers", type=int, help="Max concurrent threads for workspace processing")
@click.option("--config", type=click.Path(exists=True), help="Path to config.yaml file")
@click.option("--env-file", type=click.Path(), help="Path to .env file")
@click.option("--output-dir", type=click.Path(), help="Directory for output files")
@click.option("--table-name", type=str, help="Override database table name")
@click.option("--db-type", type=click.Choice(["postgresql", "mysql"]), help="Database type to generate scripts for")
@click.option("--skip-extraction", is_flag=True, help="Skip data extraction phase")
@click.option("--skip-schema", is_flag=True, help="Skip schema extraction phase")
@click.option("--skip-sql", is_flag=True, help="Skip SQL generation phase")
@click.option("--input-data", type=click.Path(exists=True), help="Use existing data file")
@click.option("--input-schema", type=click.Path(exists=True), help="Use existing schema file")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.option("--log-file", type=click.Path(), help="Write logs to specified file")
@click.version_option(version=__version__, prog_name="ss2db")
def main(
    sheet_id: Optional[str],
    report_id: Optional[str],
    workspace_id: Optional[str],
    max_workers: Optional[int],
    config: Optional[str],
    env_file: Optional[str],
    output_dir: Optional[str],
    table_name: Optional[str],
    db_type: Optional[str],
    skip_extraction: bool,
    skip_schema: bool,
    skip_sql: bool,
    input_data: Optional[str],
    input_schema: Optional[str],
    dry_run: bool,
    verbose: bool,
    quiet: bool,
    log_file: Optional[str],
) -> None:
    """
    Smartsheet to database export tool.

    Extract data from Smartsheet and generate database import scripts for PostgreSQL and MySQL.

    Examples:
        ss2db --sheet-id 1234567890 --output-dir ./exports --db-type postgresql
        ss2db --report-id 9876543210 --verbose --db-type mysql
        ss2db --sheet-id 1234567890 --skip-extraction --input-data data.json
        ss2db --workspace-id 1133727850647428 --db-type postgresql --max-workers 4
    """
    start_time = time.time()

    print(f"ss2db version {__version__}")

    try:
        # Load configuration
        try:
            app_config, config_manager = load_config(config, env_file)
        except Exception as e:
            click.echo(f"Error loading configuration: {e}", err=True)
            sys.exit(1)

        # Override configuration options if specified
        if output_dir:
            app_config.output.directory = output_dir
        if db_type:
            app_config.database.type = db_type

        # Set up logging
        logger = setup_logging(
            level=app_config.logging.level,
            format_type=app_config.logging.format,
            log_file=log_file,
            file_rotation=app_config.logging.file_rotation,
            max_file_size=app_config.logging.max_file_size,
            backup_count=app_config.logging.backup_count,
            quiet=quiet,
            verbose=verbose
        )

        # Validate arguments
        specified = sum(1 for x in [sheet_id, report_id, workspace_id] if x)
        if specified == 0:
            click.echo("Error: One of --sheet-id, --report-id, or --workspace-id must be specified", err=True)
            sys.exit(1)
        if specified > 1:
            click.echo("Error: Only one of --sheet-id, --report-id, or --workspace-id may be specified", err=True)
            sys.exit(1)

        if workspace_id and (input_data or input_schema):
            click.echo("Error: --input-data and --input-schema are incompatible with --workspace-id", err=True)
            sys.exit(1)

        if max_workers is not None and not workspace_id:
            click.echo("Error: --max-workers can only be used with --workspace-id", err=True)
            sys.exit(1)

        if dry_run:
            logger.info("DRY RUN MODE - No files will be created or modified")

        logger.info(f"Database type: {app_config.database.type}")

        # Create output directory
        output_path = Path(app_config.output.directory)
        if not dry_run:
            output_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created output directory: {output_path}")

        # Workspace mode: process all sheets in workspace concurrently
        if workspace_id:
            log_operation_start(
                logger,
                f"ss2db (v{__version__}) workspace export",
                resource_type="workspace",
                resource_id=workspace_id,
                database_type=app_config.database.type,
                dry_run=dry_run
            )

            effective_max_workers = max_workers or app_config.workspace.max_workers

            # Create shared client
            try:
                api_token = config_manager.get_api_token()
                client = SmartsheetClient(api_token, app_config.smartsheet.model_dump())
                if not client.test_connection():
                    logger.error("Failed to connect to Smartsheet API")
                    sys.exit(1)
                logger.info("✓ Smartsheet API connection verified")
            except Exception as e:
                logger.error(f"Failed to initialize Smartsheet client: {e}")
                sys.exit(1)

            processor = WorkspaceProcessor(
                client=client,
                config_manager=config_manager,
                app_config=app_config,
                max_workers=effective_max_workers,
                logger=logger,
            )

            results = processor.process_workspace(
                workspace_id=workspace_id,
                table_name=table_name,
                db_type=db_type,
                skip_extraction=skip_extraction,
                skip_schema=skip_schema,
                skip_sql=skip_sql,
                dry_run=dry_run,
            )

            processor.print_summary(results)

            duration = time.time() - start_time
            failed = [r for r in results if not r.success]
            if failed:
                logger.warning(f"{len(failed)} of {len(results)} sheets failed")
                # Exit 1 only if ALL sheets failed
                if len(failed) == len(results):
                    sys.exit(1)

            log_operation_complete(logger, "ss2db workspace export", duration)
            sys.exit(0)

        # Single sheet/report mode
        resource_id = sheet_id or report_id
        resource_type = "sheet" if sheet_id else "report"

        log_operation_start(
            logger,
            f"ss2db (v{__version__}) export",
            resource_type=resource_type,
            resource_id=resource_id,
            database_type=app_config.database.type,
            dry_run=dry_run
        )

        # Execute processing phases
        success = execute_phases(
            config_manager=config_manager,
            app_config=app_config,
            sheet_id=sheet_id,
            report_id=report_id,
            table_name=table_name,
            db_type=db_type,
            skip_extraction=skip_extraction,
            skip_schema=skip_schema,
            skip_sql=skip_sql,
            input_data=input_data,
            input_schema=input_schema,
            dry_run=dry_run,
            logger=logger
        )

        # Log completion
        duration = time.time() - start_time
        if success:
            log_operation_complete(logger, "ss2db export", duration)
            sys.exit(0)
        else:
            logger.error("Export failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("Export interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def execute_phases(
    config_manager: ConfigManager,
    app_config: Config,
    sheet_id: Optional[str],
    report_id: Optional[str],
    table_name: Optional[str],
    db_type: Optional[str],
    skip_extraction: bool,
    skip_schema: bool,
    skip_sql: bool,
    input_data: Optional[str],
    input_schema: Optional[str],
    dry_run: bool,
    logger,
    smartsheet_client: Optional[SmartsheetClient] = None,
    output_dir_override: Optional[Path] = None,
) -> bool:
    """Execute the processing phases.

    Args:
        smartsheet_client: Optional pre-initialized client to reuse (for workspace mode).
            When provided, skips client creation and connection testing.
        output_dir_override: Optional path to override the default output directory.
            Used by workspace mode to nest output under workspace_id/sheet_id/.
    """

    resource_id = sheet_id or report_id
    resource_type = "sheet" if sheet_id else "report"

    # Create output filenames
    timestamp = time.strftime(app_config.output.timestamp_format)
    output_dir = output_dir_override or (Path(app_config.output.directory) / resource_id)

    data_file = output_dir / f"{timestamp}_data.json"
    schema_file = output_dir / f"{timestamp}_schema.json"
    sql_file = output_dir / f"{timestamp}_import.sql"
    log_file = output_dir / f"{timestamp}_log.txt"
    config_file = output_dir / f"config_used.yaml"

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Save configuration snapshot
    if not dry_run:
        save_config_snapshot(app_config, config_file, logger)

    # Initialize Smartsheet client if needed
    if smartsheet_client is None and (not skip_extraction or not skip_schema):
        if not dry_run:
            try:
                api_token = config_manager.get_api_token()
                smartsheet_client = SmartsheetClient(api_token, app_config.smartsheet.model_dump())

                # Test connection
                if not smartsheet_client.test_connection():
                    logger.error("Failed to connect to Smartsheet API")
                    return False

                logger.info("✓ Smartsheet API connection verified")

            except Exception as e:
                logger.error(f"Failed to initialize Smartsheet client: {e}")
                return False

    # Initialize file managers
    file_manager = get_file_manager(app_config.output.model_dump())
    data_exporter = DataExporter(app_config.output.model_dump())

    # Phase 1: Data Extraction
    if not skip_extraction and not input_data:
        logger.info(f"Phase 1: Extracting {resource_type} data")
        if dry_run:
            logger.info(f"Would extract data from {resource_type} {resource_id}")
            logger.info(f"Would save to: {data_file}")
        else:
            try:
                # Create appropriate extractor
                if resource_type == "sheet":
                    extractor = SheetExtractor(smartsheet_client, app_config.advanced.model_dump())
                else:  # report
                    extractor = ReportExtractor(smartsheet_client, app_config.advanced.model_dump())

                # Extract schema first (needed for data extraction)
                logger.info("Getting schema information...")
                schema = extractor.extract_schema(resource_id)

                # Extract data with progress tracking
                logger.info(f"Extracting data: {schema.total_row_count or 'unknown'} rows, {len(schema.columns)} columns")

                def progress_callback(progress):
                    if progress.extracted_rows % 10000 == 0:
                        percentage = progress.get_progress_percentage()
                        if percentage:
                            logger.info(f"Progress: {progress.extracted_rows}/{progress.total_rows} rows ({percentage:.1f}%)")
                        else:
                            logger.info(f"Progress: {progress.extracted_rows} rows extracted")

                # Extract data in chunks
                rows_generator = extractor.extract_data(resource_id, progress_callback)

                # Export data to file
                export_result = data_exporter.export_data_chunked(rows_generator, schema, data_file)

                logger.info(f"✓ Data extraction completed: {export_result['total_rows']} rows in {export_result['elapsed_time']:.2f}s")
                logger.info(f"  Data file: {data_file} ({export_result['file_size']:,} bytes)")

                # Also export schema
                data_exporter.export_schema(schema, schema_file)
                logger.info(f"✓ Schema exported: {schema_file}")

            except SmartsheetAPIError as e:
                logger.error(f"Smartsheet API error during extraction: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error during extraction: {e}")
                return False

    elif input_data:
        data_file = Path(input_data)
        logger.info(f"Using existing data file: {data_file}")

        # Validate data file exists
        if not data_file.exists():
            logger.error(f"Data file not found: {data_file}")
            return False
    else:
        logger.info("Skipping data extraction phase")

    # Phase 2: Schema Extraction
    if not skip_schema and not input_schema:
        logger.info(f"Phase 2: Extracting {resource_type} schema")
        if dry_run:
            logger.info(f"Would extract schema from {resource_type} {resource_id}")
            logger.info(f"Would save to: {schema_file}")
        else:
            # Schema was already extracted in Phase 1 if data extraction ran
            if skip_extraction:
                try:
                    # Create appropriate extractor
                    if resource_type == "sheet":
                        extractor = SheetExtractor(smartsheet_client, app_config.advanced.model_dump())
                    else:  # report
                        extractor = ReportExtractor(smartsheet_client, app_config.advanced.model_dump())

                    # Extract schema
                    schema = extractor.extract_schema(resource_id)
                    data_exporter.export_schema(schema, schema_file)
                    logger.info(f"✓ Schema extracted: {len(schema.columns)} columns")

                except SmartsheetAPIError as e:
                    logger.error(f"Smartsheet API error during schema extraction: {e}")
                    return False
                except Exception as e:
                    logger.error(f"Unexpected error during schema extraction: {e}")
                    return False
            else:
                logger.info("✓ Schema already extracted with data")

    elif input_schema:
        schema_file = Path(input_schema)
        logger.info(f"Using existing schema file: {schema_file}")

        # Validate schema file exists
        if not schema_file.exists():
            logger.error(f"Schema file not found: {schema_file}")
            return False
    else:
        logger.info("Skipping schema extraction phase")

    # Phase 3: SQL Generation
    if not skip_sql:
        db_name = app_config.database.type.upper()
        logger.info(f"Phase 3: Generating {db_name} script")
        if dry_run:
            logger.info(f"Would generate {db_name} script using:")
            logger.info(f"  Data file: {data_file}")
            logger.info(f"  Schema file: {schema_file}")
            logger.info(f"  Output file: {sql_file}")
            logger.info(f"  Database type: {app_config.database.type}")
            if table_name:
                logger.info(f"  Table name: {table_name}")
        else:
            try:
                if app_config.database.type == "postgresql":
                    # Generate PostgreSQL script
                    postgres_config = app_config.database.postgresql.model_dump() if app_config.database.postgresql else {}

                    result = generate_postgresql_script(
                        data_file=data_file,
                        schema_file=schema_file,
                        output_file=sql_file,
                        config=postgres_config,
                        table_name=table_name
                    )

                    logger.info(f"✓ PostgreSQL script generated: {sql_file}")
                    logger.info(f"  File size: {result['file_size']:,} bytes")
                    logger.info(f"  Lines: {result['lines']:,}")
                    logger.info(f"  INSERT statements: {result['insert_statements']}")
                    logger.info(f"  Generation time: {result['elapsed_time']:.2f}s")

                elif app_config.database.type == "mysql":
                    # Generate MySQL script
                    mysql_config = app_config.database.mysql.model_dump() if app_config.database.mysql else {}

                    result = generate_mysql_script(
                        data_file=data_file,
                        schema_file=schema_file,
                        output_file=sql_file,
                        config=mysql_config,
                        table_name=table_name
                    )

                    logger.info(f"✓ MySQL script generated: {sql_file}")
                    logger.info(f"  File size: {result['file_size']:,} bytes")
                    logger.info(f"  Lines: {result['lines']:,}")
                    logger.info(f"  INSERT statements: {result['insert_statements']}")
                    logger.info(f"  Generation time: {result['elapsed_time']:.2f}s")
                else:
                    logger.error(f"Unsupported database type: {app_config.database.type}")
                    return False

            except Exception as e:
                logger.error(f"Failed to generate {db_name} script: {e}")
                return False
    else:
        logger.info("Skipping SQL generation phase")

    return True


def save_config_snapshot(config: Config, config_file: Path, logger) -> None:
    """Save a snapshot of the current configuration."""
    try:
        config_dict = config.model_dump()
        with open(config_file, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
        logger.debug(f"Saved configuration snapshot: {config_file}")
    except Exception as e:
        logger.warning(f"Failed to save configuration snapshot: {e}")


if __name__ == "__main__":
    main()