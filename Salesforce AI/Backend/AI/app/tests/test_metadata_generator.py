import pytest



from Backend.AI.app.services.metadata_generator import (

    SalesforceMetadataGenerator,

)



from Backend.AI.app.validators.plan_validator import (

    ImplementationPlan,

)



from Backend.AI.app.validators.metadata_spec_validator import (

    MetadataSpecification,

)





# =========================================================

# Existing Appointment Plan Helper

# =========================================================



def create_approved_plan():



    return ImplementationPlan.model_validate(

        {

            "id": "PLAN-META-001",

            "requirementId": "REQ-META-001",

            "summary": (

                "Create Appointment object "

                "with date and status fields."

            ),

            "assumptions": [],

            "items": [

                {

                    "id": "ITEM-001",

                    "action": "CREATE",

                    "metadataType": "CustomObject",

                    "fullName": "Appointment__c",

                    "label": "Appointment",

                    "description": (

                        "Stores appointment information."

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

                        "Stores appointment date."

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

                        "Stores appointment status."

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

            "status": "APPROVED",

        }

    )





# =========================================================

# Text Family ImplementationPlan Helper

# =========================================================



def create_text_family_plan():



    return ImplementationPlan.model_validate(

        {

            "id": "PLAN-TEXT-FAMILY-001",

            "requirementId": (

                "REQ-TEXT-FAMILY-001"

            ),

            "summary": (

                "Create Salesforce text-family "

                "custom fields."

            ),

            "assumptions": [],

            "items": [

                {

                    "id": "ITEM-001",

                    "action": "CREATE",

                    "metadataType": "CustomObject",

                    "fullName": "Text_Test__c",

                    "label": "Text Test",

                    "description": (

                        "Object used to test "

                        "text-family fields."

                    ),

                    "dependencies": [],

                    "approval": "PENDING",

                },

                {

                    "id": "ITEM-002",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Text_Test__c."

                        "Description__c"

                    ),

                    "label": "Description",

                    "description": (

                        "Stores a short description."

                    ),

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "TextArea",

                        "required": False,

                    },

                    "approval": "PENDING",

                },

                {

                    "id": "ITEM-003",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Text_Test__c."

                        "Notes__c"

                    ),

                    "label": "Notes",

                    "description": (

                        "Stores long notes."

                    ),

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "LongTextArea",

                        "length": 50000,

                        "visibleLines": 8,

                        "required": False,

                    },

                    "approval": "PENDING",

                },

                {

                    "id": "ITEM-004",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Text_Test__c."

                        "Summary__c"

                    ),

                    "label": "Summary",

                    "description": (

                        "Stores rich-text content."

                    ),

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "fieldType": (

                            "Rich Text Area"

                        ),

                        "length": 40000,

                        "visibleLines": 25,

                        "required": False,

                    },

                    "approval": "PENDING",

                },

                {

                    "id": "ITEM-005",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Text_Test__c."

                        "Secret_Token__c"

                    ),

                    "label": "Secret Token",

                    "description": (

                        "Stores encrypted text."

                    ),

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "EncryptedText",

                        "length": 100,

                        "maskChar": "asterisk",

                        "maskType": "lastFour",

                        "required": False,

                    },

                    "approval": "PENDING",

                },

            ],

            "storyPoints": 5,

            "status": "APPROVED",

        }

    )





# =========================================================

# MetadataSpecification Text Family Helper

# =========================================================



def create_text_family_metadata_specification():



    return MetadataSpecification.model_validate(

        {

            "planId": (

                "PLAN-TEXT-FAMILY-SPEC-001"

            ),

            "metadata": [

                {

                    "itemId": "ITEM-001",

                    "action": "CREATE",

                    "metadataType": "CustomObject",

                    "fullName": "Spec_Text_Test__c",

                    "label": "Spec Text Test",

                    "description": (

                        "Object for metadata "

                        "specification tests."

                    ),

                    "dependencies": [],

                    "config": {},

                },

                {

                    "itemId": "ITEM-002",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Spec_Text_Test__c."

                        "Description__c"

                    ),

                    "label": "Description",

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "TextArea",

                        "required": False,

                    },

                },

                {

                    "itemId": "ITEM-003",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Spec_Text_Test__c."

                        "Notes__c"

                    ),

                    "label": "Notes",

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "LongTextArea",

                        "length": 50000,

                        "visibleLines": 8,

                        "required": False,

                    },

                },

                {

                    "itemId": "ITEM-004",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Spec_Text_Test__c."

                        "Rich_Notes__c"

                    ),

                    "label": "Rich Notes",

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "Html",

                        "length": 40000,

                        "visibleLines": 25,

                        "required": False,

                    },

                },

                {

                    "itemId": "ITEM-005",

                    "action": "CREATE",

                    "metadataType": "CustomField",

                    "fullName": (

                        "Spec_Text_Test__c."

                        "Secret_Value__c"

                    ),

                    "label": "Secret Value",

                    "dependencies": [

                        "ITEM-001"

                    ],

                    "config": {

                        "type": "EncryptedText",

                        "length": 100,

                        "maskChar": "asterisk",

                        "maskType": "lastFour",

                        "required": False,

                    },

                },

            ],

            "validationIssues": [],

        }

    )





