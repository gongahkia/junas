from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import User
from diagrams.onprem.compute import Server
from diagrams.programming.framework import React
from diagrams.onprem.inmemory import Redis
# Try importing Sentry, if not available fall back to Server
try:
    from diagrams.saas.logging import Sentry
except ImportError:
    Sentry = Server

# AI Providers - using Server icons or specific SaaS if available
# We will use generic Server nodes for AI to be safe/standard
from diagrams.onprem.compute import Server as AIProvider

with Diagram("Junas Architecture", show=False, filename="asset/reference/architecture/junas_architecture", direction="LR"):
    user = User("User")

    with Cluster("Junas App"):
        web_app = React("Next.js\n(Frontend + API)")
        
        with Cluster("State & Security"):
            # Iron session handling
            session = Redis("Iron Session\n(Encrypted Cookie)")
            # Rate limiting
            ratelimit = Redis("Upstash Redis\n(Rate Limiting)")

    with Cluster("AI Providers"):
        anthropic = AIProvider("Anthropic\n(Claude)")
        google = AIProvider("Google\n(Gemini)")
        openai = AIProvider("OpenAI\n(GPT)")
        hf = AIProvider("HuggingFace")
        
    # Monitoring
    monitor = Sentry("Sentry\n(Monitoring)")

    # Flow
    user >> web_app
    web_app >> session
    web_app >> ratelimit
    
    web_app >> anthropic
    web_app >> google
    web_app >> openai
    web_app >> hf
    
    web_app >> monitor
