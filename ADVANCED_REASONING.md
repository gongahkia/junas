# Advanced Reasoning System

Junas now features a sophisticated multi-stage reasoning system that dramatically improves the quality of legal analysis.

## 🧠 Overview

The advanced reasoning system automatically adjusts its thinking depth based on query complexity, using provider-agnostic techniques that work with Claude, OpenAI, and Gemini.

### Key Features

- **Automatic Complexity Detection**: Queries are analyzed and classified (Simple → Expert)
- **Multi-Stage Reasoning**: Complex queries trigger 2-3 stage processing
- **Chain-of-Thought (CoT)**: Step-by-step legal analysis
- **Self-Critique**: AI reviews and refines its own analysis
- **ReAct Pattern**: Iterative reasoning cycles for expert queries
- **Structured Outputs**: Organized responses with clear sections
- **Real-Time Progress**: Visual indicators during multi-stage processing

---

## 📊 How It Works

### 1. Query Classification

When you ask a question, Junas automatically classifies it:

| Complexity | Description | Example |
|------------|-------------|---------|
| **Simple** | Factual, straightforward questions | "What is the limitation period for contracts?" |
| **Moderate** | Requires analysis of 2-3 legal elements | "What are the elements of a valid contract?" |
| **Complex** | Multi-step analysis, multiple precedents | "How would a court interpret this non-compete clause?" |
| **Expert** | Multi-jurisdictional, strategic analysis | "Tax implications of restructuring across SG/MY jurisdictions?" |

### 2. Reasoning Depth Selection

Based on complexity, Junas automatically selects the appropriate reasoning depth:

- **Quick**: Direct answers (0.5-1s response time)
- **Standard**: Chain-of-thought reasoning (2-4s)
- **Deep**: Multi-step + self-critique (5-8s, 2 stages)
- **Expert**: Full ReAct pattern (10-15s, 3 stages)

### 3. Multi-Stage Processing

For complex and expert queries, Junas uses multiple stages:

#### Stage 1: Initial Analysis
- Deep analytical reasoning
- Comprehensive legal framework examination
- Multiple precedent consideration
- Structured output generation

#### Stage 2: Self-Critique (Complex/Expert)
- Reviews initial analysis for completeness
- Checks citation accuracy
- Identifies logical gaps
- Considers counterarguments
- Assesses confidence levels

#### Stage 3: ReAct Pattern (Expert only)
- Iterative reasoning cycles
- Multi-path analysis
- Strategic considerations
- Risk assessment
- Practical implications

---

## ⚙️ Configuration

### Settings

Access advanced reasoning settings via **Settings → Advanced Reasoning**:

1. **Enable Advanced Reasoning** (Default: ON)
   - Toggle multi-stage processing on/off
   - When off, all queries use single-stage processing

2. **Default Reasoning Depth** (Default: Standard)
   - Quick: Prioritize speed
   - Standard: Balanced
   - Deep: Thorough analysis
   - Expert: Maximum depth

3. **Show Reasoning Stages** (Default: ON)
   - Display intermediate thinking steps
   - Shows stage progress during multi-stage queries

### Per-Query Override

The system automatically adjusts depth, but you can control it via settings for all queries.

---

## 📈 Response Format

### Standard Output
```
[Your question content]

## 🔍 Analysis
Step-by-step reasoning process with transparent thinking

## 📋 Key Findings
• Bullet points of critical conclusions
• Relevant precedents identified
• Key legal principles

## ⚖️ Legal Opinion
Main answer and recommendations

## ⚠️ Important Caveats
Limitations, uncertainties, and risk factors

## 📚 Citations
Full citations for all referenced cases and statutes
```

### Multi-Stage Indicator

When multi-stage reasoning is active, you'll see:

```
🧠 Multi-Stage Reasoning (Stage 1/3): Initial Analysis
[Progress bar]
```

### Reasoning Badge

After the response, you'll see a complexity badge:

- 🟢 **Simple Analysis** (Quick reasoning)
- 🔵 **Moderate Analysis** (Standard reasoning)
- 🟣 **Complex Analysis** (Deep reasoning)
- 🟡 **Expert Analysis** (Expert reasoning with ReAct)

---

## 🎯 Examples

### Example 1: Simple Query

**Query:** "What is the limitation period for breach of contract in Singapore?"

**System Behavior:**
- Complexity: SIMPLE
- Reasoning Depth: Quick
- Stages: 1
- Time: ~1s

### Example 2: Complex Query

**Query:** "Analyze whether a non-compete clause restricting employment for 3 years across Asia would be enforceable in Singapore."

**System Behavior:**
- Complexity: COMPLEX
- Reasoning Depth: Deep
- Stages: 2 (Initial + Self-Critique)
- Time: ~6s

**Stage 1:** Analyzes:
- Restraint of trade principles
- Reasonableness test (time, geography, scope)
- Relevant precedents (Man Financial, Smile Inc, etc.)
- Enforceability factors

**Stage 2:** Self-critiques:
- Checks completeness of precedent analysis
- Verifies citation accuracy
- Considers counterarguments
- Refines final opinion

