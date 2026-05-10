"""
ATC Command System
Handles parsing and execution of ATC commands
References commands.txt for available commands
"""
import os
import pygame
import sys
import logging
import random

logger = logging.getLogger('ATCCommands')

class ATCCommandProcessor:
    """Process and execute ATC commands"""
    
    def __init__(self, aircraft_manager=None, airport_data=None):
        # Phonetic alphabet for taxiways
        self.phonetics = {
            'a': 'Alpha', 'b': 'Bravo', 'c': 'Charlie', 'd': 'Delta',
            'e': 'Echo', 'f': 'Foxtrot', 'g': 'Golf', 'h': 'Hotel',
            'i': 'India', 'j': 'Juliet', 'k': 'Kilo', 'l': 'Lima',
            'm': 'Mike', 'n': 'November', 'o': 'Oscar', 'p': 'Papa',
            'q': 'Quebec', 'r': 'Romeo', 's': 'Sierra', 't': 'Tango',
            'u': 'Uniform', 'v': 'Victor', 'w': 'Whiskey', 'x': 'X-ray',
            'y': 'Yankee', 'z': 'Zulu'
        }
        self.aircraft_manager = aircraft_manager
        self.airport_data = airport_data
        print("ATC Command Processor initialized")
    
    def to_phonetic(self, letter):
        """Convert letter to phonetic"""
        return self.phonetics.get(letter.lower(), letter.upper())
    
    def find_aircraft(self, callsign):
        """Find aircraft by callsign or flight number"""
        if not self.aircraft_manager:
            return None
        
        # Try flight number first (just the number)
        aircraft = self.aircraft_manager.get_aircraft_by_flight_number(callsign)
        if aircraft:
            return aircraft
        
        # Try full callsign
        aircraft = self.aircraft_manager.get_aircraft_by_callsign(callsign)
        return aircraft
    
    def parse_command(self, command):
        """Parse a command string - always expects callsign/number first
        
        Format: [number] [command] [args...]
        Example: 123 pa
        Example: 123 t02ua (taxi to 02 via U A)
        """
        if not command or not command.strip():
            return None, []
        
        # Remove leading slash if present
        cmd = command.strip()
        if cmd.startswith('/'):
            cmd = cmd[1:].strip()
        
        # Split into parts
        parts = cmd.split()
        if not parts:
            return None, []
        
        # Special commands that don't need callsign
        special_commands = ['help', 'clear', 'quit', 'shortcuts']
        if parts[0].lower() in special_commands:
            return parts[0].lower(), []
        
        # Callsign-first format: [number/callsign] [command] [args...]
        if len(parts) >= 2:
            # Accept just numbers (like "123") or full callsigns (like "AAL123")
            callsign = parts[0]
            command_name = parts[1].lower()
            additional_args = parts[2:] if len(parts) > 2 else []
            
            # Put callsign as first argument
            args = [callsign] + additional_args
            return command_name, args
        
        # If only one part, might be a special command
        return None, []
    
    def execute(self, command, output_callback):
        """
        Execute an ATC command (supports multiple commands)
        
        Args:
            command: Command string to execute (can be multiple commands)
                    Example: "123 pa ex02" executes both pushback and expect runway
            output_callback: Function to call with output text
        
        Returns:
            bool: True if command was valid, False otherwise
        """
        # Check if this is a combined command (multiple commands for same aircraft)
        # Format: [number] [cmd1] [cmd2] [cmd3]...
        # Example: 123 pa ex02 (pushback + expect runway 02)
        
        # Strip leading slash if present
        cmd_str = command.strip()
        if cmd_str.startswith('/'):
            cmd_str = cmd_str[1:].strip()
        
        parts = cmd_str.split()
        
        # Check if we have at least 3 parts and first part looks like a callsign
        if len(parts) >= 3:
            # First part should be callsign (number or alphanumeric)
            callsign = parts[0]
            
            # Check if this is a combined command by seeing if we have multiple command-like parts
            # Known command patterns
            known_short_commands = ['pa', 'pb', 'ct', 'cto', 'h', 'to', 'x']
            
            # Count how many parts look like commands (not taxiway arguments)
            command_count = 0
            for i in range(1, len(parts)):
                part = parts[i].lower()
                # Check if this part looks like a command
                is_command = (part in known_short_commands or 
                             part.startswith(('ex', 'cr', 'r', 'h')) and len(part) > 1)
                if is_command:
                    command_count += 1
            
            # If we have 2+ commands, this is a combined command
            if command_count >= 2:
                # This is a combined command
                # Output the raw command once
                output_callback(command)
                
                commands = parts[1:]  # All remaining parts are commands
                
                # Execute each command separately (without outputting)
                # Pass is_combined=True to prevent individual readbacks
                success = True
                readback_parts = []
                for cmd in commands:
                    # Build individual command string
                    individual_cmd = f"{callsign} {cmd}"
                    if not self._execute_single(individual_cmd, output_callback, suppress_output=True, is_combined=True):
                        success = False
                        logger.warning(f"[{callsign}] Command failed: {individual_cmd}")
                    else:
                        if cmd.lower() == 'pa':
                            readback_parts.append("pushback")
                        elif cmd.lower().startswith('ex'):
                            runway = cmd[2:].upper()
                            readback_parts.append(("expect_runway", {"runway": runway}))
                        elif cmd.lower().startswith('cr'):
                            runway = cmd[2:].upper()
                            readback_parts.append(("cross", {"runway": runway}))
                        elif cmd.lower().startswith('r') and len(cmd) > 1:
                            # Taxi command - parse runway and taxiways
                            cmd_part = cmd[1:]
                            if len(cmd_part) >= 2 and cmd_part[:2].isdigit():
                                runway = cmd_part[:2]
                                via = list(cmd_part[2:].upper())
                                readback_parts.append(("taxi", {"destination": f"runway {runway}", "via": via}))
                            elif cmd_part.lower().startswith('p'):
                                via = list(cmd_part[1:].upper())
                                readback_parts.append(("taxi", {"destination": "parking", "via": via}))
                        elif cmd.lower().startswith('h') and len(cmd) > 1:
                            # Hold short command
                            runway = cmd[1:].upper()
                            readback_parts.append(("hold", {"runway": runway}))
                        elif cmd.lower() == 'h':
                            # Hold position
                            readback_parts.append(("hold", {}))
                        elif cmd.lower() in ['ct', 'cto', 'to']:
                            readback_parts.append("contact_tower")
                
                # Now send a single combined readback
                aircraft = self.find_aircraft(callsign)
                if aircraft and readback_parts:
                    # Build combined readback WITHOUT callsign on each part
                    readback_texts = []
                    for part in readback_parts:
                        if isinstance(part, tuple):
                            clearance_type, details = part
                            readback_texts.append(aircraft._generate_realistic_readback(clearance_type, details, include_callsign=False))
                        elif part == "pushback":
                            readback_texts.append(aircraft._generate_realistic_readback("pushback", include_callsign=False))
                        elif part == "contact_tower":
                            readback_texts.append(aircraft._generate_realistic_readback("contact_tower", include_callsign=False))
                        elif part == "hold":
                            readback_texts.append(aircraft._generate_realistic_readback("hold", include_callsign=False))
                    
                    # Combine readbacks with callsign only at the end
                    # Add a realistic opener
                    opener = random.choice(["Roger", "Wilco", "Copy", "Affirm"])
                    combined_parts = ", ".join(readback_texts)
                    combined_readback = f"{opener}, {combined_parts}, {aircraft.get_callsign()}"
                    
                    logger.debug(f"[COMBINED] Scheduling combined readback: {combined_readback}")
                    aircraft._schedule_radio(combined_readback, is_atc=False)
                else:
                    logger.warning(f"[COMBINED] No aircraft found for {callsign} or no readback_parts: {readback_parts}")
                
                return success
        
        # Single command
        return self._execute_single(command, output_callback)
    
    def _execute_single(self, command, output_callback, suppress_output=False, is_combined=False):
        """Execute a single ATC command
        
        Args:
            command: Single command string
            output_callback: Function to call with output text
            suppress_output: If True, don't output the command (used for combined commands)
            is_combined: If True, skip individual readbacks (combined readback will be sent)
            
        Returns:
            bool: True if command was valid, False otherwise
        """
        cmd_name, args = self.parse_command(command)
        
        if not cmd_name:
            return False
        
        # Command routing - each abbreviation is its own command
        # NOTE: raw command is NOT echoed here; each cmd_* method outputs proper ATC phraseology
        if cmd_name == "help":
            return self.cmd_help(args, output_callback)
        elif cmd_name == "clear":
            return self.cmd_clear(args, output_callback)

        # Commands from commands.txt
        elif cmd_name == "pa":
            return self.cmd_pa(args, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("r") and len(cmd_name) > 1:
            # Taxi commands like r02ua, r14abc, etc.
            return self.cmd_taxi(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name == "h":
            return self.cmd_hold_position(args, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("ht") and len(cmd_name) > 2:
            # Hold short taxiway: htF = hold short of taxiway Foxtrot
            return self.cmd_hold_short_taxiway(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("h") and len(cmd_name) > 1:
            # Hold short runway commands like h02
            return self.cmd_hold(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("cr") and len(cmd_name) > 2:
            # Cross commands like cr02, cr14, etc.
            return self.cmd_cross(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("ex") and len(cmd_name) > 2:
            # Expect runway commands like ex02, ex20, etc.
            return self.cmd_expect_runway(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name == "to" or cmd_name == "cto" or cmd_name == "ct":
            return self.cmd_contact_tower(args, output_callback, is_combined, suppress_output)
        elif cmd_name == "x":
            return self.cmd_x(args, output_callback)
        elif cmd_name == "quit":
            return self.cmd_quit(args, output_callback)
        elif cmd_name.startswith("ft"):
            # Follow traffic: ft<traffic_callsign> or ft <traffic_callsign>
            return self.cmd_follow_traffic(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("gw"):
            # Give way: gw<taxiway> e.g. gwU
            return self.cmd_give_way(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name.startswith("sq") and len(cmd_name) == 6 and cmd_name[2:].isdigit():
            # Squawk command: sqXXXX (e.g., sq1854) - tell aircraft to squawk the given code
            return self.cmd_squawk(args, cmd_name, output_callback, is_combined, suppress_output)
        elif cmd_name == "sqc":
            return self.cmd_sqc(args, output_callback, is_combined, suppress_output)
        else:
            output_callback(f"Unknown command: {cmd_name}. Type 'help' for commands.")
            return False
    
    def cmd_help(self, args, output):
        """Show help information - see commands.txt"""
        output("=== ATC COMMANDS ===")
        output("[cs] pa - Pushback approved")
        output("[cs] r[rwy][via] - Taxi to runway (e.g., r02ua = rwy 02 via U A)")
        output("[cs] rp[via] - Taxi to parking (e.g., rpeu = parking via E U)")
        output("[cs] h[rwy] - Hold short runway (e.g., h02)")
        output("[cs] ht[twy] - Hold short taxiway (e.g., htF = hold short Foxtrot)")
        output("[cs] h - Hold position")
        output("[cs] cr[rwy] - Cross runway (e.g., cr02)")
        output("[cs] ex[rwy] - Expect runway (e.g., ex02)")
        output("[cs] ft[cs2] - Follow traffic (e.g., ftDAL456)")
        output("[cs] gw[twy] - Give way on taxiway (e.g., gwU)")
        output("[cs] sqXXXX - Squawk code (e.g., sq1854)")
        output("[cs] sqc - Toggle squawk Mode C")
        output("[cs] ct - Contact tower")
        output("COMBINE: [cs] [cmd1] [cmd2] (e.g., 123 pa ex02)")
        output("---")
        output("quit - Exit simulation")
        output("Type 'shortcuts' for command shortcuts")
        return True
    
    def cmd_clear(self, args, output):
        """Clear command output (handled by caller)"""
        return True
    
    def cmd_pa(self, args, output, is_combined=False, suppress_output=False):
        """Pushback approved"""
        if len(args) < 1:
            return False

        callsign = args[0]
        aircraft = self.find_aircraft(callsign)

        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        # Check if aircraft is parked
        if aircraft.state != aircraft.STATE_PARKED:
            output(f"{aircraft.get_callsign()}, unable, already {aircraft.state}")
            return False

        if not suppress_output:
            cs = aircraft.get_callsign()
            atc_text = random.choice([
                f"{cs}, pushback approved",
                f"{cs}, push approved, report ready to taxi",
                f"{cs}, cleared to push",
            ])
            output(atc_text)

        # Clear for pushback - skip individual readback if part of combined command
        aircraft.clear_pushback(skip_readback=is_combined)

        return True
    
    def cmd_taxi(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Taxi command
        Example: r02ua = taxi to runway 02 via U A
        Example: r14abc = taxi to runway 14 via A B C
        Example: rpeu = taxi to parking via E U
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()

        # Find the aircraft
        aircraft = self.find_aircraft(callsign)

        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        # Check if aircraft can taxi
        if aircraft.state == aircraft.STATE_PARKED:
            output(f"{aircraft.get_callsign()}, unable, request pushback clearance first")
            return False
        elif aircraft.state == aircraft.STATE_TAXI:
            output(f"{aircraft.get_callsign()}, wilco, recleared")
        elif aircraft.state == aircraft.STATE_TAKEOFF or aircraft.state == aircraft.STATE_DEPARTED:
            output(f"{aircraft.get_callsign()}, unable")
            return False

        # Parse the command: r[runway][via]
        cmd_part = cmd_name[1:]  # Remove 'r'

        if not cmd_part:
            output(f"{aircraft.get_callsign()}, say again taxi instructions")
            return False

        # Determine destination and via taxiways
        destination = None
        via_letters = []

        if len(cmd_part) >= 2 and cmd_part[:2].isdigit():
            # Runway destination: r02ua
            destination = f"runway {cmd_part[:2]}"
            via_letters = list(cmd_part[2:].upper())
        elif cmd_part.lower().startswith('p'):
            # Parking/gate destination: rpue
            destination = "parking"
            via_letters = list(cmd_part[1:].upper())
        else:
            output(f"{aircraft.get_callsign()}, say again taxi instructions")
            return False

        if not via_letters and destination != "parking":
            output(f"{aircraft.get_callsign()}, taxi to {destination}, advise route")
            return False

        if not suppress_output:
            cs = aircraft.get_callsign()
            if via_letters:
                via_phonetic = ' '.join(self.to_phonetic(l) for l in via_letters)
                if destination == "parking":
                    atc_text = random.choice([
                        f"{cs}, taxi to parking via {via_phonetic}",
                        f"{cs}, taxi to the ramp via {via_phonetic}",
                    ])
                else:
                    atc_text = random.choice([
                        f"{cs}, taxi to {destination} via {via_phonetic}",
                        f"{cs}, runway {destination.replace('runway ', '')}, taxi via {via_phonetic}",
                    ])
            else:
                if destination == "parking":
                    atc_text = f"{cs}, taxi to parking"
                else:
                    atc_text = f"{cs}, taxi to {destination}"
            output(atc_text)

        # Issue clearance - clear_taxi handles readback internally
        aircraft.clear_taxi(destination, via_letters, skip_readback=is_combined)

        return True
    
    def cmd_hold(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Hold short runway command
        Example: h02 = hold short runway 2
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()
        runway = cmd_name[1:].upper()  # Remove 'h'

        # Find the aircraft
        aircraft = self.find_aircraft(callsign)
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        if runway:
            # Remove runway from cleared list if it was there
            if runway in aircraft.cleared_runways:
                aircraft.cleared_runways.remove(runway)

            # Set hold short flag
            aircraft.hold_short = runway

            if not suppress_output:
                cs = aircraft.get_callsign()
                atc_text = random.choice([
                    f"{cs}, hold short of runway {runway}",
                    f"{cs}, hold short runway {runway}",
                ])
                output(atc_text)

            # Schedule readback (skip if part of combined command)
            if not is_combined:
                readback = aircraft._generate_realistic_readback("hold", {"runway": runway})
                aircraft._schedule_radio(readback, is_atc=False)
        else:
            aircraft.target_speed = 0

            if not suppress_output:
                output(f"{aircraft.get_callsign()}, hold position")

            if not is_combined:
                readback = aircraft._generate_realistic_readback("hold", {})
                aircraft._schedule_radio(readback, is_atc=False)

        return True

    def cmd_hold_position(self, args, output, is_combined=False, suppress_output=False):
        """Hold position"""
        if len(args) < 1:
            return False
        callsign = args[0].upper()

        aircraft = self.find_aircraft(callsign)
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        aircraft.target_speed = 0

        if not suppress_output:
            output(f"{aircraft.get_callsign()}, hold position")

        if not is_combined:
            readback = aircraft._generate_realistic_readback("hold", {})
            aircraft._schedule_radio(readback, is_atc=False)

        return True

    def cmd_hold_short_taxiway(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Hold short of a taxiway.
        Example: htF = hold short of taxiway Foxtrot
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()
        taxiway = cmd_name[2:].upper()  # Remove 'ht'

        aircraft = self.find_aircraft(callsign)
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        if not taxiway:
            output(f"{aircraft.get_callsign()}, say again taxiway")
            return False

        # Slow/stop the aircraft - reuse hold_short flag with taxiway letter prefix
        # so existing hold logic knows it's a taxiway hold
        aircraft.hold_short_taxiway = taxiway
        aircraft.target_speed = 0

        twy_phonetic = self.to_phonetic(taxiway)

        if not suppress_output:
            cs = aircraft.get_callsign()
            atc_text = random.choice([
                f"{cs}, hold short of {twy_phonetic}",
                f"{cs}, hold short of taxiway {twy_phonetic}",
            ])
            output(atc_text)

        if not is_combined:
            readback = aircraft._generate_realistic_readback("hold_short_taxiway", {"taxiway": taxiway})
            aircraft._schedule_radio(readback, is_atc=False)

        return True

    def cmd_follow_traffic(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Follow traffic instruction.
        Example: ftDAL456 = follow DAL456
        Example: ft = follow traffic ahead (no specific callsign)
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()

        aircraft = self.find_aircraft(callsign)
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        # Traffic callsign is everything after 'ft' in cmd_name, or first extra arg
        traffic_cs = cmd_name[2:].upper() if len(cmd_name) > 2 else (args[1].upper() if len(args) > 1 else "")
        traffic_aircraft = self.find_aircraft(traffic_cs) if traffic_cs else None

        if not suppress_output:
            cs = aircraft.get_callsign()
            if traffic_aircraft:
                # We know the specific aircraft type
                ac_type = getattr(traffic_aircraft, 'aircraft_type', '') or getattr(traffic_aircraft, 'type', traffic_cs)
                airline = traffic_cs
                atc_text = random.choice([
                    f"{cs}, follow the {ac_type} off your nose, {airline} traffic",
                    f"{cs}, follow company traffic, {airline} ahead",
                    f"{cs}, traffic {airline} is ahead, follow that aircraft",
                ])
            else:
                atc_text = random.choice([
                    f"{cs}, follow company traffic off your nose",
                    f"{cs}, follow the traffic ahead",
                    f"{cs}, fall in behind the traffic ahead",
                ])
            output(atc_text)

        if not is_combined:
            readback = aircraft._generate_realistic_readback(
                "follow_traffic",
                {"traffic": traffic_cs or "traffic ahead"}
            )
            aircraft._schedule_radio(readback, is_atc=False)

        return True

    def cmd_give_way(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Give way instruction.
        Example: gwU = give way to traffic on Uniform
        Example: gw = give way (no specific taxiway)
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()

        aircraft = self.find_aircraft(callsign)
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        # Taxiway is everything after 'gw' in cmd_name
        taxiway = cmd_name[2:].upper() if len(cmd_name) > 2 else (args[1].upper() if len(args) > 1 else "")
        twy_phonetic = self.to_phonetic(taxiway) if taxiway else ""

        # Slow aircraft
        aircraft.target_speed = 0

        if not suppress_output:
            cs = aircraft.get_callsign()
            if twy_phonetic:
                atc_text = random.choice([
                    f"{cs}, give way to the traffic on {twy_phonetic}",
                    f"{cs}, give way to the aircraft passing left to right on {twy_phonetic}",
                    f"{cs}, hold for crossing traffic on {twy_phonetic}",
                ])
            else:
                atc_text = random.choice([
                    f"{cs}, give way to crossing traffic",
                    f"{cs}, hold for crossing traffic",
                ])
            output(atc_text)

        if not is_combined:
            readback = aircraft._generate_realistic_readback(
                "give_way",
                {"taxiway": taxiway}
            )
            aircraft._schedule_radio(readback, is_atc=False)

        return True
    
    def cmd_cross(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Cross runway command
        Example: cr02 = cross runway 2
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()
        runway = cmd_name[2:].upper()  # Remove 'cr'

        # Find aircraft and give clearance
        aircraft = self.find_aircraft(callsign)
        if aircraft:
            if not suppress_output:
                cs = aircraft.get_callsign()
                atc_text = random.choice([
                    f"{cs}, cross runway {runway}",
                    f"{cs}, cleared to cross runway {runway}",
                    f"{cs}, runway {runway}, cross runway {runway}",
                ])
                output(atc_text)

            # Schedule readback transmission (skip if part of combined command)
            if not is_combined:
                readback = aircraft._generate_realistic_readback("cross", {"runway": runway})
                readback_time = aircraft._schedule_radio(readback, is_atc=False)
            else:
                readback_time = getattr(aircraft, 'current_sim_time', 0.0) + 3.0  # Dummy time for combined
            
            # Schedule actual clearance to take effect after readback + additional delay
            def execute_cross():
                # Add runway to cleared list
                if runway not in aircraft.cleared_runways:
                    aircraft.cleared_runways.append(runway)
                # Clear the holding short flags
                if aircraft.holding_short_runway == runway:
                    aircraft.holding_short_runway = None
                if aircraft.hold_short == runway:
                    aircraft.hold_short = None
                # If aircraft is holding, resume taxi
                if aircraft.state == aircraft.STATE_HOLDING and aircraft.cleared_to_taxi:
                    aircraft.state = aircraft.STATE_TAXI
            
            # Calculate delay: readback time + additional 1-2 seconds
            total_delay = (readback_time - getattr(aircraft, 'current_sim_time', 0.0)) + random.uniform(1.0, 2.0)
            aircraft._schedule_action(execute_cross, delay=total_delay)
            return True
        else:
            output(f"Aircraft {callsign} not found")
            return False
    
    def cmd_contact_tower(self, args, output, is_combined=False, suppress_output=False):
        """Contact tower - reads frequency from scenario file and hands off aircraft"""
        if len(args) < 1:
            return False

        callsign = args[0]
        aircraft = self.find_aircraft(callsign)

        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        # Get tower frequency from airport data
        tower_freq = "118.3"  # Default
        if self.airport_data:
            controllers = self.airport_data.get('controllers', [])
            for controller in controllers:
                if controller.get('name', '').lower() == 'tower':
                    tower_freq = controller.get('frequency', '118.3')
                    break

        # Hand off aircraft to tower controller
        tower_controller = None
        if self.aircraft_manager and hasattr(self.aircraft_manager, 'tower_controller'):
            tower_controller = self.aircraft_manager.tower_controller

        aircraft.handoff_to_tower(tower_controller)

        if not suppress_output:
            cs = aircraft.get_callsign()
            atc_text = random.choice([
                f"{cs}, contact tower {tower_freq}, good day",
                f"{cs}, frequency change approved, tower {tower_freq}",
                f"{cs}, tower {tower_freq}",
            ])
            output(atc_text)

        # Aircraft reads back with delay (skip if part of combined command)
        if not is_combined:
            cs = aircraft.get_callsign()
            tower_readback = random.choice([
                f"tower {tower_freq}, {cs}, good day",
                f"switching to tower on {tower_freq}, {cs}",
                f"tower {tower_freq}, {cs}",
                f"wilco, tower {tower_freq}, good day, {cs}",
            ])
            aircraft._schedule_radio(tower_readback, is_atc=False)

        return True

    def cmd_expect_runway(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Expect runway command
        Example: ex02 = expect runway 2
        """
        if len(args) < 1:
            return False

        callsign = args[0].upper()
        runway = cmd_name[2:].upper()  # Remove 'ex' prefix

        # Find the aircraft
        aircraft = self.find_aircraft(callsign)
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        # Store expected runway on aircraft
        aircraft.expected_runway = runway

        if not suppress_output:
            cs = aircraft.get_callsign()
            atc_text = random.choice([
                f"{cs}, expect runway {runway}",
                f"{cs}, plan on runway {runway}",
                f"{cs}, runway {runway} in use, expect runway {runway}",
            ])
            output(atc_text)

        # Aircraft reads back with delay (skip if part of combined command)
        if not is_combined:
            readback = aircraft._generate_realistic_readback("expect_runway", {"runway": runway})
            aircraft._schedule_radio(readback, is_atc=False)

        return True
    
    def cmd_quit(self, args, output):
        """Quit the program"""
        output("Shutting down simulation...")
        # Post a QUIT event to pygame's event queue
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        return True
    
    def cmd_squawk(self, args, cmd_name, output, is_combined=False, suppress_output=False):
        """Squawk command - tell aircraft to squawk the given code.
        Example: sq1854 = squawk 1854. Readback soon, actual change after 5-10s.
        """
        if len(args) < 1:
            return False

        callsign = args[0]
        aircraft = self.find_aircraft(callsign)

        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False

        code = cmd_name[2:].zfill(4)
        if len(code) != 4 or not code.isdigit():
            output(f"{aircraft.get_callsign()}, invalid squawk code")
            return False

        if not suppress_output:
            cs = aircraft.get_callsign()
            output(f"{cs}, squawk {code}")

        # Readback first (skip if combined)
        if not is_combined and hasattr(aircraft, '_schedule_radio'):
            readback = f"{aircraft.get_callsign()}, squawking {code}"
            aircraft._schedule_radio(readback, is_atc=False)

        # Apply squawk change after 5-10s delay (pilot dials code)
        def apply_squawk():
            aircraft.squawking_mode_c = True
            aircraft.current_squawk_code = code
            aircraft.atc_assigned_squawk = True

        delay = random.uniform(5.0, 10.0)
        aircraft._schedule_action(apply_squawk, delay=delay)

        return True

    def cmd_sqc(self, args, output, is_combined=False, suppress_output=False):
        """Toggle squawk Mode C: if off, turn on with assigned code; if on, turn off.
        Readback soon, actual change after 5-10s.
        """
        if len(args) < 1:
            return False
        
        callsign = args[0]
        aircraft = self.find_aircraft(callsign)
        
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False
        
        squawking = getattr(aircraft, 'squawking_mode_c', False)
        
        if squawking:
            # Turning off (standby)
            if not is_combined and hasattr(aircraft, '_schedule_radio'):
                aircraft._schedule_radio(f"{aircraft.get_callsign()}, squawking standby", is_atc=False)
            
            def apply_standby():
                aircraft.squawking_mode_c = False
                aircraft.current_squawk_code = None
                aircraft.atc_squawk_standby = True
            
            aircraft._schedule_action(apply_standby, delay=random.uniform(5.0, 10.0))
        else:
            # Turning on (Mode C + assigned code)
            code = getattr(aircraft, 'correct_squawk_code', None)
            code_str = str(code).zfill(4) if code is not None else None
            
            if not is_combined and hasattr(aircraft, '_schedule_radio'):
                if code_str:
                    readback = f"{aircraft.get_callsign()}, squawking Mode C, {code_str}"
                else:
                    readback = f"{aircraft.get_callsign()}, squawking Mode C"
                aircraft._schedule_radio(readback, is_atc=False)
            
            def apply_mode_c():
                aircraft.atc_squawk_standby = False
                aircraft.squawking_mode_c = True
                aircraft.current_squawk_code = code_str
            
            aircraft._schedule_action(apply_mode_c, delay=random.uniform(5.0, 10.0))
        
        return True
    
    def cmd_x(self, args, output):
        """X command - Delete/remove aircraft from simulation"""
        if len(args) < 1:
            output("Usage: x <callsign>")
            return False
        
        callsign = args[0].upper()
        aircraft = self.find_aircraft(callsign)
        
        if not aircraft:
            output(f"Aircraft {callsign} not found")
            return False
        
        # Remove aircraft from the aircraft manager
        self.aircraft_manager.remove_aircraft(aircraft)
        output(f"Aircraft {callsign} removed from simulation")
        
        return True
