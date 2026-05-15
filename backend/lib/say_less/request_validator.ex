defmodule SayLess.RequestValidator do
  @moduledoc """
  Validates and normalizes incoming API request parameters.
  """

  alias SayLess.ExternalApis.Client

  @spoiler_levels ~w(light standard full)

  def validate_search(params) do
    source = normalize_source(Map.get(params, "source"))
    query = normalize_string(Map.get(params, "query"))

    with :ok <- validate_source(source),
         :ok <- validate_query(query) do
      {:ok, %{source: source, query: query}}
    end
  end

  def validate_targets(params) do
    source = normalize_source(Map.get(params, "source"))
    media_id = normalize_string(Map.get(params, "media_id"))

    with :ok <- validate_source(source),
         :ok <- validate_media_id(media_id) do
      {:ok, %{source: source, media_id: media_id}}
    end
  end

  def validate_summary(params) do
    source = normalize_source(Map.get(params, "source"))
    media_id = normalize_string(Map.get(params, "media_id"))
    target_type = normalize_target_type(source, Map.get(params, "target_type"))
    target_id = normalize_string(Map.get(params, "target_id"))
    spoiler_level = normalize_string(Map.get(params, "spoiler_level")) || "standard"

    with :ok <- validate_source(source),
         :ok <- validate_media_id(media_id),
         {:ok, source_spec} <- validate_source_spec(source),
         :ok <- validate_target_type(source_spec, target_type),
         :ok <- validate_target_id(target_type, target_id),
         :ok <- validate_spoiler_level(spoiler_level) do
      {:ok,
       %{
         source: source,
         media_id: media_id,
         target_type: target_type,
         target_id: target_id,
         spoiler_level: spoiler_level
       }}
    end
  end

  defp normalize_source(value) do
    value
    |> normalize_string()
    |> Client.normalize_source()
  end

  defp normalize_target_type(source, nil) do
    case Client.source_spec(source) do
      %{target_types: [default | _]} -> default
      _ -> nil
    end
  end

  defp normalize_target_type(_source, value), do: normalize_string(value)

  defp normalize_string(value) when is_binary(value) do
    case String.trim(value) do
      "" -> nil
      trimmed -> trimmed
    end
  end

  defp normalize_string(_), do: nil

  defp validate_source(source) do
    case validate_source_spec(source) do
      {:ok, _spec} -> :ok
      {:error, _, _, _} = error -> error
    end
  end

  defp validate_source_spec(source) do
    case Client.source_spec(source) do
      nil ->
        {:error, :unprocessable_entity, "unsupported_source", "Unsupported media source."}

      spec ->
        {:ok, spec}
    end
  end

  defp validate_query(nil),
    do: {:error, :unprocessable_entity, "invalid_query", "Search query must be at least 2 characters long."}

  defp validate_query(query) do
    if String.length(query) >= 2 do
      :ok
    else
      {:error, :unprocessable_entity, "invalid_query", "Search query must be at least 2 characters long."}
    end
  end

  defp validate_media_id(nil),
    do: {:error, :unprocessable_entity, "invalid_media_id", "A media identifier is required."}

  defp validate_media_id(_media_id), do: :ok

  defp validate_target_type(source_spec, target_type) do
    if target_type in source_spec.target_types do
      :ok
    else
      {:error, :unprocessable_entity, "invalid_target_type", "This source does not support the requested target type."}
    end
  end

  defp validate_target_id("title", _target_id), do: :ok

  defp validate_target_id(_target_type, nil),
    do: {:error, :unprocessable_entity, "invalid_target_id", "A target identifier is required for segment-level summaries."}

  defp validate_target_id(_target_type, _target_id), do: :ok

  defp validate_spoiler_level(level) when level in @spoiler_levels, do: :ok

  defp validate_spoiler_level(_level),
    do: {:error, :unprocessable_entity, "invalid_spoiler_level", "Spoiler level must be one of: light, standard, full."}
end
