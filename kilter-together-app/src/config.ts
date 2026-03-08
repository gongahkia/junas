const normalizeAppBasePath = (value?: string): string => {
  const rawPath = value?.trim() || "/";
  const prefixedPath = rawPath.startsWith("/") ? rawPath : `/${rawPath}`;

  if (prefixedPath === "/") {
    return "/";
  }

  return prefixedPath.replace(/\/+$/, "");
};

const normalizeApiBaseUrl = (value?: string): string => {
  const rawValue = value?.trim();

  if (!rawValue) {
    return "/api";
  }

  if (/^https?:\/\//i.test(rawValue)) {
    return rawValue.replace(/\/+$/, "");
  }

  const prefixedPath = rawValue.startsWith("/") ? rawValue : `/${rawValue}`;
  return prefixedPath === "/" ? "/api" : prefixedPath.replace(/\/+$/, "");
};

// Environment configuration
const appBasePath = normalizeAppBasePath(import.meta.env.VITE_APP_BASE_PATH);
const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export const config = {
  app: {
    basePath: appBasePath,
  },
  api: {
    baseUrl: apiBaseUrl,
  },
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const;
