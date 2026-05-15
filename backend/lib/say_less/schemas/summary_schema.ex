defmodule SayLess.Schemas.SummarySchema do
  @moduledoc """
  JSON schema for structured AI summary responses.
  """

  def get_schema_definition do
    %{
      "type" => "object",
      "properties" => %{
        "characters" => %{
          "type" => "array",
          "items" => %{"type" => "string"},
          "description" => "A list of the most relevant characters or groups."
        },
        "key_events" => %{
          "type" => "array",
          "items" => %{"type" => "string"},
          "description" => "An ordered list of the highest-signal story beats."
        },
        "plot_points" => %{
          "type" => "array",
          "items" => %{"type" => "string"},
          "description" => "An ordered list of plot developments the user would miss by skipping."
        },
        "skip_context" => %{
          "type" => "string",
          "description" => "A short paragraph describing the context the user should carry forward."
        }
      },
      "required" => ["characters", "key_events", "plot_points", "skip_context"]
    }
  end
end
