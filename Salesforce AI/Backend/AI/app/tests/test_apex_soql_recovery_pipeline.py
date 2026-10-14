from Backend.AI.app.services.apex_soql_recovery import correct_user_mode_order
from Backend.AI.app.services.apex_validator import validate_apex_source

BAD = '''public with sharing class ExampleController {
@AuraEnabled(cacheable=true)
public static List<Contact> searchContacts(Id accountId, String term) {
return [SELECT Id, Name FROM Contact WITH USER_MODE WHERE AccountId = :accountId
AND Name LIKE :term ORDER BY Name LIMIT 100];
}
}'''

def test_repair_moves_mode_after_filter_before_order():
    updated, changes = correct_user_mode_order(BAD)
    assert changes == 1
    assert updated.index('WHERE') < updated.index('WITH USER_MODE') < updated.index('ORDER BY')
    issues, _ = validate_apex_source('ApexClass', 'ExampleController', {'apexKind':'Service','body':updated})
    assert not any('SOQL WITH USER_MODE' in error for error in issues)

def test_valid_queries_untouched():
    correct = BAD.replace('WITH USER_MODE WHERE AccountId = :accountId\nAND Name LIKE :term', 'WHERE AccountId = :accountId\nAND Name LIKE :term WITH USER_MODE')
    assert correct_user_mode_order(correct) == (correct, 0)

def test_does_not_touch_strings_and_comments():
    s = "public class X {String demo = 'SELECT Id FROM Contact WITH USER_MODE WHERE Name'; // WITH USER_MODE WHERE\n}"
    assert correct_user_mode_order(s) == (s, 0)

def test_preserves_unambiguous_multiple_queries():
    s = BAD.replace('return [', 'List<Contact> first = [').replace('];\n}', '];\nreturn [SELECT Id FROM Contact WITH SYSTEM_MODE WHERE AccountId = :accountId LIMIT 1];\n}')
    corrected, count = correct_user_mode_order(s)
    assert count == 2
    assert corrected.index('WHERE') < corrected.index('WITH USER_MODE')
    assert 'WHERE AccountId = :accountId\n        WITH SYSTEM_MODE LIMIT' in corrected

def test_fails_closed_on_unbalanced_apex():
    assert correct_user_mode_order(BAD[:-1]) == (BAD[:-1], 0)