# =========================================================

# Existing Generator Tests

# =========================================================



def test_metadata_generator_requires_approved_plan(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    plan = create_approved_plan()



    plan.status = "DRAFT"



    with pytest.raises(

        ValueError,

        match=(

            "Only APPROVED plans can "

            "generate metadata"

        ),

    ):

        generator.generate(

            plan

        )





def test_generates_custom_object(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    plan = create_approved_plan()



    files = generator.generate(

        plan

    )



    object_file = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Appointment__c"

        / "Appointment__c.object-meta.xml"

    )



    assert str(

        object_file

    ) in files



    assert object_file.exists()



    content = object_file.read_text(

        encoding="utf-8"

    )



    assert "<CustomObject" in content



    assert (

        "<label>Appointment</label>"

        in content

    )





def test_generates_custom_fields(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    plan = create_approved_plan()



    generator.generate(

        plan

    )



    date_file = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Appointment__c"

        / "fields"

        / "Appointment_Date__c.field-meta.xml"

    )



    status_file = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Appointment__c"

        / "fields"

        / "Status__c.field-meta.xml"

    )



    assert date_file.exists()

    assert status_file.exists()



    date_content = (

        date_file.read_text(

            encoding="utf-8"

        )

    )



    status_content = (

        status_file.read_text(

            encoding="utf-8"

        )

    )



    assert (

        "<type>Date</type>"

        in date_content

    )



    assert (

        "<type>Picklist</type>"

        in status_content

    )





def test_custom_field_requires_object_field_format(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    plan = create_approved_plan()



    plan.items[1].fullName = (

        "InvalidFieldName"

    )



    with pytest.raises(

        ValueError,

        match=(

            "CustomField fullName must use"

        ),

    ):

        generator.generate(

            plan

        )





# =========================================================

# TextArea

# =========================================================



def test_generates_text_area_field(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    generator.generate(

        create_text_family_plan()

    )



    file_path = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Text_Test__c"

        / "fields"

        / "Description__c.field-meta.xml"

    )



    assert file_path.exists()



    content = file_path.read_text(

        encoding="utf-8"

    )



    assert (

        "<type>TextArea</type>"

        in content

    )



    assert (

        "<required>false</required>"

        in content

    )





# =========================================================

# LongTextArea

# =========================================================



def test_generates_long_text_area_field(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    generator.generate(

        create_text_family_plan()

    )



    file_path = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Text_Test__c"

        / "fields"

        / "Notes__c.field-meta.xml"

    )



    assert file_path.exists()



    content = file_path.read_text(

        encoding="utf-8"

    )



    assert (

        "<type>LongTextArea</type>"

        in content

    )



    assert (

        "<length>50000</length>"

        in content

    )



    assert (

        "<visibleLines>8</visibleLines>"

        in content

    )





# =========================================================

# Html / Rich Text

# =========================================================



def test_generates_html_field(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    generator.generate(

        create_text_family_plan()

    )



    file_path = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Text_Test__c"

        / "fields"

        / "Summary__c.field-meta.xml"

    )



    assert file_path.exists()



    content = file_path.read_text(

        encoding="utf-8"

    )



    assert (

        "<type>Html</type>"

        in content

    )



    assert (

        "<length>40000</length>"

        in content

    )



    assert (

        "<visibleLines>25</visibleLines>"

        in content

    )





# =========================================================

# EncryptedText

# =========================================================



def test_generates_encrypted_text_field(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    generator.generate(

        create_text_family_plan()

    )



    file_path = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Text_Test__c"

        / "fields"

        / "Secret_Token__c.field-meta.xml"

    )



    assert file_path.exists()



    content = file_path.read_text(

        encoding="utf-8"

    )



    assert (

        "<type>EncryptedText</type>"

        in content

    )



    assert (

        "<length>100</length>"

        in content

    )



    assert (

        "<maskChar>asterisk</maskChar>"

        in content

    )



    assert (

        "<maskType>lastFour</maskType>"

        in content

    )





# =========================================================

# fieldType Alias

# =========================================================



def test_supports_field_type_config_key(

    tmp_path,

):



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    generator.generate(

        create_text_family_plan()

    )



    file_path = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Text_Test__c"

        / "fields"

        / "Summary__c.field-meta.xml"

    )



    content = file_path.read_text(

        encoding="utf-8"

    )



    assert (

        "<type>Html</type>"

        in content

    )





# =========================================================

# Long Text Validation

# =========================================================



def test_rejects_invalid_long_text_length(

    tmp_path,

):



    plan = create_text_family_plan()



    plan.items[2].config[

        "length"

    ] = 200



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    with pytest.raises(

        ValueError,

        match=(

            "length must be between"

        ),

    ):

        generator.generate(

            plan

        )





