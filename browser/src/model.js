import { prebuiltAppConfig } from "@mlc-ai/web-llm";
import { MODEL } from "./contract.js";

export const WEIGHTS_REVISION = "80b3abcec6c3b3f5355dc0cc99cc4fb578f192bc";
export const LIBRARY_REVISION = "5b7251f3bdce957be2a7bf73a6f6c560d9874df4";
const record = prebuiltAppConfig.model_list.find(item => item.model_id === MODEL);
if (!record) throw Error("Pinned model is absent from the installed WebLLM registry.");
export const MODEL_CONFIG = { model_list: [{
  ...record,
  model: `https://huggingface.co/mlc-ai/${MODEL}/resolve/${WEIGHTS_REVISION}/`,
  model_lib: record.model_lib.replace("/main/", `/${LIBRARY_REVISION}/`),
}] };
