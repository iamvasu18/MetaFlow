from abc import ABC, abstractmethod


class AIProvider(ABC):
    """
    Common interface for all AI providers.

    Any provider we add later must implement this interface.
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Send a prompt to the AI provider and return its response.
        """
        raise NotImplementedError