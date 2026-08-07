// JS Code to interact with the simplify route (via POST request).
messages = [{"role": "system", "content": "Hello. I am your personal financial instructor. What topic would you like to learn more about today?"}];
request_messages = [];
systemFinished = true;

// Unique ID for the conversation.
conversation_id = Math.random().toString(16).slice(2);

// If query string is not empty, then the user is loading a saved conversation.
const urlParams = new URLSearchParams(window.location.search);
cid = urlParams.get('cid');
if (cid) {
    // Get the conversation from the backend.
    getConversations().then(async (response) => {
        // Get the conversations from the response.
        conversations = await response.json();

        // Iterate over the conversations and find the one with the matching cid.
        let found = false
        for (var i = 0; i < conversations.length; i++) {
            if (conversations[i]["cid"] === cid) {
                // Set the messages and request_messages variables to the conversation's messages.
                messages = conversations[i]["messages"];
                request_messages = conversations[i]["request_messages"];
                conversation_id = cid;

                // Update the save button.
                saveState = true;
                saveButton.classList.toggle("bg-rose-900");
                saveButton.classList.toggle("hover:bg-rose-700");
                const saveSVG = `
                <svg class="fill-white ml-2 w-5 transition-all aspect-square" version="1.1" id="Capa_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" 
                viewBox="0 0 486 486" xml:space="preserve">
                    <g>
                        <g>
                            <path d="M473.7,485.75c6.8,0,12.3-5.5,12.3-12.3v-359.8c0-3.6-1.6-7-4.3-9.3L363,2.85c-0.2-0.2-0.4-0.3-0.6-0.4
                            c-0.3-0.2-0.5-0.4-0.8-0.6c-0.4-0.2-0.7-0.4-1.1-0.6c-0.3-0.1-0.6-0.3-0.9-0.4c-0.4-0.2-0.9-0.3-1.3-0.4c-0.3-0.1-0.6-0.2-0.9-0.2
                            c-0.8-0.1-1.5-0.2-2.3-0.2H12.3C5.5,0.05,0,5.55,0,12.35v461.3c0,6.8,5.5,12.3,12.3,12.3h461.4V485.75z M384.5,461.25h-283v-184.1
                            c0-3.7,3-6.6,6.6-6.6h269.8c3.7,0,6.6,3,6.6,6.6V461.25z M161.8,24.45h180.9v127.8c0,0.8-0.6,1.4-1.4,1.4h-178
                            c-0.8,0-1.4-0.7-1.4-1.4V24.45H161.8z M24.6,24.45h112.8v127.8c0,14.3,11.6,25.9,25.9,25.9h178c14.3,0,25.9-11.6,25.9-25.9V38.75
                            l94.2,80.6v341.9H409v-184.1c0-17.2-14-31.1-31.1-31.1H108.1c-17.2,0-31.1,14-31.1,31.1v184.2H24.6V24.45z"/>
                            <path d="M227.4,77.65h53.8v32.6c0,6.8,5.5,12.3,12.3,12.3s12.3-5.5,12.3-12.3v-44.8c0-6.8-5.5-12.3-12.3-12.3h-66.1
                            c-6.8,0-12.3,5.5-12.3,12.3S220.7,77.65,227.4,77.65z"/>
                            <path d="M304.5,322.85h-123c-6.8,0-12.3,5.5-12.3,12.3s5.5,12.3,12.3,12.3h123c6.8,0,12.3-5.5,12.3-12.3
                            S311.3,322.85,304.5,322.85z"/>
                            <path d="M304.5,387.75h-123c-6.8,0-12.3,5.5-12.3,12.3s5.5,12.3,12.3,12.3h123c6.8,0,12.3-5.5,12.3-12.3
                            S311.3,387.75,304.5,387.75z"/>
                        </g>
                    </g>
                </svg>`
                const deleteSVG = `
                <svg class="fill-white stroke-white ml-2 w-5 aspect-square" enable-background="new 0 0 40 40" id="delete" version="1.1" viewBox="0 0 40 40" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
                    <g>
                        <path d="M28,40H11.8c-3.3,0-5.9-2.7-5.9-5.9V16c0-0.6,0.4-1,1-1s1,0.4,1,1v18.1c0,2.2,1.8,3.9,3.9,3.9H28c2.2,0,3.9-1.8,3.9-3.9V16   c0-0.6,0.4-1,1-1s1,0.4,1,1v18.1C33.9,37.3,31.2,40,28,40z"/>
                    </g>
                    <g>
                        <path d="M33.3,4.9h-7.6C25.2,2.1,22.8,0,19.9,0s-5.3,2.1-5.8,4.9H6.5c-2.3,0-4.1,1.8-4.1,4.1S4.2,13,6.5,13h26.9   c2.3,0,4.1-1.8,4.1-4.1S35.6,4.9,33.3,4.9z M19.9,2c1.8,0,3.3,1.2,3.7,2.9h-7.5C16.6,3.2,18.1,2,19.9,2z M33.3,11H6.5   c-1.1,0-2.1-0.9-2.1-2.1c0-1.1,0.9-2.1,2.1-2.1h26.9c1.1,0,2.1,0.9,2.1,2.1C35.4,10.1,34.5,11,33.3,11z"/>
                    </g>
                    <g>
                        <path d="M12.9,35.1c-0.6,0-1-0.4-1-1V17.4c0-0.6,0.4-1,1-1s1,0.4,1,1v16.7C13.9,34.6,13.4,35.1,12.9,35.1z"/>
                    </g>
                    <g>
                        <path d="M26.9,35.1c-0.6,0-1-0.4-1-1V17.4c0-0.6,0.4-1,1-1s1,0.4,1,1v16.7C27.9,34.6,27.4,35.1,26.9,35.1z"/>
                    </g>
                    <g>
                        <path d="M19.9,35.1c-0.6,0-1-0.4-1-1V17.4c0-0.6,0.4-1,1-1s1,0.4,1,1v16.7C20.9,34.6,20.4,35.1,19.9,35.1z"/>
                    </g>
                </svg>`
                const word = saveState ? `<span class="max-md:hidden">Unsave</span>` : `<span class="max-md:hidden">Save</span>`;
                const svg = saveState ? deleteSVG : saveSVG;
                saveButton.innerHTML = word + svg;

                // Update the chat UI.
                updateChat();
                found = true;
                break;
            }
        }

        if (!found) {
            // If the conversation was not found, then redirect to the simplify page without query params.
            window.location.href = "/simplify";
        }
    });
}

