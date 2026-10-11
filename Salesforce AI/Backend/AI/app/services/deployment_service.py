from pathlib import Path
from Backend.AI.app.services.page_layout_service import layout_path

from Backend.AI.app.validators.plan_validator import ImplementationPlan
from Backend.AI.app.services.profile_fls_service import component_path


class SalesforceDeploymentService:
    """Build deployment commands without generating files or executing CLI."""
    def __init__(self, target_org: str = "AIOrg", project_root: str = "."):
        self.target_org = target_org
        self.project_root = Path(project_root)

    def validate_plan(self, plan: ImplementationPlan) -> None:
        if plan.status != "APPROVED":
            raise ValueError("Only APPROVED plans can be deployed.")

    def validate_metadata_result(self, validation_result: dict) -> None:
        if not validation_result.get("valid"):
            raise ValueError("Metadata validation failed: " + "; ".join(map(str, validation_result.get("errors", []))))

    def _get_deployment_directories(self, plan: ImplementationPlan) -> list[str]:
        """Legacy call compatibility, now including ValidationRule parents."""
        directories = set()
        for item in plan.items:
            if item.action != "CREATE":
                continue
            component_path(item.metadataType, item.fullName)
            if item.metadataType in {"Flow", "ApexClass", "ApexTrigger"}:
                raise ValueError("Flow/Apex deployment requires explicit validated deploymentFiles.")
            directories.add(self.project_root / "force-app/main/default/objects" / item.fullName.split(".", 1)[0])
        if not directories:
            raise ValueError("No deployable Salesforce metadata was found in the approved plan.")
        return sorted(map(str, directories))

    def _get_deployment_files(self, plan, validation_result):
        # Exact files from the staged, validated endpoint workflow. No wildcard
        # profile directory and no unrelated fields from previous plans.
        allowed = {component_path(i.metadataType, i.fullName).as_posix() for i in plan.items if i.action == "CREATE"}
        required = set(allowed)
        allowed.add("force-app/main/default/profiles/Admin.profile-meta.xml")
        objects = {i.fullName.split(".", 1)[0] for i in plan.items
                   if i.action == "CREATE" and i.metadataType in {"CustomObject", "CustomField"}}
        for layout in validation_result.get("pageLayouts", {}).get("layouts", []):
            name = layout["fullName"]
            if name.partition("-")[0] not in objects or layout.get("object") != name.partition("-")[0]:
                raise ValueError("Layout does not belong to an approved CREATE object/field.")
            relative = layout_path(name).as_posix()
            allowed.add(relative)
            required.add(relative)
        if validation_result.get("pageLayouts", {}).get("layouts"):
            required.add("force-app/main/default/profiles/Admin.profile-meta.xml")
        root = self.project_root.resolve()
        found = set()
        for raw in validation_result["deploymentFiles"]:
            path = Path(raw)
            path = path if path.is_absolute() else root / path
            path = path.resolve()
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError as exc:
                raise ValueError("Deployment file is outside the deployment project.") from exc
            if relative not in allowed or not path.is_file():
                raise ValueError(f"Unexpected or missing deployment file: {raw}")
            flow_item = next((i for i in plan.items if i.action == "CREATE" and i.metadataType == "Flow" and component_path(i.metadataType, i.fullName).as_posix() == relative), None)
            if flow_item is not None:
                from Backend.AI.app.services.flow_generator import validate_flow_artifact
                validate_flow_artifact(path, flow_item, self.project_root)
            apex_item = next((i for i in plan.items if i.action == 'CREATE' and i.metadataType in {'ApexClass','ApexTrigger'} and component_path(i.metadataType,i.fullName).as_posix() == relative),None)
            if apex_item is not None:
                from Backend.AI.app.services.apex_validator import validate_apex_source
                from Backend.AI.app.services.apex_generator import _api_version
                import xml.etree.ElementTree as ET
                config = dict(apex_item.config or {})
                config['body'] = path.read_text(encoding='utf-8')
                errors, _ = validate_apex_source(apex_item.metadataType,apex_item.fullName,config)
                if errors:
                    raise ValueError('Invalid staged Apex: '+'; '.join(errors))
                meta_path = path.with_name(path.name+'-meta.xml')
                try:
                    metadata = ET.parse(meta_path).getroot()
                except (OSError, ET.ParseError) as exc:
                    raise ValueError('Missing or invalid Apex metadata companion.') from exc
                ns = 'http://soap.sforce.com/2006/04/metadata'
                if metadata.tag != '{'+ns+'}'+apex_item.metadataType or metadata.findtext('{'+ns+'}status') != 'Active' or metadata.findtext('{'+ns+'}apiVersion') != _api_version(root):
                    raise ValueError('Apex metadata companion does not match the project contract.')
            found.add(relative)
        if not required or not required.issubset(found):
            raise ValueError("Deployment files do not include every approved CREATE component.")
        return [str(root / relative) for relative in sorted(found)]

    def build_deploy_command(self, plan: ImplementationPlan, validation_result: dict) -> list[str]:
        self.validate_plan(plan)
        self.validate_metadata_result(validation_result)
        if not self.target_org:
            raise ValueError("Salesforce target org is not configured.")
        sources = self._get_deployment_files(plan, validation_result) if "deploymentFiles" in validation_result else self._get_deployment_directories(plan)
        command = ["sf", "project", "deploy", "start", "--target-org", self.target_org]
        for source in sources:
            command.extend(["--source-dir", source])
        apex = [item for item in plan.items if item.action == 'CREATE' and item.metadataType in {'ApexClass','ApexTrigger'}]
        if apex:
            tests = [item.fullName for item in apex if item.metadataType == 'ApexClass' and (item.config or {}).get('apexKind') == 'Test']
            if not tests:
                raise ValueError('Apex deployment requires approved test classes in the same package.')
            command.extend(['--test-level','RunSpecifiedTests'])
            for name in tests:
                command.extend(['--tests',name])
        command.extend(["--wait", "30", "--json"])
        return command

    def dry_run(self, plan: ImplementationPlan, validation_result: dict) -> dict:
        return {"planId": plan.id, "status": plan.status, "targetOrg": self.target_org,
                "dryRun": True, "command": self.build_deploy_command(plan, validation_result),
                "validatedFiles": validation_result.get("validatedFiles", [])}
