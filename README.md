# Junas - AI Legal Assistant for Singapore Law

A comprehensive legal assistant powered by AI, specifically designed for Singapore legal practice. Junas combines multiple AI providers, real-time legal search, document processing, and ML-based entity recognition to streamline legal research and document analysis.

## Features

### 🔍 **Legal Search**
- Real-time access to Singapore Statutes Online (SSO)
- Comprehensive case law database
- Intelligent ranking with multi-factor relevance scoring
- Search by topic, citation, or keyword
- Caching for fast repeated searches

### 📄 **Document Processing**
- **PDF Processing**: Text extraction with metadata (title, author, pages, dates)
- **DOCX Processing**: Style-preserved extraction, tables, sections
- **OCR Support**: Extract text from scanned images with Tesseract.js
- Multi-language OCR (English, Chinese, Korean, Japanese, and more)
- Automatic file type detection via magic numbers

### 🤖 **AI-Powered Analysis**
- **Contract Analysis**: Risk assessment, obligation extraction
- **Document Summarization**: Intelligent summarization with key points
- **Named Entity Recognition**: ML-based entity extraction (90-95% accuracy)
  - Persons, organizations, locations
  - Dates, monetary amounts
  - Legal references (statutes, cases, courts)

### 🔐 **Security**
- Session-based API key management (HTTP-only cookies)
- No client-side API key exposure
- Input sanitization (XSS protection)
- File validation (magic number verification)
- Rate limiting
- OWASP compliance

### 💬 **Multi-Provider AI**
- **Anthropic Claude**: Advanced reasoning
- **OpenAI GPT**: Versatile analysis
- **Google Gemini**: Fast processing
- Automatic provider fallback
- Streaming responses

## Tech Stack

- **Framework**: Next.js 16 + React 19
- **Language**: TypeScript
- **AI**: Anthropic SDK, OpenAI SDK, Google Generative AI
- **ML**: Transformers.js (BERT-based NER)
- **Document Processing**: pdf-parse, mammoth, tesseract.js
- **Web Scraping**: Cheerio, Axios
- **Validation**: Zod
- **Session**: iron-session
- **Styling**: Tailwind CSS

## Getting Started

### Prerequisites

- Node.js 20+
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/junas.git
cd junas

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
```

### Environment Variables

Create a `.env.local` file:

```env
# Session Secret (generate with: openssl rand -base64 32)
SESSION_SECRET=your-secret-key-here

# AI Provider API Keys (optional - users can provide via UI)
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
GOOGLE_AI_API_KEY=your-google-key

# Node Environment
NODE_ENV=development
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production

```bash
npm run build
npm start
```

## Project Structure

```
junas/
├── src/
│   ├── app/                    # Next.js app router
│   │   ├── api/               # API routes
│   │   │   ├── auth/          # Session management
│   │   │   ├── providers/     # AI provider proxies
│   │   │   ├── tools/         # Analysis tools
│   │   │   └── upload/        # File upload
│   │   └── ...                # Pages and layouts
│   ├── components/            # React components
│   ├── lib/                   # Utilities and libraries
│   │   ├── ai/               # AI integration
│   │   ├── ml/               # ML models (NER)
│   │   ├── scrapers/         # Web scrapers
│   │   ├── file-processors/  # Document processing
│   │   └── tools/            # Legal analysis tools
│   └── types/                # TypeScript types
├── docs/
│   ├── SEARCH_DOCUMENTATION.md
│   ├── FILE_PROCESSING_DOCUMENTATION.md
│   ├── ML_NER_DOCUMENTATION.md
│   ├── NER_MIGRATION_GUIDE.md
│   └── IMPROVEMENTS_SUMMARY.md
└── ...
```

## API Endpoints

### Authentication
- `POST /api/auth/keys` - Store API keys in session
- `GET /api/auth/keys` - Check configuration
- `DELETE /api/auth/keys` - Clear session

### AI Providers
- `POST /api/providers/claude/chat` - Claude chat endpoint
- `POST /api/providers/openai/chat` - OpenAI chat endpoint
- `POST /api/providers/gemini/chat` - Gemini chat endpoint

