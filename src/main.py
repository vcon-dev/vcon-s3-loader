"""Main service orchestrator for vCon S3 Loader."""

import logging
import signal
import sys
import time
from typing import Optional
from datetime import datetime, date

from .config import Config
from .s3_client import S3Client
from .redis_client import RedisClient
from .http_client import HTTPClient
from .rate_limiter import RateLimiter
from .date_processor import DateProcessor
from .checkpoint import CheckpointManager
from .vcon_loader import VConLoader
from .metrics import Metrics

logger = logging.getLogger(__name__)


class VConS3LoaderService:
    """Main service for loading vCons from S3 and POSTing them."""

    def __init__(self, config: Config):
        """
        Initialize the service.

        Args:
            config: Configuration object
        """
        logger.debug("Initializing VConS3LoaderService")
        self.config = config
        self.running = False
        self.shutdown_requested = False
        
        # Initialize components
        s3_config = config["s3"]
        logger.debug(f"Initializing S3 client: bucket={s3_config['bucket']}, prefix={s3_config.get('prefix', '')}, region={s3_config.get('region', 'us-east-1')}")
        self.s3_client = S3Client(
            bucket_name=s3_config["bucket"],
            prefix=s3_config.get("prefix", ""),
            region=s3_config.get("region", "us-east-1"),
        )
        
        redis_config = config["redis"]
        logger.debug(f"Initializing Redis client: url={redis_config['url']}, enabled={redis_config.get('enabled', True)}, prefix={redis_config.get('key_prefix', 'vcon-loader')}")
        self.redis_client = RedisClient(
            redis_url=redis_config["url"],
            key_prefix=redis_config.get("key_prefix", "vcon-loader"),
            enabled=redis_config.get("enabled", True),
        )
        
        post_config = config["post"]
        logger.debug(f"Initializing HTTP client: url={post_config['url']}, use_vcon_method={post_config.get('use_vcon_method', False)}, retry_attempts={post_config.get('retry_attempts', 3)}")
        self.http_client = HTTPClient(
            url=post_config["url"],
            headers=post_config.get("headers", {}),
            use_vcon_method=post_config.get("use_vcon_method", False),
            retry_attempts=post_config.get("retry_attempts", 3),
            retry_backoff_base=post_config.get("retry_backoff_base", 2),
        )
        
        rate_limit_config = config["rate_limit"]
        logger.debug(f"Initializing rate limiter: requests_per_second={rate_limit_config.get('requests_per_second', 10)}")
        self.rate_limiter = RateLimiter(
            requests_per_second=rate_limit_config.get("requests_per_second", 10)
        )
        
        processing_config = config["processing"]
        logger.debug(f"Initializing date processor: start_date={processing_config['start_date']}")
        self.date_processor = DateProcessor(
            start_date=processing_config["start_date"]
        )
        
        checkpoint_file = processing_config.get("checkpoint_file", ".checkpoint.json")
        logger.debug(f"Initializing checkpoint manager: checkpoint_file={checkpoint_file}")
        self.checkpoint_manager = CheckpointManager(
            checkpoint_file=checkpoint_file
        )
        
        validate_vcon = processing_config.get("validate_vcon", True)
        migrate_version = processing_config.get("migrate_version", False)
        logger.debug(f"Initializing vCon loader: validate={validate_vcon}, migrate_version={migrate_version}")
        self.vcon_loader = VConLoader(
            validate=validate_vcon,
            migrate_version=migrate_version
        )
        
        logger.debug("Initializing metrics tracker")
        self.metrics = Metrics()
        
        # Load checkpoint if exists
        self._load_checkpoint()
        
        # Setup signal handlers
        logger.debug("Setting up signal handlers for graceful shutdown")
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("VConS3LoaderService initialized successfully")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name if hasattr(signal.Signals, '__members__') else str(signum)
        logger.info(f"Received signal {signal_name} ({signum}), initiating graceful shutdown...")
        logger.debug(f"Current state: running={self.running}, processed_count={self.metrics.processed_count}, error_count={self.metrics.error_count}")
        self.shutdown_requested = True

    def _load_checkpoint(self):
        """Load checkpoint data."""
        logger.debug("Loading checkpoint data")
        checkpoint_data = self.checkpoint_manager.load()
        if checkpoint_data:
            last_date = self.checkpoint_manager.get_last_processed_date()
            last_key = self.checkpoint_manager.get_last_processed_key()
            logger.debug(f"Checkpoint data loaded: last_date={last_date}, last_key={last_key}")
            if last_date:
                # Mark dates up to last_date as processed
                dates_marked = 0
                for d in self.date_processor.date_range(last_date):
                    self.date_processor.mark_processed(d)
                    dates_marked += 1
                logger.info(f"Resumed from checkpoint: last processed date {last_date}, last key {last_key}, marked {dates_marked} dates as processed")
            else:
                logger.debug("Checkpoint loaded but no last processed date found")
        else:
            logger.debug("No checkpoint file found, starting fresh")

    def _save_checkpoint(self, processed_date: date, last_key: Optional[str] = None):
        """Save checkpoint data."""
        logger.debug(f"Saving checkpoint: date={processed_date}, key={last_key}")
        self.checkpoint_manager.set_last_processed_date(processed_date)
        if last_key:
            self.checkpoint_manager.set_last_processed_key(last_key)
        logger.debug("Checkpoint saved successfully")

    def _process_vcon(self, s3_key: str, vcon_data: dict) -> bool:
        """
        Process a single vCon.

        Args:
            s3_key: S3 key of the vCon file
            vcon_data: vCon data dictionary

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        logger.debug(f"Starting to process vCon: s3_key={s3_key}, data_size={len(str(vcon_data))} bytes")
        
        try:
            # Load and validate vCon
            logger.debug(f"Loading vCon from dictionary for {s3_key}")
            load_start = time.time()
            vcon = self.vcon_loader.load_from_dict(vcon_data)
            load_time = time.time() - load_start
            logger.debug(f"vCon loading completed in {load_time:.3f}s for {s3_key}")
            
            if vcon is None:
                self.metrics.record_validation_error()
                logger.warning(f"Failed to load/validate vCon from {s3_key} (validation or parsing failed)")
                return False
            
            # Extract identifier for deduplication
            identifier = self.vcon_loader.extract_identifier(vcon, s3_key)
            logger.debug(f"Extracted identifier for deduplication: {identifier} (from s3_key={s3_key})")
            
            # Check if already processed (Redis deduplication)
            redis_check_start = time.time()
            is_processed = self.redis_client.is_processed(identifier)
            redis_check_time = time.time() - redis_check_start
            logger.debug(f"Redis deduplication check completed in {redis_check_time:.3f}s: identifier={identifier}, is_processed={is_processed}")
            
            if is_processed:
                self.metrics.record_skipped()
                logger.info(f"Skipping already processed vCon: identifier={identifier}, s3_key={s3_key}")
                return True
            
            # Rate limit
            logger.debug(f"Waiting for rate limiter before POST for {s3_key}")
            rate_limit_start = time.time()
            self.rate_limiter.wait()
            rate_limit_time = time.time() - rate_limit_start
            logger.debug(f"Rate limiter wait completed in {rate_limit_time:.3f}s for {s3_key}")
            
            # POST vCon
            logger.debug(f"POSTing vCon to endpoint: identifier={identifier}, s3_key={s3_key}")
            post_start = time.time()
            success = self.http_client.post_vcon(vcon_data, vcon_obj=vcon)
            post_time = time.time() - post_start
            logger.debug(f"POST request completed in {post_time:.3f}s: success={success}, identifier={identifier}")
            
            if success:
                # Mark as processed in Redis
                logger.debug(f"Marking vCon as processed in Redis: identifier={identifier}")
                self.redis_client.mark_processed(identifier)
                
                # Record metrics
                processing_time = time.time() - start_time
                self.metrics.record_processed(processing_time)
                logger.info(f"Successfully processed vCon: s3_key={s3_key}, identifier={identifier}, total_time={processing_time:.3f}s (load={load_time:.3f}s, post={post_time:.3f}s)")
                return True
            else:
                self.metrics.record_error("post_failed")
                processing_time = time.time() - start_time
                logger.error(f"Failed to POST vCon: s3_key={s3_key}, identifier={identifier}, total_time={processing_time:.3f}s, post_time={post_time:.3f}s")
                return False
                
        except Exception as e:
            processing_time = time.time() - start_time
            self.metrics.record_error(type(e).__name__)
            logger.error(f"Error processing vCon s3_key={s3_key}, error_type={type(e).__name__}, error={str(e)}, processing_time={processing_time:.3f}s", exc_info=True)
            return False

    def _process_date(self, date_obj: datetime) -> bool:
        """
        Process all vCons for a specific date.

        Args:
            date_obj: Date to process

        Returns:
            True if all vCons processed successfully, False otherwise
        """
        date_str = date_obj.strftime("%Y-%m-%d")
        date_start_time = time.time()
        logger.info(f"Starting to process date: {date_str}")
        logger.debug(f"Date processing started at {datetime.now().isoformat()}")
        
        try:
            # List objects for this date
            logger.debug(f"Listing S3 objects for date {date_str}")
            list_start = time.time()
            s3_keys = self.s3_client.list_objects_by_date(date_obj)
            list_time = time.time() - list_start
            logger.debug(f"S3 listing completed in {list_time:.3f}s: found {len(s3_keys)} objects for date {date_str}")
            
            if not s3_keys:
                logger.info(f"No vCon files found for date {date_str}")
                self.date_processor.mark_processed(date_obj.date())
                self._save_checkpoint(date_obj.date())
                return True
            
            # Process each vCon
            batch_size = self.config["processing"].get("batch_size", 1)
            logger.debug(f"Processing {len(s3_keys)} vCons in batches of {batch_size} for date {date_str}")
            last_key = None
            processed_count = 0
            failed_count = 0
            
            for i in range(0, len(s3_keys), batch_size):
                batch = s3_keys[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(s3_keys) + batch_size - 1) // batch_size
                logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items) for date {date_str}")
                
                for s3_key in batch:
                    if self.shutdown_requested:
                        logger.warning(f"Shutdown requested during date processing, stopping at {s3_key}")
                        return False
                    
                    # Download vCon
                    logger.debug(f"Downloading vCon from S3: {s3_key}")
                    download_start = time.time()
                    vcon_data = self.s3_client.download_json(s3_key)
                    download_time = time.time() - download_start
                    
                    if vcon_data is None:
                        self.metrics.record_error("download_failed")
                        failed_count += 1
                        logger.warning(f"Failed to download vCon: {s3_key} (download_time={download_time:.3f}s)")
                        continue
                    
                    logger.debug(f"Downloaded vCon in {download_time:.3f}s: {s3_key}, size={len(str(vcon_data))} bytes")
                    
                    # Process vCon
                    if self._process_vcon(s3_key, vcon_data):
                        processed_count += 1
                    else:
                        failed_count += 1
                    last_key = s3_key
                
                # Save checkpoint after each batch
                if last_key:
                    logger.debug(f"Saving checkpoint after batch {batch_num}/{total_batches} for date {date_str}")
                    self._save_checkpoint(date_obj.date(), last_key)
            
            # Mark date as processed
            self.date_processor.mark_processed(date_obj.date())
            self.metrics.record_date_processed(date_str)
            self._save_checkpoint(date_obj.date(), last_key)
            
            date_processing_time = time.time() - date_start_time
            logger.info(f"Completed processing date {date_str}: processed={processed_count}, failed={failed_count}, total={len(s3_keys)}, time={date_processing_time:.3f}s")
            return True
            
        except Exception as e:
            date_processing_time = time.time() - date_start_time
            logger.error(f"Error processing date {date_str}: error_type={type(e).__name__}, error={str(e)}, time={date_processing_time:.3f}s", exc_info=True)
            self.metrics.record_error("date_processing_failed")
            return False

    def _backfill_mode(self):
        """Process all dates from start_date to today."""
        backfill_start_time = time.time()
        logger.info("Starting backfill mode")
        logger.debug(f"Backfill started at {datetime.now().isoformat()}")
        
        today = date.today()
        logger.debug(f"Calculating unprocessed dates from start_date to {today}")
        dates_to_process = self.date_processor.get_unprocessed_dates(today)
        
        if not dates_to_process:
            logger.info("No unprocessed dates found, backfill complete")
            return
        
        total_dates = len(dates_to_process)
        logger.info(f"Processing {total_dates} dates in backfill mode")
        logger.debug(f"Date range: {dates_to_process[0]} to {dates_to_process[-1]}")
        
        dates_processed = 0
        dates_failed = 0
        
        for idx, date_obj in enumerate(dates_to_process, 1):
            if self.shutdown_requested:
                logger.warning(f"Shutdown requested during backfill at date {date_obj} ({idx}/{total_dates})")
                break
            
            logger.debug(f"Processing date {idx}/{total_dates}: {date_obj}")
            datetime_obj = datetime.combine(date_obj, datetime.min.time())
            success = self._process_date(datetime_obj)
            
            if success:
                dates_processed += 1
            else:
                dates_failed += 1
            
            # Log progress periodically
            if idx % 10 == 0 or idx == total_dates:
                summary = self.metrics.get_summary()
                elapsed_time = time.time() - backfill_start_time
                avg_time_per_date = elapsed_time / idx if idx > 0 else 0
                remaining_dates = total_dates - idx
                estimated_remaining_time = avg_time_per_date * remaining_dates
                
                logger.info(
                    f"Backfill progress: {idx}/{total_dates} dates ({idx/total_dates*100:.1f}%), "
                    f"processed={summary['processed_count']}, errors={summary['error_count']}, "
                    f"success_rate={summary['success_rate']:.2%}, "
                    f"elapsed={elapsed_time:.1f}s, "
                    f"estimated_remaining={estimated_remaining_time:.1f}s"
                )
        
        backfill_time = time.time() - backfill_start_time
        summary = self.metrics.get_summary()
        logger.info(
            f"Backfill mode complete: dates_processed={dates_processed}, dates_failed={dates_failed}, "
            f"total_vcons_processed={summary['processed_count']}, total_errors={summary['error_count']}, "
            f"success_rate={summary['success_rate']:.2%}, total_time={backfill_time:.1f}s"
        )

    def _monitoring_mode(self):
        """Monitor for new dates/files after backfill."""
        logger.info("Starting monitoring mode")
        logger.debug(f"Monitoring mode started at {datetime.now().isoformat()}")
        
        poll_interval = self.config["processing"].get("poll_interval_seconds", 300)
        logger.debug(f"Poll interval set to {poll_interval} seconds")
        
        cycle_count = 0
        
        while not self.shutdown_requested:
            cycle_count += 1
            cycle_start_time = time.time()
            logger.debug(f"Starting monitoring cycle {cycle_count}")
            
            try:
                today = date.today()
                logger.debug(f"Checking for unprocessed dates up to {today}")
                unprocessed_dates = self.date_processor.get_unprocessed_dates(today)
                
                if unprocessed_dates:
                    logger.info(f"Found {len(unprocessed_dates)} new dates to process: {unprocessed_dates}")
                    for date_obj in unprocessed_dates:
                        if self.shutdown_requested:
                            logger.debug("Shutdown requested during monitoring, breaking date loop")
                            break
                        datetime_obj = datetime.combine(date_obj, datetime.min.time())
                        self._process_date(datetime_obj)
                else:
                    logger.debug(f"No new dates found (checked up to {today})")
                
                # Log metrics periodically
                if cycle_count % 5 == 0 or unprocessed_dates:
                    summary = self.metrics.get_summary()
                    logger.info(
                        f"Monitoring cycle {cycle_count} metrics: "
                        f"processed={summary['processed_count']}, "
                        f"errors={summary['error_count']}, "
                        f"skipped={summary['skipped_count']}, "
                        f"success_rate={summary['success_rate']:.2%}, "
                        f"dates_processed={summary['dates_processed_count']}, "
                        f"last_processed_date={summary['last_processed_date']}"
                    )
                
            except Exception as e:
                cycle_time = time.time() - cycle_start_time
                logger.error(f"Error in monitoring mode cycle {cycle_count}: error_type={type(e).__name__}, error={str(e)}, cycle_time={cycle_time:.3f}s", exc_info=True)
                self.metrics.record_error("monitoring_error")
            
            if not self.shutdown_requested:
                cycle_time = time.time() - cycle_start_time
                sleep_time = max(0, poll_interval - cycle_time)
                logger.debug(f"Monitoring cycle {cycle_count} completed in {cycle_time:.3f}s, sleeping for {sleep_time:.1f}s")
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        logger.info(f"Monitoring mode stopped after {cycle_count} cycles")

    def run(self):
        """Run the service."""
        service_start_time = time.time()
        logger.info("Starting vCon S3 Loader Service")
        logger.debug(f"Service start time: {datetime.now().isoformat()}")
        logger.debug(f"Configuration: bucket={self.config['s3']['bucket']}, post_url={self.config['post']['url']}, start_date={self.config['processing']['start_date']}")
        self.running = True
        
        try:
            # Test connections
            logger.debug("Testing service connections")
            redis_available = self.redis_client.is_available()
            logger.debug(f"Redis availability check: {redis_available}")
            
            if not redis_available:
                logger.warning("Redis is not available, continuing without deduplication")
                self.metrics.record_redis_unavailable()
            else:
                logger.info("Redis connection verified")
            
            # Test HTTP endpoint
            logger.debug("Testing HTTP endpoint connectivity")
            http_available = self.http_client.test_connection()
            logger.debug(f"HTTP endpoint availability check: {http_available}")
            if not http_available:
                logger.warning("HTTP endpoint connectivity test failed, but continuing")
            
            # Run backfill mode
            logger.debug("Entering backfill mode")
            self._backfill_mode()
            
            # Run monitoring mode
            if not self.shutdown_requested:
                logger.debug("Entering monitoring mode")
                self._monitoring_mode()
            else:
                logger.debug("Skipping monitoring mode due to shutdown request")
            
        except Exception as e:
            service_time = time.time() - service_start_time
            logger.error(f"Fatal error in service: error_type={type(e).__name__}, error={str(e)}, service_time={service_time:.3f}s", exc_info=True)
            raise
        finally:
            self.running = False
            service_time = time.time() - service_start_time
            # Save final checkpoint
            summary = self.metrics.get_summary()
            logger.info(f"Service stopped after {service_time:.1f}s. Final metrics: {summary}")
            logger.debug(f"Service stop time: {datetime.now().isoformat()}")
            logger.info("vCon S3 Loader Service stopped")


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="vCon S3 Loader Service")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (YAML or JSON)",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        help="Path to .env file (defaults to .env in current directory)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (default: INFO)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    try:
        # Load configuration (will load .env file automatically)
        config = Config(config_file=args.config, env_file=args.env_file)
        
        # Create and run service
        service = VConS3LoaderService(config)
        service.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