def test_rejects_invalid_visible_lines(

    tmp_path,

):



    plan = create_text_family_plan()



    plan.items[2].config[

        "visibleLines"

    ] = 51



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    with pytest.raises(

        ValueError,

        match=(

            "visibleLines must be between"

        ),

    ):

        generator.generate(

            plan

        )





# =========================================================

# EncryptedText Validation

# =========================================================



def test_rejects_invalid_encrypted_text_length(

    tmp_path,

):



    plan = create_text_family_plan()



    plan.items[4].config[

        "length"

    ] = 176



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    with pytest.raises(

        ValueError,

        match=(

            "length must be between"

        ),

    ):

        generator.generate(

            plan

        )





def test_rejects_invalid_encrypted_mask_char(

    tmp_path,

):



    plan = create_text_family_plan()



    plan.items[4].config[

        "maskChar"

    ] = "#"



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    with pytest.raises(

        ValueError,

        match="maskChar",

    ):

        generator.generate(

            plan

        )





def test_rejects_invalid_encrypted_mask_type(

    tmp_path,

):



    plan = create_text_family_plan()



    plan.items[4].config[

        "maskType"

    ] = "unsupported"



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    with pytest.raises(

        ValueError,

        match="unsupported maskType",

    ):

        generator.generate(

            plan

        )





# =========================================================

# MetadataSpecification -> Generator -> XML

# =========================================================



def test_generates_text_family_from_metadata_specification(

    tmp_path,

):



    specification = (

        create_text_family_metadata_specification()

    )



    generator = SalesforceMetadataGenerator(

        project_root=str(tmp_path)

    )



    generated_files = (

        generator.generate_from_specification(

            specification

        )

    )



    assert len(

        generated_files

    ) == 5



    fields_root = (

        tmp_path

        / "force-app"

        / "main"

        / "default"

        / "objects"

        / "Spec_Text_Test__c"

        / "fields"

    )



    text_area_file = (

        fields_root

        / "Description__c.field-meta.xml"

    )



    long_text_file = (

        fields_root

        / "Notes__c.field-meta.xml"

    )



    html_file = (

        fields_root

        / "Rich_Notes__c.field-meta.xml"

    )



    encrypted_file = (

        fields_root

        / "Secret_Value__c.field-meta.xml"

    )



    assert text_area_file.exists()

    assert long_text_file.exists()

    assert html_file.exists()

    assert encrypted_file.exists()



    text_area_content = (

        text_area_file.read_text(

            encoding="utf-8"

        )

    )



    long_text_content = (

        long_text_file.read_text(

            encoding="utf-8"

        )

    )



    html_content = (

        html_file.read_text(

            encoding="utf-8"

        )

    )



    encrypted_content = (

        encrypted_file.read_text(

            encoding="utf-8"

        )

    )



    assert (

        "<type>TextArea</type>"

        in text_area_content

    )



    assert (

        "<type>LongTextArea</type>"

        in long_text_content

    )



    assert (

        "<length>50000</length>"

        in long_text_content

    )



    assert (

        "<visibleLines>8</visibleLines>"

        in long_text_content

    )



    assert (

        "<type>Html</type>"

        in html_content

    )



    assert (

        "<length>40000</length>"

        in html_content

    )



    assert (

        "<visibleLines>25</visibleLines>"

        in html_content

    )



    assert (

        "<type>EncryptedText</type>"

        in encrypted_content

    )



    assert (

        "<length>100</length>"

        in encrypted_content

    )



    assert (

        "<maskChar>asterisk</maskChar>"

        in encrypted_content

    )



    assert (

        "<maskType>lastFour</maskType>"

        in encrypted_content

    )





# =========================================================

# MetadataSpecification Validation

# =========================================================



def test_metadata_specification_rejects_invalid_long_text_length():



    data = (

        create_text_family_metadata_specification()

        .model_dump()

    )



    data["metadata"][2]["config"][

        "length"

    ] = 200



    with pytest.raises(

        ValueError,

        match="length must be between",

    ):



        MetadataSpecification.model_validate(

            data

        )





def test_metadata_specification_rejects_invalid_visible_lines():



    data = (

        create_text_family_metadata_specification()

        .model_dump()

    )



    data["metadata"][2]["config"][

        "visibleLines"

    ] = 51



    with pytest.raises(

        ValueError,

        match=(

            "visibleLines must be between"

        ),

    ):



        MetadataSpecification.model_validate(

            data

        )





def test_metadata_specification_rejects_invalid_encrypted_length():



    data = (

        create_text_family_metadata_specification()

        .model_dump()

    )



    data["metadata"][4]["config"][

        "length"

    ] = 176



    with pytest.raises(

        ValueError,

        match="length must be between",

    ):



        MetadataSpecification.model_validate(

            data

        )