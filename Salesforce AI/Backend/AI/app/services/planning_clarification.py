"""Convert recognized unresolved facts to targeted user questions, not guesses."""
def planning_error_detail(exc):
    message = str(exc)
    if getattr(exc,"code",None)=="NO_CHANGE_REQUIRED":
        return {"code": exc.code,"message": message}
    if hasattr(exc, "question"):
        return {"code": "CLARIFICATION_REQUIRED", "message": message, "question": exc.question}
    if hasattr(exc, 'candidate'):
        from Backend.AI.app.account_api import current_account, current_org
        from Backend.AI.app.account_api import db
        import json, time
        from uuid import uuid4
        owner, org = current_account.get(), current_org.get()
        if owner and org:
            ticket = uuid4().hex
            with db() as c:
                c.execute('INSERT INTO repair_tickets VALUES(?,?,?,?,?)',
                    (ticket,owner,org,json.dumps({'originalRequirement':exc.requirement,
                    'rejectedPlan':exc.candidate,'failureEvidence':message}),time.time()))
            return {'code': 'PLAN_REJECTED', 'message': message, 'repairTicket': ticket}

    if 'existing calculated field' in message:
        question = 'This reference is not verified as a Salesforce Formula field. Should the Flow use its stored value, or calculate a new value? If calculating, provide the expression and source fields.'
    elif 'already exists' in message.lower():
        question = message + ' Should we reuse the existing component unchanged, or create a separate component with a different name?'
    elif 'requires existing org metadata for ' in message or 'Field parent ' in message:
        question = message + ' Should we include this object as a new custom object, or use an existing object? Reply with the intended object API name and any required field definitions. An inaccessible object may need permission changes rather than creation.'
    elif any(part in message.lower() for part in ('unknown or inaccessible', 'neither verified', 'unknown field')):
        question = message + ' Should we use a different existing field, or include a new field? For a new field, provide its object API name, field API name and type. If it already exists, confirm its API name and access.'
    elif 'access or sharing instructions' in message:
        question = 'This version supports the default object sharing configuration only. Should we proceed without changing sharing, or revise the requirement?'
    else:
        return message
    return {'code': 'CLARIFICATION_REQUIRED', 'message': message, 'question': question}
