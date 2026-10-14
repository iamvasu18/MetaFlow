import json
from pathlib import Path
import shutil
import subprocess

from Backend.AI.app.services.deployment_service import (
    SalesforceDeploymentService,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


class SalesforceDeploymentExecutor:
    """
    Executes a validated Salesforce deployment command.

    IMPORTANT:
    This is the service that can actually change the
    Salesforce target org.

    It performs safety checks before executing the
    Salesforce CLI command.
    """

    def __init__(
        self,
        target_org: str = "AIOrg",
        project_root: str = ".",
    ):
        self.project_root = Path(project_root).resolve()
        self.target_org = (
            target_org
        )

        self.deployment_service = (
            SalesforceDeploymentService(
                target_org=target_org,
                project_root=str(self.project_root),
            )
        )

    # =====================================================
    # Salesforce CLI Resolution
    # =====================================================

    def _get_sf_command(
        self,
    ) -> str:
        """
        Resolve the Salesforce CLI executable.

        On Windows, shutil.which("sf") may resolve to
        sf.CMD. We use the resolved executable path
        instead of relying on subprocess to resolve
        the command again.
        """

        sf_command = (
            shutil.which(
                "sf"
            )
        )

        if not sf_command:

            raise RuntimeError(
                "Salesforce CLI 'sf' was not found "
                "in PATH."
            )

        return sf_command

    # =====================================================
    # Deployment Validation
    # =====================================================

    def validate_before_deployment(
        self,
        plan: ImplementationPlan,
        validation_result: dict,
    ) -> None:
        """
        Perform all safety checks before deployment.
        """

        # -------------------------------------------------
        # 1. Plan must be approved
        # -------------------------------------------------

        if plan.status != "APPROVED":

            raise ValueError(
                "Only APPROVED plans can be deployed."
            )

        # -------------------------------------------------
        # 2. Metadata must be valid
        # -------------------------------------------------

        if not validation_result.get(
            "valid",
            False,
        ):

            errors = (
                validation_result.get(
                    "errors",
                    [],
                )
            )

            raise ValueError(
                "Metadata validation failed: "
                + "; ".join(
                    errors
                )
            )

        # -------------------------------------------------
        # 3. Target org must be configured
        # -------------------------------------------------

        if not self.target_org:

            raise ValueError(
                "Salesforce target org is not "
                "configured."
            )

        # -------------------------------------------------
        # 4. Salesforce CLI must exist
        # -------------------------------------------------

        self._get_sf_command()

    # =====================================================
    # Command Builder
    # =====================================================

    def build_command(
        self,
        plan: ImplementationPlan,
        validation_result: dict,
    ) -> list[str]:
        """
        Build the validated Salesforce deployment command.

        The command is scoped to the metadata represented
        by the approved implementation plan.
        """

        self.validate_before_deployment(
            plan,
            validation_result,
        )

        command = (
            self.deployment_service
            .build_deploy_command(
                plan,
                validation_result,
            )
        )

        # -------------------------------------------------
        # Replace "sf" with resolved executable.
        #
        # Windows normally resolves this to:
        #
        # C:\\\Program Files\\\sf\\\bin\\\sf.CMD
        # -------------------------------------------------

        command[0] = (
            self._get_sf_command()
        )

        return command

    # =====================================================
    # JSON Parser
    # =====================================================

    @staticmethod
    def _parse_json_output(
        stdout: str,
    ) -> dict | None:
        """
        Parse Salesforce CLI JSON output.

        Returns None when stdout is empty or does not
        contain valid JSON.
        """

        if not stdout:
            return None

        try:

            parsed = json.loads(
                stdout
            )

        except json.JSONDecodeError:
            return None

        if not isinstance(
            parsed,
            dict,
        ):
            return None

        return parsed

    # =====================================================
    # Salesforce Error Extraction
    # =====================================================

    @staticmethod
    def _extract_error_message(
        parsed: dict | None,
        stdout: str,
        stderr: str,
    ) -> str:
        """
        Extract the most useful Salesforce deployment
        error message from CLI JSON output.

        Component failures are preferred because they
        normally contain the exact Salesforce metadata
        problem.
        """

        if isinstance(
            parsed,
            dict,
        ):

            # -------------------------------------------------
            # Look for component-level deployment failures.
            # -------------------------------------------------

            result_data = (
                parsed.get(
                    "result"
                )
            )

            if isinstance(
                result_data,
                dict,
            ):

                details = (
                    result_data.get(
                        "details"
                    )
                )

                if isinstance(
                    details,
                    dict,
                ):

                    component_failures = (
                        details.get(
                            "componentFailures"
                        )
                    )

                    if isinstance(
                        component_failures,
                        dict,
                    ):

                        component_failures = [
                            component_failures
                        ]

                    if isinstance(
                        component_failures,
                        list,
                    ):

                        messages = []

                        for failure in (
                            component_failures
                        ):

                            if not isinstance(
                                failure,
                                dict,
                            ):
                                continue

                            full_name = (
                                failure.get(
                                    "fullName"
                                )
                                or failure.get(
                                    "fileName"
                                )
                                or "Unknown component"
                            )

                            problem = (
                                failure.get(
                                    "problem"
                                )
                                or failure.get(
                                    "message"
                                )
                                or failure.get(
                                    "problemType"
                                )
                            )

                            if problem:

                                messages.append(
                                    f"{full_name}: "
                                    f"{problem}"
                                )

                        if messages:

                            return "; ".join(
                                messages
                            )

                # -------------------------------------------------
                # Some CLI responses put an error directly
                # inside result.
                # -------------------------------------------------

                result_error = (
                    result_data.get(
                        "error"
                    )
                    or result_data.get(
                        "message"
                    )
                )

                if result_error:

                    return str(
                        result_error
                    )

            # -------------------------------------------------
            # Standard Salesforce CLI JSON error.
            # -------------------------------------------------

            message = (
                parsed.get(
                    "message"
                )
            )

            if message:

                return str(
                    message
                )

            name = (
                parsed.get(
                    "name"
                )
            )

            if name:

                return str(
                    name
                )

        # -------------------------------------------------
        # Fallback to raw output.
        # -------------------------------------------------

        if stdout:
            return stdout

        if stderr:
            return stderr

        return (
            "Salesforce CLI deployment failed "
            "without returning an error message."
        )

    # =====================================================
    # Execute Deployment
    # =====================================================

    def deploy(
        self,
        plan: ImplementationPlan,
        validation_result: dict,
    ) -> dict:
        """
        Execute the Salesforce deployment.

        This method performs the REAL deployment.

        Salesforce CLI is requested to return JSON so
        deployment failures can be returned through the
        API without losing the original Salesforce error.
        """

        command = (
            self.build_command(
                plan,
                validation_result,
            )
        )

        try:

            from Backend.AI.app.services.sf_process import sf_arguments
            result = subprocess.run(
                sf_arguments(command),
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=180,
            )

        except subprocess.TimeoutExpired:
            return {'success':False,'planId':plan.id,'status':plan.status,
                    'targetOrg':self.target_org,'operationStatus':'unknown',
                    'reconciliationRequired':True,'returnCode':None,
                    'nextAction':'Do not resubmit. Check Salesforce deployment history and report the original job before retrying.',
                    'error':'Deployment submission timed out; Salesforce may still be processing it.'}

        except (OSError, RuntimeError) as exc:

            return {
                "success": False,
                "planId": plan.id,
                "status": plan.status,
                "targetOrg": self.target_org,
                "command": command,
                "returnCode": None,
                "stdout": "",
                "stderr": str(
                    exc
                ),
                "salesforceResponse": None,
                "errorMessage": str(
                    exc
                ),
            }

        # -------------------------------------------------
        # Normalize output.
        # -------------------------------------------------

        stdout = (
            result.stdout
            or ""
        ).strip()

        stderr = (
            result.stderr
            or ""
        ).strip()

        salesforce_response = (
            self._parse_json_output(
                stdout
            )
        )

        # =================================================
        # Failed Deployment
        # =================================================

        nested_result = (salesforce_response or {}).get("result", {})
        completed_successfully = (
            result.returncode == 0
            and isinstance(salesforce_response, dict)
            and salesforce_response.get("status") == 0
            and isinstance(nested_result, dict)
            and nested_result.get("success") is True
            and nested_result.get("done") is True
        )
        if not completed_successfully:

            error_message = (
                self._extract_error_message(
                    parsed=(
                        salesforce_response
                    ),
                    stdout=stdout,
                    stderr=stderr,
                )
            )

            return {
                "success": False,
                "planId": plan.id,
                "status": plan.status,
                "targetOrg": self.target_org,
                "command": command,
                "returnCode": (
                    result.returncode
                ),
                "stdout": stdout,
                "stderr": stderr,
                "salesforceResponse": (
                    salesforce_response
                ),
                "errorMessage": (
                    error_message
                ),
            }

        # =================================================
        # Successful Deployment
        # =================================================

        return {
            "success": True,
            "planId": plan.id,
            "status": plan.status,
            "targetOrg": self.target_org,
            "command": command,
            "returnCode": (
                result.returncode
            ),
            "stdout": stdout,
            "stderr": stderr,
            "salesforceResponse": (
                salesforce_response
            ),
            "errorMessage": None,
        }