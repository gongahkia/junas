import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Adjust this value in production, or use tracesSampler for greater control
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

  // Setting this option to true will print useful information to the console while you're setting up Sentry
  debug: false,

  environment: process.env.NODE_ENV,

  // Filter out sensitive data before sending to Sentry
  beforeSend(event, hint) {
    // Don't send events if Sentry is not configured
    if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
      return null
    }

    // Remove API keys and sensitive headers
    if (event.request) {
      delete event.request.headers?.['Authorization']
      delete event.request.headers?.['authorization']
      delete event.request.cookies
    }

    // Remove sensitive environment variables
    if (event.contexts?.runtime) {
      const filtered = { ...event.contexts.runtime }
      Object.keys(filtered).forEach(key => {
        if (
          key.includes('KEY') ||
          key.includes('SECRET') ||
          key.includes('TOKEN') ||
          key.includes('PASSWORD')
        ) {
          filtered[key] = '[FILTERED]'
        }
      })
      event.contexts.runtime = filtered
    }

    return event
  },

  // Add custom tags
  initialScope: {
    tags: {
      app: 'junas',
      runtime: 'server',
    },
  },
})
