"""
AsdeSim - Airport Surface Detection Equipment Simulator
Main entry point with launch menu
"""
import sys
import os
import ctypes
import json
import platform


import argparse
import time

# Set SDL environment variables BEFORE importing pygame
# These improve multi-display and focus handling
os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'
os.environ['SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS'] = '1'
os.environ['SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS'] = '0'
# Better DPI handling for multi-monitor setups
os.environ['SDL_VIDEO_CENTERED'] = '1'
os.environ['SDL_WINDOWS_DPI_AWARENESS'] = 'permonitorv2'  # Per-monitor DPI awareness
# macOS-specific display improvements
if platform.system() == "Darwin":
    os.environ['SDL_RENDER_DRIVER'] = 'metal'  # Use Metal renderer on macOS
    os.environ['SDL_VIDEO_HIGHDPI_DISABLED'] = '0'  # Enable high DPI support
    os.environ['SDL_WINDOWPOS_CENTERED_DISPLAY'] = '0'  # Center on primary display
    os.environ['SDL_MAC_FULLSCREEN_MENU'] = '1'  # Show menu bar in fullscreen on macOS

import pygame


from src.rendering.menu import MainMenu
from src.rendering.settings import SettingsMenu
from src.rendering.airportMenu import AirportMenu
from src.rendering.simulation import SimulationScreen
from src.rendering.error_dialog import show_error_dialog
from src.rendering.loading_screen import LoadingScreen
from discord_rich import init_discord_rpc, get_discord_rpc, shutdown_discord_rpc


