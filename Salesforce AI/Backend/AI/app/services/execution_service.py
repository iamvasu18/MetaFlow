from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


class SalesforceExecutionService:
    """
    Converts an approved Salesforce implementation plan
    into Salesforce CLI commands.

    Current version supports dry-run only.

    IMPORTANT:
    This service does not execute Salesforce commands yet.
    """

    def __init__(
        self,
        target_org: str = "DevOrg",
    ):
        self.target_org = target_org

    def validate_plan(
        self,
        plan: ImplementationPlan,
    ) -> None:
        """
        Ensure that only APPROVED plans can be executed.
        """

        if plan.status != "APPROVED":

            raise ValueError(
                "Only APPROVED plans can be executed."
            )

    def build_commands(
        self,
        plan: ImplementationPlan,
    ) -> list[list[str]]:
        """
        Convert plan items into Salesforce CLI commands.

        This currently builds commands only.
        It does NOT execute them.
        """

        self.validate_plan(plan)

        commands = []

        for item in plan.items:

            if item.action == "CREATE":

                if item.metadataType == "CustomObject":

                    commands.append(
                        [
                            "sf",
                            "project",
                            "generate",
                            "metadata",
                            "--name",
                            item.fullName,
                            "--type",
                            "CustomObject",
                            "--output-dir",
                            "force-app/main/default",
                        ]
                    )

                elif item.metadataType == "CustomField":

                    commands.append(
                        [
                            "sf",
                            "project",
                            "generate",
                            "metadata",
                            "--name",
                            item.fullName,
                            "--type",
                            "CustomField",
                            "--output-dir",
                            "force-app/main/default",
                        ]
                    )

        return commands

    def dry_run(
        self,
        plan: ImplementationPlan,
    ) -> dict:

        commands = self.build_commands(
            plan
        )

        return {
            "planId": plan.id,
            "status": plan.status,
            "targetOrg": self.target_org,
            "dryRun": True,
            "commands": commands,
        }