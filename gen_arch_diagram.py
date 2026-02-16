from diagrams import Diagram, Cluster, Edge
from diagrams.programming.framework import React, FastAPI
from diagrams.programming.language import Python, NodeJS, JavaScript
from diagrams.onprem.database import MongoDB
from diagrams.onprem.ml import PyTorch
from diagrams.onprem.client import User
from diagrams.generic.storage import Storage
from diagrams.generic.compute import Rack
from diagrams.custom import Custom
from diagrams.onprem.network import Nginx
import os, urllib.request

ICON_DIR = "/tmp/caipng_icons"
os.makedirs(ICON_DIR, exist_ok=True)

ICONS = {
    "gemini": ("https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Google_Gemini_logo.svg/200px-Google_Gemini_logo.svg.png", "gemini.png"),
    "onnx": ("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/ONNX_logo_main.png/200px-ONNX_logo_main.png", "onnx.png"),
    "vite": ("https://vitejs.dev/logo.svg", "vite.svg"),
    "camera": ("https://cdn-icons-png.flaticon.com/128/685/685655.png", "camera.png"),
}

for key, (url, fname) in ICONS.items():
    path = os.path.join(ICON_DIR, fname)
    if not os.path.exists(path):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=10).read()
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"warn: could not download {key} icon: {e}")

def icon(name):
    fname = ICONS[name][1]
    path = os.path.join(ICON_DIR, fname)
    return path if os.path.exists(path) else None

graph_attr = {
    "bgcolor": "white",
    "pad": "0.5",
    "fontsize": "14",
    "fontname": "Helvetica",
    "rankdir": "TB",
    "nodesep": "0.8",
    "ranksep": "1.0",
    "splines": "ortho",
}
node_attr = {
    "fontsize": "11",
    "fontname": "Helvetica",
}
edge_attr = {
    "fontsize": "9",
    "fontname": "Helvetica",
    "color": "#555555",
}

OUTPUT = "/home/gongahkia/Desktop/coding/projects/caipng/asset/reference/architecture"

with Diagram(
    "cAIpng - Food Recognition & Nutrition Estimation",
    filename=OUTPUT,
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png",
):
    # --- user / browser ---
    user = User("User\n(Browser + Webcam)")

    # --- frontend ---
    with Cluster("Frontend (React + Vite)", graph_attr={"bgcolor": "#E8F4FD", "style": "rounded", "pencolor": "#2196F3"}):
        react_app = React("App.jsx\nRoot Component")
        liveview = JavaScript("LiveView.jsx\nVideo Feed + Canvas\nNMS / Tracking / FPS")
        local_detect = JavaScript("Local Detection\n(Color Heuristics\nFallback)")

    # --- backend ---
    with Cluster("Backend (Node.js + Express)", graph_attr={"bgcolor": "#FFF3E0", "style": "rounded", "pencolor": "#FF9800"}):
        server = NodeJS("server.js\nExpress + Middleware\nHelmet / CORS / Morgan")

        with Cluster("Routes & Controllers", graph_attr={"bgcolor": "#FFF8E1", "style": "dashed", "pencolor": "#FFA726"}):
            analyze_ep = Rack("POST /api/live/analyze\nFrame Analysis")
            macros_ep = Rack("POST /api/live/macros\nMacro Estimation")
            health_ep = Rack("GET /health\nStatus Check")

        with Cluster("Services", graph_attr={"bgcolor": "#FFF8E1", "style": "dashed", "pencolor": "#FFA726"}):
            vision_svc = Storage("visionService\nDish Analysis\nBBox Generation")
            model_svc = Storage("modelService\nONNX Inference\nCache (LRU 200)\nAbstention Logic")
            img_proc = Storage("imageProcessor\nSharp: Resize 224x224\nNormalize (ImageNet)")
            llm_svc = Storage("llmService\nPrompt Construction\nRetry + Fallback")

        rate_limit = Storage("Rate Limiter\n100 req / 15 min")

    # --- ml inference ---
    with Cluster("ML Inference (ONNX Runtime)", graph_attr={"bgcolor": "#F3E5F5", "style": "rounded", "pencolor": "#9C27B0"}):
        if icon("onnx"):
            onnx_model = Custom("caifan_model.onnx\nFood Classification\nTop-5 Predictions", icon("onnx"))
        else:
            onnx_model = Storage("caifan_model.onnx\nFood Classification\nTop-5 Predictions")
        classes_json = Storage("classes.json\n101 Food Categories")

    # --- external services ---
    with Cluster("External Services", graph_attr={"bgcolor": "#E8F5E9", "style": "rounded", "pencolor": "#4CAF50"}):
        if icon("gemini"):
            gemini = Custom("Google Gemini API\ngemini-2.0-flash\nMacro Estimation", icon("gemini"))
        else:
            gemini = Storage("Google Gemini API\ngemini-2.0-flash\nMacro Estimation")
        mongo = MongoDB("MongoDB\ncaipng DB\n50+ Dish Records")

    # --- training pipeline ---
    with Cluster("Training Pipeline (Python + PyTorch)", graph_attr={"bgcolor": "#FCE4EC", "style": "rounded", "pencolor": "#E91E63"}):
        train_tui = Python("train_tui.py\nInteractive TUI\nRich Progress")
        dataset = Python("dataset.py\nCaiFanDataset\nFood-101 Loader")
        metrics = Python("metrics.py\nP/R/F1\nConfusion Matrix")
        pytorch = PyTorch("PyTorch\nResNet Backbone\nFine-tuning")
        onnx_export = Storage("ONNX Export\nModel Conversion")

    # === edges ===

    # user <-> frontend
    user >> Edge(label="webcam frames", color="#2196F3") >> react_app
    react_app >> liveview
    liveview >> local_detect

    # frontend -> backend
    liveview >> Edge(label="base64 frame\nPOST /analyze", color="#FF9800") >> server
    liveview >> Edge(label="derived text\nPOST /macros", color="#FF9800") >> server
    liveview >> Edge(label="GET /health", style="dashed", color="#999999") >> server

    # server -> routes
    server >> analyze_ep
    server >> macros_ep
    server >> health_ep

    # routes -> services
    analyze_ep >> vision_svc
    vision_svc >> img_proc
    vision_svc >> model_svc
    macros_ep >> rate_limit >> llm_svc

    # services -> inference
    model_svc >> Edge(label="preprocessed\ntensor", color="#9C27B0") >> onnx_model
    onnx_model - classes_json

    # services -> external
    llm_svc >> Edge(label="prompt +\ndish context", color="#4CAF50") >> gemini
    llm_svc >> Edge(label="dish nutrition\nreference", color="#4CAF50") >> mongo
    health_ep >> Edge(style="dashed", color="#999999") >> mongo

    # training pipeline
    dataset >> pytorch
    train_tui >> pytorch
    pytorch >> metrics
    pytorch >> onnx_export
    onnx_export >> Edge(label="deploy model", style="dashed", color="#E91E63") >> onnx_model

    # response back
    gemini >> Edge(label="macros JSON\n+ narrative", color="#4CAF50", style="dashed") >> llm_svc
    onnx_model >> Edge(label="top-5 predictions\n+ confidence", color="#9C27B0", style="dashed") >> model_svc

print(f"Diagram saved to {OUTPUT}.png")
