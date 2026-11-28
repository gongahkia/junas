import { prebuiltAppConfig } from "@mlc-ai/web-llm";
import { MODEL } from "./contract.js";

export const WEIGHTS_REVISION = "80b3abcec6c3b3f5355dc0cc99cc4fb578f192bc";
export const LIBRARY_REVISION = "5b7251f3bdce957be2a7bf73a6f6c560d9874df4";
export const WEIGHTS_REVISIONS = {
  [MODEL]: WEIGHTS_REVISION,
  "Llama-3.2-3B-Instruct-q4f16_1-MLC": "1e80abf71e3d17cd564e2d2b63caa15cb226018e",
  "Qwen3-4B-q4f16_1-MLC": "a5c9fab855e3ccbdfed2e7e69683d75f30332161",
};
export function modelConfig(id = MODEL) {
  const revision = WEIGHTS_REVISIONS[id];
  const record = prebuiltAppConfig.model_list.find(item => item.model_id === id);
  if (!revision || !record) throw Error("Unsupported or unpinned local model.");
  return { model_list: [{
  ...record,
  model: `https://huggingface.co/mlc-ai/${id}/resolve/${revision}/`,
  model_lib: record.model_lib.replace("/main/", `/${LIBRARY_REVISION}/`),
  }] };
}
export const MODEL_CONFIG = modelConfig();