async function submit(event) {
    event.preventDefault();
    if (!systemFinished) {
        return;
    }

    user_prompt = document.getElementById("user_prompt");
    messages = [...messages, {"role": "user", "content": user_prompt.value}];
    updateChat();

    data = JSON.stringify({"messages": messages})
    if (messages.length == 2) {
        data = JSON.stringify({"topic": user_prompt.value});
    }
    user_prompt.value = ""; // Clear the input field.
    systemFinished = false;

    // Send POST request to simplify route. Response will be a stream.
    await fetch("/simplify", {
        method: "POST",
        body: data,
        headers: {
            "Content-Type": "application/json"
        }
    })
    // Retrieve its body as ReadableStream
    .then(async (response) => {
        const reader = response.body.getReader();
        // read() returns a promise that resolves when a value has been received
        await reader.read().then(function pump({ done, value }) {
            if (done) {
                // Do something with last chunk of data then exit reader
                return;
            }
            // Otherwise do something here to process current chunk
            // Convert Uint8Array to string
            var decoder = new TextDecoder();
            var chunk = decoder.decode(value);

            // Check if the chunk is a json object in string form.
            try {
                chunk = JSON.parse(chunk);
            } catch (e) {
                // If not, then it is a string.
                chunk = chunk;
            }

            // If chunk is a json...
            if (typeof chunk === "object") {
                request_messages = chunk;
            } else {
                if (typeof chunk !== "string") {
                    chunk = chunk.toString();
                }
                // Replace all newlines with <br> tags.
                chunk = chunk.replace(/\n/g, "<br>");
                // Replace ** with nothing.
                chunk = chunk.replace(/\*\*/g, "");

                // If last message is a user message, add the chunk to the messages array.
                if (messages[messages.length - 1]["role"] === "user") {
                    var conversation = document.getElementById("conversation");
                    messages = [...messages, {"role": "system", "content": chunk}];
                    const last_message = conversation.lastChild;
                    last_message.scrollIntoView();
                } else {
                    messages[messages.length - 1]["content"] += chunk;
                }
            }

            // Update the chat UI
            updateChat();

            // Read some more, and call this function again
            return reader.read().then(pump);
        });
        systemFinished = true;
        if (saveState) {
            updateConversation(conversation_id, messages, request_messages);
        }
    })
    .catch((err) => console.error(err));
}

function updateChat() {
    // Update the Chat UI to reflect the messages data model.
    var conversation = document.getElementById("conversation");

    // Clear the conversation.
    conversation.innerHTML = "";

    // Iterate through messages and add them to the conversation.
    for (var i = 0; i < messages.length; i++) {
        var message = messages[i];
        var div = document.createElement("div");
        div.className = "h-auto w-full text-lg text-white py-10 px-[10vw]";
        if (message["role"] === "user") {
            div.className += " bg-slate-100/25";
        }
        div.innerHTML = message["content"];
        conversation.appendChild(div);
    }
    conversation.scrollTop = conversation.scrollHeight - conversation.clientHeight;

    if (messages.length > 1 && saveButton) {
        saveButton.classList.remove("hidden");
    }
}