### Analysis Tools
- `POST /api/tools/analyze` - Contract analysis
- `POST /api/tools/summarize` - Document summarization
- `POST /api/tools/ner` - Named entity recognition
- `POST /api/tools/search` - Legal search

### File Upload
- `POST /api/upload` - Upload and process documents

## Usage Examples

### Legal Search

```typescript
import { LegalSearchEngine } from '@/lib/tools/legal-search';

// Search all sources
const results = await LegalSearchEngine.searchAll('employment contract');

// Search statutes only
const statutes = await LegalSearchEngine.searchSingaporeStatutes('Companies Act');

// Search by citation
const caseResult = await LegalSearchEngine.searchByCitation('[2024] SGCA 15');
```

### Document Processing

```typescript
import { processFile } from '@/lib/file-processors';

const result = await processFile(buffer, 'contract.pdf', {
  ocrLanguage: 'eng',
  preserveStyles: true,
});

console.log(result.text); // Extracted text
console.log(result.metadata.wordCount);
console.log(result.metadata.readingTimeMinutes);
```

### Named Entity Recognition

```typescript
import { extractLegalEntities } from '@/lib/ml';

const entities = await extractLegalEntities(contractText);

console.log(entities.parties); // Persons
console.log(entities.organizations); // Companies
console.log(entities.dates); // Important dates
```

## Configuration

### NER Presets

```typescript
import { getPresetConfig } from '@/lib/ml';

// For legal documents
const config = getPresetConfig('LEGAL');

// For contracts
const config = getPresetConfig('CONTRACT');

// For case law
const config = getPresetConfig('CASE_LAW');
```

### File Size Limits

Default: 10MB. Configure in `next.config.ts`:

```typescript
experimental: {
  serverActions: {
    bodySizeLimit: '10mb',
  },
}
```

## Documentation

Comprehensive documentation available in the `/docs` directory:

- **[SEARCH_DOCUMENTATION.md](./SEARCH_DOCUMENTATION.md)**: Legal search system
- **[FILE_PROCESSING_DOCUMENTATION.md](./FILE_PROCESSING_DOCUMENTATION.md)**: Document processing
- **[ML_NER_DOCUMENTATION.md](./ML_NER_DOCUMENTATION.md)**: ML-based entity recognition
- **[NER_MIGRATION_GUIDE.md](./NER_MIGRATION_GUIDE.md)**: Regex to ML migration
- **[IMPROVEMENTS_SUMMARY.md](./IMPROVEMENTS_SUMMARY.md)**: Complete changelog

## Performance

### Search
- Cached: ~50ms
- First request: ~500ms

### Document Processing
- PDF: ~300ms
- DOCX: ~500ms
- OCR: ~2-5s

### NER
- Cached model: ~100-300ms
- First load: ~2-5s
- Accuracy: 90-95%

## Security Features

✅ **Session-based authentication** (HTTP-only cookies)
✅ **Input validation** with Zod schemas
✅ **XSS protection** with DOMPurify
✅ **File validation** with magic numbers
✅ **Rate limiting** on all endpoints
✅ **OWASP compliant** (A01, A03)

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

WebAssembly support required for ML features.

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Testing

```bash
# Run all tests
npm test

# Run specific test suite
npm test src/lib/ml/*.test.ts
```

## Troubleshooting

### Model Loading Issues

If ML models fail to load:

1. Check browser console for errors
2. Verify WebAssembly is enabled
3. Check network tab for CDN access
4. Try clearing browser cache

### Performance Issues

For slow performance:

1. Enable model caching (enabled by default)
2. Use chunking for large documents
3. Preload models on app initialization
4. Clear unused models from cache

See documentation for detailed troubleshooting guides.

## License

MIT License - see [LICENSE](./LICENSE) for details.

## Acknowledgments

- Singapore Academy of Law for legal resources
- Anthropic, OpenAI, and Google for AI models
- Hugging Face for Transformers.js
- Open source community

## Version

**Current Version**: 2.0.0

**Release Date**: October 2025

## Contact

For issues and questions:
- GitHub Issues: [github.com/yourusername/junas/issues](https://github.com/yourusername/junas/issues)
- Documentation: See `/docs` directory

---

Built with ❤️ for the Singapore legal community
