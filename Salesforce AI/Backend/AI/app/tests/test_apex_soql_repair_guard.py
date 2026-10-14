"""Regression for Apex/SOQL validation before an AI repair can be saved."""
from Backend.AI.app.services.apex_validator import validate_apex_source


def check(body):
    errors, _ = validate_apex_source('ApexClass', 'ContactSearch',
                                     {'apexKind': 'Service', 'body': body})
    return errors


def test_with_user_mode_before_where_is_blocked():
    body = """public with sharing class ContactSearch {
    public static List<Contact> search(Id accountId) {
        return [SELECT Id FROM Contact WITH USER_MODE WHERE AccountId = :accountId ORDER BY Name LIMIT 10];
    }
    }"""
    assert any('WITH USER_MODE/SYSTEM_MODE' in err for err in check(body))


def test_with_user_mode_after_where_is_allowed():
    body = """public with sharing class ContactSearch {
    public static List<Contact> search(Id accountId) {
        return [SELECT Id FROM Contact WHERE AccountId = :accountId WITH USER_MODE ORDER BY Name LIMIT 10];
    }
    }"""
    assert not any('WITH USER_MODE/SYSTEM_MODE' in err for err in check(body))


def test_comments_and_strings_do_not_trigger_soql_check():
    body = """public with sharing class ContactSearch {
    // [SELECT Id FROM Contact WITH USER_MODE WHERE AccountId = :fake]
    public static String explain() {
        return '[SELECT Id FROM Contact WITH USER_MODE WHERE Id = :fake]';
    }
    }"""
    assert not any('WITH USER_MODE/SYSTEM_MODE' in err for err in check(body))


def test_multiple_queries_catch_later_invalid_query():
    body = """public with sharing class ContactSearch {
    public static void search(Id accountId) {
        List<Contact> a = [SELECT Id FROM Contact WHERE AccountId = :accountId WITH USER_MODE];
        List<Contact> b = [SELECT Id FROM Contact WITH USER_MODE WHERE AccountId = :accountId];
    }
    }"""
    assert any('WITH USER_MODE/SYSTEM_MODE' in err for err in check(body))