let saveState = false;
async function toggleSave(e) {
    // Toggle the favorite button state in the backend asychronously
    saveState = !saveState;
    if (saveState) {
        addConversation(conversation_id, messages, request_messages);
    } else {
        removeConversation(conversation_id, messages, request_messages);
    }
    saveButton.classList.toggle("bg-rose-900");
    saveButton.classList.toggle("hover:bg-rose-700");
    const saveSVG = `
    <svg class="fill-white ml-2 w-5 transition-all aspect-square" version="1.1" id="Capa_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" 
    viewBox="0 0 486 486" xml:space="preserve">
        <g>
            <g>
                <path d="M473.7,485.75c6.8,0,12.3-5.5,12.3-12.3v-359.8c0-3.6-1.6-7-4.3-9.3L363,2.85c-0.2-0.2-0.4-0.3-0.6-0.4
                c-0.3-0.2-0.5-0.4-0.8-0.6c-0.4-0.2-0.7-0.4-1.1-0.6c-0.3-0.1-0.6-0.3-0.9-0.4c-0.4-0.2-0.9-0.3-1.3-0.4c-0.3-0.1-0.6-0.2-0.9-0.2
                c-0.8-0.1-1.5-0.2-2.3-0.2H12.3C5.5,0.05,0,5.55,0,12.35v461.3c0,6.8,5.5,12.3,12.3,12.3h461.4V485.75z M384.5,461.25h-283v-184.1
                c0-3.7,3-6.6,6.6-6.6h269.8c3.7,0,6.6,3,6.6,6.6V461.25z M161.8,24.45h180.9v127.8c0,0.8-0.6,1.4-1.4,1.4h-178
                c-0.8,0-1.4-0.7-1.4-1.4V24.45H161.8z M24.6,24.45h112.8v127.8c0,14.3,11.6,25.9,25.9,25.9h178c14.3,0,25.9-11.6,25.9-25.9V38.75
                l94.2,80.6v341.9H409v-184.1c0-17.2-14-31.1-31.1-31.1H108.1c-17.2,0-31.1,14-31.1,31.1v184.2H24.6V24.45z"/>
                <path d="M227.4,77.65h53.8v32.6c0,6.8,5.5,12.3,12.3,12.3s12.3-5.5,12.3-12.3v-44.8c0-6.8-5.5-12.3-12.3-12.3h-66.1
                c-6.8,0-12.3,5.5-12.3,12.3S220.7,77.65,227.4,77.65z"/>
                <path d="M304.5,322.85h-123c-6.8,0-12.3,5.5-12.3,12.3s5.5,12.3,12.3,12.3h123c6.8,0,12.3-5.5,12.3-12.3
                S311.3,322.85,304.5,322.85z"/>
                <path d="M304.5,387.75h-123c-6.8,0-12.3,5.5-12.3,12.3s5.5,12.3,12.3,12.3h123c6.8,0,12.3-5.5,12.3-12.3
                S311.3,387.75,304.5,387.75z"/>
            </g>
        </g>
    </svg>`
    const deleteSVG = `
    <svg class="fill-white stroke-white ml-2 w-5 aspect-square" enable-background="new 0 0 40 40" id="delete" version="1.1" viewBox="0 0 40 40" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <g>
            <path d="M28,40H11.8c-3.3,0-5.9-2.7-5.9-5.9V16c0-0.6,0.4-1,1-1s1,0.4,1,1v18.1c0,2.2,1.8,3.9,3.9,3.9H28c2.2,0,3.9-1.8,3.9-3.9V16   c0-0.6,0.4-1,1-1s1,0.4,1,1v18.1C33.9,37.3,31.2,40,28,40z"/>
        </g>
        <g>
            <path d="M33.3,4.9h-7.6C25.2,2.1,22.8,0,19.9,0s-5.3,2.1-5.8,4.9H6.5c-2.3,0-4.1,1.8-4.1,4.1S4.2,13,6.5,13h26.9   c2.3,0,4.1-1.8,4.1-4.1S35.6,4.9,33.3,4.9z M19.9,2c1.8,0,3.3,1.2,3.7,2.9h-7.5C16.6,3.2,18.1,2,19.9,2z M33.3,11H6.5   c-1.1,0-2.1-0.9-2.1-2.1c0-1.1,0.9-2.1,2.1-2.1h26.9c1.1,0,2.1,0.9,2.1,2.1C35.4,10.1,34.5,11,33.3,11z"/>
        </g>
        <g>
            <path d="M12.9,35.1c-0.6,0-1-0.4-1-1V17.4c0-0.6,0.4-1,1-1s1,0.4,1,1v16.7C13.9,34.6,13.4,35.1,12.9,35.1z"/>
        </g>
        <g>
            <path d="M26.9,35.1c-0.6,0-1-0.4-1-1V17.4c0-0.6,0.4-1,1-1s1,0.4,1,1v16.7C27.9,34.6,27.4,35.1,26.9,35.1z"/>
        </g>
        <g>
            <path d="M19.9,35.1c-0.6,0-1-0.4-1-1V17.4c0-0.6,0.4-1,1-1s1,0.4,1,1v16.7C20.9,34.6,20.4,35.1,19.9,35.1z"/>
        </g>
    </svg>`
    const word = saveState ? `<span class="max-md:hidden">Unsave</span>` : `<span class="max-md:hidden">Save</span>`;
    const svg = saveState ? deleteSVG : saveSVG;
    saveButton.innerHTML = word + svg;
}


document.getElementById("form").onsubmit = submit;
let saveButton = document.getElementById("save-button")
if (saveButton) {
    saveButton.addEventListener("click", toggleSave)
}

updateChat();