from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles  
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import asyncio
import json
import logging
import csv
import os
from datetime import datetime

app = FastAPI(title="RealTime Chat Hub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.mount("/static", StaticFiles(directory="static"), name="static")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Message(BaseModel):
    client_id: str
    content: str
    timestamp: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_history: List[Message] = []
        self.csv_file_path = "message_history.csv"
        # Create CSV file and write header if it doesn't exist
        if not os.path.exists(self.csv_file_path):
            with open(self.csv_file_path, mode='w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["sender", "message", "time"])

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.broadcast(f"System: {client_id} has joined the chat.")

    def disconnect(self, client_id: str):
        del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    def add_to_history(self, message: Message):
        self.message_history.append(message)
        self.append_to_csv(message)
        if len(self.message_history) > 100:  
            self.message_history.pop(0)

    def append_to_csv(self, message: Message):
        with open(self.csv_file_path, mode='a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([message.client_id, message.content, message.timestamp])

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NightOwl Chat</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: Georgia, serif;;
                background: url('static/bg.png') no-repeat center center fixed;
                background-size: cover;
                color: #e0e0e0;
            }
            .overlay {
                background-color: rgba(18, 18, 18, 0.8);
                min-height: 100vh;
                padding: 20px;
            }
            .card {
                background-color: #1e1e1e;
                border: none;
                border-radius: 15px;
            }
            .btn-orange {
                background-color: #ff6a00;
                border-color: #ff6a00;
                color: white;
                border-radius: 25px;
                padding: 10px 20px;
                transition: all 0.3s ease;
            }
            .btn-orange:hover {
                background-color: #ff8c00;
                border-color: #ff8c00;
                color: white;
            }
            .form-control {
                background-color: #2a2a2a;
                border: none;
                color: #e0e0e0;
                border-radius: 25px;
            }
            .form-control:focus {
                background-color: #2a2a2a;
                color: #e0e0e0;
                box-shadow: 0 0 0 0.2rem rgba(255, 106, 0, 0.25);
            }
            .message {
                padding: 5px 0;
                margin-bottom: 10px;
            }
            .message.self {
                text-align: right;
            }
            .message .content {
                display: inline-block;
                max-width: 80%;
                word-wrap: break-word;
            }
            .message small {
                font-size: 0.75rem;
                color: #aaa;
            }
            #messages {
                height: 400px;
                overflow-y: auto;
                padding: 15px;
            }
            ::-webkit-scrollbar {
                width: 8px;
            }
            ::-webkit-scrollbar-track {
                background: #1a1a1a;
            }
            ::-webkit-scrollbar-thumb {
                background-color: #ff6a00;
                border-radius: 4px;
            }
            @media (max-width: 768px) {
                body {
                    background-size: cover;
                }
                .container {
                    padding-left: 15px;
                    padding-right: 15px;
                }
                .card {
                    border-radius: 10px;
                }
                h1.h3 {
                    font-size: 1.5rem;
                }
                #messages {
                    height: 600px;
                }
                .btn-orange {
                    padding: 8px 15px;
                    font-size: 0.9rem;
                }
                .form-control {
                    border-radius: 20px;
                    padding: 10px;
                }
            }
        </style>
    </head>
    <body>
        <div class="overlay">
            <div class="container py-3">
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <div class="card shadow-lg">
                            <div class="card-header bg-dark d-flex justify-content-between align-items-center">
                                <h1 class="h3 mb-0 text-orange">NightOwl Chat</h1>
                                <img src="/static/Designer.png" alt="NightOwl Logo" class="rounded-circle" width="40" height="40">
                            </div>
                            <div class="card-body">
                                <div id="login-form" class="mb-4">
                                    <center><input type="text" id="client_id" class="form-control mb-2 w-50" placeholder="Enter your nickname"></center>
                                    <center><button onclick="connectWebSocket()" class="btn btn-orange w-30">Join the Night</button></center>
                                </div>

                                <div id="chat-interface" class="d-none">
                                    <div id="messages" class="mb-3 bg-dark rounded"></div>
                                    <div class="input-group">
                                        <input type="text" id="message" class="form-control" placeholder="Whisper into the night...">
                                        <button onclick="sendMessage()" class="btn btn-orange">Send</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
let socket;
let clientId;

function connectWebSocket() {
    clientId = document.getElementById("client_id").value.trim();
    if (!clientId) {
        alert("Please enter a valid name.");
        return;
    }

    document.getElementById("login-form").classList.add("d-none");
    document.getElementById("chat-interface").classList.remove("d-none");

    const ws_url = `ws://${window.location.host}/ws/${encodeURIComponent(clientId)}`;
    socket = new WebSocket(ws_url);

    socket.onopen = function(event) {
        console.log("WebSocket connection established.");
    };

    socket.onmessage = function(event) {
        const message = JSON.parse(event.data);
        displayMessage(message);
    };

    socket.onerror = function(event) {
        console.error("WebSocket error observed:", event);
    };

    socket.onclose = function(event) {
        console.log("WebSocket connection closed.");
    };
}

function sendMessage() {
    const messageInput = document.getElementById("message");
    const message = messageInput.value.trim();
    if (message && socket && socket.readyState === WebSocket.OPEN) {
        socket.send(message);
        messageInput.value = "";
    }
}

// Add an event listener for the Enter key press
document.getElementById("message").addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        event.preventDefault(); // Prevent the default action (like form submission)
        sendMessage();
    }
});

function formatTime(date) {
    let hours = date.getHours();
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; 
    return `${hours}:${minutes} ${ampm}`;
}

function displayMessage(message) {
    const messageContainer = document.createElement("div");
    messageContainer.classList.add("message", message.client_id === clientId ? "self" : "other");
    messageContainer.innerHTML = `<div class="content">${message.content}</div><small>${formatTime(new Date(message.timestamp))}</small>`;
    document.getElementById("messages").appendChild(messageContainer);
    document.getElementById("messages").scrollTop = document.getElementById("messages").scrollHeight;
}
        </script>
    </body>
    </html>
    """)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            timestamp = datetime.now().isoformat()
            message = Message(client_id=client_id, content=data, timestamp=timestamp)
            manager.add_to_history(message)
            await manager.broadcast(json.dumps(message.dict()))
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(f"System: {client_id} has left the chat.")
