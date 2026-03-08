import axios from "axios";

interface ApiErrorPayload {
  error?: string;
  status?: string;
}

export function getApiErrorMessage(
  error: unknown,
  fallbackMessage: string
): string {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const responseMessage = error.response?.data?.error?.trim();
    if (responseMessage) {
      return responseMessage;
    }
  }

  const maybeResponseMessage = (
    error as { response?: { data?: ApiErrorPayload } } | undefined
  )?.response?.data?.error?.trim();
  if (maybeResponseMessage) {
    return maybeResponseMessage;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallbackMessage;
}
