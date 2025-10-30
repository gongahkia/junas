'use client'

import { AlertTriangle } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { StorageManager } from "@/lib/storage"

interface LegalDisclaimerProps {
  onDismiss?: () => void;
}

export function LegalDisclaimerContent() {
  return (
    <>
      <p className="mb-2">
        <strong>Important:</strong> Junas is an AI-powered assistant and does not provide legal advice.
        The information provided is for general informational purposes only and should not be relied upon
        as a substitute for professional legal counsel.
      </p>
      <p className="text-xs">
        For specific legal matters, please consult a qualified lawyer licensed to practice in Singapore.
        By using Junas, you acknowledge that AI-generated responses may contain errors or inaccuracies.
      </p>
    </>
  );
}

export function LegalDisclaimer({ onDismiss }: LegalDisclaimerProps = {}) {
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      // Show disclaimer only if user hasn't seen it before
      return !StorageManager.hasSeenDisclaimer()
    }
    return true
  })

  const handleAccept = () => {
    setIsOpen(false)
    StorageManager.setDisclaimerSeen()
    if (onDismiss) {
      onDismiss()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent
        className="sm:max-w-[500px] bg-white"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <DialogTitle>Legal Disclaimer</DialogTitle>
          </div>
          <DialogDescription className="text-left pt-2">
            <LegalDisclaimerContent />
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={handleAccept} className="w-full sm:w-auto">
            I Agree
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
