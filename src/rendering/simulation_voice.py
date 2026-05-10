"""
Voice command mixin for SimulationScreen
"""
import logging
import pygame
from src.core import radio_hold as _radio_hold

logger = logging.getLogger(__name__)


class VoiceMixin:
    """Mixin providing voice/PTT command methods for SimulationScreen."""

    def handle_radio_transmission(self, text, is_atc=False, callsign=None, frequency=None):
        """Handle radio transmission from aircraft or ATC

        Args:
            text: The message text
            is_atc: Whether this is an ATC transmission
            callsign: Optional callsign of the sender (extracted from text if not provided)
            frequency: Optional frequency type ('ground' or 'tower'), defaults to 'ground'
        """
        # Default to ground frequency if not specified
        if frequency is None:
            frequency = 'ground'
        if is_atc:
            # Only show ATC transmission if monitoring this frequency
            if self.radio_panel and self.radio_panel.active_frequency == frequency:
                # Ground control transmission - green (show immediately, no TTS delay)
                self.add_output(text, color=(0, 224, 21))

            # Always log transmission to radio panel (for frequency switching)
            if self.radio_panel:
                from_callsign = "Ground" if frequency == 'ground' else "Tower"
                freq = self.radio_panel.ground_freq if frequency == 'ground' else self.radio_panel.tower_freq
                self.radio_panel.add_transmission(
                    freq,
                    from_callsign,
                    text,
                    is_atc=True
                )
        else:
            # Aircraft transmission - delay text display until audio is ready
            # Extract callsign from text if not provided
            if callsign is None:
                words = text.split()
                callsign = words[0] if words else ""

            # Only update last_callsign for aircraft-initiated calls (not readbacks)
            # Aircraft calls typically end with "ready", "request", "with you", or are short position reports
            call_indicators = ["ready", "request", "with you", "at gate", "holding short", "for departure", "for landing"]
            text_lower = text.lower()

            # Check if this is an aircraft-initiated call (not a readback)
            is_aircraft_call = any(indicator in text_lower for indicator in call_indicators) or (
                len(text.split()) <= 6 and not any(readback_word in text_lower for readback_word in
                ["roger", "wilco", "understand", "copy", "read back", "confirm"])
            )

            if is_aircraft_call and callsign:
                self.last_callsign = callsign
                # Lock the radio for this aircraft while its request is playing
                # so other aircraft don't talk over it.
                sim_time = (self.aircraft_manager.simulation_time
                            if self.aircraft_manager else 0.0)
                _radio_hold.priority_callsign = callsign
                _radio_hold.exchange_locked   = True
                _radio_hold.hold_until        = sim_time + 30.0  # safety timeout

            # Check if we're monitoring this frequency
            monitoring_frequency = (not self.radio_panel or self.radio_panel.active_frequency == frequency)

            # Always log transmission to radio panel (for frequency switching history)
            if self.radio_panel:
                freq = self.radio_panel.ground_freq if frequency == 'ground' else self.radio_panel.tower_freq
                self.radio_panel.add_transmission(
                    freq,
                    callsign,
                    text,
                    is_atc=False
                )

            # Create callback to show text and play radio sound when audio is ready
            def show_transmission():
                # Only show transmission if monitoring this frequency
                if monitoring_frequency:
                    # Play radio sound for aircraft transmissions (synchronized with text/voice)
                    self.play_radio_sound()
                    # Add to output display
                    self.add_aircraft_transmission(text)

            # Detect if this is the priority aircraft's readback.
            # A readback is any non-initiated transmission from the aircraft that
            # currently holds the exchange lock.
            is_priority_readback = (
                not is_aircraft_call
                and _radio_hold.exchange_locked
                and callsign == _radio_hold.priority_callsign
            )

            # When the readback finishes playing, release the exchange lock so
            # other aircraft may now transmit.
            def _release_exchange():
                _radio_hold.exchange_locked   = False
                _radio_hold.priority_callsign = None
                _radio_hold.hold_until        = 0.0

            complete_cb = _release_exchange if is_priority_readback else None

            # Check if TTS is enabled (both service exists and toggle is on)
            tts_enabled = (self.tts_service is not None and
                          self.top_menu_bar and
                          self.top_menu_bar.enable_tts_audio)

            # Only play TTS if monitoring this frequency
            if tts_enabled and monitoring_frequency:
                # Look up the aircraft by callsign to get its assigned voice
                voice = None
                if self.aircraft_manager and callsign:
                    # Try exact callsign match first
                    aircraft = self.aircraft_manager.get_aircraft_by_callsign(callsign)
                    if aircraft:
                        voice = getattr(aircraft, 'assigned_voice', None)

                # Use the aircraft's assigned voice if found, otherwise fall back to callsign-based assignment
                if voice:
                    self.tts_service.speak(text, voice=voice,
                                           on_ready_callback=show_transmission,
                                           on_complete_callback=complete_cb)
                else:
                    self.tts_service.speak(text, callsign=callsign,
                                           on_ready_callback=show_transmission,
                                           on_complete_callback=complete_cb)
            else:
                # TTS disabled or not available - show transmission immediately with no delay
                show_transmission()
                # Still release the exchange lock so the sim doesn't stall
                if complete_cb:
                    complete_cb()

    def load_radio_sound(self):
        """Load radio transmission sound effect"""
        import os
        # Try multiple file formats
        sound_files = [
            "data/audio/sfx/radio-static.mp3",
            "data/audio/sfx/radio-static.wav",
            "data/audio/sfx/radio-static.ogg"
        ]

        for radio_sound_path in sound_files:
            try:
                if os.path.exists(radio_sound_path):
                    self.radio_sound = pygame.mixer.Sound(radio_sound_path)
                    self.radio_sound.set_volume(0.5)  # 50% volume
                    logger.info(f"Loaded radio sound: {radio_sound_path}")
                    return
            except Exception as e:
                logger.warning(f"Could not load {radio_sound_path}: {e}")
                continue

        logger.warning("Radio sound not found. Place your audio file at data/audio/sfx/radio-static.mp3")
        

    def play_radio_sound(self):
        """Play radio transmission sound"""
        # Check if radio audio is enabled in settings
        if not self.settings.get("radio_audio", True):
            return

        # Don't play radio sound while user's PTT is held
        if getattr(self, 'ptt_active', False):
            return

        if self.radio_sound:
            try:
                self.radio_sound.play()
            except Exception as e:
                logger.warning(f"Error playing radio sound: {e}")

    def _get_ptt_key(self) -> int:
        """Return the current PTT key code (from voice panel or default LSHIFT)."""
        if hasattr(self, 'top_menu_bar') and self.top_menu_bar:
            return self.top_menu_bar.ptt_key_code
        return pygame.K_LSHIFT

    def _set_voice_status(self, msg: str, duration: float = 3.0):
        """Set the voice status message shown in the HUD."""
        self.voice_status = msg
        self.voice_status_timer = duration

    def _on_voice_transcript(self, transcript):
        """
        Called by the STT background thread when transcription is complete.
        Parses and executes the command. Safe to call from any thread since
        _set_voice_status only writes simple Python values.
        """
        import traceback
        # Always release the radio hold when the transcript arrives — even if
        # recognition fails or an exception occurs, other aircraft must not be
        # blocked forever.  We tighten the hold again below if commands succeed.
        def _release_hold():
            sim_time = (self.aircraft_manager.simulation_time
                        if self.aircraft_manager else 0.0)
            _radio_hold.priority_callsign = None
            _radio_hold.hold_until = sim_time  # unblock immediately

        try:
            logger.debug(f"[VOICE] Transcript received: {repr(transcript)}")

            if not transcript:
                _release_hold()
                self._set_voice_status("PTT | NO SPEECH", 3.0)
                return

            self._set_voice_status(f"HEARD: {transcript}", 5.0)

            logger.debug(f"[VOICE] Parsing: {transcript!r}")
            cmds = self.voice_parser.parse(transcript)
            logger.debug(f"[VOICE] Parsed: {repr(cmds)}")

            if not cmds:
                _release_hold()
                self._set_voice_status(f"NOT UNDERSTOOD: {transcript[:40]}", 4.0)
                return

            result_lines = []
            def _out(text):
                result_lines.append(text)
                logger.debug(f"[VOICE CMD] {text}")

            # Group commands by callsign so same-aircraft commands collapse into
            # a single combined-command string (e.g. "ENY659 pa ex02"), which
            # triggers the existing combined-readback path in commands.py and
            # produces one merged pilot transmission instead of two.
            from collections import OrderedDict
            grouped: OrderedDict[str, list[str]] = OrderedDict()
            for cmd in cmds:
                parts = cmd.split(maxsplit=1)
                cs = parts[0]
                body = parts[1] if len(parts) > 1 else ""
                grouped.setdefault(cs, []).append(body)

            merged_cmds = [f"{cs} {' '.join(bodies)}" for cs, bodies in grouped.items()]

            any_success = False
            for cmd in merged_cmds:
                logger.debug(f"[VOICE] Executing: {cmd!r}")
                success = self.command_processor.execute(cmd, _out)
                logger.debug(f"[VOICE] success={success}")
                if success:
                    any_success = True

            # Lock radio for the addressed aircraft's readback.
            # exchange_locked stays True until the readback TTS finishes playing
            # (on_complete_callback in handle_radio_transmission releases it).
            # hold_until is a 30 s safety timeout in case the callback never fires.
            addressed = cmds[0].split()[0] if cmds else None
            # Resolve short-form (e.g. "123") to full callsign (e.g. "AAL123")
            # so the is_priority check in _process_pending_radio matches get_callsign()
            if addressed and self.command_processor:
                ac = self.command_processor.find_aircraft(addressed)
                if ac:
                    addressed = ac.get_callsign()
            sim_time = (self.aircraft_manager.simulation_time
                        if self.aircraft_manager else 0.0)
            if any_success and addressed:
                _radio_hold.priority_callsign = addressed
                _radio_hold.exchange_locked   = True
                _radio_hold.hold_until        = sim_time + 30.0
            else:
                # Command failed — short courtesy hold, don't lock indefinitely
                _radio_hold.priority_callsign = addressed
                _radio_hold.exchange_locked   = False
                _radio_hold.hold_until        = sim_time + 3.0

            status_cmds = " | ".join(merged_cmds)
            self._set_voice_status(f"OK: {status_cmds}" if any_success else f"FAILED: {status_cmds}", 4.0)

            if hasattr(self, 'add_command_output'):
                for line in result_lines:
                    self.add_command_output(line)

        except Exception as e:
            _release_hold()   # never leave aircraft permanently silenced
            logger.error(f"[VOICE] Exception in callback: {e}")
            logger.error(traceback.format_exc())
            self._set_voice_status(f"ERROR: {e}", 5.0)

    def _load_transmitting_mic(self):
        """Load transmitting_mic image once and cache it on the instance."""
        if getattr(self, '_transmitting_mic_img', None) is not None:
            return
        import os
        path = os.path.join("data", "images", "trasmitting_mic.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            # Scale to a reasonable HUD size (64 px tall, preserve aspect)
            orig_w, orig_h = img.get_size()
            target_h = 15
            target_w = int(orig_w * target_h / orig_h)
            self._transmitting_mic_img = pygame.transform.smoothscale(img, (target_w, target_h))
        except Exception as e:
            logger.warning(f"[HUD] Could not load transmitting_mic: {e}")
            self._transmitting_mic_img = None   # flag as "tried but failed"

    def _render_voice_hud(self):
        """Show transmitting_mic.png in the top-left corner while PTT is active."""
        if not self.ptt_active:
            return

        self._load_transmitting_mic()

        bar_h = getattr(self.top_menu_bar, 'height', 15) if hasattr(self, 'top_menu_bar') else 15
        x, y = 8, bar_h + 8

        img = getattr(self, '_transmitting_mic_img', None)
        if img:
            self.screen.blit(img, (x, y))
        else:
            # Fallback: simple red dot if image failed to load
            pygame.draw.circle(self.screen, (220, 40, 40), (x + 12, y + 12), 10)

    