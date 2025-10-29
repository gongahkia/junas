# Junas

**AI-Powered Legal Assistant for Singapore Law**

Junas is an intelligent legal research and drafting assistant specifically designed for Singapore's legal system. Built with cutting-edge AI technology, Junas helps legal professionals, law students, and individuals navigate Singapore law through structured analysis, document drafting, and comprehensive legal research.

## Features

### 🎯 Legal Analysis Tools

Junas provides six structured analysis workflows with intelligent pop-up assistance:

| Tool | Trigger Keywords | Purpose |
|------|-----------------|---------|
| **IRAC Analysis** | `irac`, `analyze`, `legal analysis` | Structure legal problems using Issue, Rule, Application, Conclusion |
| **Case Facts Extraction** | `facts`, `case facts`, `extract facts` | Extract and organize material facts from case law |
| **Ruling Analysis** | `ruling`, `judgment`, `decision` | Analyze court decisions, reasoning, and remedies |
| **Obiter Dicta** | `obiter`, `dicta`, `remarks` | Identify non-binding judicial observations |
| **Ratio Decidendi** | `ratio`, `binding principle`, `precedent` | Extract binding legal principles from cases |
| **Legal Argumentation** | `argue`, `argument`, `submission` | Build persuasive legal arguments with authorities |

### 📝 Document Templates

13 comprehensive templates for Singapore legal documents:

- **Contracts**: NDA, Service Agreement, Partnership Agreement, Settlement Agreement
- **Employment**: Employment Contract
- **Corporate**: Shareholders Agreement, Corporate Resolution
- **Property**: Tenancy Agreement, Loan Agreement
- **Intellectual Property**: IP Assignment Agreement
- **Clauses**: Confidentiality, Force Majeure, Dispute Resolution

### 🔍 Research & Analysis

- **Citation Extraction**: Automatically recognizes and validates Singapore legal citations
- **Case Law Search**: Search Singapore cases with relevance scoring
- **Named Entity Recognition**: Extract parties, organizations, dates, and legal entities
- **Contract Analysis**: Identify key terms, risks, and missing provisions
- **Web Scraping**: Fetch legal information from Singapore legal databases

### 🤖 Multi-Provider AI Support

- **Google Gemini** (Free tier available)
- **OpenAI GPT-4**
- **Anthropic Claude**
- Automatic fallback between providers

### 💾 Privacy-First Design

- All data stored locally in browser (localStorage)
- No backend database - your legal research stays private
- BYOK (Bring Your Own Key) - use your own API keys

## Tech Stack

**Frontend Framework:**
- Next.js 16.0.0 (React 19.2.0)
- TypeScript
- Tailwind CSS

**UI Components:**
- Radix UI primitives
- shadcn/ui design system
- Lucide React icons

**AI & ML:**
- Anthropic Claude SDK
- Google Generative AI
- OpenAI SDK
- Transformers.js (Named Entity Recognition)

**Utilities:**
- Zustand (State management)
- React Markdown (with KaTeX for math)
- jsPDF (Document export)
- Cheerio (Web scraping)
- Fuse.js (Fuzzy search)

## Installation

### Prerequisites

- Node.js 20+ (recommended)
- npm or yarn

### Setup

1. **Clone the repository**

```bash
git clone <repository-url>
cd junas
```

2. **Install dependencies**

```bash
npm install
```

3. **Configure API keys**

Junas supports multiple AI providers. You'll need at least one API key:

