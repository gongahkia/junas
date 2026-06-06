/**
 * server api boundary
 *
 * server components and route-time code import from here so every request uses
 * the same endpoint contract as api-client.ts with Next.js SSR/RSC no-store
 * fetch semantics. add endpoints in createApiClient only.
 */
import { apiUrl, createApiClient, type ApiTransport } from "./api-client";

const serverTransport: ApiTransport = (path, init = {}) => fetch(apiUrl(path), {
  ...init,
  cache: init.cache ?? "no-store",
});

export const apiServer = createApiClient(serverTransport);

export const {
  chatStream,
  chatSend,
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
} = apiServer;
