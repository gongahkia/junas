defmodule SayLess.TestSupport.FakeHttpClient do
  @moduledoc false

  use Agent

  def start_link(_opts) do
    Agent.start_link(fn -> %{get: nil, post: nil} end, name: __MODULE__)
  end

  def reset do
    Agent.update(__MODULE__, fn _state -> %{get: nil, post: nil} end)
  end

  def stub_get(fun) when is_function(fun, 3) do
    Agent.update(__MODULE__, &Map.put(&1, :get, fun))
  end

  def stub_post(fun) when is_function(fun, 4) do
    Agent.update(__MODULE__, &Map.put(&1, :post, fun))
  end

  def get(url, headers \\ [], options \\ []) do
    call_stub(:get, [url, headers, options])
  end

  def post(url, body, headers \\ [], options \\ []) do
    call_stub(:post, [url, body, headers, options])
  end

  defp call_stub(kind, args) do
    case Agent.get(__MODULE__, &Map.get(&1, kind)) do
      nil -> raise "No #{kind} stub configured for #{__MODULE__}"
      fun -> apply(fun, args)
    end
  end
end
