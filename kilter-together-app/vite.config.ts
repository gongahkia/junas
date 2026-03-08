import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import tailwindcss from "@tailwindcss/vite";

const normalizeBasePath = (value?: string): string => {
  const rawPath = value?.trim() || "/";
  const prefixedPath = rawPath.startsWith("/") ? rawPath : `/${rawPath}`;
  const trimmedPath =
    prefixedPath === "/" ? "/" : prefixedPath.replace(/\/+$/, "");

  return trimmedPath === "/" ? "/" : `${trimmedPath}/`;
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

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const apiBaseUrl = normalizeApiBaseUrl(env.VITE_API_BASE_URL);
  const shouldProxyApi = apiBaseUrl === "/api";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    base: normalizeBasePath(env.VITE_APP_BASE_PATH),
    server: shouldProxyApi
      ? {
          proxy: {
            "/api": {
              target: "http://localhost:8082",
              changeOrigin: true,
            },
          },
        }
      : undefined,
  };
});
