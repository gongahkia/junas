defmodule SayLess do
  @moduledoc """
  Core application context for catalog search, target selection, and summarization.
  """

  alias SayLess.ExternalApis.Client
  alias SayLess.RequestValidator

  def search_titles(params) do
    with {:ok, request} <- RequestValidator.validate_search(params),
         {:ok, adapter} <- Client.adapter_for_source(request.source),
         {:ok, results} <- adapter.search_titles(request.query) do
      {:ok, %{results: results}}
    end
  end

  def list_targets(params) do
    with {:ok, request} <- RequestValidator.validate_targets(params),
         {:ok, adapter} <- Client.adapter_for_source(request.source),
         {:ok, payload} <- adapter.list_targets(request.media_id) do
      {:ok, payload}
    end
  end

  def summarize(params) do
    with {:ok, request} <- RequestValidator.validate_summary(params),
         {:ok, adapter} <- Client.adapter_for_source(request.source),
         {:ok, payload} <- adapter.fetch_summary_subject(request),
         {:ok, summary} <-
           summarizer_module().generate_summary_from_content(
             payload.content,
             build_prompt_context(payload, request)
           ) do
      {:ok,
       %{
         media: payload.media,
         target: payload.target,
         summary: summary,
         meta: %{
           spoiler_level: request.spoiler_level,
           source_name: payload.media.source_label,
           generated_at: generated_at(),
           attribution: %{
             label: payload.media.source_label,
             url: payload.media.external_url
           }
         }
       }}
    end
  end

  defp summarizer_module do
    Application.get_env(:say_less, :summarizer_module, SayLess.Ai.Summarizer)
  end

  defp build_prompt_context(payload, request) do
    %{
      "media_title" => payload.media.title,
      "media_type" => payload.media.media_type,
      "source_name" => payload.media.source_label,
      "target_label" => payload.target.label,
      "target_type" => payload.target.type,
      "spoiler_level" => request.spoiler_level
    }
  end

  defp generated_at do
    DateTime.utc_now()
    |> DateTime.truncate(:second)
    |> DateTime.to_iso8601()
  end
end
