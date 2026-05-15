defmodule SayLess.Ai.Summarizer do
  @moduledoc """
  Handles all interactions with the Google Gemini AI model for summarization.
  """

  alias SayLess.Schemas.SummarySchema

  @gemini_api_url "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

  def generate_summary_from_content(content, context) do
    api_key = Application.fetch_env!(:say_less, :gemini_api_key)
    headers = [
      {"Content-Type", "application/json"},
      {"X-goog-api-key", api_key}
    ]
    body = build_request_body(content, context)

    with {:ok, %{status_code: 200, body: resp_body}} <- http_client().post(@gemini_api_url, body, headers, []),
         {:ok, parsed_body} <- Jason.decode(resp_body) do
      parse_gemini_response(parsed_body)
    else
      {:ok, %{status_code: code, body: error_body}} ->
        {:error, :bad_gateway, "ai_request_failed", "AI service returned status #{code}: #{inspect(error_body)}"}

      {:error, %{reason: reason}} ->
        {:error, :bad_gateway, "ai_connection_failed", "Failed to connect to the AI service: #{inspect(reason)}"}

      {:error, reason} ->
        {:error, :bad_gateway, "ai_connection_failed", "Failed to connect to the AI service: #{inspect(reason)}"}
    end
  end

  defp build_request_body(content, context) do
    prompt = create_prompt(content, context)

    Jason.encode!(%{
      "contents" => [%{"parts" => [%{"text" => prompt}]}],
      "generationConfig" => %{
        "responseMimeType" => "application/json",
        "responseJsonSchema" => SummarySchema.get_schema_definition()
      }
    })
  end

  defp create_prompt(content, context) do
    spoiler_instruction =
      case context["spoiler_level"] do
        "light" ->
          "Keep details restrained. Mention only the minimum sequence of events needed to understand what was skipped."

        "full" ->
          "Be explicit and comprehensive about revealed events, outcomes, and consequences."

        _ ->
          "Balance clarity and brevity. Include the main reveals and consequences without turning it into a scene-by-scene transcript."
      end

    """
    You are the summarization engine for the SayLess product.
    The user is asking for a skip-ahead summary of the #{context["target_type"]} "#{context["target_label"]}" from the #{context["media_type"]} "#{context["media_title"]}" sourced from #{context["source_name"]}.

    Output a single JSON object and nothing else.
    Use only the supplied content. Do not invent details.
    #{spoiler_instruction}

    Field requirements:
    - characters: short list of the most relevant characters or groups
    - key_events: concise ordered bullets describing the highest-signal beats
    - plot_points: slightly more detailed ordered bullets covering what the user would miss
    - skip_context: one short paragraph telling the user what context they should carry forward after skipping

    --- CONTENT TO SUMMARIZE ---
    #{content}
    --------------------------
    """
  end

  defp parse_gemini_response(parsed_body) do
    case get_in(parsed_body, ["candidates"]) do
      [first_candidate | _] ->
        case get_in(first_candidate, ["content", "parts"]) do
          [first_part | _] ->
            json_string = get_in(first_part, ["text"])

            if json_string do
              case Jason.decode(json_string) do
                {:ok, summary_map} -> normalize_summary(summary_map)
                {:error, _} -> {:error, :bad_gateway, "ai_invalid_json", "The AI returned text that was not valid JSON."}
              end
            else
              {:error, :bad_gateway, "ai_invalid_response", "The AI response did not include the expected text payload."}
            end

          _ ->
            {:error, :bad_gateway, "ai_invalid_response", "The AI response contained an empty parts list."}
        end

      _ ->
        {:error, :bad_gateway, "ai_invalid_response", "The AI model returned no candidates in the response."}
    end
  end

  defp normalize_summary(summary_map) when is_map(summary_map) do
    with {:ok, characters} <- normalize_string_list(summary_map["characters"]),
         {:ok, key_events} <- normalize_string_list(summary_map["key_events"]),
         {:ok, plot_points} <- normalize_string_list(summary_map["plot_points"]),
         {:ok, skip_context} <- normalize_text(summary_map["skip_context"]) do
      {:ok,
       %{
         characters: characters,
         key_events: key_events,
         plot_points: plot_points,
         skip_context: skip_context
       }}
    end
  end

  defp normalize_summary(_summary_map) do
    {:error, :bad_gateway, "ai_invalid_shape", "The AI response did not match the expected summary shape."}
  end

  defp normalize_string_list(items) when is_list(items) do
    normalized =
      items
      |> Enum.filter(&is_binary/1)
      |> Enum.map(&String.trim/1)
      |> Enum.reject(&(&1 == ""))

    if normalized == [] do
      {:error, :bad_gateway, "ai_invalid_shape", "The AI response omitted a required summary list."}
    else
      {:ok, normalized}
    end
  end

  defp normalize_string_list(_items) do
    {:error, :bad_gateway, "ai_invalid_shape", "The AI response omitted a required summary list."}
  end

  defp normalize_text(text) when is_binary(text) do
    case String.trim(text) do
      "" -> {:error, :bad_gateway, "ai_invalid_shape", "The AI response omitted the skip context field."}
      trimmed -> {:ok, trimmed}
    end
  end

  defp normalize_text(_text) do
    {:error, :bad_gateway, "ai_invalid_shape", "The AI response omitted the skip context field."}
  end

  defp http_client do
    Application.get_env(:say_less, :http_client, SayLess.HttpClient)
  end
end
