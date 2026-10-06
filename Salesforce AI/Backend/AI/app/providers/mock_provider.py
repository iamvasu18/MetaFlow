import json
import re

from Backend.AI.app.providers.base import AIProvider


class MockProvider(AIProvider):
    """
    Development-only AI provider.

    Returns deterministic Salesforce implementation plans
    without calling an external LLM.

    Supported scenarios:
        1. Contact
        2. Training Session
        3. Appointment

    The Contact scenario additionally inspects Salesforce
    context so existing metadata is not recreated.

    Requirement detection uses the content inside
    USER_REQUIREMENT markers.
    """

    # =================================================
    # Generate
    # =================================================

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

       

        # ---------------------------------------------
        # Contact scenario
        # ---------------------------------------------

        if self._contains_contact_requirement(
            user_prompt
        ):
            return json.dumps(
                self._contact_plan_from_context(
                    user_prompt
                )
            )

        # ---------------------------------------------
        # Training Session scenario
        # ---------------------------------------------

        if self._contains_training_session_requirement(
            user_prompt
        ):
            return json.dumps(
                self._training_session_plan()
            )

        # ---------------------------------------------
        # Default Appointment scenario
        # ---------------------------------------------

        return json.dumps(
            self._appointment_plan()
        )

    # =================================================
    # Requirement Detection
    # =================================================

    @staticmethod
    def _extract_user_requirement(
        prompt: str,
    ) -> str:
        """
        Extract the actual user requirement from the
        assembled planning prompt.

        Expected markers:
            <USER_REQUIREMENT>
            ...
            </USER_REQUIREMENT>

        Falls back to the complete prompt for older
        tests that use plain text.
        """

        start_marker = "<USER_REQUIREMENT>"
        end_marker = "</USER_REQUIREMENT>"

        if (
            start_marker in prompt
            and end_marker in prompt
        ):
            return (
                prompt.split(
                    start_marker,
                    1,
                )[1]
                .split(
                    end_marker,
                    1,
                )[0]
                .strip()
            )

        return prompt.strip()

    @classmethod
    def _contains_contact_requirement(
        cls,
        prompt: str,
    ) -> bool:
        """
        Determine whether the user requirement
        is a Contact scenario.
        """

        requirement = (
            cls._extract_user_requirement(
                prompt
            ).lower()
        )

        return bool(
            re.search(
                r"\bcontact\b",
                requirement,
            )
        )

    @classmethod
    def _contains_training_session_requirement(
        cls,
        prompt: str,
    ) -> bool:
        """
        Determine whether the user requirement
        is a Training Session scenario.
        """

        requirement = (
            cls._extract_user_requirement(
                prompt
            ).lower()
        )

        return bool(
            re.search(
                r"\btraining\s+session\b",
                requirement,
            )
        )

    # =================================================
    # Salesforce Context Parsing
    # =================================================

    @staticmethod
    def _extract_salesforce_context(
        prompt: str,
    ) -> dict:
        """
        Extract Salesforce context from the planning
        prompt.

        Expected markers:
            <SALESFORCE_CONTEXT>
            {...}
            </SALESFORCE_CONTEXT>
        """

        start_marker = "<SALESFORCE_CONTEXT>"
        end_marker = "</SALESFORCE_CONTEXT>"

        if (
            start_marker not in prompt
            or end_marker not in prompt
        ):
            return {
                "objects": []
            }

        context_text = (
            prompt.split(
                start_marker,
                1,
            )[1]
            .split(
                end_marker,
                1,
            )[0]
            .strip()
        )

        try:
            context = json.loads(
                context_text
            )

            if isinstance(
                context,
                dict,
            ):
                return context

        except json.JSONDecodeError:
            pass

        return {
            "objects": []
        }

    @staticmethod
    def _find_object(
        salesforce_context: dict,
        object_name: str,
    ) -> dict | None:
        """
        Find a Salesforce object by API name.
        """

        for obj in salesforce_context.get(
            "objects",
            [],
        ):
            if not isinstance(
                obj,
                dict,
            ):
                continue

            if (
                str(
                    obj.get(
                        "name",
                        "",
                    )
                ).lower()
                == object_name.lower()
            ):
                return obj

        return None

    @staticmethod
    def _field_exists(
        salesforce_object: dict,
        field_name: str,
    ) -> bool:
        """
        Determine whether a Salesforce field
        already exists on the object.
        """

        for field in salesforce_object.get(
            "fields",
            [],
        ):
            if not isinstance(
                field,
                dict,
            ):
                continue

            if (
                str(
                    field.get(
                        "name",
                        "",
                    )
                ).lower()
                == field_name.lower()
            ):
                return True

        return False

    # =================================================
    # Contact Plan
    # =================================================

    @classmethod
    def _contact_plan_from_context(
        cls,
        prompt: str,
    ) -> dict:
        """
        Build a Contact plan based on Salesforce
        metadata contained in the planning prompt.

        Existing metadata receives NO_CHANGE.
        Missing metadata receives CREATE.
        """

        salesforce_context = (
            cls._extract_salesforce_context(
                prompt
            )
        )

        contact = cls._find_object(
            salesforce_context,
            "Contact",
        )

        # ---------------------------------------------
        # Contact object action
        # ---------------------------------------------

        contact_exists = (
            contact is not None
        )

        contact_action = (
            "NO_CHANGE"
            if contact_exists
            else "CREATE"
        )

        # ---------------------------------------------
        # Field actions
        # ---------------------------------------------

        first_name_exists = (
            contact_exists
            and cls._field_exists(
                contact,
                "FirstName",
            )
        )

        last_name_exists = (
            contact_exists
            and cls._field_exists(
                contact,
                "LastName",
            )
        )

        email_exists = (
            contact_exists
            and cls._field_exists(
                contact,
                "Email",
            )
        )

        first_name_action = (
            "NO_CHANGE"
            if first_name_exists
            else "CREATE"
        )

        last_name_action = (
            "NO_CHANGE"
            if last_name_exists
            else "CREATE"
        )

        email_action = (
            "NO_CHANGE"
            if email_exists
            else "CREATE"
        )

        # ---------------------------------------------
        # Dependencies
        # ---------------------------------------------

        first_name_dependencies = (
            []
            if first_name_action == "NO_CHANGE"
            else ["ITEM-001"]
        )

        last_name_dependencies = (
            []
            if last_name_action == "NO_CHANGE"
            else ["ITEM-001"]
        )

        email_dependencies = (
            []
            if email_action == "NO_CHANGE"
            else ["ITEM-001"]
        )

        # ---------------------------------------------
        # Build plan
        # ---------------------------------------------

        return {
            "id": "PLAN-MOCK-CONTACT-001",

            "requirementId": (
                "REQ-MOCK-CONTACT-001"
            ),

            "summary": (
                "Create a Contact with "
                "First Name, Last Name and Email."
            ),

            "assumptions": [
                (
                    "The Salesforce context is used "
                    "to determine whether Contact "
                    "metadata already exists."
                ),
                (
                    "First Name is stored in the "
                    "standard FirstName field."
                ),
                (
                    "Last Name is stored in the "
                    "standard LastName field."
                ),
                (
                    "Email is stored in the "
                    "standard Email field."
                ),
            ],

            "items": [
                {
                    "id": "ITEM-001",
                    "action": contact_action,
                    "metadataType": "CustomObject",
                    "fullName": "Contact",
                    "label": "Contact",
                    "description": (
                        "Represents the Salesforce "
                        "Contact object."
                    ),
                    "dependencies": [],
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-002",
                    "action": first_name_action,
                    "metadataType": "CustomField",
                    "fullName": "Contact.FirstName",
                    "label": "First Name",
                    "description": (
                        "Represents the First Name "
                        "field on Contact."
                    ),
                    "dependencies": (
                        first_name_dependencies
                    ),
                    "config": {
                        "type": "Text",
                        "required": False,
                    },
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-003",
                    "action": last_name_action,
                    "metadataType": "CustomField",
                    "fullName": "Contact.LastName",
                    "label": "Last Name",
                    "description": (
                        "Represents the Last Name "
                        "field on Contact."
                    ),
                    "dependencies": (
                        last_name_dependencies
                    ),
                    "config": {
                        "type": "Text",
                        "required": True,
                    },
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-004",
                    "action": email_action,
                    "metadataType": "CustomField",
                    "fullName": "Contact.Email",
                    "label": "Email",
                    "description": (
                        "Represents the Email "
                        "field on Contact."
                    ),
                    "dependencies": (
                        email_dependencies
                    ),
                    "config": {
                        "type": "Email",
                        "required": False,
                    },
                    "approval": "PENDING",
                },
            ],

            "storyPoints": 2,
            "status": "DRAFT",
        }

    # =================================================
    # Training Session Plan
    # =================================================

    @staticmethod
    def _training_session_plan() -> dict:
        """
        Return the deterministic Training Session plan.
        """

        return {
            "id": "PLAN-MOCK-TRAINING-001",

            "requirementId": (
                "REQ-MOCK-TRAINING-001"
            ),

            "summary": (
                "Create a Training Session custom "
                "object with Session Date and "
                "Status fields."
            ),

            "assumptions": [
                (
                    "Training Session does not "
                    "already exist in the Salesforce "
                    "organization."
                ),
                (
                    "Session Date is required."
                ),
                (
                    "Status is implemented as "
                    "a picklist."
                ),
            ],

            "items": [
                {
                    "id": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "TrainingSession__c",
                    "label": "Training Session",
                    "description": (
                        "Stores training session "
                        "information."
                    ),
                    "dependencies": [],
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-002",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "TrainingSession__c."
                        "Session_Date__c"
                    ),
                    "label": "Session Date",
                    "description": (
                        "Stores the training "
                        "session date."
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Date",
                        "required": True,
                    },
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-003",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "TrainingSession__c."
                        "Status__c"
                    ),
                    "label": "Status",
                    "description": (
                        "Stores the training "
                        "session status."
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Picklist",
                        "values": [
                            "Scheduled",
                            "Completed",
                            "Cancelled",
                        ],
                    },
                    "approval": "PENDING",
                },
            ],

            "storyPoints": 3,
            "status": "DRAFT",
        }

    # =================================================
    # Appointment Plan
    # =================================================

    @staticmethod
    def _appointment_plan() -> dict:
        """
        Return the deterministic Appointment plan.
        """

        return {
            "id": "PLAN-MOCK-001",

            "requirementId": (
                "REQ-MOCK-001"
            ),

            "summary": (
                "Create an Appointment custom "
                "object with Appointment Date "
                "and Status fields."
            ),

            "assumptions": [
                (
                    "Appointment does not already "
                    "exist in the Salesforce "
                    "organization."
                ),
                (
                    "Appointment Date is required."
                ),
                (
                    "Status is implemented as "
                    "a picklist."
                ),
            ],

            "items": [
                {
                    "id": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "Appointment__c",
                    "label": "Appointment",
                    "description": (
                        "Stores appointment "
                        "information."
                    ),
                    "dependencies": [],
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-002",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "Appointment__c."
                        "Appointment_Date__c"
                    ),
                    "label": "Appointment Date",
                    "description": (
                        "Stores the appointment "
                        "date."
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Date",
                        "required": True,
                    },
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-003",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "Appointment__c."
                        "Status__c"
                    ),
                    "label": "Status",
                    "description": (
                        "Stores the appointment "
                        "status."
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Picklist",
                        "values": [
                            "Scheduled",
                            "Completed",
                            "Cancelled",
                        ],
                    },
                    "approval": "PENDING",
                },
            ],

            "storyPoints": 3,
            "status": "DRAFT",
        }