import pytest
from Backend.AI.app.services.apex_validator import validate_apex_source
from Backend.AI.app.services.apex_generator import generate_apex
from types import SimpleNamespace

@pytest.mark.parametrize("operation", ["insert new Account(Name='X');", "Database.update(records);", "List<Account> rows=[SELECT Id FROM Account];"])
def test_unsafe_loop_is_blocked_in_validator_and_writer(tmp_path, operation):
    body="public with sharing class Worker { public static void run() { for(Integer i=0;i<200;i++) { " + operation + " } } }"
    config={"apexKind":"Service", "body":body}
    errors, _=validate_apex_source("ApexClass", "Worker", config)
    assert any("inside a loop is prohibited" in error for error in errors)
    with pytest.raises(ValueError, match="inside a loop is prohibited"):
        generate_apex(SimpleNamespace(metadataType="ApexClass",fullName="Worker",config=config),tmp_path)
    assert not (tmp_path/'force-app').exists()

def test_bulk_collection_and_single_write_are_allowed():
    body="public with sharing class Worker { public static void run() { List<Account> records=new List<Account>(); for(Integer i=0;i<200;i++) { records.add(new Account(Name='X')); } insert as user records; } }"
    errors,_=validate_apex_source("ApexClass","Worker",{"apexKind":"Service","body":body})
    assert not errors
