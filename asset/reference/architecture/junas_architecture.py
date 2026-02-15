from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.onprem.client import User
from diagrams.programming.framework import React
from diagrams.programming.language import Rust, TypeScript
from diagrams.onprem.mlops import MlFlow
from diagrams.onprem.database import PostgreSQL
from diagrams.generic.storage import Storage
from diagrams.generic.blank import Blank
graph_attr = {"bgcolor": "white", "pad": "0.5", "nodesep": "0.8", "ranksep": "1.2"}
with Diagram("Junas Architecture", filename="junas_architecture", outformat="png", show=False, direction="TB", graph_attr=graph_attr):
    user = User("User")
    with Cluster("Tauri Desktop App"):
        with Cluster("React Frontend (Vite)"):
            chat = React("Chat Interface")
            cmd = React("Command Palette")
            diagrams_r = React("Diagram Renderers")
            settings = React("Settings / Config")
        ipc = Blank("Tauri IPC Bridge")
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
        claude = Blank("Claude")
        gpt = Blank("GPT")
        gemini = Blank("Gemini")
        ollama = Blank("Ollama")
        lmstudio = Blank("LM Studio")
    with Cluster("External Services"):
        serper = Blank("Serper.dev")
        url_fetch = Blank("URL Fetch")
    keychain_os = Blank("macOS Keychain")
    onnx = Blank("ONNX Runtime")
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
