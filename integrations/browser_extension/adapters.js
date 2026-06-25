(function registerKaypohBrowserAdapters(global) {
  const GENERIC_SELECTORS = [
    "textarea",
    "input[type='text']",
    "input[type='search']",
    "input[type='url']",
    "input[type='email']",
    "[contenteditable='true']"
  ];

  const ADAPTERS = [
    {
      id: "chatgpt",
      hostnames: ["chatgpt.com"],
      selectors: [
        "[data-testid='prompt-textarea']",
        "textarea#prompt-textarea",
        "textarea[name='prompt-textarea']",
        "div[contenteditable='true']"
      ],
      submitSelectors: [
        "[data-testid='send-button']",
        "button[data-testid='send-button']",
        "button[aria-label*='Send' i]"
      ]
    },
    {
      id: "claude",
      hostnames: ["claude.ai"],
      selectors: [
        "div.ProseMirror[contenteditable='true']",
        "[contenteditable='true'][aria-label*='prompt' i]",
        "textarea"
      ],
      submitSelectors: [
        "button[aria-label*='Send' i]",
        "button[aria-label*='Submit' i]"
      ]
    },
    {
      id: "gemini",
      hostnames: ["gemini.google.com"],
      selectors: [
        "rich-textarea textarea",
        "[aria-label*='Enter a prompt' i]",
        "[contenteditable='true']"
      ],
      submitSelectors: [
        "button[aria-label*='Send message' i]",
        "button[aria-label*='Send' i]"
      ]
    },
    {
      id: "generic",
      hostnames: [],
      selectors: GENERIC_SELECTORS,
      submitSelectors: [
        "button[type='submit']",
        "button[aria-label*='Send' i]",
        "button[aria-label*='Submit' i]"
      ]
    }
  ];

  function normalizedHost(locationLike) {
    return String(locationLike?.hostname || "").toLowerCase().replace(/^www\./, "");
  }

  function adapterForLocation(locationLike) {
    const host = normalizedHost(locationLike);
    return ADAPTERS.find((adapter) => adapter.hostnames.includes(host)) || ADAPTERS.find((adapter) => adapter.id === "generic");
  }

  function selectorsForLocation(locationLike) {
    const adapter = adapterForLocation(locationLike);
    if (adapter.id === "generic") return adapter.selectors;
    return [...adapter.selectors, ...GENERIC_SELECTORS];
  }

  function submitSelectorsForLocation(locationLike) {
    const adapter = adapterForLocation(locationLike);
    if (adapter.id === "generic") return adapter.submitSelectors;
    const generic = ADAPTERS.find((item) => item.id === "generic");
    return [...adapter.submitSelectors, ...generic.submitSelectors];
  }

  function findPromptComposer(root, locationLike) {
    if (!root || typeof root.querySelector !== "function") return null;
    for (const selector of selectorsForLocation(locationLike)) {
      const found = root.querySelector(selector);
      if (found) return found;
    }
    return null;
  }

  function resolvePromptTarget(element, locationLike) {
    if (!element) return null;
    for (const selector of selectorsForLocation(locationLike)) {
      if (typeof element.matches === "function" && element.matches(selector)) return element;
      if (typeof element.closest === "function") {
        const closest = element.closest(selector);
        if (closest) return closest;
      }
    }
    return null;
  }

  function findSubmitButton(root, locationLike) {
    if (!root || typeof root.querySelector !== "function") return null;
    for (const selector of submitSelectorsForLocation(locationLike)) {
      const found = root.querySelector(selector);
      if (found) return found;
    }
    return null;
  }

  function resolveSubmitTarget(element, locationLike) {
    if (!element) return null;
    for (const selector of submitSelectorsForLocation(locationLike)) {
      if (typeof element.matches === "function" && element.matches(selector)) return element;
      if (typeof element.closest === "function") {
        const closest = element.closest(selector);
        if (closest) return closest;
      }
    }
    return null;
  }

  global.KAYPOH_BROWSER_ADAPTERS = {
    all: ADAPTERS,
    adapterForLocation,
    findPromptComposer,
    findSubmitButton,
    resolveSubmitTarget,
    resolvePromptTarget
  };
})(globalThis);
