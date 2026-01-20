'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { StorageManager } from '@/lib/storage';
import { useToast } from '@/components/ui/toast';
import { ProvidersTab } from '@/components/ProvidersTab';
import {
  AVAILABLE_MODELS,
  getModelsWithStatus,
  downloadModel,
  removeModelFromDownloaded,
  type ModelInfo,
  type DownloadProgress,
} from '@/lib/ml/model-manager';
import { Download, Trash2, Check, Loader2, AlertCircle } from 'lucide-react';

interface ConfigDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'profile' | 'localModels' | 'providers';

export function ConfigDialog({ isOpen, onClose }: ConfigDialogProps) {
  const [activeTab, setActiveTab] = useState<Tab>('profile');

  // Listen for custom event to open Providers tab
  useEffect(() => {
    const handler = (e: any) => {
      if (e.detail && e.detail.tab === 'providers') {
        setActiveTab('providers');
      }
    };
    window.addEventListener('open-config-dialog', handler);
    return () => window.removeEventListener('open-config-dialog', handler);
  }, []);

  // Profile state
  const [userRole, setUserRole] = useState('');
  const [userPurpose, setUserPurpose] = useState('');

  // Models state
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [downloadingModels, setDownloadingModels] = useState<Record<string, DownloadProgress>>({});
  const { addToast } = useToast();

  useEffect(() => {
    if (isOpen) {
      // Load profile settings
      const settings = StorageManager.getSettings();
      setUserRole(settings.userRole || '');
      setUserPurpose(settings.userPurpose || '');

      // Load models status
      setModels(getModelsWithStatus());
    }
  }, [isOpen]);

  const handleSaveProfile = () => {
    const settings = StorageManager.getSettings();
    StorageManager.saveSettings({
      ...settings,
      userRole,
      userPurpose,
    });
    onClose();
  };

  const handleDownloadModel = async (modelId: string) => {
    try {
      setDownloadingModels(prev => ({
        ...prev,
        [modelId]: {
          modelId,
          progress: 0,
          loaded: 0,
          total: 0,
          status: 'downloading',
        },
      }));

      await downloadModel(modelId, (progress) => {
        setDownloadingModels(prev => ({
          ...prev,
          [modelId]: progress,
        }));
      });

      // Refresh models list
      setModels(getModelsWithStatus());

      // Get model name for toast
      const modelInfo = AVAILABLE_MODELS.find(m => m.id === modelId);
      addToast({
        type: 'success',
        title: 'Model Ready',
        description: `${modelInfo?.name || modelId} has been downloaded and is ready to use.`,
        duration: 4000,
      });

      // Clear from downloading state after a delay
      setTimeout(() => {
        setDownloadingModels(prev => {
          const updated = { ...prev };
          delete updated[modelId];
          return updated;
        });
      }, 2000);
    } catch (error: any) {
      setDownloadingModels(prev => ({
        ...prev,
        [modelId]: {
          modelId,
          progress: 0,
          loaded: 0,
          total: 0,
          status: 'error',
          error: error.message,
        },
      }));

      const modelInfo = AVAILABLE_MODELS.find(m => m.id === modelId);
      addToast({
        type: 'error',
        title: 'Download Failed',
        description: `Failed to download ${modelInfo?.name || modelId}: ${error.message}`,
        duration: 5000,
      });
    }
  };

  const handleRemoveModel = (modelId: string) => {
    removeModelFromDownloaded(modelId);
    setModels(getModelsWithStatus());
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg font-mono max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm">[ ⚙ Configuration ]</DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex border-b border-muted-foreground/30">
          <button
            onClick={() => setActiveTab('profile')}
            className={`px-4 py-2 text-xs transition-colors ${
              activeTab === 'profile'
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Profile
          </button>
          <button
            onClick={() => setActiveTab('localModels')}
            className={`px-4 py-2 text-xs transition-colors ${
              activeTab === 'localModels'
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Local Models
          </button>
          <button
            onClick={() => setActiveTab('providers')}
            className={`px-4 py-2 text-xs transition-colors ${
              activeTab === 'providers'
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Providers
          </button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto py-4">
          {activeTab === 'profile' && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Set your role and purpose to help Junas provide more relevant assistance.
              </p>

              <div className="space-y-2">
                <Label htmlFor="userRole" className="text-xs font-mono">
                  &gt; Your Role
                </Label>
                <Input
                  id="userRole"
                  placeholder="e.g., lawyer, law student, legal researcher"
                  value={userRole}
                  onChange={(e) => setUserRole(e.target.value)}
                  className="text-xs font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="userPurpose" className="text-xs font-mono">
                  &gt; Your Purpose
                </Label>
                <Input
                  id="userPurpose"
                  placeholder="e.g., contract analysis, case law research"
                  value={userPurpose}
                  onChange={(e) => setUserPurpose(e.target.value)}
                  className="text-xs font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-mono">
                  &gt; Context Preview
                </Label>
                <p className="text-xs text-muted-foreground pl-1">
                  {userRole || '[Your Role]'} using Junas for {userPurpose || '[Your Purpose]'}
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <button
                  onClick={handleSaveProfile}
                  className="px-3 py-2 text-xs bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  [ Save ]
                </button>
              </div>
            </div>
          )}

          {activeTab === 'localModels' && (
            <div className="space-y-4">
              <div className="text-xs text-muted-foreground space-y-1">
                <p>Download local ML models for offline processing.</p>
                <p>Models are cached in your browser and run without API calls.</p>
              </div>

              <div className="space-y-3">
                {models.map((model) => {
                  const downloadProgress = downloadingModels[model.id];
                  const isDownloading = downloadProgress?.status === 'downloading' || downloadProgress?.status === 'loading';
                  const hasError = downloadProgress?.status === 'error';
                  const justCompleted = downloadProgress?.status === 'ready';

                  return (
                    <div
                      key={model.id}
                      className="border border-muted-foreground/30 p-3 space-y-2"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium">{model.name}</span>
                            <span className="text-[10px] text-muted-foreground">
                              {model.size}
                            </span>
                            {model.isDownloaded && !isDownloading && (
                              <span className="text-[10px] px-1.5 py-0.5 bg-green-500/20 text-green-600 dark:text-green-400 rounded">
                                READY
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-1">
                            {model.description}
                          </p>
                        </div>

                        <div className="flex items-center gap-2">
                          {model.isDownloaded ? (
                            <button
                              onClick={() => handleRemoveModel(model.id)}
                              className="p-1.5 text-xs hover:bg-red-500/10 text-red-500 transition-colors"
                              title="Remove model"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleDownloadModel(model.id)}
                              disabled={isDownloading}
                              className="p-1.5 text-xs hover:bg-primary/10 text-primary transition-colors disabled:opacity-50"
                              title="Download model"
                            >
                              {isDownloading ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : justCompleted ? (
                                <Check className="h-3.5 w-3.5 text-green-500" />
                              ) : (
                                <Download className="h-3.5 w-3.5" />
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Progress bar */}
                      {isDownloading && (
                        <div className="space-y-1">
                          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300"
                              style={{ width: `${downloadProgress.progress}%` }}
                            />
                          </div>
                          <p className="text-[10px] text-muted-foreground">
                            Downloading... {downloadProgress.progress}%
                          </p>
                        </div>
                      )}

                      {/* Error message */}
                      {hasError && (
                        <div className="flex items-center gap-1 text-[10px] text-red-500">
                          <AlertCircle className="h-3 w-3" />
                          <span>{downloadProgress.error || 'Download failed'}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="text-[10px] text-muted-foreground pt-2 border-t border-muted-foreground/20">
                <p>Models are powered by ONNX Runtime and run entirely in your browser.</p>
                <p>First download may take a while depending on your connection.</p>
              </div>
            </div>
          )}
          {activeTab === 'providers' && (
            <ProvidersTab />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
