from Backend.AI.app.salesforce.metadata_service import (
    SalesforceMetadataService,
)


service = SalesforceMetadataService(
    target_org="AIOrg"
)


account = service.describe_object(
    "Account"
)


print("\nSalesforce Object:")
print(account["name"])

print("\nLabel:")
print(account["label"])

print("\nFields:")

for field in account["fields"]:
    print(
        f"- {field['name']} "
        f"| {field['type']} "
        f"| required={field['required']}"
    )