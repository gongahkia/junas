/**
 * browser api boundary
 *
 * this file is the single endpoint contract for the frontend. add or change
 * backend routes in createApiClient only. the browser export binds that
 * contract to window-aware fetch/localStorage behavior; api-server.ts binds
 * the same contract to the SSR/RSC no-store transport.
 */
const API_BASE = typeof window !== "undefined"
  ? (window as any).__NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
  : process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiTransport = (path: string, init?: RequestInit) => Promise<Response>;
export type ApiError = { error?: string };
export type ChatMessage = { role: string; content: string };
export type SessionMeta = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  deleted_at?: string | null;
  user_id?: string | null;
};
export type SessionDetail = SessionMeta & {
  node_map: Record<string, any>;
  current_leaf_id: string;
};
export type SessionSavePayload = {
  id?: string;
  title?: string;
  node_map?: Record<string, any>;
  current_leaf_id?: string;
  user_id?: string | null;
};
export type BatchDocumentPayload = { id: string; file_name: string; text: string };
export type BatchResult = {
  document_id: string;
  file_name: string;
  status: "pending" | "running" | "done" | "error" | "cancelled";
  summary: string;
  clauses: Array<Record<string, any>>;
  flagged_clauses: Array<Record<string, any>>;
  reasoning: string;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};
export type BatchJob = {
  id: string;
  status: "queued" | "running" | "completed" | "cancelled" | "error";
  total: number;
  completed: number;
  cancelled: boolean;
  created_at: string;
  updated_at: string;
  results: BatchResult[];
} & ApiError;
export type ChatStreamOptions = {
  provider: string;
  model?: string;
  messages: ChatMessage[];
  temperature?: number;
  maxTokens?: number;
  topP?: number;
  systemPrompt?: string;
  apiKey?: string;
  endpoint?: string;
  signal?: AbortSignal;
};
export type ChatSendResponse = { content: string; model: string; provider?: string };
export type ProviderInfo = {
  id: string;
  label: string;
  default_model: string;
  is_local: boolean;
  token_budget: number;
};
export type Clause = {
  id: string;
  name: string;
  category: string;
  jurisdiction: string;
  description: string;
  standard: string;
  aggressive: string;
  balanced: string;
  protective: string;
  notes: string;
};
export type ClauseTone = "standard" | "aggressive" | "balanced" | "protective";
export type ClauseToneResponse = { clause_id: string; tone: string; wording: string } & ApiError;
export type TemplateVariable = { name: string; label: string; placeholder: string; type: string };
export type Template = {
  id: string;
  title: string;
  category: string;
  jurisdiction: string;
  description: string;
  variables: TemplateVariable[];
  content: string;
  source_urls?: string[];
};
export type RenderTemplateResponse = { template_id?: string; rendered?: string } & ApiError;
export type ComplianceRule = {
  id: string;
  name: string;
  category: string;
  description: string;
  keywords: string[];
  severity: string;
  jurisdiction: string;
};
export type ComplianceCheckResult = {
  rule_id: string;
  rule_name: string;
  status: string;
  details: string;
  severity: string;
};
export type ComplianceSummary = { total: number; passed: number; warnings: number; failed: number };
export type ComplianceCheckResponse = {
  results: ComplianceCheckResult[];
  summary: ComplianceSummary;
  jurisdiction?: string;
} & ApiError;
export type ParseDocumentResponse = {
  filename: string;
  text: string;
  page_count?: number;
  char_count?: number;
  detail?: unknown;
};
export type Jurisdiction = {
  id: string;
  name: string;
  short_name: string;
  citation_patterns?: Array<{ kind: string; regex: string; description: string }>;
  legal_source_domains?: string[];
  system_prompt_addition: string;
  template_ids?: string[];
};
export type LegalSourceResult = { title: string; url: string; snippet: string; source: string };
export type GlossarySearchResult = {
  phrase: string;
  definition_html: string;
  definition_text: string;
  jurisdiction: string;
  domain: string;
  source_title: string;
  source_url: string;
  score: number;
};
export type GlossarySearchResponse = {
  total: number;
  page: number;
  per_page: number;
  results: GlossarySearchResult[];
  aggregations: { jurisdictions: Record<string, number>; domains: Record<string, number> };
};
export type GlossaryDefinition = {
  jurisdiction: string;
  domain: string;
  definition_html: string;
  definition_text: string;
  source_title: string;
  source_url: string;
};
export type GlossaryTermResponse = { phrase: string; definitions: GlossaryDefinition[] };
export type GlossaryCompareResponse = {
  term: string;
  comparisons: Array<{ jurisdiction: string; domain: string; definition_text: string }>;
  available_in: string[];
  not_found_in: string[];
};
export type GlossarySuggestResponse = { suggestions: string[] };
export type GlossaryJurisdictionsResponse = {
  jurisdictions: Array<{ code: string; name: string; count: number; domains: string[] }>;
};
export type StatuteSearchResponse = { total: number; results: Array<Record<string, any>> };
export type StatuteChaptersResponse = { chapters: Array<Record<string, any>> };
export type SearchCasesResponse = { results?: Array<Record<string, any>>; cases?: Array<Record<string, any>> } & ApiError;
export type ChargesResponse = { charges: string[] };
export type EntityTypesResponse = {
  fine_grained: Array<Record<string, any>>;
  coarse_grained: Array<Record<string, any>>;
};
export type EntityExtractionResponse = Record<string, any> & ApiError;
export type ContractClassifyResponse = Record<string, any> & ApiError;
export type ResearchResponse = Record<string, any> & ApiError;
export type ReadyResponse = { services: Record<string, boolean> };
export type MetricsResponse = Record<string, any>;
export type BenchmarkTask = { name: string };
export type BenchmarkEvaluator = { name: string; strength: "strong" | "weak" };
export type BenchmarkLeaderboardEntry = {
  run_id: string;
  workflow: string;
  dataset: string;
  finished_at: string;
  total_cases: number;
  per_evaluator_mean: Record<string, number>;
  strict: boolean;
  data_tier?: "regulator" | "synthetic" | "mixed";
};
export type BenchmarkLeaderboard = {
  entries: BenchmarkLeaderboardEntry[];
  aggregated_per_workflow: Record<string, Record<string, number>>;
};
export type BenchmarkRunPayload = {
  workflow: string;
  dataset: string;
  evaluators: string[];
  max_concurrency?: number;
  strict?: boolean;
};
export type BenchmarkRunResponse = Record<string, any> & ApiError;

