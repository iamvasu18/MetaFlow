import re


class SalesforceContextSelector:
    """
    Selects Salesforce metadata relevant to a user requirement.

    The first version uses deterministic whole-word keyword matching.
    This keeps retrieval predictable and easy to test.
    """

    def __init__(self, max_objects: int = 10):
        self.max_objects = max_objects

    def _extract_terms(
        self,
        requirement: str,
    ) -> set[str]:
        """
        Extract normalized terms from the requirement.
        """

        words = re.findall(
            r"[A-Za-z][A-Za-z0-9_]*",
            requirement.lower(),
        )

        return set(words)

    def _contains_term(
        self,
        text: str,
        term: str,
    ) -> bool:
        """
        Check whether a term exists as a complete word.

        Example:
            "a" matches "a Contact"
            "a" does NOT match "Account"
        """

        words = re.findall(
            r"[A-Za-z][A-Za-z0-9_]*",
            text.lower(),
        )

        return term.lower() in words

    def select(
        self,
        requirement: str,
        metadata: dict,
    ) -> dict:
        """
        Select relevant Salesforce objects from metadata.
        """

        terms = self._extract_terms(
            requirement
        )

        objects = metadata.get(
            "objects",
            [],
        )

        scored_objects = []

        for obj in objects:

            name = str(
                obj.get("name", "")
            )

            label = str(
                obj.get("label", "")
            )

            score = 0

            # -----------------------------------------
            # Object-level matching
            # -----------------------------------------

            for term in terms:

                if self._contains_term(
                    name,
                    term,
                ):
                    score += 1

                if self._contains_term(
                    label,
                    term,
                ):
                    score += 1

            # -----------------------------------------
            # Field-level matching
            # -----------------------------------------

            for field in obj.get(
                "fields",
                [],
            ):

                field_name = str(
                    field.get("name", "")
                )

                field_label = str(
                    field.get("label", "")
                )

                for term in terms:

                    if self._contains_term(
                        field_name,
                        term,
                    ):
                        score += 1

                    if self._contains_term(
                        field_label,
                        term,
                    ):
                        score += 1

            # -----------------------------------------
            # Only include relevant objects
            # -----------------------------------------

            if score > 0:

                scored_objects.append(
                    (
                        score,
                        obj,
                    )
                )

        # ---------------------------------------------
        # Sort by relevance
        # ---------------------------------------------

        scored_objects.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        # ---------------------------------------------
        # Apply maximum object limit
        # ---------------------------------------------

        selected_objects = [
            obj
            for _, obj in scored_objects[
                : self.max_objects
            ]
        ]

        return {
            "objects": selected_objects
        }