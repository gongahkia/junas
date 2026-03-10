import axios from "axios";
import type { ApiErrorCode, ApiErrorPayload } from "@/types";

export interface ApiErrorDetails {
  message: string;
  code?: ApiErrorCode | string;
  status?: number;
  requestId?: string;
  traceId?: string;
}

export function getApiErrorDetails(
  error: unknown,
  fallbackMessage: string
): ApiErrorDetails {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const responseData = error.response?.data as
      | ApiErrorPayload
      | string
      | undefined;
    const responseMessage =
      typeof responseData === "string"
        ? responseData.trim()
        : responseData?.error?.trim();
    const baseDetails: ApiErrorDetails = {
      code:
        typeof responseData === "string"
          ? undefined
          : responseData?.code,
      message: responseMessage || fallbackMessage,
      requestId:
        typeof responseData === "string"
          ? undefined
          : responseData?.request_id,
      status: error.response?.status,
      traceId:
        typeof responseData === "string"
          ? undefined
          : responseData?.trace_id,
    };

    if (responseMessage) {
      return baseDetails;
    }

    const normalizedMessage = error.message.trim();
    if (
      normalizedMessage &&
      !/^Request failed with status code \d+$/.test(normalizedMessage)
    ) {
      return {
        ...baseDetails,
        message: normalizedMessage,
      };
    }

    return baseDetails;
  }

  const maybeResponseMessage = (
    error as { response?: { data?: ApiErrorPayload } } | undefined
  )?.response?.data?.error?.trim();
  if (maybeResponseMessage) {
    return {
      code: (error as { response?: { data?: ApiErrorPayload } } | undefined)?.response?.data?.code,
      message: maybeResponseMessage,
      requestId: (error as { response?: { data?: ApiErrorPayload } } | undefined)?.response?.data?.request_id,
      status: Number(
        (error as { response?: { status?: number } } | undefined)?.response?.status
      ) || undefined,
      traceId: (error as { response?: { data?: ApiErrorPayload } } | undefined)?.response?.data?.trace_id,
    };
  }

  if (error instanceof Error && error.message.trim()) {
    return {
      message: error.message,
    };
  }

  return {
    message: fallbackMessage,
  };
}

export function getApiErrorMessage(
  error: unknown,
  fallbackMessage: string
): string {
  return getApiErrorDetails(error, fallbackMessage).message;
}

export function hasApiErrorCode(error: unknown, ...codes: string[]): boolean {
  const code = getApiErrorDetails(error, "").code;
  return typeof code === "string" && codes.includes(code);
}
