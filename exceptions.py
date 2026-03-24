"""Custom exceptions for the OpenSky Flight Tracker."""


class FlightTrackerError(Exception):
    """Base exception for flight tracker errors."""
    pass


class AuthenticationError(FlightTrackerError):
    """Token authentication failed."""
    pass


class APIError(FlightTrackerError):
    """External API call failed."""
    pass


class NoFlightsError(FlightTrackerError):
    """No flights found in the search area."""
    pass
