class PipelineError(Exception):
    """An actionable error safe to display without credentials or payloads."""


class Cancelled(Exception):
    pass
