"""
Shared ATIS state — written by WeatherPanel, read by aircraft callup phrases.
"""

# Current ATIS information letter (e.g. "charlie"), or None if not yet fetched
current_atis_letter: str | None = None

# Full ATIS text, for display in the weather panel
current_atis_text: str | None = None