- **Google Gemini**: [Get API Key](https://aistudio.google.com/) (Free tier available)
- **OpenAI**: [Get API Key](https://platform.openai.com/)
- **Anthropic**: [Get API Key](https://console.anthropic.com/)

API keys are configured directly in the app's settings (stored in browser localStorage).

4. **Run the development server**

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

5. **Build for production**

```bash
npm run build
npm start
```

## Usage

### Getting Started

1. **Configure your API keys**: Click the settings icon and add at least one AI provider key
2. **Select your provider**: Choose between Gemini, OpenAI, or Claude
3. **Start chatting**: Ask questions about Singapore law or use the intelligent templates

### Using Legal Analysis Tools

Simply type a trigger keyword in the message input:

```
irac breach of contract
```

A pop-up will appear showing the analysis structure. Click to start or press Enter.

### Drafting Documents

Type "draft" followed by the document type:

```
draft nda
```

Junas will show matching templates. Select one and fill in the dynamic form.

### Citation Recognition

Junas automatically recognizes Singapore legal citations:

- `[2023] SGCA 15` - Court of Appeal
- `[2023] SGHC 45` - High Court
- `[2023] SGDC 120` - District Court

### Example Prompts

- "What is the test for breach of contract under Singapore law?"
- "Analyze the ratio decidendi in *Ngee Ann Development v Takashimaya*"
- "Draft an employment contract for a senior software engineer"
- "Extract the facts from *Spandeck Engineering v Defence Science*"
- "What are the remedies for breach of fiduciary duty?"

## Project Structure

```
junas/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── api/               # API routes (chat, providers, tools)
│   │   ├── layout.tsx         # Root layout
│   │   └── page.tsx           # Main chat interface
│   ├── components/
│   │   ├── chat/              # Chat components
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── AnalysisToolPreview.tsx  # NEW: Legal analysis pop-ups
│   │   │   └── TemplateForm.tsx
│   │   ├── settings/          # Settings components
│   │   └── ui/                # Reusable UI components
│   ├── lib/
│   │   ├── ai/                # AI provider abstractions
│   │   │   ├── chat-service.ts
│   │   │   ├── claude.ts
│   │   │   ├── gemini.ts
│   │   │   └── openai.ts
│   │   ├── ml/                # Machine learning utilities
│   │   │   └── ner.ts         # Named Entity Recognition
│   │   ├── scrapers/          # Legal database scrapers
│   │   │   ├── lawnet.ts
│   │   │   ├── commonlii.ts
│   │   │   └── statutes.ts
│   │   ├── tools/             # Legal analysis tools
│   │   │   ├── citation-extractor.ts
│   │   │   ├── contract-analyzer.ts
│   │   │   └── legal-search.ts
│   │   ├── templates.ts       # Legal templates & analysis tools
│   │   └── storage.ts         # Browser storage management
│   └── types/                 # TypeScript type definitions
├── public/                    # Static assets
└── package.json
```

## Legal Analysis Tools (Detailed)

### IRAC Analysis
Structure legal problems systematically:
- **Issue**: Identify the precise legal question
- **Rule**: State applicable Singapore law and precedents
- **Application**: Apply law to facts with case comparisons
- **Conclusion**: Provide clear answer with practical implications

### Case Facts Extraction
Organize case information:
- Parties and their roles
- Background context
- Material facts (legally significant only)
- Procedural history through court levels
- Chronological timeline

### Ruling Analysis
Comprehensive decision breakdown:
- Court's holding and decision
- Chain of reasoning
- Remedies granted/denied
- Specific orders made
- Costs allocation

### Obiter Dicta Identification
Separate binding precedent from persuasive remarks:
- Identify non-essential judicial statements
- Contextualize why courts made these remarks
- Assess persuasive value for future cases

### Ratio Decidendi Extraction
Extract binding legal principles:
- State the legal issue precisely
- Identify material facts essential to the decision
- Formulate the binding rule of law
- Define scope and limitations

### Legal Argumentation Builder
Construct persuasive submissions:
- Clear position statement
- Legal basis with Singapore authorities
- Application to your facts
- Anticipate counter-arguments
- Conclusion with relief sought

## Document Templates (Detailed)

All templates include:
- ✅ Singapore law compliance
- ✅ Detailed clause-by-clause guidance
- ✅ Relevant statutory references
- ✅ Common law principles
- ✅ Execution blocks and formalities

Each template provides comprehensive drafting instructions tailored to Singapore's legal framework.

## Configuration

Settings are stored in browser localStorage:

- **API Keys**: Provider-specific API keys
- **Temperature**: Controls response creativity (0.0 - 1.0)
- **Max Tokens**: Maximum response length
- **Auto-save**: Automatically save conversation history
- **Dark Mode**: Theme preference

## Privacy & Security

- **No backend database**: All data stays in your browser
- **Local storage only**: Conversations, settings, and API keys stored locally
- **BYOK model**: You control your own API keys
- **No tracking**: No analytics or user tracking
- **No server logs**: API requests go directly from browser to providers

## Important Disclaimers

⚠️ **Legal Disclaimer**:
- Junas is a research and drafting assistant tool
- **NOT a substitute for professional legal advice**
- Always consult a qualified lawyer for legal matters
- No attorney-client relationship is created
- Use at your own risk

⚠️ **Singapore Law Focus**:
- Optimized specifically for Singapore legal system
- Templates comply with Singapore statutes
- Case law references are Singapore courts
- May not be suitable for other jurisdictions

⚠️ **AI Limitations**:
- AI responses may contain errors or outdated information
- Always verify legal principles and citations
- Cross-reference with official legal sources
- AI models have knowledge cutoff dates

## Contributing

Contributions are welcome! Areas for improvement:

- Additional legal templates for Singapore
- More analysis tools and workflows
- Enhanced citation recognition
- Integration with legal databases
- Export formats (PDF, Word)
- Collaborative features

## License

This project is private and proprietary.

## Acknowledgments

Built with:
- Next.js and React
- Anthropic Claude, Google Gemini, and OpenAI APIs
- shadcn/ui component library
- Radix UI primitives
- The open-source community

---

**Version**: 0.1.0
**Status**: Active Development
**Focus**: Singapore Law
**Privacy**: Local-first, BYOK