class Application:
    """Main application controller"""
    
    def __init__(self, dev_mode=False):
        # Enable DPI awareness based on platform
        if platform.system() == "Windows":
            try:
                # Windows 8.1+: Per-monitor DPI awareness v2
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except:
                try:
                    # Fallback for older Windows versions
                    ctypes.windll.user32.SetProcessDPIAware()
                except:
                    pass  # If DPI awareness fails, continue anyway
        elif platform.system() == "Darwin":
            # macOS: Enable Retina display support
            try:
                import AppKit
                # Only try to set activation policy if NSApp is available
                if hasattr(AppKit, 'NSApp') and AppKit.NSApp is not None:
                    try:
                        AppKit.NSApp.setActivationPolicy_(0)  # Regular app policy
                    except AttributeError as e:
                        print(f"ℹ NSApp activation policy failed: {e}")
                        # Continue anyway - this is not critical
                else:
                    print("ℹ NSApp not available during initialization")
            except ImportError:
                pass  # AppKit not available, continue anyway
            except Exception as e:
                print(f"ℹ AppKit initialization failed: {e}")
                pass  # Continue anyway if AppKit fails
        
        pygame.init()
        pygame.mixer.init()  # Initialize audio mixer
        
        # Store dev mode flag
        self.dev_mode = dev_mode
        if self.dev_mode:
            print("\n" + "="*60)
            print("DEVELOPER MODE ENABLED")
            print("="*60 + "\n")
        
        # Detect available display modes
        self.detect_display_modes()
        
        # Set up display with better multi-monitor support
        self.fullscreen = False
        if self.fullscreen:
            # Fullscreen mode - add hardware acceleration and scaling flags
            flags = pygame.FULLSCREEN
            if platform.system() == "Darwin":
                flags |= pygame.HWSURFACE | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode((0, 0), flags)
        else:
            # Windowed mode with resizable window and DPI scaling
            info = pygame.display.Info()
            default_width = int(info.current_w * 0.8)
            default_height = int(info.current_h * 0.8)
            flags = pygame.RESIZABLE
            if platform.system() == "Darwin":
                flags |= pygame.HWSURFACE | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode((default_width, default_height), flags)
        
        pygame.display.set_caption("GroundStop - Airport Ground Control Simulator")
        
        # Store original display size for resize handling
        self.display_size = self.screen.get_size()
        
        # Show startup loading screen with minimum display time
        startup_start_time = time.time()
        startup_screen = LoadingScreen(self.screen)
        startup_screen.update(0.2, "Loading application...", "")
        startup_screen.render()
        
        # Load icon and set window properties
        startup_screen.update(0.6, "Loading resources...", "")
        startup_screen.render()
        
        self.icon = pygame.image.load("data/images/aircraft_icon_norm.png")

        # Set app ID for Windows taskbar (Windows only)
        if platform.system() == "Windows":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AsdeSim.App")
        pygame.display.set_icon(self.icon)  
        
        # Print display information in dev mode
        if self.dev_mode:
            print(f"\nDisplay Info:")
            print(f"  Screen Size: {self.display_size}")
            print(f"  Fullscreen: {self.fullscreen}")
            try:
                info = pygame.display.Info()
                print(f"  Current Display: {info.current_w}x{info.current_h}")
                print(f"  Per-Monitor DPI: Enabled (Windows 8.1+)")
                print(f"  Hint: Press F11 to toggle fullscreen/windowed mode\n")
            except:
                pass
        
        # Create clock for FPS control
        self.clock = pygame.time.Clock()
        
        # Initialize Discord Rich Presence
        startup_screen.update(0.7, "Connecting to Discord...", "")
        startup_screen.render()
        self.discord_rpc = init_discord_rpc()
        
        # Prepare main menu
        startup_screen.update(0.9, "Preparing main menu...", "")
        startup_screen.render()
        
        # Ensure startup screen displays for at least 5 seconds
        elapsed_time = time.time() - startup_start_time
        min_display_time = 2.0  # seconds
        if elapsed_time < min_display_time:
            remaining_time = min_display_time - elapsed_time
            startup_screen.update(1.0, "Starting...", "")
            startup_screen.render()
            time.sleep(remaining_time)
        
        # Screen management
        self.current_screen = None
        self.show_main_menu()
        
        self.running = True
    
    def detect_display_modes(self):
        """Detect and log available display modes"""
        try:
            modes = pygame.display.list_modes()
            if self.dev_mode:
                print(f"Available display modes: {len(modes)}")
                for i, mode in enumerate(modes[:5]):  # Show first 5 modes
                    print(f"  Mode {i}: {mode[0]}x{mode[1]} @ {mode[2]}Hz")
                if len(modes) > 5:
                    print(f"  ... and {len(modes) - 5} more modes")
            
            # Get current display info
            info = pygame.display.Info()
            if self.dev_mode:
                print(f"Current display: {info.current_w}x{info.current_h} @ {info.refresh_rate}Hz")
                print(f"Hardware acceleration: {'Yes' if info.hw_accel else 'No'}")
        except Exception as e:
            if self.dev_mode:
                print(f"Error detecting display modes: {e}")
    
    def show_main_menu(self):
        """Switch to main menu"""
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)  # Reset cursor
        self.current_screen = MainMenu(self.screen, self)
        # Update Discord presence (wrapped in error handling)
        try:
            if self.discord_rpc:
                self.discord_rpc.set_in_menu()
        except Exception:
            # Silently ignore Discord errors - don't let them affect the app
            pass
    
    def show_settings(self, simulation_screen=None):
        """Switch to settings menu"""
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)  # Reset cursor
        self.current_screen = SettingsMenu(self.screen, self.show_main_menu, simulation_screen)
    
    def show_airport_menu(self):
        """Switch to airport/scenario selection menu"""
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)  # Reset cursor
        self.current_screen = AirportMenu(self.screen, self)
    
    def show_simulation(self, scenario):
        """Switch to simulation screen with loading screen."""
        # Create loading screen
        loading_screen = LoadingScreen(self.screen)

        # Show initial loading state
        loading_screen.update(0.0, "Initializing simulation...", "")
        loading_screen.render()

        # Initialize simulation directly without brief modal
        try:
            self.current_screen = SimulationScreen(
                screen=self.screen,
                scenario=scenario,
                loading_callback=loading_screen,
                app=self
            )
        except Exception as e:
            print(f"❌ Failed to start simulation: {e}")
            return
    

    def continue_simulation(self, save_data):
        """Continue a previously saved simulation with enhanced loading"""
        from src.rendering.simulation import SimulationScreen
        from src.rendering.loading_screen import LoadingScreen
        
        # Validate save data first
        if not save_data:
            print("❌ No save data available")
            return
        
        metadata = save_data.get('metadata', {})
        airport_code = metadata.get('airport_code', 'Unknown')
        airport_name = metadata.get('airport_name', 'Unknown Airport')
        save_time = metadata.get('datetime', 'Unknown time')
        
        print(f"📂 Loading saved simulation from {save_time}")
        print(f"✈️ Airport: {airport_code} - {airport_name}")
        
        # Create loading screen
        loading_screen = LoadingScreen(self.screen)
        
        # Enhanced loading progress
        loading_steps = [
            (0.1, "Validating save data...", "Checking save file integrity"),
            (0.2, "Loading airport information...", f"Preparing {airport_code} data"),
            (0.3, "Initializing simulation...", "Setting up simulation environment"),
            (0.5, "Restoring aircraft state...", "Loading aircraft positions and routes"),
            (0.7, "Rebuilding ATC commands...", "Restoring air traffic control"),
            (0.8, "Loading weather data...", "Fetching current weather"),
            (0.9, "Restoring camera position...", "Setting view perspective"),
            (1.0, "Finalizing...", "Ready to resume")
        ]
        
        # Show loading progress
        for progress, main_text, detail_text in loading_steps:
            loading_screen.update(progress, main_text, detail_text)
            loading_screen.render()
            pygame.display.flip()
            pygame.time.wait(200)  # Brief pause for visual feedback
        
        # Create simulation screen with saved data
        try:
            self.current_screen = SimulationScreen(
                self.screen,
                None,  # No scenario - loading from save
                dev_mode=self.dev_mode,
                loading_callback=loading_screen,
                app=self,
                save_data=save_data  # Pass the save data
            )
            
            print(f"✅ Successfully resumed simulation from {save_time}")
            
        except Exception as e:
            print(f"❌ Failed to resume simulation: {e}")
            # Delete corrupted save file and fallback to main menu
            try:
                import os
                save_file = "data/saves/current_simulation.json"
                if os.path.exists(save_file):
                    os.remove(save_file)
                    print("🗑️  Removed corrupted save file")
            except Exception as cleanup_error:
                print(f"ℹ Could not remove save file: {cleanup_error}")
            
            # Fallback to main menu
            self.show_main_menu()
    
    def run(self):
        """Main application loop with error handling"""
        try:
            while self.running:
                dt = self.clock.tick(60) / 1000.0  # Delta time in seconds
                
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    
                    # Handle window resize and display changes
                    elif event.type == pygame.VIDEORESIZE:
                        # Window was resized (dragged to different display or manually resized)
                        new_size = (event.w, event.h)
                        if new_size != self.display_size and not self.fullscreen:
                            if self.dev_mode:
                                print(f"Display resize: {self.display_size} -> {new_size}")
                            self.display_size = new_size
                            try:
                                # Recreate screen with new size (only in windowed mode)
                                flags = pygame.RESIZABLE
                                if platform.system() == "Darwin":
                                    flags |= pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.SCALED
                                self.screen = pygame.display.set_mode(new_size, flags)
                                # Update current screen with new surface
                                if hasattr(self.current_screen, 'screen'):
                                    self.current_screen.screen = self.screen
                                # Notify current screen of resize
                                if hasattr(self.current_screen, 'handle_resize'):
                                    self.current_screen.handle_resize(new_size)
                            except Exception as e:
                                if self.dev_mode:
                                    print(f"Error handling resize: {e}")
                                # Continue with old screen if resize fails
                                pass
                    
                    # Toggle fullscreen with F11
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                        self.fullscreen = not self.fullscreen
                        if self.dev_mode:
                            print(f"Toggling fullscreen: {self.fullscreen}")
                        try:
                            if self.fullscreen:
                                # Enter fullscreen mode
                                flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
                                if platform.system() == "Darwin":
                                    # On macOS, use Metal renderer for better performance
                                    os.environ['SDL_RENDER_DRIVER'] = 'metal'
                                self.screen = pygame.display.set_mode((0, 0), flags)
                                if self.dev_mode:
                                    info = pygame.display.Info()
                                    print(f"Entered fullscreen mode: {info.current_w}x{info.current_h}")
                            else:
                                # Exit fullscreen mode
                                info = pygame.display.Info()
                                windowed_size = (int(info.current_w * 0.8), int(info.current_h * 0.8))
                                flags = pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF
                                if platform.system() == "Darwin":
                                    flags |= pygame.SCALED
                                self.screen = pygame.display.set_mode(windowed_size, flags)
                                if self.dev_mode:
                                    print(f"Exited fullscreen mode: {windowed_size[0]}x{windowed_size[1]}")
                            
                            # Update display size and notify screens
                            self.display_size = self.screen.get_size()
                            if hasattr(self.current_screen, 'screen'):
                                self.current_screen.screen = self.screen
                            # Notify current screen of display change
                            if hasattr(self.current_screen, 'handle_display_change'):
                                self.current_screen.handle_display_change(self.display_size, self.fullscreen)
                            
                        except Exception as e:
                            if self.dev_mode:
                                print(f"Error toggling fullscreen: {e}")
                            # Revert on error
                            self.fullscreen = not self.fullscreen
                    
                    # Handle window focus events - keep running even when not focused
                    elif event.type == pygame.ACTIVEEVENT:
                        # Don't pause or stop when losing focus
                        pass
                    elif event.type == pygame.WINDOWFOCUSLOST:
                        # Keep running when focus is lost
                        pass
                    elif event.type == pygame.WINDOWMINIMIZED:
                        # Keep running when minimized
                        pass
                    else:
                        self.current_screen.handle_event(event)
                
                # Update and render current screen
                self.current_screen.update(dt)
                self.current_screen.render()
                
                pygame.display.flip()
        except Exception as e:
            # Show stylish error dialog
            print(f"\n{'='*60}")
            print(f"ERROR: {type(e).__name__}: {str(e)}")
            print(f"{'='*60}\n")
            import traceback
            traceback.print_exc()
            
            # Show error dialog if screen is available
            if hasattr(self, 'screen') and self.screen:
                show_error_dialog(self.screen, e)
        finally:
            # Cleanup Discord RPC
            shutdown_discord_rpc()
            pygame.quit()
            sys.exit()


