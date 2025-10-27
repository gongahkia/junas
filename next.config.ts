import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */

  // Turbopack configuration for Next.js 16+
  turbopack: {},

  // Keep webpack config for fallback/compatibility
  webpack: (config, { isServer }) => {
    // Transformers.js specific configuration
    config.resolve.alias = {
      ...config.resolve.alias,
      // Fallback for Node.js modules in browser
      'fs': false,
      'path': false,
      'os': false,
    };

    // Handle ONNX runtime files
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      };
    }

    return config;
  },
};

export default nextConfig;