export function apiUrl(path: string): string {
  return `${API_BASE}/api/v1${path}`;
}

export function contractBatchEventsUrl(batchId: string): string {
  return apiUrl(`/contracts/batch/${encodeURIComponent(batchId)}/events`);
}

function getStoredApiKey(provider: string): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(`junas_apikey_${provider}`) || "";
}

export function setStoredApiKey(provider: string, key: string): void {
  if (typeof window === "undefined") return;
  if (key) localStorage.setItem(`junas_apikey_${provider}`, key);
  else localStorage.removeItem(`junas_apikey_${provider}`);
}

function queryPath(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function jsonHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers);
  if (!merged.has("Content-Type")) merged.set("Content-Type", "application/json");
  return merged;
}

function cleanPayload(payload: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

async function errorMessage(resp: Response): Promise<string> {
  const body = await resp.json().catch(() => null);
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  return `HTTP ${resp.status}`;
}

async function requestJson<T>(
  transport: ApiTransport,
  path: string,
  init?: RequestInit,
  fallback?: T,
): Promise<T> {
  try {
    const resp = await transport(path, init);
    if (!resp.ok && fallback !== undefined) return fallback;
    return (await resp.json()) as T;
  } catch {
    if (fallback !== undefined) return fallback;
    throw new Error("Network error");
  }
}

async function postJson<T extends ApiError>(
  transport: ApiTransport,
  path: string,
  body: unknown,
  init: RequestInit = {},
): Promise<T> {
  try {
    const resp = await transport(path, {
      ...init,
      method: "POST",
      headers: jsonHeaders(init.headers),
      body: JSON.stringify(body),
    });
    if (!resp.ok) return { error: await errorMessage(resp) } as T;
    return (await resp.json()) as T;
  } catch (err) {
    return { error: err instanceof Error ? err.message : "Network error" } as T;
  }
}

async function putJson<T extends ApiError>(
  transport: ApiTransport,
  path: string,
  body: unknown,
): Promise<T> {
  try {
    const resp = await transport(path, {
      method: "PUT",
      headers: jsonHeaders(),
      body: JSON.stringify(body),
    });
    if (!resp.ok) return { error: await errorMessage(resp) } as T;
    return (await resp.json()) as T;
  } catch (err) {
    return { error: err instanceof Error ? err.message : "Network error" } as T;
  }
}

async function patchJson<T extends ApiError>(
  transport: ApiTransport,
  path: string,
  body: unknown,
): Promise<T> {
  try {
    const resp = await transport(path, {
      method: "PATCH",
      headers: jsonHeaders(),
      body: JSON.stringify(body),
    });
    if (!resp.ok) return { error: await errorMessage(resp) } as T;
    return (await resp.json()) as T;
  } catch (err) {
    return { error: err instanceof Error ? err.message : "Network error" } as T;
  }
}

export function createApiClient(transport: ApiTransport) {
  return {
    async *chatStream(opts: ChatStreamOptions): AsyncGenerator<string> {
      const apiKey = opts.apiKey || getStoredApiKey(opts.provider);
      const resp = await transport("/chat/stream", {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(cleanPayload({
          provider: opts.provider,
          model: opts.model || undefined,
          messages: opts.messages,
          temperature: opts.temperature,
          max_tokens: opts.maxTokens || 4096,
          top_p: opts.topP,
          system_prompt: opts.systemPrompt || undefined,
          api_key: apiKey,
          endpoint: opts.endpoint || undefined,
        })),
        signal: opts.signal,
      });
      if (!resp.ok) throw new Error(`Chat failed: ${resp.status}`);
      const reader = resp.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.error) throw new Error(event.error);
            if (event.delta) yield event.delta;
            if (event.done) return;
          } catch {}
        }
      }
    },
    async chatSend(opts: Omit<ChatStreamOptions, "signal">): Promise<ChatSendResponse> {
      const apiKey = opts.apiKey || getStoredApiKey(opts.provider);
      const resp = await transport("/chat/send", {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(cleanPayload({
          provider: opts.provider,
          model: opts.model || undefined,
          messages: opts.messages,
          temperature: opts.temperature,
          max_tokens: opts.maxTokens || 4096,
          top_p: opts.topP,
          system_prompt: opts.systemPrompt || undefined,
          api_key: apiKey,
          endpoint: opts.endpoint || undefined,
        })),
      });
      if (!resp.ok) throw new Error(`Chat failed: ${resp.status}`);
      return resp.json();
    },
    listProviders(): Promise<ProviderInfo[]> {
      return requestJson<ProviderInfo[]>(transport, "/chat/providers", undefined, []);
    },
    listSessions(): Promise<SessionMeta[]> {
      return requestJson<SessionMeta[]>(transport, "/sessions", undefined, []);
    },
    getSession(id: string): Promise<SessionDetail | null> {
      return requestJson<SessionDetail | null>(transport, `/sessions/${encodeURIComponent(id)}`, undefined, null);
    },
    createSession(payload: SessionSavePayload): Promise<SessionDetail & ApiError> {
      return postJson<SessionDetail & ApiError>(transport, "/sessions", payload);
    },
    saveSession(id: string, payload: SessionSavePayload): Promise<SessionDetail & ApiError> {
      return putJson<SessionDetail & ApiError>(transport, `/sessions/${encodeURIComponent(id)}`, payload);
    },
    renameSession(id: string, title: string): Promise<SessionDetail & ApiError> {
      return patchJson<SessionDetail & ApiError>(transport, `/sessions/${encodeURIComponent(id)}`, { title });
    },
    deleteSession(id: string): Promise<(Record<string, any> & ApiError)> {
      return requestJson<Record<string, any> & ApiError>(
        transport,
        `/sessions/${encodeURIComponent(id)}`,
        { method: "DELETE" },
        { error: "Delete failed" },
      );
    },
    listClauses(query = "", jurisdiction = "", category = ""): Promise<Clause[]> {
      const params = new URLSearchParams({ query });
      if (jurisdiction) params.set("jurisdiction", jurisdiction);
      if (category) params.set("category", category);
      return requestJson<Clause[]>(transport, queryPath("/clauses", params), undefined, []);
    },
    getClause(id: string): Promise<Clause | null> {
      return requestJson<Clause | null>(transport, `/clauses/${encodeURIComponent(id)}`, undefined, null);
    },
    getClauseTone(clauseId: string, tone: ClauseTone | string): Promise<ClauseToneResponse> {
      return requestJson<ClauseToneResponse>(
        transport,
        `/clauses/${encodeURIComponent(clauseId)}/tone/${encodeURIComponent(tone)}`,
      );
    },
    listTemplates(jurisdiction = "", category = ""): Promise<Template[]> {
      const params = new URLSearchParams();
      if (jurisdiction) params.set("jurisdiction", jurisdiction);
      if (category) params.set("category", category);
      return requestJson<Template[]>(transport, queryPath("/templates", params), undefined, []);
    },
    getTemplate(id: string): Promise<Template | null> {
      return requestJson<Template | null>(transport, `/templates/${encodeURIComponent(id)}`, undefined, null);
    },
    renderTemplate(id: string, values: Record<string, string>): Promise<RenderTemplateResponse> {
      return postJson<RenderTemplateResponse>(transport, `/templates/${encodeURIComponent(id)}/render`, { values });
    },
    checkCompliance(text: string, jurisdiction = "sg", customRules?: ComplianceRule[]): Promise<ComplianceCheckResponse> {
      return postJson<ComplianceCheckResponse>(
        transport,
        "/compliance/check",
        cleanPayload({ text, jurisdiction, custom_rules: customRules }),
      );
    },
    listComplianceRules(jurisdiction = "sg"): Promise<ComplianceRule[]> {
      return requestJson<ComplianceRule[]>(
        transport,
        `/compliance/rules?jurisdiction=${encodeURIComponent(jurisdiction)}`,
        undefined,
        [],
      );
    },
    parseDocument(file: File): Promise<ParseDocumentResponse> {
      const form = new FormData();
      form.append("file", file);
      return requestJson<ParseDocumentResponse>(transport, "/documents/parse", { method: "POST", body: form });
    },
    listJurisdictions(): Promise<Jurisdiction[]> {
      return requestJson<Jurisdiction[]>(transport, "/jurisdictions", undefined, []);
    },
    searchSSO(query: string): Promise<LegalSourceResult[]> {
      return requestJson<LegalSourceResult[]>(
        transport,
        `/legal-sources/sso?query=${encodeURIComponent(query)}`,
        undefined,
        [],
      );
    },
    searchCommonLII(query: string): Promise<LegalSourceResult[]> {
      return requestJson<LegalSourceResult[]>(
        transport,
        `/legal-sources/commonlii?query=${encodeURIComponent(query)}`,
        undefined,
        [],
      );
    },
    searchGlossary(q: string, jurisdiction = "", domain = "", page = 1, perPage = 20): Promise<Record<string, any>> {
      const params = new URLSearchParams({ q, page: String(page), per_page: String(perPage) });
      if (jurisdiction) params.set("jurisdiction", jurisdiction);
      if (domain) params.set("domain", domain);
      return requestJson<Record<string, any>>(
        transport,
        queryPath("/glossary/search", params),
        undefined,
        { total: 0, page, per_page: perPage, results: [], aggregations: { jurisdictions: {}, domains: {} } },
      );
    },
    getGlossaryTerm(phrase: string): Promise<GlossaryTermResponse | null> {
      return requestJson<GlossaryTermResponse | null>(
        transport,
        `/glossary/term/${encodeURIComponent(phrase)}`,
        undefined,
        null,
      );
    },
    compareGlossaryTerm(term: string, jurisdictions?: string[]): Promise<Record<string, any>> {
      const params = new URLSearchParams({ term });
      jurisdictions?.forEach((j) => params.append("jurisdictions", j));
      return requestJson<Record<string, any>>(
        transport,
        queryPath("/glossary/compare", params),
        undefined,
        { term, comparisons: [], available_in: [], not_found_in: [] },
      );
    },
    suggestGlossary(prefix: string, size = 10): Promise<GlossarySuggestResponse> {
      return requestJson<GlossarySuggestResponse>(
        transport,
        `/glossary/suggest?prefix=${encodeURIComponent(prefix)}&size=${size}`,
        undefined,
        { suggestions: [] },
      );
    },
    listGlossaryJurisdictions(): Promise<GlossaryJurisdictionsResponse> {
      return requestJson<GlossaryJurisdictionsResponse>(
        transport,
        "/glossary/jurisdictions",
        undefined,
        { jurisdictions: [] },
      );
    },
    searchStatutes(q: string, chapter = "", mode = "hybrid", page = 1, perPage = 20): Promise<StatuteSearchResponse> {
      const params = new URLSearchParams({ q, mode, page: String(page), per_page: String(perPage) });
      if (chapter) params.set("chapter", chapter);
      return requestJson<StatuteSearchResponse>(
        transport,
        queryPath("/statutes/search", params),
        undefined,
        { total: 0, results: [] },
      );
    },
    getStatuteSection(number: string): Promise<Record<string, any> | null> {
      return requestJson<Record<string, any> | null>(
        transport,
        `/statutes/section/${encodeURIComponent(number)}`,
        undefined,
        null,
      );
    },
    listStatuteChapters(): Promise<StatuteChaptersResponse> {
      return requestJson<StatuteChaptersResponse>(transport, "/statutes/chapters", undefined, { chapters: [] });
    },
    getChapterSections(chapterNumber: string): Promise<Record<string, any> | null> {
      return requestJson<Record<string, any> | null>(
        transport,
        `/statutes/chapter/${encodeURIComponent(chapterNumber)}`,
        undefined,
        null,
      );
    },
    searchCases(
      query: string,
      topK = 10,
      stages = ["bm25", "dense", "rerank"],
      includeScores = true,
    ): Promise<SearchCasesResponse> {
      return postJson<SearchCasesResponse>(
        transport,
        "/search/cases",
        { query, top_k: topK, stages, include_scores: includeScores },
      );
    },
    getCaseDetails(caseId: string): Promise<Record<string, any> | null> {
      return requestJson<Record<string, any> | null>(
        transport,
        `/search/cases/${encodeURIComponent(caseId)}`,
        undefined,
        null,
      );
    },
    listCharges(): Promise<ChargesResponse> {
      return requestJson<ChargesResponse>(transport, "/search/charges", undefined, { charges: [] });
    },
    getSearchMetrics(): Promise<Record<string, any> | null> {
      return requestJson<Record<string, any> | null>(transport, "/search/metrics", undefined, null);
    },
    extractEntities(text: string, language = "en", granularity = "fine", useGazetteer = false): Promise<EntityExtractionResponse> {
      return postJson<EntityExtractionResponse>(
        transport,
        "/ner/extract",
        { text, language, granularity, use_gazetteer: useGazetteer },
      );
    },
    batchExtractEntities(texts: string[], language = "en", granularity = "fine", useGazetteer = false): Promise<Array<EntityExtractionResponse>> {
      return requestJson<Array<EntityExtractionResponse>>(
        transport,
        "/ner/batch",
        {
          method: "POST",
          headers: jsonHeaders(),
          body: JSON.stringify({ texts, language, granularity, use_gazetteer: useGazetteer }),
        },
        [],
      );
    },
    listEntityTypes(): Promise<EntityTypesResponse> {
      return requestJson<EntityTypesResponse>(
        transport,
        "/ner/entity-types",
        undefined,
        { fine_grained: [], coarse_grained: [] },
      );
    },
    classifyContract(text: string, topK = 5): Promise<ContractClassifyResponse> {
      return postJson<ContractClassifyResponse>(transport, "/contracts/classify", { text, top_k_types: topK });
    },
    scanToS(text: string, threshold = 0.5): Promise<ContractClassifyResponse> {
      return postJson<ContractClassifyResponse>(transport, "/contracts/scan-tos", { text, threshold });
    },
    createContractBatch(documents: BatchDocumentPayload[], threshold = 0.5, topKTypes = 3): Promise<BatchJob> {
      return postJson<BatchJob>(transport, "/contracts/batch", { documents, threshold, top_k_types: topKTypes });
    },
    getContractBatch(batchId: string): Promise<BatchJob | null> {
      return requestJson<BatchJob | null>(transport, `/contracts/batch/${encodeURIComponent(batchId)}`, undefined, null);
    },
    cancelContractBatch(batchId: string): Promise<BatchJob> {
      return postJson<BatchJob>(transport, `/contracts/batch/${encodeURIComponent(batchId)}/cancel`, {});
    },
    askResearch(question: string, sources?: string[], topK = 8, conversationId?: string): Promise<ResearchResponse> {
      return postJson<ResearchResponse>(
        transport,
        "/research/ask",
        cleanPayload({ question, sources, top_k: topK, conversation_id: conversationId }),
      );
    },
    getResearchConversation(conversationId: string): Promise<Record<string, any> | null> {
      return requestJson<Record<string, any> | null>(
        transport,
        `/research/conversations/${encodeURIComponent(conversationId)}`,
        undefined,
        null,
      );
    },
    deleteResearchConversation(conversationId: string): Promise<Record<string, any> & ApiError> {
      return requestJson<Record<string, any> & ApiError>(
        transport,
        `/research/conversations/${encodeURIComponent(conversationId)}`,
        { method: "DELETE" },
      );
    },
    getResearchConfig(): Promise<Record<string, any>> {
      return requestJson<Record<string, any>>(
        transport,
        "/research/config",
        undefined,
        { provider: "", model: "", available_sources: [], max_context_chunks: 12 },
      );
    },
    getReady(): Promise<ReadyResponse> {
      return requestJson<ReadyResponse>(transport, "/ready", undefined, { services: {} });
    },
    getMetrics(): Promise<MetricsResponse | null> {
      return requestJson<MetricsResponse | null>(transport, "/metrics", undefined, null);
    },
    getHealth(): Promise<Record<string, any> | null> {
      return requestJson<Record<string, any> | null>(transport, "/health", undefined, null);
    },
    listBenchmarkTasks(): Promise<BenchmarkTask[]> {
      return requestJson<BenchmarkTask[]>(transport, "/benchmarks/tasks", undefined, []);
    },
    listBenchmarkEvaluators(): Promise<BenchmarkEvaluator[]> {
      return requestJson<BenchmarkEvaluator[]>(transport, "/benchmarks/evaluators", undefined, []);
    },
    getBenchmarkLeaderboard(): Promise<BenchmarkLeaderboard> {
      return requestJson<BenchmarkLeaderboard>(
        transport,
        "/benchmarks/leaderboard",
        undefined,
        { entries: [], aggregated_per_workflow: {} },
      );
    },
    runBenchmark(payload: BenchmarkRunPayload): Promise<BenchmarkRunResponse> {
      return postJson<BenchmarkRunResponse>(transport, "/benchmarks/run", payload);
    },
    getBenchmarkRun(runId: string, apiKey = ""): Promise<Record<string, any> | null> {
      const headers = apiKey.trim() ? { "X-API-Key": apiKey.trim() } : undefined;
      return requestJson<Record<string, any> | null>(
        transport,
        `/benchmarks/runs/${encodeURIComponent(runId)}`,
        { headers },
        null,
      );
    },
  };
}

