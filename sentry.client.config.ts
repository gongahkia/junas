import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Adjust this value in production, or use tracesSampler for greater control
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

  // Setting this option to true will print useful information to the console while you're setting up Sentry
  debug: false,

  replaysOnErrorSampleRate: 1.0,

  // This sets the sample rate to be 10%. You may want this to be 100% while
  // in development and sample at a lower rate in production
  replaysSessionSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

  // You can remove this option if you're not planning to use the Sentry Session Replay feature
  integrations: [
    Sentry.replayIntegration({
      // Additional Replay configuration goes in here, for example:
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],

  environment: process.env.NODE_ENV,

  // Filter out sensitive data before sending to Sentry
  beforeSend(event, hint) {
    // Don't send events if Sentry is not configured
    if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
      return null
    }

    // Remove API keys from error data
    if (event.request) {
      delete event.request.headers?.['Authorization']
      delete event.request.headers?.['authorization']
    }

    // Filter out localStorage data that might contain API keys
    if (event.contexts?.browser?.localStorage) {
      const filtered: Record<string, any> = { ...event.contexts.browser.localStorage }
      Object.keys(filtered).forEach(key => {
        if (key.includes('api') || key.includes('key')) {
          filtered[key] = '[FILTERED]'
        }
      })
      event.contexts.browser.localStorage = filtered
    }

    return event
  },

  // Add custom tags
  initialScope: {
    tags: {
      app: 'junas',
    },
  },
})
