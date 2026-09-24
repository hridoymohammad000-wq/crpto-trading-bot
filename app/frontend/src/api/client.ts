import { ApiError, RequestOptions } from './types';

/**
 * Public backend URL configured at build time by Vite.
 */
const configuredUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

export const API_BASE_URL = configuredUrl.replace(/\/+$/, '');

/**
 * Custom Error Class for HTTP and API execution failures
 */
export class ApiClientError extends Error implements ApiError {
  public status?: number;
  public code?: string;
  public details?: unknown;

  constructor(message: string, status?: number, code?: string, details?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * Builds a query string safely from a key-value dictionary
 */
function buildQueryString(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

/**
 * Central HTTP client using native fetch with timeouts, error mapping, and typing
 */
export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 60000, params, headers, ...customOptions } = options;

  if (!API_BASE_URL) {
    throw new ApiClientError(
      'VITE_API_BASE_URL is not configured for this frontend deployment.',
      undefined,
      'CONFIG_ERROR',
    );
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const formattedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const queryString = buildQueryString(params);
  const targetUrl = `${API_BASE_URL}${formattedEndpoint}${queryString}`;

  const defaultHeaders: HeadersInit = { Accept: 'application/json' };
  if (customOptions.body !== undefined) defaultHeaders['Content-Type'] = 'application/json';

  try {
    const response = await fetch(targetUrl, {
      ...customOptions,
      headers: {
        ...defaultHeaders,
        ...headers,
      },
      signal: controller.signal,
    });

    // Handle non-2xx status responses
    if (!response.ok) {
      let errorBody: unknown;
      let errorMessage = `API Request failed with status ${response.status} (${response.statusText})`;

      try {
        errorBody = await response.json();
        if (typeof errorBody === 'object' && errorBody !== null) {
          const body = errorBody as { detail?: string; message?: string; error?: string };
          errorMessage = body.detail || body.message || body.error || errorMessage;
        }
      } catch {
        // Response was not JSON, fallback to status text
        try {
          const rawText = await response.text();
          if (rawText) errorMessage = rawText;
        } catch {
          // Ignore read errors
        }
      }

      throw new ApiClientError(errorMessage, response.status, response.statusText, errorBody);
    }

    // 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Parse JSON
    return (await response.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiClientError) {
      throw err;
    }

    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiClientError(
        `Request timed out after ${timeoutMs}ms: ${endpoint}`,
        408,
        'TIMEOUT_ERROR'
      );
    }

    const message = err instanceof Error ? err.message : 'Unknown network error';
    throw new ApiClientError(message, undefined, 'NETWORK_ERROR', err);
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Reusable HTTP convenience methods
 */
export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions): Promise<T> =>
    request<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

};