const browserTransport: ApiTransport = (path, init) => fetch(apiUrl(path), init);
export const apiClient = createApiClient(browserTransport);
export type JunasApi = ReturnType<typeof createApiClient>;

export const {
  chatStream,
  chatSend,
  listSessions,
  getSession,
  createSession,
  saveSession,
  renameSession,
  deleteSession,
  listProviders,
  listClauses,
  getClause,
  getClauseTone,
  listTemplates,
  getTemplate,
  renderTemplate,
  checkCompliance,
  listComplianceRules,
  parseDocument,
  listJurisdictions,
  searchSSO,
  searchCommonLII,
  searchGlossary,
  getGlossaryTerm,
  compareGlossaryTerm,
  suggestGlossary,
  listGlossaryJurisdictions,
  searchStatutes,
  getStatuteSection,
  listStatuteChapters,
  getChapterSections,
  searchCases,
  getCaseDetails,
  listCharges,
  getSearchMetrics,
  extractEntities,
  batchExtractEntities,
  listEntityTypes,
  classifyContract,
  scanToS,
  createContractBatch,
  getContractBatch,
  cancelContractBatch,
  askResearch,
  getResearchConversation,
  deleteResearchConversation,
  getResearchConfig,
  getReady,
  getMetrics,
  getHealth,
  listBenchmarkTasks,
  listBenchmarkEvaluators,
  getBenchmarkLeaderboard,
  runBenchmark,
  getBenchmarkRun,
} = apiClient;
