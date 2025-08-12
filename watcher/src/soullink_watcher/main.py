"""Main entrypoint for the SoulLink Production Watcher."""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .cli import parse_args, build_config
from .config import ensure_dirs, WatcherConfig
from .http_client import EventSender
from .ndjson_reader import iter_ndjson, validate_event_minimal, count_events_in_file, preview_events
from .retry import compute_backoff
from .spool import SpoolQueue

logger = logging.getLogger(__name__)


def configure_logging(cfg):
    """Configure logging based on configuration."""
    log_level = logging.DEBUG if cfg.dev else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce noise from requests library
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    if cfg.dev:
        logger.info("Development mode enabled - verbose logging active")


def ingest_from_file(cfg, spool: SpoolQueue, sender: EventSender) -> int:
    """
    Ingest events from NDJSON file.
    
    Args:
        cfg: Watcher configuration
        spool: Spool queue instance
        sender: HTTP event sender
    
    Returns:
        Number of events processed
    """
    if not cfg.from_file:
        return 0
    
    logger.info(f"Ingesting events from {cfg.from_file}")
    
    # Preview the file
    try:
        total_events = count_events_in_file(cfg.from_file)
        logger.info(f"File contains approximately {total_events} events")
        
        if cfg.dev and total_events > 0:
            logger.info("Preview of first few events:")
            for preview in preview_events(cfg.from_file, limit=3):
                logger.info(f"  {preview}")
                
    except Exception as e:
        logger.warning(f"Could not preview file: {e}")
    
    processed = 0
    successful = 0
    spooled = 0
    errors = 0
    
    try:
        for event in iter_ndjson(cfg.from_file):
            processed += 1
            
            try:
                # Validate and normalize the event
                normalized_event = validate_event_minimal(event, cfg.run_id, cfg.player_id)
                
                # Generate idempotency key
                idempotency_key = str(uuid4())
                
                # Prepare headers
                headers = {
                    'Authorization': f'Bearer {cfg.token}',
                    'Content-Type': 'application/json',
                    'Idempotency-Key': idempotency_key
                }
                
                # Try immediate send (optimistic)
                spool_record_data = {
                    'record_id': str(uuid4()),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'next_attempt_at': datetime.now(timezone.utc).isoformat(),
                    'attempt': 0,
                    'idempotency_key': idempotency_key,
                    'base_url': cfg.base_url,
                    'headers': headers,
                    'request_json': normalized_event,
                    'run_id': cfg.run_id,
                    'player_id': cfg.player_id
                }
                
                # Create a temporary SpoolRecord for sending
                from .spool import SpoolRecord
                temp_record = SpoolRecord.from_dict(spool_record_data)
                
                result = sender.send_event(cfg, temp_record)
                
                if result.success:
                    successful += 1
                    logger.debug(f"Event {processed} sent immediately: {normalized_event.get('type')}")
                else:
                    # Spool for retry
                    spool_path = spool.enqueue(
                        payload=normalized_event,
                        idempotency_key=idempotency_key,
                        headers=headers,
                        base_url=cfg.base_url
                    )
                    spooled += 1
                    
                    if result.retriable:
                        logger.info(f"Event {processed} spooled for retry: {result.message}")
                    else:
                        logger.warning(f"Event {processed} spooled but may be non-retryable: {result.message}")
                
            except Exception as e:
                errors += 1
                logger.error(f"Error processing event {processed}: {e}")
                if cfg.dev:
                    logger.debug(f"Problematic event: {event}")
                continue
            
            # Progress logging
            if processed % 100 == 0:
                logger.info(f"Processed {processed} events ({successful} sent, {spooled} spooled, {errors} errors)")
    
    except KeyboardInterrupt:
        logger.info(f"Interrupted after processing {processed} events")
    except Exception as e:
        logger.error(f"Error reading from file: {e}")
        return processed
    
    logger.info(f"Ingestion complete: {processed} total, {successful} sent immediately, {spooled} spooled, {errors} errors")
    return processed


