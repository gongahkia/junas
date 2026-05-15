defmodule SayLess.HttpClient do
  @moduledoc """
  Default HTTP client wrapper used by external adapters and the AI summarizer.
  """

  @callback get(String.t(), list(), keyword()) :: {:ok, %{status_code: integer(), body: binary()}} | {:error, any()}
  @callback post(String.t(), iodata(), list(), keyword()) :: {:ok, %{status_code: integer(), body: binary()}} | {:error, any()}

  def get(url, headers \\ [], options \\ []) do
    HTTPoison.get(url, headers, options)
  end

  def post(url, body, headers \\ [], options \\ []) do
    HTTPoison.post(url, body, headers, options)
  end
end
