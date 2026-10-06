from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest

from Backend.AI.app.services.change_generator import (
    SalesforceChangeGenerator,
    SALESFORCE_METADATA_NS,
)

from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
)


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[4]
)

REAL_FIELD_FILE = (
    PROJECT_ROOT
    / "force-app"
    / "main"
    / "default"
    / "objects"
    / "AI_Test_Session__c"
    / "fields"
    / "Status__c.field-meta.xml"
)


NS = {
    "sf": SALESFORCE_METADATA_NS
}


# =========================================================
# Helper
# =========================================================

def get_picklist_values(
    file_path: Path,
) -> list[str]:

    root = ET.parse(
        file_path
    ).getroot()

    values = []

    for element in root.findall(
        ".//sf:value/sf:fullName",
        NS,
    ):

        if element.text:

            values.append(
                element.text.strip()
            )

    return values


# =========================================================
# Real Metadata Integration Test
# =========================================================

def test_change_generator_with_real_retrieved_status_field(
    tmp_path,
):

    # -----------------------------------------------------
    # 1. Skip when real retrieved metadata is unavailable
    # -----------------------------------------------------

    if not REAL_FIELD_FILE.exists():

        pytest.skip(
            "Real Salesforce metadata is not available "
            "locally. Skipping real change-generator "
            "integration test."
        )

    # -----------------------------------------------------
    # 2. Verify existing real picklist values
    # -----------------------------------------------------

    original_values = (
        get_picklist_values(
            REAL_FIELD_FILE
        )
    )

    print(
        "\nORIGINAL REAL PICKLIST VALUES:"
    )

    print(
        original_values
    )

    assert "Planned" in original_values
    assert "Active" in original_values
    assert "Completed" in original_values

    assert "Cancelled" not in original_values, (
        "Cancelled already exists in the retrieved "
        "Salesforce metadata."
    )

    # -----------------------------------------------------
    # 3. Build temporary Salesforce project structure
    # -----------------------------------------------------

    temp_field_dir = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "AI_Test_Session__c"
        / "fields"
    )

    temp_field_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_field_file = (
        temp_field_dir
        / "Status__c.field-meta.xml"
    )

    # -----------------------------------------------------
    # 4. Copy REAL metadata to temporary location
    #
    # Original project file remains unchanged.
    # -----------------------------------------------------

    shutil.copy2(
        REAL_FIELD_FILE,
        temp_field_file,
    )

    # -----------------------------------------------------
    # 5. Create validated ChangeSpecification
    # -----------------------------------------------------

    specification = (
        ChangeSpecification.model_validate(
            {
                "planId": (
                    "PLAN-CHANGE-REAL-001"
                ),
                "changes": [
                    {
                        "itemId": "ITEM-001",
                        "action": "UPDATE",
                        "metadataType": (
                            "CustomField"
                        ),
                        "fullName": (
                            "AI_Test_Session__c."
                            "Status__c"
                        ),
                        "dependencies": [
                            "AI_Test_Session__c"
                        ],
                        "changes": {
                            "addPicklistValues": [
                                "Cancelled"
                            ]
                        },
                    }
                ],
                "validationIssues": [],
            }
        )
    )

    # -----------------------------------------------------
    # 6. Apply change ONLY to temporary project
    # -----------------------------------------------------

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    modified_files = generator.apply(
        specification
    )

    # -----------------------------------------------------
    # 7. Read modified temporary XML
    # -----------------------------------------------------

    updated_values = (
        get_picklist_values(
            temp_field_file
        )
    )

    print(
        "\nUPDATED TEMPORARY PICKLIST VALUES:"
    )

    print(
        updated_values
    )

    # -----------------------------------------------------
    # 8. Verify original values are preserved
    # -----------------------------------------------------

    assert "Planned" in updated_values
    assert "Active" in updated_values
    assert "Completed" in updated_values

    # -----------------------------------------------------
    # 9. Verify new value was added
    # -----------------------------------------------------

    assert "Cancelled" in updated_values

    assert (
        updated_values.count(
            "Cancelled"
        )
        == 1
    )

    # -----------------------------------------------------
    # 10. Verify generator reports modified file
    # -----------------------------------------------------

    assert len(
        modified_files
    ) == 1

    assert (
        "Status__c.field-meta.xml"
        in modified_files[0]
    )

    # -----------------------------------------------------
    # 11. CRITICAL SAFETY CHECK
    #
    # Confirm original retrieved XML was NOT modified.
    # -----------------------------------------------------

    original_values_after_test = (
        get_picklist_values(
            REAL_FIELD_FILE
        )
    )

    assert (
        original_values_after_test
        == original_values
    )

    assert (
        "Cancelled"
        not in original_values_after_test
    )