def drain_loop(cfg, spool: SpoolQueue, sender: EventSender) -> None:
    """
    Main drain loop for processing spooled events.
    
    Args:
        cfg: Watcher configuration
        spool: Spool queue instance
        sender: HTTP event sender
    """
    logger.info("Starting spool drain loop")
    logger.info(f"Poll interval: {cfg.poll_interval_secs}s, Backoff base: {cfg.backoff_base_secs}s, Max: {cfg.backoff_max_secs}s")
    
    consecutive_empty_polls = 0
    max_empty_polls_for_summary = 60  # Print summary every 60 empty polls
    
    try:
        while True:
            now = datetime.now(timezone.utc)
            due_files = spool.list_due(now)
            
            if not due_files:
                consecutive_empty_polls += 1
                
                # Log summary periodically when queue is empty
                if consecutive_empty_polls % max_empty_polls_for_summary == 0:
                    logger.info(f"Spool queue empty for {consecutive_empty_polls * cfg.poll_interval_secs:.0f} seconds")
                
                time.sleep(cfg.poll_interval_secs)
                continue
            
            consecutive_empty_polls = 0
            processed_this_round = 0
            successful_this_round = 0
            
            logger.info(f"Processing {len(due_files)} due events")
            
            for file_path in due_files[:10]:  # Process max 10 per iteration to avoid starvation
                try:
                    # Claim the file
                    sending_path = spool.claim(file_path)
                    
                    # Load the record
                    import json
                    with sending_path.open('r', encoding='utf-8') as f:
                        record_data = json.load(f)
                    
                    from .spool import SpoolRecord
                    record = SpoolRecord.from_dict(record_data)
                    
                    # Send the event
                    result = sender.send_event(cfg, record)
                    processed_this_round += 1
                    
                    if result.success:
                        # Success - delete the record
                        spool.delete(sending_path)
                        successful_this_round += 1
                        logger.debug(f"Successfully sent event {record.idempotency_key}")
                        
                    elif result.retriable:
                        # Retryable error - schedule for retry
                        next_attempt_at = now
                        
                        if result.retry_after:
                            # Honor Retry-After header
                            next_attempt_at = result.retry_after
                            logger.info(f"Event {record.idempotency_key} scheduled for retry at {next_attempt_at} (Retry-After)")
                        else:
                            # Compute exponential backoff
                            backoff_secs = compute_backoff(
                                record.attempt,
                                cfg.backoff_base_secs,
                                cfg.backoff_max_secs,
                                cfg.backoff_jitter_ratio
                            )
                            next_attempt_at = now + timedelta(seconds=backoff_secs)
                            logger.info(f"Event {record.idempotency_key} scheduled for retry in {backoff_secs:.1f}s (attempt {record.attempt + 1})")
                        
                        spool.release_for_retry(sending_path, next_attempt_at, result.message or "Unknown error")
                        
                    else:
                        # Non-retryable error - move to dead letter
                        dead_path = spool.move_to_dead(sending_path, result.message or "Non-retryable error")
                        logger.warning(f"Event {record.idempotency_key} moved to dead letter: {result.message}")
                        
                except FileNotFoundError:
                    # File was already claimed by another process
                    logger.debug(f"File already claimed: {file_path}")
                    continue
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    # Try to move to dead letter as fallback
                    try:
                        if 'sending_path' in locals():
                            spool.move_to_dead(sending_path, f"Processing error: {e}")
                    except Exception:
                        pass  # Give up
                    continue
            
            if processed_this_round > 0:
                logger.info(f"Round complete: {processed_this_round} processed, {successful_this_round} successful")
            
            # Brief pause between rounds
            if processed_this_round < len(due_files):
                time.sleep(0.1)  # Short pause if we didn't process all due files
            else:
                time.sleep(cfg.poll_interval_secs)
                
    except KeyboardInterrupt:
        logger.info("Drain loop interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in drain loop: {e}")
        raise


def main(config=None, argv=None) -> int:
    """
    Main entrypoint for the watcher.
    
    Args:
        config: Optional WatcherConfig instance (overrides argv)
        argv: Command line arguments (for testing)
    
    Returns:
        Exit code (0 for success)
    """
    try:
        # Get configuration - use provided config or parse from argv
        if config is not None:
            cfg = config
        else:
            # Parse arguments and build configuration
            ns = parse_args(argv)
            cfg = build_config(ns)
        
        # Configure logging
        configure_logging(cfg)
        
        logger.info(f"SoulLink Production Watcher starting")
        logger.info(f"Base URL: {cfg.base_url}")
        logger.info(f"Run ID: {cfg.run_id}")
        logger.info(f"Player ID: {cfg.player_id}")
        logger.info(f"Spool directory: {cfg.spool_dir}")
        
        # Ensure directories exist
        ensure_dirs(cfg)
        
        # Initialize spool queue
        spool = SpoolQueue(cfg.spool_dir, cfg.run_id, cfg.player_id)
        
        # Try to acquire lock
        if not spool.acquire_lock():
            logger.warning("Could not acquire lock file - another watcher may be running")
            if not cfg.dev:
                logger.error("Exiting to prevent conflicts (use --dev to override)")
                return 1
        
        try:
            # Recover stale .sending files
            recovered = spool.recover_stale()
            if recovered > 0:
                logger.info(f"Recovered {recovered} stale sending files")
            
            # Initialize HTTP client
            sender = EventSender(timeout_secs=cfg.http_timeout_secs)
            
            try:
                # Ingest from file if specified
                if cfg.from_file:
                    events_ingested = ingest_from_file(cfg, spool, sender)
                    logger.info(f"File ingestion complete: {events_ingested} events processed")
                
                # Enter drain loop
                drain_loop(cfg, spool, sender)
                
            finally:
                sender.close()
                
        finally:
            spool.release_lock()
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130  # Standard exit code for Ctrl+C
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if '--dev' in (argv or sys.argv):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())