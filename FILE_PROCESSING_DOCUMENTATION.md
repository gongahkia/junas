# File Processing System Documentation

## Overview

The Junas file processing system provides comprehensive document processing capabilities for legal documents including PDFs, Word documents, and scanned images.

## Architecture

### Components

1. **File Processors** (`src/lib/file-processors/`)
   - `pdf-processor.ts`: PDF text extraction with metadata
   - `docx-processor.ts`: Word document processing with style preservation
   - `image-processor.ts`: OCR text extraction from images
   - `index.ts`: Unified processing pipeline
   - `error-handler.ts`: Comprehensive error handling

2. **File Validation** (`src/lib/file-validation.ts`)
   - Magic number validation
   - File type detection
   - Security checks

3. **Upload API** (`src/app/api/upload/route.ts`)
   - File upload endpoint
   - Integration with processing pipeline

## Usage

### Basic File Processing

```typescript
import { processFile } from '@/lib/file-processors';

// Process any supported file type
const result = await processFile(buffer, filename, {
  ocrLanguage: 'eng',      // OCR language for images
  preserveStyles: true,     // Preserve formatting for DOCX
});

if (result.success) {
  console.log('Text:', result.text);
  console.log('Word count:', result.metadata.wordCount);
  console.log('Reading time:', result.metadata.readingTimeMinutes);
}
```

### PDF Processing

```typescript
import { processPDF } from '@/lib/file-processors';

const result = await processPDF(buffer);

// Access PDF metadata
console.log('Title:', result.metadata.title);
console.log('Author:', result.metadata.author);
console.log('Pages:', result.metadata.pageCount);
console.log('Creation date:', result.metadata.creationDate);
```

### DOCX Processing

```typescript
import { processDOCX, processDOCXWithStyles } from '@/lib/file-processors';

// Basic processing
const result = await processDOCX(buffer);

// With legal document style mapping
const styledResult = await processDOCXWithStyles(buffer);

// Access HTML with preserved formatting
console.log('HTML:', styledResult.html);

// Extract sections
import { extractDOCXSections } from '@/lib/file-processors/docx-processor';
const sections = extractDOCXSections(styledResult.html);
```

### Image Processing (OCR)

```typescript
import { processImage, extractLegalDocument } from '@/lib/file-processors';

// Basic OCR
const result = await processImage(buffer, 'eng');

// Extract structured legal document data
const legalDoc = await extractLegalDocument(buffer);
console.log('Sections:', legalDoc.sections);
console.log('Dates:', legalDoc.dates);
console.log('Case references:', legalDoc.references);
```

### Batch Processing

```typescript
import { processBatchFiles, getProcessingStats } from '@/lib/file-processors';

const files = [
  { buffer: pdfBuffer, filename: 'contract.pdf' },
  { buffer: docxBuffer, filename: 'agreement.docx' },
  { buffer: imageBuffer, filename: 'scan.png' },
];

const results = await processBatchFiles(files, {
  ocrLanguage: 'eng',
  preserveStyles: true,
});

// Get statistics
const stats = getProcessingStats(results);
console.log('Total words:', stats.totalWords);
console.log('Success rate:', stats.successfulFiles / stats.totalFiles);
```

## Supported File Types

### PDF
- **Extensions**: `.pdf`
- **Features**:
  - Text extraction
  - Metadata extraction (title, author, dates)
  - Document structure detection
  - Page count
  - Table of contents detection

### DOCX
- **Extensions**: `.docx`
- **Features**:
  - Text and HTML extraction
  - Style preservation
  - Table extraction
  - Section detection
  - Image/footnote detection

### Images
- **Extensions**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`
- **Features**:
  - OCR text extraction
  - Multi-language support (10+ languages)
  - Confidence scoring
  - Legal reference extraction
  - Date extraction

## OCR Languages

Supported OCR languages:

- `eng` - English
- `chi_sim` - Simplified Chinese
- `chi_tra` - Traditional Chinese
- `spa` - Spanish
- `fra` - French
- `deu` - German
- `jpn` - Japanese
- `kor` - Korean
- `rus` - Russian
- `ara` - Arabic

## Error Handling

### Error Types

```typescript
import {
  FileProcessingError,
  PDFProcessingError,
  DOCXProcessingError,
  OCRProcessingError,
  FileSizeError,
  FileTypeError,
  CorruptedFileError
} from '@/lib/file-processors/error-handler';
```

### Error Handling Example

```typescript
import { FileErrorHandler } from '@/lib/file-processors/error-handler';

