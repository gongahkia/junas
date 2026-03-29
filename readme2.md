# Junas — Competitive Analysis & Roadmap

## What is Junas?

Junas is a **free, open-source, BYOK (Bring Your Own Key)** desktop AI legal assistant specialized in **Singapore law**. Built with Tauri (Rust) + React + TypeScript, it runs entirely on your machine with no backend server required.

## Competitive Landscape

### Feature Comparison Matrix

| Feature | Junas | Harvey | CoCounsel | Spellbook | Luminance | Ironclad |
|---------|-------|--------|-----------|-----------|-----------|----------|
| **Pricing** | Free/OSS | Enterprise | $220-500/mo | $20-350/mo | Enterprise | Enterprise |
| **BYOK / Privacy** | Yes (keychain) | No | No | No | No | No |
| **Multi-Provider** | 5 providers | OpenAI only | GPT-4 | GPT-4 | Proprietary | OpenAI |
| **Local ML** | ONNX (NER, embeddings, classify) | No | No | No | Yes (proprietary) | No |
| **Offline Capable** | Yes (Ollama/LM Studio) | No | No | No | No | No |
| **Singapore Law Focus** | Deep (citations, statutes) | General | US-centric | US/UK | Multi-jurisdiction | US-centric |
| **Contract Analysis** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Document Upload (PDF/DOCX)** | Yes | Yes | Yes | Yes | Yes | Yes |
| **RAG Pipeline** | Local vector store | Cloud | Cloud | Cloud | Cloud | Cloud |
| **Risk Visualization** | Traffic-light matrix | Custom | Limited | No | Traffic-light | Basic |
| **Template Library** | 6 SG templates | Custom | Via Practical Law | Clause library | Enterprise | Enterprise |
| **Contract Redlining** | Planned | Yes | Yes | Yes (Word) | Yes | Yes |
| **Compliance Monitoring** | Planned | Yes | Via Westlaw | No | Yes (Comply) | No |
| **Legal DB Integration** | Planned (SSO, CommonLII) | LexisNexis, 500+ | Westlaw | No | No | No |
| **Multi-Jurisdiction** | Planned (SG + MY) | Multi | US primarily | US/UK/CA | Multi | US |
| **CI/CD Cross-Platform** | macOS + Windows + Linux | SaaS | SaaS | SaaS | SaaS | SaaS |
| **Diagram Generation** | Mermaid, Graphviz, PlantUML | No | No | No | No | No |

### Key Differentiators

**Junas wins on:**
1. **Privacy & Control** — BYOK model, local keychain storage, no data leaves your machine except to your chosen provider
2. **Cost** — Free and open source; competitors charge $220-500+/user/month
3. **Provider Flexibility** — 5 providers including fully local options (Ollama, LM Studio)
4. **Singapore Specialization** — Deep citation extraction/validation, statute patterns, SG-specific templates
5. **Local ML** — ONNX-based NER, classification, and embeddings run without any API calls
6. **Desktop-First** — Cross-platform (macOS, Windows, Linux) with native performance

**Competitors win on:**
1. **Scale** — Harvey processes 200K+ queries/day with proprietary legal models
2. **Integrations** — Word, Outlook, iManage, Salesforce, Westlaw
3. **Content Libraries** — Spellbook has 2,300+ clause benchmarks; CoCounsel has Westlaw
4. **Enterprise Features** — SSO, audit trails, team management, role-based access
5. **Agentic Workflows** — Ironclad Jurist, Harvey Workflow Agents handle multi-step tasks

### Target Users

| Segment | Fit | Why |
|---------|-----|-----|
| Solo practitioners | Excellent | Free, private, easy to set up |
| Small firms (1-10) | Excellent | Cost-effective, SG-focused |
| In-house legal (startups) | Good | BYOK privacy, template library |
| Law students | Excellent | Free educational tool |
| Large firms | Moderate | Lacks enterprise features (SSO, audit) |

## Market Context

- Legal AI market: $1.2B (2024) → projected $12.1B (2033) at 29.3% CAGR
- 46% adoption barrier is **security concerns** — Junas's BYOK model directly addresses this
- Solo practitioners adopt AI 2-3x faster than firms — Junas's target demographic
- 80% of corporate legal execs expect reduced outside counsel bills from AI adoption

## Implemented Features (Current)

### Phase 1: Foundation (Complete)
- [x] Cross-platform keychain (macOS, Windows, Linux)
- [x] 7 AI-delegated slash commands (contract analysis, compliance, due diligence, etc.)
- [x] ONNX inference for NER, classification, embeddings
- [x] Expanded test coverage
- [x] Cross-platform CI/CD (macOS + Windows + Linux builds)
- [x] First-run onboarding wizard

### Phase 2: Document Intelligence (Complete)
- [x] PDF and DOCX upload/parsing
- [x] Legal document template library (6 SG templates)
- [x] Local RAG pipeline (chunk → embed → vector store → retrieve)
- [x] Risk scoring and traffic-light visualization

## Roadmap

### Phase 3: Advanced Legal Intelligence
- [ ] Singapore legal database integration (SSO, CommonLII)
- [ ] Multi-jurisdiction framework (SG + Malaysia)
- [ ] Contract redlining with diff view
- [ ] Compliance monitoring dashboard

### Phase 4: Polish & Distribution
- [ ] Clause library with market-standard benchmarking
- [ ] Multi-document workflow agent

## Sources

Research based on public information from:
- [Harvey AI](https://harvey.ai) — Platform features, enterprise integrations
- [CoCounsel / Thomson Reuters](https://thomsonreuters.com) — Pricing, Westlaw integration
- [Spellbook](https://spellbook.legal) — Clause benchmarking, Word integration
- [Luminance](https://luminance.com) — Proprietary LPT model, traffic-light risk
- [Ironclad](https://ironcladapp.com) — Jurist AI, Smart Import
- [ContractPodAi / Leah](https://contractpodai.com) — Agentic CLM
- [LawDroid](https://lawdroid.ai) — Client intake, no-code bots
- ABA Tech Survey, Wolters Kluwer Legal AI Survey, Harvard CLP reports