def print_aircraft_icao():
    """Print all aircraft ICAO types from aircraft.json"""
    try:
        with open('aircraft.json', 'r') as f:
            data = json.load(f)
        
        aircraft_list = data.get('aircraft', [])
        print(f"\nAircraft ICAO Types ({len(aircraft_list)} total):\n")
        
        for aircraft in aircraft_list:
            icao = aircraft.get('icao_code', 'N/A')
            print(icao)
        
        print()  # Empty line at end
        
    except FileNotFoundError:
        print("Error: aircraft.json not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in aircraft.json")
        sys.exit(1)


def main():
    """Initialize and run the application"""
    try:
        # Parse command-line arguments
        parser = argparse.ArgumentParser(description='AsdeSim - Airport Ground Control Simulator')
        parser.add_argument('-aircrafts', action='store_true', 
                            help='Print all aircraft ICAO types and exit')
        parser.add_argument('-dev', action='store_true',
                            help='Start in developer mode with advanced debugging features')
        
        args = parser.parse_args()
        
        # Handle -aircrafts flag
        if args.aircrafts:
            print_aircraft_icao()
            sys.exit(0)
        
        # Normal application startup
        app = Application(dev_mode=args.dev)
        app.run()
    except Exception as e:
        # Catch initialization errors
        print(f"\n{'='*60}")
        print(f"INITIALIZATION ERROR: {type(e).__name__}: {str(e)}")
        print(f"{'='*60}\n")
        import traceback
        traceback.print_exc()
        
        # Try to show error dialog if pygame initialized
        try:
            if pygame.get_init():
                screen = pygame.display.get_surface()
                if screen:
                    show_error_dialog(screen, e)
        except:
            pass  # If we can't show dialog, just exit
        
        sys.exit(1)


if __name__ == "__main__":
    main()
