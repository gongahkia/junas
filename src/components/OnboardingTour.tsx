'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronRight, ChevronLeft, X } from 'lucide-react';

interface TourStep {
  target: string;
  title: string;
  content: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
}

const tourSteps: TourStep[] = [
  {
    target: '[data-tour="new-chat"]',
    title: 'Start a New Conversation',
    content: 'Click here to begin a fresh conversation with Junas. Your previous chat will be saved automatically.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="settings"]',
    title: 'Configure Your Settings',
    content: 'Access your API keys, choose your AI provider (Gemini, OpenAI, or Claude), and customize your experience.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="import"]',
    title: 'Import Conversations',
    content: 'Import previously exported conversations to continue where you left off.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="message-input"]',
    title: 'Ask Junas Anything',
    content: 'Type your legal questions here. Junas specializes in Singapore law and can help with case analysis, contract review, legal research, and more.',
    placement: 'top',
  },
  {
    target: '[data-tour="send-button"]',
    title: 'Send Your Message',
    content: 'Click to send your message, or simply press Enter. Use Shift+Enter for new lines.',
    placement: 'top',
  },
];

interface OnboardingTourProps {
  onComplete: () => void;
}

export function OnboardingTour({ onComplete }: OnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [isVisible, setIsVisible] = useState(true);

  const updateTargetPosition = useCallback(() => {
    const step = tourSteps[currentStep];
    const element = document.querySelector(step.target);
    if (element) {
      const rect = element.getBoundingClientRect();
      setTargetRect(rect);
    } else {
      setTargetRect(null);
    }
  }, [currentStep]);

  useEffect(() => {
    updateTargetPosition();
    window.addEventListener('resize', updateTargetPosition);
    window.addEventListener('scroll', updateTargetPosition);

    return () => {
      window.removeEventListener('resize', updateTargetPosition);
      window.removeEventListener('scroll', updateTargetPosition);
    };
  }, [updateTargetPosition]);

  const handleNext = () => {
    if (currentStep < tourSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = () => {
    setIsVisible(false);
    onComplete();
  };

  const handleSkip = () => {
    handleComplete();
  };

  if (!isVisible) return null;

  const step = tourSteps[currentStep];
  const isLastStep = currentStep === tourSteps.length - 1;
  const isFirstStep = currentStep === 0;

  // Calculate tooltip position
  const getTooltipStyle = (): React.CSSProperties => {
    if (!targetRect) {
      return {
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
      };
    }

    const padding = 16;
    const tooltipWidth = 320;
    const tooltipHeight = 180;
    const placement = step.placement || 'bottom';

    let top = 0;
    let left = 0;

    switch (placement) {
      case 'bottom':
        top = targetRect.bottom + padding;
        left = targetRect.left + targetRect.width / 2 - tooltipWidth / 2;
        break;
      case 'top':
        top = targetRect.top - tooltipHeight - padding;
        left = targetRect.left + targetRect.width / 2 - tooltipWidth / 2;
        break;
      case 'left':
        top = targetRect.top + targetRect.height / 2 - tooltipHeight / 2;
        left = targetRect.left - tooltipWidth - padding;
        break;
      case 'right':
        top = targetRect.top + targetRect.height / 2 - tooltipHeight / 2;
        left = targetRect.right + padding;
        break;
    }

    // Keep tooltip within viewport
    left = Math.max(padding, Math.min(left, window.innerWidth - tooltipWidth - padding));
    top = Math.max(padding, Math.min(top, window.innerHeight - tooltipHeight - padding));

    return { top, left };
  };

  // Calculate spotlight cutout
  const getSpotlightStyle = (): React.CSSProperties => {
    if (!targetRect) return {};

    const padding = 8;
    return {
      clipPath: `polygon(
        0% 0%,
        0% 100%,
        ${targetRect.left - padding}px 100%,
        ${targetRect.left - padding}px ${targetRect.top - padding}px,
        ${targetRect.right + padding}px ${targetRect.top - padding}px,
        ${targetRect.right + padding}px ${targetRect.bottom + padding}px,
        ${targetRect.left - padding}px ${targetRect.bottom + padding}px,
        ${targetRect.left - padding}px 100%,
        100% 100%,
        100% 0%
      )`,
    };
  };

  return (
    <div className="fixed inset-0 z-[100]">
      {/* Overlay with spotlight cutout */}
      <div
        className="absolute inset-0 bg-black/60 transition-all duration-300"
        style={getSpotlightStyle()}
        onClick={handleSkip}
      />

      {/* Highlight border around target */}
      {targetRect && (
        <div
          className="absolute border-2 border-primary rounded-lg pointer-events-none transition-all duration-300 animate-pulse"
          style={{
            top: targetRect.top - 8,
            left: targetRect.left - 8,
            width: targetRect.width + 16,
            height: targetRect.height + 16,
          }}
        />
      )}

      {/* Tooltip */}
      <div
        className="absolute w-80 bg-card border border-border rounded-lg shadow-xl p-4 transition-all duration-300"
        style={getTooltipStyle()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-foreground">{step.title}</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSkip}
            className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content */}
        <p className="text-sm text-muted-foreground mb-4">{step.content}</p>

        {/* Progress indicators */}
        <div className="flex items-center justify-center gap-1 mb-4">
          {tourSteps.map((_, index) => (
            <div
              key={index}
              className={`h-1.5 w-1.5 rounded-full transition-colors ${
                index === currentStep
                  ? 'bg-primary'
                  : index < currentStep
                  ? 'bg-primary/50'
                  : 'bg-muted'
              }`}
            />
          ))}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSkip}
            className="text-xs text-muted-foreground"
          >
            Skip Tour
          </Button>

          <div className="flex items-center gap-2">
            {!isFirstStep && (
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrev}
                className="h-8"
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleNext}
              className="h-8"
            >
              {isLastStep ? 'Get Started' : 'Next'}
              {!isLastStep && <ChevronRight className="h-4 w-4 ml-1" />}
            </Button>
          </div>
        </div>

        {/* Step counter */}
        <div className="text-xs text-center text-muted-foreground mt-2">
          Step {currentStep + 1} of {tourSteps.length}
        </div>
      </div>
    </div>
  );
}
