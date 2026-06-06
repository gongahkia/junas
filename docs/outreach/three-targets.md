# Independent Reproduction Targets

These briefs are written for first-contact outreach. They are not private
profiles; every institutional fact below is based on public sources linked in
each section.

## SMU SOLID / Centre For Digital Law

Public anchors:

- [SMU Centre for Digital Law](https://cdl.smu.edu.sg/)
- [SMU Centre for Computational Law](https://cclaw.smu.edu.sg/)
- [MinLaw remarks at the SOLID launch event, 18 November 2025](https://news.smu.edu.sg/sites/news.smu.edu.sg/files/smu/news_room/Opening%20Remarks%20by%20MinLaw%20Director%20of%20Legal%20Tech%20Transformation%20Office%20Mr%20Lim%20Joo%20Hong%20at%20the%20SOLID%20Launch%20Event_0.pdf)

Who they are:

SMU's Centre for Computational Law has merged with the Centre for AI and Data
Governance to form the Centre for Digital Law. The Centre positions itself
around law, computer science, digital humanities, governance, regulation, and
legal-tech research. The SOLID launch remarks describe the Singapore Open Legal
Informatics Database as a three-year project to build open-source empirical
legal-data infrastructure for Singapore, in collaboration with SMU's Centre for
Digital Law and the Ministry of Law.

What they care about:

[Inference] SOLID's mandate is closest to benchmark reproducibility because both
projects depend on structured, public, inspectable Singapore legal data. SMU CDL
also has a Computational Law and LegalTech Lab, so a reproducible legal-LLM
benchmark is a natural technical artifact rather than a generic AI demo.

Why this reproduction serves their mandate:

[Inference] Running SG-LegalBench gives SOLID a concrete downstream test of
whether open Singapore legal-data infrastructure can support model evaluation.
It also lets SMU CDL show that Singapore-specific legal AI can be measured with
public receipts, not just described in workshops or policy language.

What we ask:

- Run the strict v0.1 eligible suite against a model chosen by SMU SOLID/CDL.
- Publish receipts under `runs/external/smu-solid/`.
- Add a short reviewer note on whether the receipt fields, task framing, and
  contamination probe are sufficient for empirical legal-informatics reuse.

Best angle:

Frame this as a small empirical-legal-data collaboration. Ask for a named ML
engineer plus one CDL/SOLID reviewer, not a broad institutional partnership.

Likely objection:

[Inference] SMU may ask whether this needs to sit under a SOLID data-sharing or
research-collaboration agreement. Keep the first run public-domain only and make
clear that no LawNet, client, or confidential data is required.

Academic-year timing:

SMU's public AY2026-27 materials list Term 1 as starting on 17 August 2026. A
4-6 week run started on 6 June 2026 would finish by 18 July 2026, before the
main term, but faculty travel and pre-term planning can still slow sign-off.

## NUS TRAIL

Public anchor:

- [NUS Centre for Technology, Robotics, Artificial Intelligence and the Law](https://law.nus.edu.sg/trail/about-us/)
- [NUS academic calendar](https://www.nus.edu.sg/registrar/calendar)

Who they are:

TRAIL is a NUS Law centre focused on the relationship between technology and
legal research. Its public description emphasises legal, ethical, policy,
philosophical, and regulatory questions around IT, AI, data analytics, and
robotics, including interdisciplinary research and possible standards or
solutions for technology governance.

What they care about:

[Inference] TRAIL is likely to care less about leaderboard marketing and more
about whether the benchmark's claims are methodologically defensible: public
sources, mechanical label extraction, contamination checks, confidence
intervals, and a public dispute process.

Why this reproduction serves their mandate:

[Inference] A reproduction lets TRAIL turn AI-and-law governance questions into
a concrete audit artifact: given a Singapore legal task, a model, and a receipt,
what can a researcher responsibly infer about model capability? The output also
creates teaching or seminar material for empirical legal-AI evaluation.

What we ask:

- Run the strict v0.1 eligible suite against a TRAIL-selected model or a named
  frontier model.
- Publish receipts under `runs/external/nus-trail/`.
- Add a short methods note on contamination interpretation, SGLB-08 synthetic
  label limitations, and whether the public dispute process is adequate.

Best angle:

Lead with methodology and governance, not vendor usefulness. Ask TRAIL to be
the adversarial reviewer of what a public legal-LLM benchmark can and cannot
claim.

Likely objection:

[Inference] TRAIL may be unwilling to endorse a benchmark if SGLB-08's
synthetic labels or inter-judge agreement are not yet strong enough. Offer to
publish their reproduction with a caveat or to scope their run to SGLB-01,
SGLB-02, and SGLB-04 if that is the cleaner research position.

Academic-year timing:

NUS says its standard academic calendar commences on the first Monday of August;
the AY2026-27 calendar lists orientation from 3-8 August 2026 and Semester 1
instruction from 10 August 2026. A 4-6 week run started on 6 June 2026 would
finish before orientation week.

## SAL / LawNet Technology Services

Public anchors:

- [LawNet Technology Services](https://tech.lawnet.com/)
- [SAL Technology](https://sal.org.sg/technology/)
- [SAL announcement on LawNet 4.0 and global content partnerships](https://sal.org.sg/articles/singapore-academy-of-law-signs-global-content-partnerships-to-expand-worldwide-access-of-singapore-law-and-unveils-ai-powered-lawnet-4-0-at-techlaw-fest-2025/)

Who they are:

LawNet Technology Services is the technology company behind LawNet and is a
wholly owned subsidiary of the Singapore Academy of Law. Its public description
connects LawNet to Singapore legal research, legal information, transactions,
and SAL support services. SAL's technology page describes legal-technology
programmes including LawNet AI, AI-generated summaries for unreported Singapore
judgments, prompt-engineering resources, and TechLaw.Fest.

What they care about:

[Inference] SAL/LTS is likely to care about trusted legal content, professional
adoption, reliability, provenance, and whether AI tools are useful to the legal
community without overstating legal correctness.

Why this reproduction serves their mandate:

[Inference] An independent receipt bundle gives SAL/LTS a public way to evaluate
Singapore legal-LLM behaviour without exposing proprietary LawNet content. It
also aligns with the practical question SAL's users will ask: which Singapore
legal tasks can be scored, audited, and explained with public evidence?

What we ask:

- Run the strict v0.1 eligible suite against a SAL/LTS-approved model or a named
  frontier model.
- Publish receipts under `runs/external/sal-lts/`.
- Add a short note on whether the receipt fields are sufficient for a legal
  information-service operator to inspect model claims.

Best angle:

Lead with trust, provenance, and public-domain scope. Make clear that the run
does not need LawNet subscriber data, unreported judgments, or any confidential
SAL material.

Likely objection:

[Inference] SAL/LTS may need internal approval before any public statement that
touches LawNet AI or model evaluation. Offer a no-endorsement publication style:
"receipt independently run by SAL/LTS; scores and comments do not constitute
SAL endorsement of any model."

Calendar timing:

SAL is not tied to the university teaching calendar. [Inference] The bigger
timing risk is institutional communications, legal review, and alignment with
events such as TechLaw.Fest or product-release windows, not semester load.