### Example 3: Expert Query

**Query:** "What are the corporate restructuring options for a Singapore entity with subsidiaries in Malaysia, considering tax implications, regulatory requirements, and shareholder approval processes?"

**System Behavior:**
- Complexity: EXPERT
- Reasoning Depth: Expert
- Stages: 3 (Initial + Self-Critique + ReAct)
- Time: ~12s

**Stage 1:** Comprehensive analysis of restructuring options

**Stage 2:** Self-critique and refinement

**Stage 3:** ReAct pattern applies iterative reasoning:
- Thought: What factors affect choice between merger vs. acquisition?
- Observation: Tax treaties, regulatory approvals, shareholder rights
- Reasoning: Trade-offs between different structures
- Conclusion: Recommended approach with justification

---

## 🔬 Technical Details

### Provider-Agnostic Design

All reasoning features work identically across:
- **Claude** (claude-3-5-sonnet-20241022)
- **OpenAI** (gpt-4o)
- **Google Gemini** (gemini-2.0-flash-exp)

The system does NOT use provider-specific features like:
- Claude's extended thinking mode
- OpenAI's o1 model
- Special reasoning APIs

Instead, it uses carefully crafted prompts and multi-stage orchestration.

### Token Budgets

Token allocation scales with complexity:
- Simple: 1,024 tokens
- Moderate: 2,048 tokens
- Complex: 4,096 tokens
- Expert: 8,192 tokens

### Temperature Settings

- Simple: 0.3 (factual)
- Moderate: 0.5 (balanced)
- Complex: 0.7 (nuanced)
- Expert: 0.7 (strategic)

---

## 💡 Best Practices

### For Users

1. **Trust the Auto-Detection**
   - The system is highly accurate at classifying complexity
   - Manual depth override rarely needed

2. **Be Specific**
   - More detailed questions → better classification
   - Include context to help complexity detection

3. **Review Stage Outputs** (if enabled)
   - Multi-stage reasoning shows its work
   - Useful for understanding AI's thinking process

4. **Balance Speed vs. Depth**
   - Simple questions don't need expert depth
   - System handles this automatically

### For Complex Queries

- Include all relevant facts
- Specify jurisdiction (Singapore is default)
- Mention if strategic advice needed
- Ask for comparison if evaluating options

---

## 🚀 Performance

### Single-Stage Queries (70-80% of queries)
- No performance impact
- Same speed as before
- Better quality due to improved prompts

### Multi-Stage Queries (20-30% of queries)
- 2-3x longer response time
- Significantly higher quality
- Transparent reasoning process

### Token Usage

Increased token usage for complex queries:
- Simple: ~1-2K tokens (unchanged)
- Complex: ~4-6K tokens (2-3x increase)
- Expert: ~8-12K tokens (3-4x increase)

---

## 🛠️ Development

### Files

- `src/lib/prompts/system-prompts.ts` - Prompt templates
- `src/lib/prompts/query-classifier.ts` - Complexity classification
- `src/lib/prompts/reasoning-engine.ts` - Multi-stage orchestration
- `src/lib/ai/chat-service.ts` - Integration layer
- `src/components/chat/ReasoningIndicator.tsx` - UI components

### Architecture

```
User Query
    ↓
Query Classifier (analyzes complexity)
    ↓
Reasoning Engine (orchestrates stages)
    ↓
Chat Service (provider abstraction)
    ↓
[Stage 1] Initial Analysis
    ↓
[Stage 2] Self-Critique (if complex/expert)
    ↓
[Stage 3] ReAct Pattern (if expert)
    ↓
Final Response + Metadata
```

---

## 📝 Limitations

1. **Not All Queries Benefit**
   - Simple factual questions don't need multi-stage
   - System automatically detects and uses quick mode

2. **Increased Latency**
   - Complex queries take 2-3x longer
   - Trade-off for significantly better quality

3. **Token Costs**
   - Multi-stage uses more tokens
   - Roughly 2-4x for complex/expert queries

4. **Provider-Dependent Quality**
   - Better models = better reasoning
   - Gemini 2.0 Flash, GPT-4o, Claude 3.5 Sonnet all perform well

---

## 🎓 Learn More

- Chain-of-Thought Prompting: [Research Paper](https://arxiv.org/abs/2201.11903)
- ReAct Pattern: [Research Paper](https://arxiv.org/abs/2210.03629)
- Self-Critique in AI: [Research Paper](https://arxiv.org/abs/2302.04761)

---

## 🆘 Troubleshooting

### Issue: Responses too slow

**Solution:** Disable advanced reasoning or adjust default depth to "Quick" in settings

### Issue: Not seeing multi-stage progress

**Solution:** Enable "Show Reasoning Stages" in Advanced Reasoning settings

### Issue: Want more depth for specific query

**Solution:** Rephrase to be more complex or include words like "analyze", "compare", "evaluate"

### Issue: Responses don't show reasoning sections

**Solution:** This is controlled by the prompt. Standard responses include structured sections.

---

**Built with ❤️ for better legal reasoning**
