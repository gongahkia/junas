# DR-001: Name and license

This is a research brief, not legal advice. It records observed naming collisions and open-source precedent so the maintainer can choose quickly; it does not give author legal opinions.

## 1. Name candidates

| Option | Pros | Cons | Discoverability check |
|---|---|---|---|
| **SG-LegalBench** | Clearest; matches the LegalBench naming convention; immediately says Singapore + legal benchmark. | Least distinct; close to the new Singapore retrieval benchmark [SG-LegalCite](https://arxiv.org/abs/2605.21057); inherits some generic `LegalBench` search noise. | Exact searches for `"SG-LegalBench"` and `"sg legal benchmark"` found no exact same-name project; the closest live collision is `SG-LegalCite`. |
| **SingLegalBench** | More distinct than `SG-LegalBench`; still carries Singapore + LegalBench. | Unwieldy; `Sing` reads less formal and may be misread as music-related; weaker convention match. | Exact search for `"SingLegalBench"` found no same-name collision. |
| **LexSG-Eval** | Academic-flavoured; compact; avoids direct `LegalBench` dependency. | Loses the `LegalBench` brand/category signal; `Lex` is generic legal-tech vocabulary. | Exact search for `"LexSG-Eval"` found no same-name collision; broader `LexSG`-style names are less self-explanatory than `SG-LegalBench`. |

## 2. Code license

| Option | What it optimises for | Trade-off | Legal-tech precedent |
|---|---|---|---|
| [MIT](https://opensource.org/license/mit/) | Maximum reuse, lowest friction, easy commercial adoption. | No patent grant; easiest path for closed-source forks. | [OpenLegalData legal-ner](https://github.com/openlegaldata/legal-ner) is MIT; [Legal RAG Bench](https://github.com/isaacus-dev/legal-rag-bench) is MIT. Caveat: LegalBench itself is not a clean top-level MIT precedent; its README says task licenses are per creator. |
| [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | MIT-like adoption with an explicit patent grant. | Slightly more compliance overhead than MIT; still permits closed-source forks. | Stanford CRFM [HELM](https://github.com/stanford-crfm/helm) is Apache-2.0; [OpenLaw core](https://github.com/openlawteam/openlaw-core) is Apache-2.0. |
| [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.en.html) | Protects against closed-source hosted competitor builds by requiring network-service source availability. | Reduces commercial-vendor uptake; some companies refuse AGPL dependencies or hosted derivatives outright. | [Mike OSS](https://github.com/willchen96/mike) is AGPL-3.0; LexNLP/ContraxSuite uses AGPL/commercial dual licensing. |
| [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html) | Strong copyleft for distributed code without AGPL's network-service clause. | Still vendor-frictional, but weaker than AGPL against SaaS-only forks. | [OpenStates scrapers](https://github.com/openstates/openstates-scrapers) are GPL-3.0; [Marker](https://github.com/datalab-to/marker) is GPL-3.0. |

## 3. Dataset license

| Option | What it optimises for | Trade-off | Benchmark / data precedent |
|---|---|---|---|
| [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) | Broad research and commercial reuse with attribution. | Does not force share-alike and does not block commercial dataset reuse. | [LegalBench on Hugging Face](https://huggingface.co/datasets/nguha/legalbench), [CUAD](https://www.atticusprojectai.org/cuad/), and [SG-LegalCite](https://huggingface.co/datasets/anonymousmeowmeow/SG-LegalCite) use CC-BY-4.0. |
| [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Attribution plus share-alike for adapted datasets. | More friction for benchmark aggregation and vendor eval packs. | [Multi_Legal_Pile_Commercial](https://huggingface.co/datasets/joelniklaus/Multi_Legal_Pile_Commercial), [LegalBench.BR](https://huggingface.co/datasets/celsowm/legalbench.br), and [LegalQAEval](https://huggingface.co/datasets/isaacus/LegalQAEval) use CC-BY-SA-4.0. |
| [CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/) | Blocks commercial reuse unless separately licensed. | Not Open Definition; vendor/commercial labs may skip it, and "noncommercial" can create review ambiguity. | [Refugee Law Lab Canadian Legal Data](https://huggingface.co/datasets/refugee-law-lab/canadian-legal-data), [MTEB LegalBench consumer contracts QA](https://huggingface.co/datasets/mteb/legalbench_consumer_contracts_qa), and [MLEB Legal RAG Bench](https://huggingface.co/datasets/isaacus/mleb-legal-rag-bench) use CC-BY-NC-4.0. |
| [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | Maximum downstream reuse, including commercial and benchmark aggregation. | No required attribution; competitors can reuse silently. | Free Law's [Caselaw Access Project](https://huggingface.co/datasets/free-law/Caselaw_Access_Project), [LegalCiteBench](https://huggingface.co/datasets/legalcitebench/LegalCiteBench), and [Swiss Legal RAG Bench](https://huggingface.co/datasets/voilaj/swiss-legal-rag-bench) use CC0. |

## 4. Recommendation

Choose **SG-LegalBench**, **Apache-2.0 for code**, and **CC-BY-4.0 for datasets**: this preserves the clearest benchmark positioning, keeps vendor and research adoption easy, and still requires dataset attribution.
