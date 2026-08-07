async function addConversation(cid, messages, request_messages) {
    await fetch('/conversations', {
        method: 'POST',
        headers: {
            'action': 'add',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            'cid': cid,
            'messages': messages,
            'request_messages': request_messages
        })
    });
}

async function removeConversation(cid, messages, request_messages) {
    await fetch('/conversations', {
        method: 'POST',
        headers: {
            'action': 'remove',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            'cid': cid,
            'messages': messages,
            'request_messages': request_messages
        })
    });
}

async function updateConversation(cid, messages, request_messages) {
    await fetch('/conversations', {
        method: 'POST',
        headers: {
            'action': 'update',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            'cid': cid,
            'messages': messages,
            'request_messages': request_messages
        })
    });
}

async function getConversations() {
    const response = await fetch('/conversations').then((response) => {
        return response;
    });
    return response;
}