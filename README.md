[![](https://img.shields.io/badge/junas_1.0.0-passing-green)](https://github.com/gongahkia/junas/releases/tag/1.0.0)
![Vercel Deploy](https://deploy-badge.vercel.app/vercel/junas)

# `Junas`

`Junas` is a [BYOK](https://en.wikipedia.org/wiki/Bring_your_own_encryption) Web App that automates out the [boring part](#tools) of legal tasks.

## Stack

* *Frontend*: [Next.js 16](https://nextjs.org/), [React 19](https://react.dev/), [Tailwind CSS 3](https://tailwindcss.com/), [TypeScript 5](https://www.typescriptlang.org/)
* *AI Providers*: [Anthropic SDK](https://www.anthropic.com/) (Claude), [Google Generative AI](https://ai.google.dev/) (Gemini), [OpenAI](https://platform.openai.com/) (GPT)
* *Markdown Rendering*: [react-markdown](https://remarkjs.github.io/react-markdown/), [remark-gfm](https://github.com/remarkjs/remark-gfm), [remark-math](https://github.com/remarkjs/remark-math), [rehype-katex](https://github.com/remarkjs/remark-math/tree/main/packages/rehype-katex), [KaTeX](https://katex.org/)
* *Web Scraping*: [Cheerio](https://cheerio.js.org/), [Axios](https://axios-http.com/)
* *Session Management*: [iron-session](https://github.com/vvo/iron-session)
* *Rate Limiting*: [Upstash Redis](https://upstash.com/), [Upstash Ratelimit](https://github.com/upstash/ratelimit)
* *Monitoring*: [Sentry](https://sentry.io/)

## Usage

> [!IMPORTANT]  
> Read the [legal disclaimer](#legal-disclaimer) before using `Junas`.

Use the live website [**here**](https://junas.vercel.app/).

## Screenshots

### Landing page

<div align="center">
    <img width="100%" src="./asset/reference/1.png">
</div>

### Draft documents, IRAC Analysis

<div align="center">
    <img width="45%" src="./asset/reference/2.png">
    <img width="45%" src="./asset/reference/3.png">
</div>

### Case facts, Case ruling

<div align="center">
    <img width="45%" src="./asset/reference/4.png">
    <img width="45%" src="./asset/reference/5.png">
</div>

### Obiter, Ratio, Legal argumentation

<div align="center">
    <img width="33%" src="./asset/reference/6.png">
    <img width="33%" src="./asset/reference/7.png">
    <img width="33%" src="./asset/reference/8.png">
</div>

### Sample response

<div align="center">
    <img width="100%" src="./asset/reference/9.png">
</div>

### Export conversation, Import conversation history

<div align="center">
    <img width="45%" src="./asset/reference/10.png">
    <img width="45%" src="./asset/reference/12.png">
</div>

### Start a new chat, Configure API Keys

<div align="center">
    <img width="45%" src="./asset/reference/11.png">
    <img width="45%" src="./asset/reference/13.png">
</div>

## Local Usage

The below instructions are for locally hosting `Junas`.

1. First run the below.

```console
$ git clone https://github.com/gongahkia/junas && cd junas
$ npm install
```

2. Then execute the following to run the local dev server or build for production.

```console
$ npm run dev
$ npm run build
$ npm start
```

3. Finally, get your API keys from the below sources, then configure them inside the `Junas` web app settings.
    1. [Google Gemini](https://aistudio.google.com/) *(free tier available)*
    2. [OpenAI](https://platform.openai.com/)
    3. [Anthropic](https://console.anthropic.com/)

## Tools

`Junas` currently provides 6 structured analysis workflows, explicitly called by their keywords.

| Tool | Keywords | Purpose |
|------|-----------------|---------|
| Document Drafting | `draft`,  | Drafts legal documents based off 13 comprehensive templates |
| IRAC Analysis | `irac`, `analyze`, `legal analysis` | Structure legal problems using Issue, Rule, Application, Conclusion |
| Case Facts Extraction | `facts`, `case facts`, `extract facts` | Extract and organize material facts from case law |
| Ruling Analysis | `ruling`, `judgment`, `decision` | Analyze court decisions, reasoning, and remedies |
| Obiter Dicta | `obiter`, `dicta`, `remarks` | Identify non-binding judicial observations |
| Ratio Decidendi | `ratio`, `binding principle`, `precedent` | Extract binding legal principles from cases |
| Legal Argumentation | `argue`, `argument`, `submission` | Build persuasive legal arguments with authorities |

## Architecture

### C4 Context Diagram (Level 1)

Shows Junas in its environment with users and external systems.

```mermaid
C4Context
    title System Context Diagram for Junas

    Person(user, "Legal Professional", "Lawyers, law students, legal researchers who need assistance with legal analysis and document drafting")

    System(junas, "Junas", "AI-Powered Legal Assistant that provides legal analysis tools, document drafting, and case law processing for Singapore Law")

    System_Ext(gemini, "Google Gemini API", "Provides AI language model capabilities")
    System_Ext(openai, "OpenAI API", "Provides GPT model capabilities")
    System_Ext(anthropic, "Anthropic API", "Provides Claude model capabilities")
    System_Ext(legal_sources, "Legal Data Sources", "Singapore legal databases and case law sources")

    Rel(user, junas, "Uses for legal analysis and document drafting", "HTTPS")
    Rel(junas, gemini, "Sends prompts and receives AI-generated analysis", "HTTPS/API")
    Rel(junas, openai, "Sends prompts and receives AI-generated analysis", "HTTPS/API")
    Rel(junas, anthropic, "Sends prompts and receives AI-generated analysis", "HTTPS/API")
    Rel(junas, legal_sources, "Scrapes case law and legal information", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

### C4 Container Diagram (Level 2)

Shows the high-level technical building blocks of Junas.

```mermaid
C4Container
    title Container Diagram for Junas

    Person(user, "Legal Professional", "Uses Junas for legal tasks")

    System_Boundary(junas_boundary, "Junas System") {
        Container(web_app, "Web Application", "Next.js, React, TypeScript", "Provides user interface for legal analysis, chat interaction, and document management")
        Container(api, "API Routes", "Next.js API Routes", "Handles requests for AI processing, authentication, tool execution, and data scraping")
        ContainerDb(browser_storage, "Browser Storage", "LocalStorage, Zustand", "Stores user API keys (BYOK), chat history, and user preferences locally")
        Container(ml_engine, "ML/NER Engine", "Xenova Transformers", "Performs Named Entity Recognition for legal entities and case citations")
    }

    System_Ext(ai_providers, "AI Provider APIs", "Google Gemini, OpenAI, Anthropic")
    System_Ext(legal_sources, "Legal Data Sources", "Singapore legal databases")
    System_Ext(sentry, "Sentry", "Error tracking and monitoring")

    Rel(user, web_app, "Interacts with", "HTTPS")
    Rel(web_app, api, "Makes API calls", "JSON/HTTPS")
    Rel(web_app, browser_storage, "Reads/writes", "Browser API")
    Rel(api, ai_providers, "Sends prompts, receives completions", "HTTPS/API")
    Rel(api, legal_sources, "Scrapes legal data", "HTTPS")
    Rel(api, ml_engine, "Extracts legal entities", "Function calls")
    Rel(api, sentry, "Sends error logs", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

### C4 Component Diagram (Level 3)

Shows the internal components of the Junas application.

```mermaid
C4Component
    title Component Diagram for Junas API and Application

    Container_Boundary(web_boundary, "Web Application") {
        Component(chat_ui, "Chat Interface", "React Components", "Manages chat interaction, message display, and user input")
        Component(template_ui, "Template Selector", "React Components", "Provides UI for selecting and using legal document templates")
        Component(settings_ui, "Settings Manager", "React Components", "Manages API keys and provider selection")
        Component(export_ui, "Export Components", "React Components", "Handles PDF export and data import/export")
    }

    Container_Boundary(api_boundary, "API Routes") {
        Component(chat_api, "Chat API", "Next.js API Route", "Processes chat requests and coordinates AI responses")
        Component(tools_api, "Tools API", "Next.js API Route", "Executes legal analysis tools (IRAC, case facts, etc.)")
        Component(auth_api, "Auth API", "Next.js API Route", "Manages session authentication")
        Component(providers_api, "Providers API", "Next.js API Route", "Lists available AI providers")
    }

    Container_Boundary(lib_boundary, "Core Libraries") {
        Component(provider_factory, "Provider Factory", "TypeScript", "Creates appropriate AI provider instances based on user selection")
        Component(chat_service, "Chat Service", "TypeScript", "Orchestrates AI chat interactions and streaming responses")
        Component(tool_system, "Legal Tools System", "TypeScript", "Implements IRAC, case analysis, ratio decidendi, obiter dicta tools")
        Component(ner_processor, "NER Processor", "Xenova Transformers", "Extracts legal entities, case names, and citations")
        Component(scrapers, "Web Scrapers", "Cheerio, Axios", "Scrapes Singapore case law and statute data")
        Component(template_engine, "Template Engine", "TypeScript", "Manages legal document templates")
        Component(session_mgmt, "Session Management", "iron-session", "Handles secure session storage")
        Component(storage_mgmt, "Storage Manager", "Zustand", "Manages client-side state and persistence")
    }

    System_Ext(ai_apis, "AI Provider APIs")
    System_Ext(legal_data, "Legal Data Sources")

    Rel(chat_ui, chat_api, "Sends messages", "JSON/HTTPS")
    Rel(template_ui, tools_api, "Requests document drafts", "JSON/HTTPS")
    Rel(settings_ui, providers_api, "Updates provider config", "JSON/HTTPS")
    Rel(settings_ui, storage_mgmt, "Stores API keys", "Browser API")

    Rel(chat_api, chat_service, "Uses")
    Rel(tools_api, tool_system, "Executes")
    Rel(auth_api, session_mgmt, "Uses")

    Rel(chat_service, provider_factory, "Creates providers")
    Rel(provider_factory, ai_apis, "Calls")
    Rel(tool_system, ner_processor, "Extracts entities")
    Rel(tool_system, scrapers, "Fetches legal data")
    Rel(scrapers, legal_data, "Scrapes")
    Rel(tool_system, template_engine, "Uses templates")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

### Data Flow Diagram

Shows how data flows through the system during a typical legal analysis request.

```mermaid
sequenceDiagram
    actor User
    participant UI as Web Interface
    participant Storage as Browser Storage
    participant API as API Routes
    participant Tools as Legal Tools
    participant NER as NER Engine
    participant AI as AI Provider
    participant Scraper as Web Scraper
    participant Legal as Legal Sources

    User->>UI: Input legal query with tool keyword
    UI->>Storage: Retrieve API key
    Storage-->>UI: Return API key
    UI->>API: POST /api/chat (query, provider, API key)

    API->>Tools: Detect and route to appropriate tool

    alt Tool requires entity extraction
        Tools->>NER: Extract legal entities
        NER-->>Tools: Return entities (cases, statutes)
    end

    alt Tool requires legal data
        Tools->>Scraper: Fetch case law/statutes
        Scraper->>Legal: HTTP request
        Legal-->>Scraper: Return legal data
        Scraper-->>Tools: Parsed legal information
    end

    Tools->>AI: Generate analysis with structured prompt
    AI-->>Tools: Stream AI response
    Tools-->>API: Stream processed response
    API-->>UI: SSE stream
    UI-->>User: Display analysis results

    User->>UI: Export to PDF
    UI->>UI: Generate PDF locally
    UI-->>User: Download PDF file
```

## Legal Disclaimer

### For Informational Purposes Only

The information provided on Junas is for general informational purposes only. While we strive to ensure the accuracy and reliability of the legal analysis workflows and templates provided, Junas makes no guarantees, representations, or warranties of any kind, express or implied, about the completeness, accuracy, reliability, suitability, or availability of the information. Users should independently verify any information before making decisions based on it.

### No Professional Advice

Junas does not provide professional legal advice or consultation services. The legal analysis tools, document drafting templates, and case law analysis features should not be considered as a substitute for professional advice from qualified legal practitioners or attorneys. Users are encouraged to consult with appropriate legal professionals regarding their specific legal matters and requirements.

### No Endorsement

The inclusion of any legal templates, analysis methodologies, or reference to any legal principles on Junas does not constitute an endorsement or recommendation of specific legal strategies or approaches. Junas is not affiliated with any law firms, legal institutions, or bar associations unless explicitly stated otherwise.

### AI-Generated Content

Junas utilizes artificial intelligence models to generate legal analysis and drafts. AI-generated content may contain errors, omissions, or inaccuracies. The quality of AI outputs depends on various factors including the quality of input, the limitations of the underlying AI models, and the complexity of legal issues. We do not control or guarantee the accuracy of AI-generated content. Using AI-generated legal analysis and documents is at your own risk, and Junas is not responsible for any errors, misinterpretations, or damages resulting from their use.

### Use at Your Own Risk

Users access, use, and rely on legal analysis and documents generated by Junas at their own risk. Legal information may become outdated or inaccurate without notice, and legal landscapes may change rapidly. Junas disclaims all liability for any loss, injury, or damage, direct or indirect, arising from reliance on the information provided on this platform. This includes but is not limited to legal misinformation, outdated legal precedents, incorrect interpretations, AI hallucinations, or decisions made based on the content generated.

### Limitation of Liability

To the fullest extent permitted by law:

* Junas shall not be liable for any direct, indirect, incidental, consequential, or punitive damages arising out of your use of this web app or reliance on any legal analysis or documents generated by it.
* Junas disclaims all liability for errors or omissions in the content provided.
* Our total liability under any circumstances shall not exceed the amount paid by you (if any) for using Junas.

### User Responsibility

Users are solely responsible for:

* Verifying the accuracy and currency of any legal information generated through Junas.
* Seeking appropriate professional legal advice for their specific circumstances.
* Complying with all applicable laws, regulations, and professional conduct rules.
* Understanding that AI-generated legal analysis and documents are not substitutes for formal legal counsel.
* Exercising independent judgment when interpreting legal information and using generated content.
* Reviewing and editing all AI-generated documents before use in any legal proceedings or official capacity.

### Copyright and Intellectual Property

Junas respects intellectual property rights. The legal templates and analysis methodologies provided are for general use. If you believe your copyrighted work has been inappropriately used or displayed on Junas, please contact us to request its removal.

### Data Collection and Privacy

Junas may collect user data to improve service functionality. By using Junas, you consent to our data collection practices. Your API keys remain private and are stored locally on your device as part of the BYOK (Bring Your Own Key) model. We do not have access to your API keys or the content you process through the platform.

### Changes to Content

Junas reserves the right to modify, update, or remove any content on this platform at any time without prior notice. Legal analysis tools, templates, and methodologies may change without notice due to various factors including updates to legal standards, improvements to AI models, or changes in best practices.

### Jurisdiction

This disclaimer and your use of Junas shall be governed by and construed in accordance with the laws of Singapore. Any disputes arising out of or in connection with this disclaimer shall be subject to the exclusive jurisdiction of the courts in Singapore.
