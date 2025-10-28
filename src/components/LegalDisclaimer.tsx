'use client'

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertTriangle, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"

export function LegalDisclaimer() {
  const [isVisible, setIsVisible] = useState(() => {
    if (typeof window !== 'undefined') {
      const dismissed = localStorage.getItem('junas_disclaimer_dismissed')
      return dismissed !== 'true'
    }
    return true
  })

  const handleDismiss = () => {
    setIsVisible(false)
    localStorage.setItem('junas_disclaimer_dismissed', 'true')
  }

  if (!isVisible) return null

  return (
    <Alert variant="warning" className="mb-4 relative">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Legal Disclaimer</AlertTitle>
      <AlertDescription>
        <p className="mb-2">
          <strong>Important:</strong> Junas is an AI-powered assistant and does not provide legal advice.
          The information provided is for general informational purposes only and should not be relied upon
          as a substitute for professional legal counsel.
        </p>
        <p className="text-xs">
          For specific legal matters, please consult a qualified lawyer licensed to practice in Singapore.
          By using Junas, you acknowledge that AI-generated responses may contain errors or inaccuracies.
        </p>
      </AlertDescription>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleDismiss}
        className="absolute top-2 right-2 h-6 w-6 p-0"
        aria-label="Dismiss disclaimer"
      >
        <X className="h-4 w-4" />
      </Button>
    </Alert>
  )
}
