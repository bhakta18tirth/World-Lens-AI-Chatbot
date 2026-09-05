from flask import Flask,jsonify
import requests
from flask_socketio import SocketIO, emit
import json
from pprint import pprint

app = Flask(__name__, static_folder='pages', static_url_path='/my_files')

socketio = SocketIO(app, cors_allowed_origins='*')

endpoint = 'http://127.0.0.1:11434/api/chat'

tag_response = requests.get('http://127.0.0.1:11434/api/tags')

models = tag_response.json()['models']

model_options = []

for model in models:
    model_options.append({
        'value': model['model'],
        'label': model['name']
    })

message_mapping = {} # in-memory database
start_id = 1

@socketio.on('connect')
def connect():
    emit('models', model_options)
    emit('thread_list', get_thread_list())

@socketio.on('chat')
def chat(data):
    global start_id
    prompt = data.get('prompt')
    model = data.get('model') # model can be selected by user so they can generate different responses
    id = data.get('id', None) # thread id
    old_id = id
    print('id', id)
    print('start_id before', start_id)

    if id is None:
        message_mapping[start_id] = []
        id = start_id
        start_id += 1
        print('start_id after', start_id)

    messages = message_mapping.get(id, [])

    messages.append({
        'role': 'user', # user / assistant / system
        'content': prompt
    })

    message_mapping[id] = messages

    if old_id is None:
        emit('thread_list', get_thread_list())
        emit('new_thread_id', {'id':id})

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": """
    You are Atlas AI, a geography expert.
    Answer geography questions clearly with useful details.
    -Give short and informative answers (2-4 sentences).
    -Include important facts only.
    -Do not give one-line answers and also not give too much unless the user asks for a short answer.
    """
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_predict":150
        },
        "think": False
    }
    keywords = [
    "country",
    "countries",
    "capital",
    "geography",
    "map",
    "river",
    "mountain",
    "continent",
    "ocean",
    "population",
    "climate",
    "flag",
    "city",
    "border",
    "india",
    "japan",
    "china",
    "usa",
    "uk",
    "europe",
    "asia"
]
    
    if not any(word in prompt.lower() for word in keywords):
        emit('token', {
            'token': 'I can only answer geography and countries related questions.'
        })
        emit('complete')
        return

    response = requests.post(
        endpoint,
        json=payload,
        stream=True,
        timeout=100
    )

    print("OLLAMA STATUS:", response.status_code)
    server_response = ""


    for line in response.iter_lines(decode_unicode=True):

        if not line:
            continue
        print("RAW:", line)
        chunk = json.loads(line)
        
        token = chunk.get("message", {}).get("content", "")

        if token:

            emit(
                "token",
                {
                    "token": token
                }
            )
            server_response += token

        if chunk.get("done"):

            messages.append(
                {
                    "role":"assistant",
                    "content":server_response
                }
            )
            message_mapping[id] = messages
            emit("complete")
            print("FINAL:", server_response)
            break
    pprint(message_mapping)
    print('----------------')
    pprint(messages)

@socketio.on('get_messages')
def get_messages(data):
    id = data.get('id')
    print('thread id', id)
    messages = message_mapping.get(id,[])
    print('below messages for thread id', id)
    emit('messages', messages)

# function that prepare the thread list with id and their first message
def get_thread_list():
    thread_list = []
    for id in message_mapping:
        thread_list.append({
            'id': id,
            'title': message_mapping.get(id)[0].get('content')
        })
    print('thread_list')
    pprint(thread_list)
    thread_list.reverse() # reverse the order of the threads, new thread on top always.
    return thread_list

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)