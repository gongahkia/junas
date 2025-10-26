/**
 * Model loading and caching utilities for ML models
 */

export interface CachedModel {
  pipeline: any;
  modelName: string;
  loadedAt: number;
  lastUsedAt: number;
  usageCount: number;
  memorySize?: number;
}

export interface ModelLoadingStats {
  totalLoads: number;
  cacheHits: number;
  cacheMisses: number;
  averageLoadTime: number;
  modelsInCache: number;
}

/**
 * Model cache manager for efficient model reuse
 */
export class ModelCache {
  private static instance: ModelCache;
  private cache: Map<string, CachedModel>;
  private loadingPromises: Map<string, Promise<any>>;
  private stats: ModelLoadingStats;
  private maxCacheSize: number = 3; // Maximum number of models to cache
  private cacheTimeout: number = 30 * 60 * 1000; // 30 minutes

  private constructor() {
    this.cache = new Map();
    this.loadingPromises = new Map();
    this.stats = {
      totalLoads: 0,
      cacheHits: 0,
      cacheMisses: 0,
      averageLoadTime: 0,
      modelsInCache: 0,
    };
  }

  /**
   * Get singleton instance
   */
  static getInstance(): ModelCache {
    if (!ModelCache.instance) {
      ModelCache.instance = new ModelCache();
    }
    return ModelCache.instance;
  }

  /**
   * Get or load a model
   */
  async getModel(
    modelName: string,
    loader: () => Promise<any>
  ): Promise<any> {
    // Check cache first
    const cached = this.cache.get(modelName);
    if (cached) {
      // Update last used time
      cached.lastUsedAt = Date.now();
      cached.usageCount++;
      this.stats.cacheHits++;
      console.log(`Model cache HIT for ${modelName}`);
      return cached.pipeline;
    }

    // Check if model is currently being loaded
    const loadingPromise = this.loadingPromises.get(modelName);
    if (loadingPromise) {
      console.log(`Waiting for ${modelName} to finish loading...`);
      return loadingPromise;
    }

    // Load model
    console.log(`Model cache MISS for ${modelName}, loading...`);
    this.stats.cacheMisses++;

    const startTime = performance.now();

    // Create loading promise
    const promise = (async () => {
      try {
        const pipeline = await loader();
        const loadTime = performance.now() - startTime;

        // Update average load time
        this.stats.totalLoads++;
        this.stats.averageLoadTime =
          (this.stats.averageLoadTime * (this.stats.totalLoads - 1) + loadTime) /
          this.stats.totalLoads;

        // Cache the model
        this.cacheModel(modelName, pipeline);

        console.log(`Model ${modelName} loaded in ${loadTime.toFixed(2)}ms`);

        return pipeline;
      } finally {
        // Remove loading promise
        this.loadingPromises.delete(modelName);
      }
    })();

    this.loadingPromises.set(modelName, promise);
    return promise;
  }

  /**
   * Cache a loaded model
   */
  private cacheModel(modelName: string, pipeline: any): void {
    // Check cache size limit
    if (this.cache.size >= this.maxCacheSize) {
      this.evictLeastRecentlyUsed();
    }

    const cachedModel: CachedModel = {
      pipeline,
      modelName,
      loadedAt: Date.now(),
      lastUsedAt: Date.now(),
      usageCount: 1,
    };

    this.cache.set(modelName, cachedModel);
    this.stats.modelsInCache = this.cache.size;

    // Set up auto-eviction timer
    this.scheduleEviction(modelName);
  }

  /**
   * Evict least recently used model
   */
  private evictLeastRecentlyUsed(): void {
    let oldestModel: string | null = null;
    let oldestTime = Infinity;

    for (const [modelName, model] of this.cache.entries()) {
      if (model.lastUsedAt < oldestTime) {
        oldestTime = model.lastUsedAt;
        oldestModel = modelName;
      }
    }

    if (oldestModel) {
      console.log(`Evicting least recently used model: ${oldestModel}`);
      this.cache.delete(oldestModel);
      this.stats.modelsInCache = this.cache.size;
    }
  }

