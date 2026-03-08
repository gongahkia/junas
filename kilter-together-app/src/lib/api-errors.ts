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
    const responseData = error.response?.data as
      | ApiErrorPayload
      | string
      | undefined;
    const responseMessage =
      typeof responseData === "string"
        ? responseData.trim()
        : responseData?.error?.trim();
    if (responseMessage) {
      return responseMessage;
    }

    const normalizedMessage = error.message.trim();
    if (
      normalizedMessage &&
      !/^Request failed with status code \d+$/.test(normalizedMessage)
    ) {
      return normalizedMessage;
    }

    return fallbackMessage;
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