try {
  const result = await processFile(buffer, filename);
} catch (error) {
  const fileError = FileErrorHandler.handle(error);

  // Get user-friendly message
  const message = FileErrorHandler.getUserMessage(fileError);

  // Get recovery suggestions
  const suggestions = FileErrorHandler.getRecoverySuggestions(fileError);

  console.error(message);
  console.log('Try:', suggestions);
}
```

### Retry with Exponential Backoff

```typescript
import { retryFileProcessing } from '@/lib/file-processors/error-handler';

const result = await retryFileProcessing(
  () => processFile(buffer, filename),
  3,      // max retries
  1000    // initial delay (ms)
);
```

## API Integration

### Upload Endpoint

**POST** `/api/upload`

Upload and process a file.

```bash
curl -X POST http://localhost:3000/api/upload \
  -F "file=@document.pdf"
```

**Response**:

```json
{
  "success": true,
  "text": "Extracted text content...",
  "html": "<p>Formatted content...</p>",
  "metadata": {
    "fileName": "document.pdf",
    "fileSize": 102400,
    "fileType": "application/pdf",
    "wordCount": 1250,
    "readingTimeMinutes": 5,
    "processedAs": "pdf",
    "pageCount": 10
  },
  "warnings": []
}
```

**GET** `/api/upload`

Get endpoint information.

```json
{
  "message": "File upload API endpoint",
  "supportedFormats": ["PDF", "DOCX", "JPEG", "PNG", "GIF", "BMP", "WEBP"],
  "maxFileSize": "10MB"
}
```

## Configuration

### File Size Limits

Edit in `src/lib/file-validation.ts`:

```typescript
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
```

### OCR Configuration

OCR is powered by Tesseract.js and runs client-side using WASM. Configuration options:

```typescript
const result = await processImage(buffer, 'eng', {
  logger: (m) => console.log(`OCR Progress: ${m.progress * 100}%`),
});
```

### DOCX Style Mapping

Customize style mapping in `src/lib/file-processors/docx-processor.ts`:

```typescript
const styleMap = [
  "p[style-name='Heading 1'] => h1:fresh",
  "p[style-name='Heading 2'] => h2:fresh",
  // Add custom mappings
].join('\n');
```

## Performance

### Optimization Tips

1. **Batch Processing**: Process multiple files in parallel for better throughput
2. **Caching**: Cache processed results for frequently accessed documents
3. **Streaming**: For large files, consider chunked processing
4. **OCR**: OCR is computationally expensive - use only when necessary

### Performance Metrics

- **PDF**: ~500ms for 50-page document
- **DOCX**: ~300ms for 20-page document
- **OCR**: ~2-5s per image (depending on size and quality)

## Security

### Validation

All files are validated using:

1. **Magic Number Detection**: Verify file type from content, not extension
2. **Size Limits**: Enforce maximum file size
3. **Sanitization**: Remove sensitive metadata
4. **Error Message Sanitization**: Remove file paths and URLs from errors

### Best Practices

1. Always validate files before processing
2. Use sanitized filenames
3. Implement rate limiting on upload endpoints
4. Set appropriate file size limits
5. Scan uploaded files for malware (not included, implement separately)

## Troubleshooting

### Common Issues

**Issue**: PDF extraction returns empty text
- **Cause**: PDF contains scanned images, not text
- **Solution**: Use OCR or extract images and process separately

**Issue**: DOCX processing fails
- **Cause**: Old .doc format or corrupted file
- **Solution**: Convert to .docx format using Word or Google Docs

**Issue**: OCR returns gibberish
- **Cause**: Low image quality or wrong language
- **Solution**: Use higher quality image and specify correct language

**Issue**: Memory errors with large files
- **Cause**: File too large to process in memory
- **Solution**: Implement chunked processing or reduce file size

## Testing

```bash
# Test file processing
npm test src/lib/file-processors/*.test.ts

# Test upload endpoint
npm test src/app/api/upload/route.test.ts
```

## Future Enhancements

1. **Streaming**: Implement streaming for large file processing
2. **Caching**: Redis/database caching for processed documents
3. **Queue**: Background job queue for async processing
4. **ML Models**: Advanced NER and document classification
5. **Format Conversion**: Convert between formats (PDF to DOCX, etc.)
6. **Table Extraction**: Advanced table detection and extraction
7. **Multi-page OCR**: Optimize batch OCR for multi-page documents

## License

Part of Junas legal assistant application.
