#!/usr/bin/env python3
"""
REO Scheduler - Runs the dashboard generation periodically.

This script runs generate_dashboard.py on a schedule (default: every 5 minutes).
It's designed to run in a Docker container as a long-running service.
"""

import time
import signal
import sys
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/output/scheduler.log')
    ]
)
logger = logging.getLogger('REO-Scheduler')


class Scheduler:
    """Simple scheduler for running tasks periodically."""

    def __init__(self, interval_minutes=5):
        """
        Initialize the scheduler.

        Args:
            interval_minutes: Minutes between runs (default: 5)
        """
        self.interval_seconds = interval_minutes * 60
        self.running = True
        logger.info(f"Scheduler initialized with {interval_minutes} minute interval")

    def run_task(self):
        """
        Run the dashboard generation task.

        This imports and calls the main function from generate_dashboard.py
        """
        logger.info("Starting dashboard generation...")
        start_time = time.time()

        try:
            # Import here to get fresh module state each run
            from generate_dashboard import main

            # Run the dashboard generation
            success = main()

            elapsed = time.time() - start_time

            if success:
                logger.info(f"✅ Dashboard generation completed in {elapsed:.2f}s")
            else:
                logger.error(f"❌ Dashboard generation failed after {elapsed:.2f}s")

            return success

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Exception during dashboard generation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start(self):
        """
        Start the scheduler loop.

        Runs immediately, then waits for the interval before running again.
        Handles graceful shutdown on SIGTERM/SIGINT.
        """
        logger.info("🚀 Scheduler started")
        logger.info(f"⏰ Schedule: Run every {self.interval_seconds // 60} minutes")

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Initial run
        logger.info("Running initial dashboard generation...")
        self.run_task()

        # Scheduler loop
        while self.running:
            try:
                logger.info(f"⏳ Waiting {self.interval_seconds // 60} minutes until next run...")

                # Sleep in small increments to allow signal handling
                for _ in range(self.interval_seconds):
                    if not self.running:
                        break
                    time.sleep(1)

                if self.running:
                    logger.info("⏰ Time for next run!")
                    self.run_task()

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Continue running even if one run fails

        logger.info("🛑 Scheduler stopped")

    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False


def main():
    """Main entry point for the scheduler."""
    # Read interval from environment variable (default: 5 minutes)
    interval_minutes = int(os.getenv('REO_SCHEDULER_INTERVAL_MINUTES', '5'))

    # Create and start scheduler
    scheduler = Scheduler(interval_minutes=interval_minutes)
    scheduler.start()


if __name__ == '__main__':
    main()
