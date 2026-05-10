"""
Discord Rich Presence integration for GroundStop
"""
import time
import threading
import logging
import warnings
import atexit

# Try to import pypresence
try:
    from pypresence import Presence
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False
    print("[Discord] Warning: pypresence not installed. Install with: pip install pypresence")

# Suppress pypresence asyncio warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*Enable tracemalloc.*")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('DiscordRPC')
logger.setLevel(logging.INFO)

# Suppress asyncio errors from pypresence
asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.CRITICAL)

class DiscordRichPresence:
    """Manages Discord Rich Presence for the simulator"""
    
    def __init__(self, client_id="1439026430146117662"):
        self.client_id = client_id
        self.RPC = None
        self.connected = False
        self.running = False
        self.thread = None
        self._wake_event = threading.Event()
        self._update_lock = threading.Lock()
        self._pending_update = None  # Queue for pending updates
        self._update_in_progress = False
        
        # Current state
        self.state = "In menu"
        self.details = "GroundStop - ATC Ground Control Sim"
        self.large_image = "icon"
        self.large_text = "GroundStop"
        self.start_time = None
    
    def connect(self):
        """Connect to Discord RPC"""
        if not PYPRESENCE_AVAILABLE:
            print("[Discord] pypresence library not available. Rich Presence disabled.")
            self.connected = False
            self.RPC = None
            return
        
        try:
            self.RPC = Presence(self.client_id)
            # Try to connect with a timeout
            self.RPC.connect()
            self.connected = True
            print("[Discord] Rich Presence connected successfully")
            logger.info("Discord Rich Presence connected successfully")
            # Queue initial update (will be processed by background thread)
            self.update_presence()
        except FileNotFoundError:
            print("[Discord] Discord is not running. Rich Presence disabled.")
            logger.warning("Discord is not running. Rich Presence disabled.")
            self.connected = False
            self.RPC = None
        except ConnectionRefusedError:
            print("[Discord] Discord RPC connection refused. Is Discord running?")
            logger.warning("Discord RPC connection refused. Is Discord running?")
            self.connected = False
            self.RPC = None
        except Exception as e:
            error_msg = str(e).lower()
            if "no pipe" in error_msg or "not found" in error_msg:
                print("[Discord] Discord is not running. Rich Presence disabled.")
                logger.warning("Discord is not running. Rich Presence disabled.")
            else:
                print(f"[Discord] Failed to connect: {e}")
                logger.warning(f"Failed to connect to Discord: {e}")
            self.connected = False
            self.RPC = None
    
    def disconnect(self):
        """Disconnect from Discord RPC and clear presence"""
        self.running = False
        self.connected = False  # Mark disconnected immediately to stop any pending updates
        
        if self._wake_event:
            self._wake_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)  # Shorter timeout
            self.thread = None
        
        if self.RPC:
            # Run cleanup in a timeout thread to prevent hanging
            def cleanup():
                try:
                    self.RPC.clear()
                except:
                    pass
                try:
                    self.RPC.close()
                except:
                    pass
            
            cleanup_thread = threading.Thread(target=cleanup, daemon=True)
            cleanup_thread.start()
            cleanup_thread.join(timeout=1.0)  # 1 second timeout for cleanup
            
            if not cleanup_thread.is_alive():
                logger.info("Discord Rich Presence disconnected")
        
        self.RPC = None
    
    def update_presence(self):
        """Queue a Discord presence update (non-blocking)"""
        if not self.connected or not self.RPC:
            return
        
        # Queue the update data - actual update happens in background thread
        update_data = {
            "state": self.state,
            "details": self.details,
            "large_image": self.large_image,
            "large_text": self.large_text
        }
        
        if self.start_time:
            update_data["start"] = self.start_time
        
        with self._update_lock:
            self._pending_update = update_data
        
        # Wake background thread to process update
        if self._wake_event:
            self._wake_event.set()
    
    def _do_update(self, update_data):
        """Actually perform the Discord update (called from background thread)"""
        if not self.connected or not self.RPC:
            return
        
        # Use a timeout thread to prevent hanging forever
        result = [None]  # Use list to allow modification in nested function
        error = [None]
        
        def update_with_timeout():
            try:
                self.RPC.update(**update_data)
                result[0] = True
            except Exception as e:
                error[0] = e
        
        update_thread = threading.Thread(target=update_with_timeout, daemon=True)
        update_thread.start()
        update_thread.join(timeout=2.0)  # 2 second timeout
        
        if update_thread.is_alive():
            # Update is hanging - disable Discord to prevent further issues
            logger.warning("Discord RPC update timed out - disabling")
            self.connected = False
            self.RPC = None
            return
        
        if error[0]:
            e = error[0]
            if isinstance(e, (ConnectionRefusedError, FileNotFoundError, BrokenPipeError)):
                # Connection lost - mark as disconnected
                logger.warning("Discord RPC connection lost")
                self.connected = False
                self.RPC = None
            elif isinstance(e, (RuntimeError, RuntimeWarning, AssertionError)):
                # Suppress asyncio warnings - these are harmless pypresence internal issues
                error_str = str(e).lower()
                if "event loop" not in error_str and "coroutine" not in error_str and "overlapped" not in error_str:
                    logger.warning(f"Failed to update Discord presence: {e}")
            else:
                # Only log non-asyncio errors
                error_str = str(e).lower()
                if all(x not in error_str for x in ["event loop", "coroutine", "overlapped", "proactor"]):
                    logger.warning(f"Failed to update Discord presence: {e}")
    
    def set_state(self, state, details=None):
        """Update the current state and optionally details"""
        try:
            self.state = state
            if details:
                self.details = details
            self.update_presence()
        except Exception as e:
            # Silently catch all errors - Discord should never affect simulation
            self.connected = False
            self.RPC = None
    
    def set_in_menu(self):
        """Set presence to main menu"""
        try:
            self.state = "In menu"
            self.details = "GroundStop - ATC Ground Control Sim"
            self.start_time = None
            self.update_presence()
        except Exception as e:
            # Silently catch all errors - Discord should never affect simulation
            self.connected = False
            self.RPC = None
    
    def set_in_simulation(self, airport_code="", aircraft_count=0, active_actions=None):
        """Set presence to active simulation
        
        Args:
            airport_code: ICAO code of the airport
            aircraft_count: Number of aircraft being controlled
            active_actions: Dict with action states (ground_stop, gate_hold, gdp, emergency_stop)
        """
        # Quick check before doing anything - if not connected, bail immediately
        if not self.connected or not self.RPC:
            return
        
        try:
            # Build state string with active actions
            action_parts = []
            if active_actions:
                if active_actions.get('emergency_stop'):
                    action_parts.append("EMERGENCY")
                elif active_actions.get('ground_stop'):
                    action_parts.append("GS")
                if active_actions.get('gate_hold') and not active_actions.get('emergency_stop'):
                    action_parts.append("GATE HOLD")
                if active_actions.get('gdp'):
                    gdp_mins = active_actions.get('gdp_delay', 15)
                    action_parts.append(f"GDP+{gdp_mins}m")
            
            if action_parts:
                self.state = f"{aircraft_count} aircraft | {' | '.join(action_parts)}"
            else:
                self.state = f"Controlling {aircraft_count} aircraft"
            
            if airport_code:
                self.details = f"Ground Control - {airport_code}"
            else:
                self.details = "Ground Control"
            
            if not self.start_time:
                self.start_time = int(time.time())
            
            # Only update if actually connected - double check to prevent hangs
            if self.connected and self.RPC:
                self.update_presence()
        except Exception as e:
            # Silently catch all errors - Discord should never affect simulation
            # If Discord fails, just mark as disconnected to prevent further attempts
            self.connected = False
            self.RPC = None
    
    def start_background_update(self):
        """Start background thread for periodic updates"""
        if self.running:
            return
        
        self.running = True
        self._wake_event.clear()
        self.thread = threading.Thread(target=self._background_loop, daemon=True)
        self.thread.start()
    
    def _background_loop(self):
        """Background loop to process updates and keep connection alive"""
        while self.running:
            # Wake periodically or immediately when update queued or shutting down
            self._wake_event.wait(timeout=15)
            self._wake_event.clear()
            if not self.running:
                break
            if self.connected:
                try:
                    # Check for pending update
                    update_data = None
                    with self._update_lock:
                        if self._pending_update:
                            update_data = self._pending_update
                            self._pending_update = None
                    
                    # Process the update in background thread (won't block main)
                    if update_data:
                        self._do_update(update_data)
                except (RuntimeError, Exception):
                    # Silently ignore all errors in background thread
                    pass

# Global instance
_discord_rpc = None

def init_discord_rpc():
    """Initialize Discord Rich Presence"""
    global _discord_rpc
    if _discord_rpc is None:
        try:
            _discord_rpc = DiscordRichPresence()
            _discord_rpc.connect()
            if _discord_rpc.connected:
                _discord_rpc.start_background_update()
                print("[Discord] Rich Presence initialized successfully")
            else:
                print("[Discord] Rich Presence disabled (Discord not running or unavailable)")
        except Exception as e:
            print(f"[Discord] Failed to initialize Rich Presence: {e}")
            _discord_rpc = None
    return _discord_rpc

def get_discord_rpc():
    """Get the Discord RPC instance"""
    return _discord_rpc

def shutdown_discord_rpc():
    """Shutdown Discord Rich Presence"""
    global _discord_rpc
    if _discord_rpc:
        _discord_rpc.disconnect()
        _discord_rpc = None

# Register atexit handler to ensure Discord is cleared on any exit
atexit.register(shutdown_discord_rpc)
