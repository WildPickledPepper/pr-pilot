# pr_pilot/git_providers/exceptions.py

class PullRequestException(Exception):
    """Base exception for pull request related errors."""
    pass

class PullRequestNotFound(PullRequestException):
    """Raised when a pull request is not found or is not in a valid state."""
    pass