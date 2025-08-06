"""Utility functions and classes."""

import threading
import time


class LoadingIndicator:
    """Shows a loading animation while waiting for responses."""
    
    def __init__(self, message="🤖 Assistant: "):
        self.message = message
        self.chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the loading animation."""
        if self.running:
            return
        self.running = True
        print(self.message, end="", flush=True)
        self.thread = threading.Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop the loading animation and clear the line."""
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.1)
        # Clear the loading indicator
        print("\r" + " " * (len(self.message) + 2) + "\r", end="", flush=True)
        print(self.message, end="", flush=True)
    
    def _animate(self):
        """Run the loading animation."""
        i = 0
        while self.running:
            print(f"\r{self.message}{self.chars[i % len(self.chars)]}", end="", flush=True)
            time.sleep(0.1)
            i += 1