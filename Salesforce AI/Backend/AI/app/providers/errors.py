"""Provider-independent exceptions used for safe generation recovery."""


class AIOutputLimitError(RuntimeError):
    """The model exhausted its output budget before completing a response."""
