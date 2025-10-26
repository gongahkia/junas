import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */

  // Turbopack configuration for Next.js 16+
  turbopack: {},

  // Keep webpack config for fallback/compatibility
  webpack: (config, { isServer }) => {
    // Add WebAssembly support
    config.experiments = {
      ...config.experiments,
      asyncWebAssembly: true,
    };

    // Handle .wasm files
    config.module.rules.push({
      test: /\.wasm$/,
      type: 'webassembly/async',
    });

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

  // Increase body size limit for file uploads
  experimental: {
    serverActions: {
      bodySizeLimit: '10mb',
    },
  },
};

export default nextConfig;
