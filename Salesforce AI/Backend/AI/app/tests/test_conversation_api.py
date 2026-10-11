from Backend.AI.app.tests.test_workspace_regression import client,accounts

ROOT='/api/orgs/app_ours/conversations'


def create(client):
    response=client.post(ROOT,json={'title':'Employee leave system'})
    assert response.status_code==200,response.text
    return response.json()['id']


def test_conversation_round_trip_multiple_messages_and_plan_links(client):
    thread=create(client)
    messages=[{'role':'user','content':'Create leave system'}, {'role':'assistant','content':'Plan ready','kind':'plan','plan_id':'PLAN-old'}, {'role':'user','content':'Also add a Status field'}]
    for payload in messages:
        response=client.post(ROOT+'/'+thread+'/messages',json=payload)
        assert response.status_code==200,response.text
    saved=client.get(ROOT+'/'+thread).json()
    assert [m['content'] for m in saved['messages']]==[m['content'] for m in messages]
    assert saved['messages'][1]['plan_id']=='PLAN-old'
    assert client.get(ROOT).json()[0]['id']==thread


def test_foreign_conversation_and_plan_are_not_accessible(client):
    thread=create(client)
    with accounts.db() as db:
        db.execute('UPDATE workspace_conversations SET user_id=? WHERE id=?',('foreign',thread))
    assert client.get(ROOT+'/'+thread).status_code==404
    assert client.post(ROOT+'/'+thread+'/messages',json={'role':'user','content':'intrusion'}).status_code==404
    thread=create(client)
    with accounts.db() as db:db.execute('INSERT INTO plans VALUES(?,?,?)',('PLAN-foreign','foreign','app_ours'))
    assert client.post(ROOT+'/'+thread+'/messages',json={'role':'assistant','content':'foreign plan','plan_id':'PLAN-foreign'}).status_code==404


def test_clarification_persists_for_reply_after_reload(client):
    thread=create(client)
    payload={'role':'assistant','content':'Account exists. Reuse or choose another name?','kind':'clarification','context':'Create an object named Account'}
    assert client.post(ROOT+'/'+thread+'/messages',json=payload).status_code==200
    saved=client.get(ROOT+'/'+thread).json()['messages'][-1]
    assert saved['kind']=='clarification' and saved['context']==payload['context']


def test_unknown_org_and_oversized_message_are_rejected(client):
    assert client.post('/api/orgs/foreign/conversations',json={'title':'test'}).status_code==404
    thread=create(client)
    assert client.post(ROOT+'/'+thread+'/messages',json={'role':'user','content':'x'*20001}).status_code==422


def test_thread_plan_is_not_duplicated_as_a_separate_sidebar_chat(client):
    accounts.save_chat('u','app_ours','PLAN-old','Original requirement')
    thread=create(client)
    assert client.post(ROOT+'/'+thread+'/messages',json={'role':'assistant','content':'Plan ready','kind':'plan','plan_id':'PLAN-old'}).status_code==200
    assert client.get('/api/orgs/app_ours/chats').json()==[]


def test_legacy_collision_has_component_specific_question():
    from Backend.AI.app.services.planning_clarification import planning_error_detail
    detail=planning_error_detail(ValueError('Object already exists: Account (standard object). No new object was generated.'))
    assert detail['code']=='CLARIFICATION_REQUIRED' and 'Account' in detail['question']
    assert 'field type' not in detail['question'].lower()


def test_rejected_plan_remains_viewable_but_cannot_be_approved(client):
    response=client.post('/api/plans/PLAN-old/reject')
    assert response.status_code==200,response.text
    saved=client.get('/api/plans/PLAN-old')
    assert saved.status_code==200,saved.text
    assert saved.json()['state']=='rejected' and saved.json()['files']
    assert saved.json()['plan']['status']=='REJECTED'
    assert client.post('/api/plans/PLAN-old/approve',json={'source_hash':saved.json()['sourceHash']}).status_code==422