  /**
   * Schedule automatic eviction of unused model
   */
  private scheduleEviction(modelName: string): void {
    setTimeout(() => {
      const model = this.cache.get(modelName);
      if (model) {
        const timeSinceLastUse = Date.now() - model.lastUsedAt;
        if (timeSinceLastUse >= this.cacheTimeout) {
          console.log(`Auto-evicting unused model: ${modelName}`);
          this.cache.delete(modelName);
          this.stats.modelsInCache = this.cache.size;
        } else {
          // Reschedule if still in use
          this.scheduleEviction(modelName);
        }
      }
    }, this.cacheTimeout);
  }

  /**
   * Preload models
   */
  async preloadModels(
    models: Array<{ name: string; loader: () => Promise<any> }>
  ): Promise<void> {
    console.log(`Preloading ${models.length} models...`);

    const promises = models.map(({ name, loader }) =>
      this.getModel(name, loader).catch(error => {
        console.error(`Failed to preload model ${name}:`, error);
      })
    );

    await Promise.all(promises);
    console.log('Model preloading complete');
  }

  /**
   * Clear specific model from cache
   */
  clearModel(modelName: string): void {
    if (this.cache.delete(modelName)) {
      console.log(`Cleared model from cache: ${modelName}`);
      this.stats.modelsInCache = this.cache.size;
    }
  }

  /**
   * Clear all models from cache
   */
  clearAll(): void {
    const count = this.cache.size;
    this.cache.clear();
    this.stats.modelsInCache = 0;
    console.log(`Cleared ${count} models from cache`);
  }

  /**
   * Get cache statistics
   */
  getStats(): ModelLoadingStats {
    return { ...this.stats };
  }

  /**
   * Get cached model info
   */
  getModelInfo(modelName: string): CachedModel | undefined {
    return this.cache.get(modelName);
  }

  /**
   * List all cached models
   */
  listCachedModels(): string[] {
    return Array.from(this.cache.keys());
  }

  /**
   * Get cache hit rate
   */
  getCacheHitRate(): number {
    const total = this.stats.cacheHits + this.stats.cacheMisses;
    return total > 0 ? this.stats.cacheHits / total : 0;
  }

  /**
   * Configure cache settings
   */
  configure(options: {
    maxCacheSize?: number;
    cacheTimeout?: number;
  }): void {
    if (options.maxCacheSize !== undefined) {
      this.maxCacheSize = options.maxCacheSize;
      // Evict excess models if new limit is smaller
      while (this.cache.size > this.maxCacheSize) {
        this.evictLeastRecentlyUsed();
      }
    }

    if (options.cacheTimeout !== undefined) {
      this.cacheTimeout = options.cacheTimeout;
    }
  }
}

/**
 * Global model cache instance
 */
export const globalModelCache = ModelCache.getInstance();

/**
 * Warmup function to preload common models
 */
export async function warmupModels(): Promise<void> {
  console.log('Starting model warmup...');

  // This would be called on app initialization
  // Models will be lazy-loaded on first use

  console.log('Model warmup complete (lazy loading enabled)');
}

/**
 * Memory monitor for model cache
 */
export class ModelMemoryMonitor {
  private static checkInterval: number = 60000; // 1 minute
  private static maxMemoryMB: number = 500; // 500MB limit

  /**
   * Start monitoring memory usage
   */
  static startMonitoring(): void {
    setInterval(() => {
      this.checkMemoryUsage();
    }, this.checkInterval);
  }

  /**
   * Check memory usage and evict if necessary
   */
  static checkMemoryUsage(): void {
    if (typeof performance !== 'undefined' && 'memory' in performance) {
      const memory = (performance as any).memory;
      const usedMB = memory.usedJSHeapSize / 1024 / 1024;

      if (usedMB > this.maxMemoryMB) {
        console.warn(
          `Memory usage high (${usedMB.toFixed(2)}MB), clearing model cache`
        );
        globalModelCache.clearAll();
      }
    }
  }
}
