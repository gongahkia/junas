from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import User
from diagrams.programming.framework import React
from diagrams.programming.language import Rust
from diagrams.generic.storage import Storage
from diagrams.generic.blank import Blank
from diagrams.custom import Custom
graph_attr = {"bgcolor": "white", "pad": "0.5", "nodesep": "0.8", "ranksep": "1.2"}
with Diagram("Junas Architecture", filename="junas_architecture", outformat="png", show=False, direction="TB", graph_attr=graph_attr):
    user = User("User")
    with Cluster("Tauri Desktop App"):
        with Cluster("React Frontend (Vite)"):
            chat = React("Chat Interface")
            cmd = React("Command Palette")
            diagrams_r = React("Diagram Renderers")
            settings = React("Settings / Config")
        ipc = Custom("Tauri IPC Bridge", "./tauri.webp")
        with Cluster("Rust Backend"):
            providers = Rust("providers.rs")
            streaming = Rust("streaming.rs")
            keychain = Rust("keychain.rs")
            tools = Rust("tools.rs")
            ml = Rust("ml.rs")
        with Cluster("Local Storage"):
            settings_json = Storage("settings.json")
            conversations = Storage("conversations/")
            profiles = Storage("profiles.json")
    with Cluster("AI Providers"):
        claude = Custom("Claude", "./claude.png")
        gpt = Custom("GPT", "./openai.webp")
        gemini = Custom("Gemini", "./gemini.png")
        ollama = Custom("Ollama", "./ollama.png")
        lmstudio = Custom("LM Studio", "./lmstudio.png")
    with Cluster("External Services"):
        serper = Custom("Serper.dev", "./serper.png")
        url_fetch = Custom("URL Fetch", "./url_fetch.png")
    keychain_os = Custom("macOS Keychain", "./keychain.webp")
    onnx = Custom("ONNX Runtime", "./onnx.png")
    user >> Edge(label="launches") >> chat
    chat >> ipc # frontend -> IPC
    cmd >> ipc
    diagrams_r >> ipc
    settings >> ipc
    ipc >> providers # IPC -> backend
    ipc >> streaming
    ipc >> keychain
    ipc >> tools
    ipc >> ml
    providers >> claude # backend -> external
    providers >> gpt
    providers >> gemini
    providers >> ollama
    providers >> lmstudio
    keychain >> keychain_os
    tools >> serper
    tools >> url_fetch
    ml >> onnx
    keychain >> settings_json # backend -> local storage
    providers >> conversations
    settings >> profiles
