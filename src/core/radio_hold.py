"""
Radio hold state — written by the voice/PTT system, read by aircraft.

While the controller is transmitting (PTT active):
  hold_until = a very large number → all aircraft hold their radio calls.

After PTT is released and commands are dispatched:
  priority_callsign = the addressed aircraft → it transmits its readback normally.
  hold_until = sim_time + BUFFER → everyone else waits until the readback is done.
"""

# Simulation time after which non-priority aircraft may transmit.
# Set to a large value while PTT is active; to sim_time + buffer after release.
hold_until: float = 0.0

# Callsign of the aircraft that was just addressed — allowed to transmit
# even during the hold window.
priority_callsign: str | None = None

# True while an exchange is in progress (request → ATC response → readback).
# Non-priority aircraft are blocked until the readback audio finishes playing.
# hold_until acts as a safety timeout in case the TTS callback never fires.
exchange_locked: bool = False
