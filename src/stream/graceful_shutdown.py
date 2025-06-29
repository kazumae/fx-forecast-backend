"""
Graceful Shutdown Handler for TraderMade Stream
"""
import signal
import sys
import time
import threading
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .websocket_manager import WebSocketManager
    from .data_processor import DataProcessor


class GracefulShutdownHandler:
    """Handles graceful shutdown of the streaming application"""
    
    def __init__(
        self, 
        websocket_manager: Optional['WebSocketManager'] = None,
        data_processor: Optional['DataProcessor'] = None,
        timeout: int = 10
    ):
        """
        Initialize graceful shutdown handler
        
        Args:
            websocket_manager: WebSocket manager instance
            data_processor: Data processor instance
            timeout: Maximum time to wait for shutdown (seconds)
        """
        self.websocket_manager = websocket_manager
        self.data_processor = data_processor
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Shutdown state
        self.shutdown_event = threading.Event()
        self.is_shutting_down = False
        self._shutdown_lock = threading.Lock()
        
        # Track original signal handlers
        self._original_sigterm = None
        self._original_sigint = None
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        # Store original handlers
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        
        self.logger.info("Graceful shutdown handlers registered")
        
    def restore_signal_handlers(self):
        """Restore original signal handlers"""
        # Only restore in main thread
        try:
            if self._original_sigterm is not None:
                signal.signal(signal.SIGTERM, self._original_sigterm)
            if self._original_sigint is not None:
                signal.signal(signal.SIGINT, self._original_sigint)
        except ValueError as e:
            # This can happen when called from a non-main thread
            self.logger.debug(f"Cannot restore signal handlers from non-main thread: {e}")
            
    def _handle_signal(self, signum: int, frame):
        """
        Handle shutdown signals
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        with self._shutdown_lock:
            if self.is_shutting_down:
                self.logger.warning("Shutdown already in progress, ignoring signal")
                return
                
            self.is_shutting_down = True
        
        # Get signal name
        try:
            signal_name = signal.Signals(signum).name
        except:
            signal_name = str(signum)
            
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown")
        
        # Start shutdown in a separate thread to avoid blocking signal handler
        shutdown_thread = threading.Thread(
            target=self._shutdown_sequence,
            name="Shutdown-Thread",
            daemon=True
        )
        shutdown_thread.start()
        
        # Wait for shutdown with timeout
        shutdown_thread.join(timeout=self.timeout)
        
        if shutdown_thread.is_alive():
            self.logger.error(f"Graceful shutdown timeout after {self.timeout}s, forcing exit")
            self._force_exit(1)
        
    def _shutdown_sequence(self):
        """Execute shutdown sequence"""
        try:
            start_time = time.time()
            
            # Step 1: Stop accepting new data
            self.logger.info("Step 1/5: Stopping new data reception")
            if self.websocket_manager:
                self.websocket_manager._should_run = False
            
            # Step 2: Process remaining data
            self.logger.info("Step 2/5: Processing remaining data")
            if self.data_processor:
                # Give data processor time to finish current operations
                time.sleep(0.5)
                # Display final summary
                self.data_processor.display_summary()
            
            # Step 3: Close WebSocket connection
            self.logger.info("Step 3/5: Closing WebSocket connection")
            if self.websocket_manager:
                self.websocket_manager.close()
            
            # Step 4: Log error summary
            self.logger.info("Step 4/5: Generating error summary")
            if self.websocket_manager and hasattr(self.websocket_manager, 'error_handler'):
                error_summary = self.websocket_manager.error_handler.get_error_summary()
                if error_summary["total_errors"] > 0:
                    self.logger.info(f"Error Summary: {error_summary}")
            
            # Step 5: Final cleanup
            self.logger.info("Step 5/5: Final cleanup")
            self.restore_signal_handlers()
            
            # Calculate shutdown time
            shutdown_time = time.time() - start_time
            self.logger.info(f"Graceful shutdown completed in {shutdown_time:.2f} seconds")
            
            # Set shutdown event
            self.shutdown_event.set()
            
            # Exit successfully
            self._force_exit(0)
            
        except Exception as e:
            self.logger.error(f"Error during shutdown sequence: {e}", exc_info=True)
            self._force_exit(1)
    
    def _force_exit(self, exit_code: int):
        """
        Force exit with given code
        
        Args:
            exit_code: Exit code (0 for success, non-zero for error)
        """
        self.logger.info(f"Exiting with code {exit_code}")
        # Use os._exit to avoid any cleanup that might hang
        import os
        os._exit(exit_code)
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown to complete
        
        Args:
            timeout: Maximum time to wait (None for infinite)
            
        Returns:
            True if shutdown completed, False if timeout
        """
        return self.shutdown_event.wait(timeout)
    
    def trigger_shutdown(self, reason: str = "Manual trigger"):
        """
        Manually trigger shutdown
        
        Args:
            reason: Reason for shutdown
        """
        self.logger.info(f"Manual shutdown triggered: {reason}")
        self._handle_signal(signal.SIGTERM, None)