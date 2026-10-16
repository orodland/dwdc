# AI Governance, Reliability Controls and QA for an LLM-Assisted Extraction Pipeline Feeding a Deterministic Financial Reconciliation (Audit-Evidence Use)

*Method note (for the report writer): researched 16 Oct 2026. Direct page fetching was blocked in this environment (egress proxy refused WebFetch/curl and the Tavily API), so findings come from web-search result summaries plus primary-source URLs those searches returned. Items marked **[TK – not re-verified]** come from the researcher's prior knowledge of stable primary documents (cutoff mid-2026) and could not be re-opened this session; treat exact figures in them as needing a spot check. Items marked **[older]** predate 2025. Scenario is generic: an LLM extracts trade or confirmation fields from heterogeneous broker documents (PDF/email/CSV), and deterministic code reconciles them against internal books. Reconciliation outputs are retained as audit evidence.*

## 1. Repeatability: LLM non-determinism, versioning/deprecation risk and mitigations

### Takeaway
Temperature 0 does not make hosted LLM output repeatable. The main cause identified in 2025 research is that inference kernels are not batch-invariant: server load changes the batch size, which changes floating-point reduction order. Provider "seed" features are best-effort only, and model snapshots get retired on provider schedules. So the defensible pattern for audit evidence is not to re-run the model and get the same answer. Instead: freeze and hash every AI output once it is reviewed, record the full inference configuration, and where possible use the LLM to *author* deterministic parsers or configuration that is reviewed, versioned and then executed without the LLM.

### Cited Findings
- **Root cause (2025):** Thinking Machines Lab (Horace He et al., Sept 2025), "Defeating Nondeterminism in LLM Inference", argues that floating-point non-associativity plus GPU concurrency is *not* the main cause, because most kernels are run-to-run deterministic. The dominant cause is that kernels lack **batch invariance**: on a shared inference server the batch size varies with load, which changes reduction order and therefore the numerics for any single request — [Thinking Machines Lab blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) (summarised via [OpenAI community thread](https://community.openai.com/t/defeating-nondeterminism-in-llm-inference/1358623) and [Spheron explainer](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/))
- **Headline experiment:** 1,000 temperature-0 completions of the same prompt on a Qwen model gave about **80 distinct outputs**. With batch-invariant kernels (matmul, RMSNorm, attention), all 1,000 were identical — [Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/); [Morph write-up](https://www.morphllm.com/defeating-nondeterminism-llm-inference). [TK – not re-verified]: the model was Qwen3-235B-A22B-Instruct-2507, and the first divergence appeared around token 103.
- **Cost of determinism:** batch-invariant kernels carried roughly a **61.5% throughput overhead** in the original post (about 26s rising to about 42s with an optimised attention kernel). A later secondary write-up cites about 34% average overhead (range 24–46%) in subsequent implementations. These figures come from secondary summaries — [Spheron](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/); [Substack summary](https://ursula8sciform.substack.com/p/finally-your-llm-will-become-deterministic)
- **Ecosystem uptake:** vLLM added a `VLLM_BATCH_INVARIANT` mode, and SGLang 0.5.3 shipped batch-invariant / deterministic inference kernels (22 Sept 2025). Self-hosted open-weight deployments can therefore choose bit-reproducible inference at a throughput cost — [Spheron](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/) (secondary)
- **Earlier empirical evidence [older]:** Atil et al. (2024), "Non-Determinism of 'Deterministic' LLM Settings", measured run-to-run accuracy swings of up to about 15% across five temperature-0 runs on hosted models, with best-to-worst gaps far larger. Exact string-match repeatability was rare on long outputs — [arXiv 2408.04667](https://arxiv.org/abs/2408.04667) [TK – not re-verified]
- **Hardware and precision sensitivity (2025):** "Give Me FP32 or Give Me Death?" reports that under bf16 greedy decoding, changing GPU count, GPU type or batch size shifted reasoning-model accuracy by several percentage points and changed response lengths substantially. The authors propose FP32 "LayerCast" as a mitigation — [arXiv 2506.09501](https://arxiv.org/abs/2506.09501) [TK – not re-verified]
- **Practitioner evidence:** a 2026 practitioner post documents 29 "flapping" test cases whose outputs changed at temperature 0 across identical calls — [memx.app](https://memx.app/blog/llm-determinism-is-a-lie-29-flapping-cases/) (practitioner blog, low-moderate weight)
- **Provider seed controls (OpenAI):** OpenAI's docs say Chat Completions are non-deterministic by default. `seed` offers only partial ("best effort") control and works best with all other parameters fixed. The returned `system_fingerprint` identifies the backend configuration, and if it changes, outputs may change. OpenAI also says determinism "may be impacted by necessary changes OpenAI makes to model configurations" — [OpenAI Advanced usage docs](https://developers.openai.com/api/docs/guides/advanced-usage); [OpenAI Cookbook – reproducible outputs with seed](https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter)
- **Fingerprint is not a sufficient signal:** developer-forum reports describe outputs drifting while `system_fingerprint` stayed constant — [OpenAI community: "Seed param and reproducible output do not work"](https://community.openai.com/t/seed-param-and-reproducible-output-do-not-work/487245?page=2) (anecdotal)
- **No seed at some providers:** one secondary source says Anthropic still offered no seed parameter as of May 2026 — [memx.app](https://memx.app/blog/why-temperature-0-isnt-deterministic/) (secondary; verify against current docs)
- **Deprecation / weight preservation:** Anthropic's Nov 2025 commitments say it will preserve the weights of all publicly released models for at least the company's lifetime. Preservation is not continued serving: retired models do not answer API calls, and continued public availability is only "being explored". Claude Opus 3 was retired on 5 Jan 2026 under this process — [Anthropic – Commitments on model deprecation and preservation](https://www.anthropic.com/research/deprecation-commitments); [Anthropic – Opus 3 deprecation update](https://www.anthropic.com/research/deprecation-updates-opus-3); [Forbes](https://www.forbes.com/sites/ronschmelzer/2025/11/07/anthropic-commits-to-preserving-retired-models-what-does-this-mean/)
- **Deprecation windows differ by channel:** one analysis reports that cloud resellers such as Amazon Bedrock kept some models available months beyond the original provider's retirement date. Notice windows vary across Anthropic, OpenAI, Google and the hyperscalers — [beri.net](https://www.beri.net/article/model-deprecation-policy-notice-windows-bedrock-azure-anthropic-openai-gemini); [lifecycle calendar](https://hidekazu-konishi.com/entry/ai_model_deprecation_and_lifecycle_calendar.html) (secondary). [TK – not re-verified]: Anthropic's docs state at least 60 days' notice before retiring publicly released models — [Anthropic model deprecations](https://docs.anthropic.com/en/docs/about-claude/model-deprecations); OpenAI publishes a deprecations page — [OpenAI deprecations](https://platform.openai.com/docs/deprecations)
- **What breaks on retirement:** a practitioner write-up describes prompts tuned to one snapshot regressing on the successor model. Validation must be re-performed rather than assumed to carry over — [DEV Community](https://dev.to/axrisi/api-deprecation-for-ai-models-what-breaks-when-a-model-is-retired-1a01)

### Inferences
- For audit evidence, the evidential object should be **the frozen extraction output plus its provenance**, not "the model". Evidence is reproducible by re-performance of the deterministic reconciliation on the frozen, hashed extraction. It is *not* reproducible by re-querying a hosted LLM. This framing mirrors how auditors treat other system-generated reports: the auditor tests the report's reliability once and retains the report.
- Recommended mitigation stack, strongest first:
  1. **LLM-as-code-author:** the LLM proposes a per-broker parser, template or mapping config (regex, column map, XPath). A human reviews it and version-controls it, and it is then executed deterministically. The LLM is out of the run-time path for known formats and is used only for onboarding and for exceptions.
  2. **Self-hosted, pinned open-weight model** with batch-invariant kernels, fixed hardware and precision, a fixed container digest and weight hashes. This gives bit-reproducibility at a throughput cost.
  3. **Hosted model pinned to a dated snapshot ID** (never a floating alias). Log `system_fingerprint` or its equivalent, temperature 0, and fixed tokenizer and prompt. Treat any change in model ID or fingerprint as a change event that triggers the regression suite.
  4. **Cache and freeze:** key each output by content hash, i.e. `sha256(source_document) + sha256(prompt_template) + model_id + params`. Never regenerate an accepted output, and serve repeats from cache.
- Run-to-run disagreement is also a free reliability signal. Running the same extraction 2–3 times and flagging any field-level disagreement for review turns non-determinism into an uncertainty detector. This is an inference and was not found as published guidance.
- A model-retirement plan should be part of model governance: an inventory of snapshot IDs with provider retirement dates, a migration regression test, and a documented re-validation sign-off before cut-over.

### Gaps
- Could not open the Thinking Machines post directly to confirm exact overhead figures. The 61.5% and 34% numbers are from secondary summaries.
- No authoritative 2026 cross-provider table of seed support and deprecation notice periods was retrieved. Provider terms change frequently and should be checked at contracting time.
- Whether newer reasoning-model APIs (2025–26) honour `seed` at all was not confirmed.

## 2. Hallucination and error controls for extraction

### Takeaway
Constrained decoding and structured outputs guarantee the *shape* of the output, not its truth. Accuracy effects are contested and depend on schema size. Extraction controls therefore have to be layered:
- **Syntactic:** schema validation.
- **Semantic:** type, range and enum rules, and cross-field logic such as quantity × price ≈ gross amount.
- **Grounding:** verbatim or normalised-match checks of every extracted value against the source text, with page or character offsets.
- **Population:** row counts and control totals against document footers or trailers.
- **Redundancy:** independent second extraction (a different model or a deterministic parser) with disagreement routed to review.
- **Human sampling**, with routing driven by validated (not self-reported) confidence.

LLM-as-judge is useful for triage but is itself biased and must be validated against human labels. It should not be the sole control over audit-relevant fields.

### Cited Findings
- **Structured outputs ≠ correctness:** a schema-valid object can still be "full of facts the model made up" — [Sanity glossary: structured output](https://www.sanity.io/glossary/structured-output) (secondary, consistent with all primary sources below)
- **Format restriction can degrade reasoning [older, 2024]:** Tam et al., "Let Me Speak Freely?" (EMNLP 2024 Industry) found stricter format constraints such as JSON mode degraded reasoning performance. A two-step "answer in natural language, then convert to schema" approach mitigated this — [arXiv 2408.02442](https://arxiv.org/pdf/2408.02442)
- **Contested:** dottxt's rebuttal "Say What You Mean" argues the degradation came from prompt and evaluation design, and that structured generation can match or beat free-form output — reported via [Sanity glossary](https://www.sanity.io/glossary/structured-output); original at [dottxt blog](https://blog.dottxt.co/say-what-you-mean.html) [TK – not re-verified]
- **Complex-extraction benchmark (2026):** ExtractBench found structured-output mode *reduced* both validity and accuracy compared with prompt-based extraction on 210 extractions: validity fell from 51% (107/210) to 37% (77/210), and the best-model pass rate fell from 6.9% to 5.5%. The largest schema (369 fields) could not be handled at all in structured mode — [arXiv 2602.12247 ExtractBench](https://arxiv.org/pdf/2602.12247)
- **Constrained-decoding coverage varies:** JSONSchemaBench (about 10K real-world schemas) evaluates constrained-decoding frameworks on efficiency, schema coverage and quality. It notes poor understanding of how effective these methods are in practice, and frameworks differ in which JSON Schema features they support — [arXiv 2501.10868](https://arxiv.org/abs/2501.10868)
- **Vendor claim [older, TK – not re-verified]:** OpenAI's Aug 2024 Structured Outputs launch claimed 100% schema adherence on its complex-schema eval for gpt-4o-2024-08-06, versus under 40% for an earlier model with prompting alone. This is adherence to the schema, not factual accuracy — [OpenAI – Introducing Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- **LLM-as-judge biases:**
  - **Position bias:** in MT-Bench, only GPT-4 was position-consistent in more than about 60% of cases [older, 2023] — [Zheng et al., arXiv 2306.05685](https://arxiv.org/pdf/2306.05685)
  - **Verbosity and self-enhancement biases** are catalogued in the same paper — [arXiv 2306.05685](https://arxiv.org/pdf/2306.05685)
  - **Self-preference:** judges favour lower-perplexity, more "familiar" text, including their own outputs — [Self-Preference Bias in LLM-as-a-Judge, arXiv 2410.21819](https://arxiv.org/html/2410.21819v1)
  - **Broader catalogue:** the "Justice or Prejudice?" CALM framework quantifies a dozen judge biases — [arXiv 2410.02736](https://arxiv.org/html/2410.02736v1)
  - **Position bias depends on quality gap:** it is strongest when the candidates are close in quality, and a more consistent judge is not necessarily a fairer one — [arXiv 2406.07791](https://arxiv.org/pdf/2406.07791v5)
- **Practitioner guidance:** validate any judge against human labels, and avoid grading a model with the same model family. Practitioner-reported human–judge agreement of κ≈0.75–0.83 on well-scoped tasks could not be traced to a primary source — [Grepture](https://grepture.com/blog/llm-as-a-judge-bias); [Nakrani](https://alpeshnakrani.com/blog/llm-as-a-judge/) (blogs; unverified figures)
- **Specialised verifiers:** small specialised encoder ensembles have been proposed as cheaper, more predictable alternatives to general LLM judges for guard-type classification [older, 2024] — [JurEE, arXiv 2410.08442](https://arxiv.org/pdf/2410.08442)
- **Calibration [older, TK – not re-verified]:** LLMs asked to verbalise confidence tend to be **overconfident**, and verbalised scores are poorly calibrated without sampling-consistency or other aggregation — [Xiong et al., "Can LLMs Express Their Uncertainty?", arXiv 2306.13063](https://arxiv.org/abs/2306.13063)
- **NIST names this risk:** NIST AI 600-1 lists "confabulation" (confidently stated false content) among its 12 GenAI risks, with suggested actions across Govern/Map/Measure/Manage — [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) [older, July 2024]; summary at [governancedocs.com](https://governancedocs.com/nist-ai-rmf-generative-ai-profile/)

### Inferences
- Recommended control set for broker-document extraction. Each control is deterministic and testable, so it can be tested as an automated control:
  1. **Schema validation:** JSON Schema / Pydantic with required fields, types, ISIN/CUSIP/SEDOL check digits, ISO 4217 currency codes, ISO 10383 MIC codes, valid date ranges, and trade date ≤ settlement date.
  2. **Arithmetic and cross-field checks:** qty × price ± fees ≈ net amount within tolerance; buy/sell sign consistency; FX consistency.
  3. **Verbatim / grounding check:** require the model to return a source span (page plus text snippet or offsets) for every field. Code then confirms the normalised value appears in the source text, or in the OCR text layer. Any field with no locatable span is rejected or routed to review. This is the single strongest control against fabricated values.
  4. **Completeness controls:** extracted row count = rows detected by a deterministic table or line detector; sum of extracted amounts = statement control total or footer; sequence or page continuity checks. Any break means the document fails.
  5. **Independent dual extraction:** a second model from a different family, or a deterministic template parser where one exists. Agreement means auto-accept candidate; disagreement goes to a human. Correlated errors between LLMs are likely, so diversity of method matters more than adding more LLMs.
  6. **Confidence routing:** only use scores calibrated on the golden set, e.g. run-agreement rate, logprob-based scores or verifier scores. Set thresholds from measured precision at each score band, and do not rely on self-reported confidence.
  7. **LLM-as-judge:** use only as a prioritiser for human review, never as the final acceptance control for audit-relevant fields. Test it periodically against human labels.
- The reconciliation itself acts as a downstream detective control. Breaks against internal books surface many extraction errors. However, an extraction error that happens to *match* a wrong internal record (a correlated or confirmation-bias error) will not break, so extraction controls must stand on their own and not rely on the reconciliation.
- Use a two-step pattern where the schema is large: free-text or reasoning extraction first, then constrained conversion, or field-group-by-field-group extraction. This is consistent with the Tam et al. and ExtractBench findings on large schemas.

### Gaps
- No financial-document-specific (trade confirmation or broker statement) public benchmark of LLM extraction accuracy was found. ExtractBench is the closest general benchmark.
- No primary study quantifying the error-reduction from verbatim-grounding checks or dual-model extraction in finance was found. The recommendations rest on design logic.

## 3. Evaluation methodology: golden sets, metrics, sampling, regression and drift

### Takeaway
Leading practice treats the AI extractor like any other model under validation:
- a **versioned golden dataset** stratified by broker, format and edge case;
- **field-level precision, recall and exact-match** plus **row-level completeness** metrics with pre-set acceptance thresholds;
- **statistical acceptance sampling** of production output, using zero-deviation attribute-sampling logic familiar to auditors;
- a **regression suite gating every model, prompt or config change**;
- **drift monitoring** that detects new or changed broker layouts and routes them to onboarding rather than silent extraction.

### Cited Findings
- **NIST GenAI profile measurement actions:** NIST AI 600-1 provides 200+ suggested actions across Govern/Map/Measure/Manage, including measurement and TEVV (test, evaluation, verification and validation) of GenAI risks such as confabulation — [governancedocs.com summary](https://governancedocs.com/nist-ai-rmf-generative-ai-profile/); [aigovernance.com](https://aigovernance.com/policy/nist-ai-600-1-generative-ai-profile); primary: [NIST AI 600-1 PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
- **US MRM guidance on ongoing monitoring:** the revised US interagency guidance (SR 26-2, April 2026) carries forward effective challenge, independent validation and ongoing monitoring. Reports differ on what was removed: one says prescriptive detail on backtesting and code verification was dropped — [Federal Reserve SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm); [Elevate Consult commentary](https://elevateconsult.com/insights/sr-11-7-rescinded-model-risk-guidance-ai-gap/) (secondary)
- **Validation scalability concern:** at Bank of England/PRA roundtables (Oct 2025), firms questioned whether traditional validation approaches scale to generative and agentic AI — [BoE PRA MRM AI/ML Roundtable Oct 2025](https://www.bankofengland.co.uk/-/media/boe/files/prudential-regulation/publication/2025/november/ai-roundtable-oct-2025.pdf)
- **Benchmark methodology:** ExtractBench proposes per-field, schema-aware scoring for complex structured extraction, with validity and pass-rate reported separately. It is a template for field-level metrics — [arXiv 2602.12247](https://arxiv.org/pdf/2602.12247)
- **Zero-failure sampling math:** if n independent samples show 0 errors, the one-sided 95% upper confidence bound on the error rate is ≈ 3/n (the "rule of three") — [Wikipedia: Rule of three (statistics)](https://en.wikipedia.org/wiki/Rule_of_three_(statistics)). Worked example: n=59 with 0 errors supports "error rate < 5% at 95% confidence", because 0.95^59 ≈ 0.048. n≈300 supports < 1%.
- **Audit sampling standards** that auditors will map these plans to: PCAOB AS 2315 (Audit Sampling) — [PCAOB AS 2315](https://pcaobus.org/oversight/standards/auditing-standards/details/AS2315) [TK – not re-verified]; the AICPA Audit Guide *Audit Sampling* provides attribute-sampling tables [TK – not re-verified]
- **Run-to-run variance affects evaluation itself:** single-run evaluations of LLMs at temperature 0 can misstate accuracy by several points, so evaluations should use multiple runs or frozen outputs — [Atil et al. arXiv 2408.04667](https://arxiv.org/abs/2408.04667) [TK – not re-verified]; [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)

### Inferences
- **Golden dataset design:**
  - Stratify by broker × document type × format version, and include edge cases: multi-page tables, cancels and corrects, partial fills, multiple currencies, scanned/OCR documents, and footnoted fees.
  - Label at field level with source-span annotations, using double-keyed human labelling with adjudication.
  - Version-control the dataset and its hash.
  - Hold out a sealed test partition that is never used for prompt tuning, to avoid overfitting prompts to the test set.
- **Metrics:**
  - **Field-level:** precision (extracted values that are correct), recall (true values that were extracted), exact-match after normalisation, and numeric tolerance error.
  - **Row-level completeness:** share of true trades captured, and spurious rows.
  - **Document-level straight-through rate:** documents passing all controls without review.
  - Report each metric per broker or stratum. Aggregates hide weak formats.
- **Acceptance thresholds** should be risk-weighted: zero tolerance for critical fields (ISIN, quantity, net amount, settlement date, direction, account) and looser tolerance for descriptive fields.
- **Acceptance testing for go-live:** use zero-deviation attribute sampling per critical field per stratum, e.g. 59 documents with no critical-field error for each new broker format, for < 5% at 95% confidence. Larger samples apply for high-volume brokers or tighter targets. Any deviation triggers root-cause analysis and expanded testing, consistent with how auditors treat deviations in control testing.
- **Production QA sampling:**
  - Continuous random sampling of auto-accepted outputs for human re-performance, at a rate proportionate to volume and risk, plus targeted sampling of low-confidence and novel-format items.
  - Track the observed error rate with confidence bounds over time, e.g. monthly.
- **Regression gates:**
  - Any change to model snapshot, prompt, schema, parser, OCR engine or decoding parameters is a change event. It re-runs the full golden set and must meet or beat the incumbent per stratum, with a documented sign-off.
  - Store the old-vs-new diff report as part of the change record.
- **Drift monitoring:**
  - Fingerprint incoming documents by layout or template hash, header tokens, column sets and sender, and alert on unseen fingerprints.
  - Monitor per-broker validation-failure rates, review-override rates, field null rates and reconciliation-break rates attributable to extraction.
  - Unknown formats should route to a quarantine/onboarding queue, not to auto-accept.

### Gaps
- No regulator-published sampling standard specifically for AI-extracted data was found. The sampling logic is borrowed from audit sampling practice (inference).
- No public financial-services benchmark for broker-document drift detection was found.

## 4. Governance frameworks (status as of Oct 2026)

### Takeaway
As of Oct 2026, the landscape changed materially in 2026.

**US:**
- SR 11-7 was **rescinded on 17 Apr 2026**, replaced by interagency **SR 26-2 / OCC Bulletin 2026-13 / FDIC guidance**. The new guidance is principles-based, non-binding, aimed mainly at banks with more than $30bn in assets, and **excludes generative and agentic AI from its scope**.
- That leaves a GenAI gap that firms are filling with NIST AI RMF and AI 600-1, Treasury's **Financial Services AI RMF (Feb 2026, 230 control objectives)**, and ISO/IEC 42001.

**UK:** PRA **SS1/23** keeps AI and ML inside model risk management under its general model definition.

**EU:**
- The AI Act was amended by the **AI Omnibus (Reg. (EU) 2026/1744, in force 27 Jul 2026)**. Annex III high-risk obligations are deferred to **2 Dec 2027**. GPAI obligations and enforcement were *not* delayed, and the Article 4 AI-literacy duty was softened.
- An internal trade-extraction/reconciliation tool is very unlikely to be high-risk, but the firm is a "deployer" with literacy and governance expectations, and it relies on GPAI providers' compliance.

### Cited Findings
**US – model risk management**
- **SR 26-2 basics:** issued 17 Apr 2026 by the Fed, OCC and FDIC, it "supersedes and replaces SR letter 11-7 … and SR letter 21-8". It is tailored to the bank's size, complexity and model risk profile, "does not set forth enforceable standards or prescriptive requirements", and is expected to be most relevant to banks with over $30bn in total assets. Supervisory action may still follow for violations of law or unsafe or unsound practices — [Federal Reserve SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm); [SR 26-2 attachment PDF](https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf); [FDIC press release](https://www.fdic.gov/news/press-releases/2026/agencies-issue-revised-model-risk-guidance); [FDIC guidance PDF](https://www.fdic.gov/model-risk-management-revised-guidance.pdf)
- **No supervisory criticism for non-adherence:** commentary reports that the agencies say non-compliance with the guidance itself will not result in supervisory criticism, a notable shift from SR 11-7 — [Elevate Consult](https://elevateconsult.com/insights/sr-11-7-rescinded-model-risk-guidance-ai-gap/); [RiskTemplate](https://risktemplate.com/blog/2026-05-02-occ-fed-fdic-revised-model-risk-management-guidance-2026/) (secondary)
- **Vendor models:** SR 26-2 includes considerations specific to vendor and third-party products, including their validation — [Federal Reserve SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm)
- **GenAI and agentic AI excluded:** Vice Chair for Supervision Bowman (1 May 2026) described the revised guidance as applying "narrowly to traditional models and basic AI applications" — [Bowman speech, 1 May 2026](https://www.federalreserve.gov/newsevents/speech/bowman20260501a.htm). Secondary sources report a separate request for information on GenAI and agentic AI is planned — [Elevate Consult](https://elevateconsult.com/insights/sr-11-7-rescinded-model-risk-guidance-ai-gap/) (not confirmed in a primary source)
- **OCC numbering conflict:** the OCC's 2026 bulletin index lists "Model Risk Management: Revised Guidance" as OCC 2026-13 dated 04/17/2026, and also shows an entry referencing 2026-14 dated 04/22/2026. Most sources use 2026-13 — [OCC 2026 Bulletins](https://www.occ.gov/news-events/newsroom/news-issuances-by-year/bulletins/2026-bulletins.html); [RiskTemplate on OCC 2026-13](https://risktemplate.com/blog/2026-06-10-occ-bulletin-2026-13-model-risk-management-sr-11-7-what-changed/)
- **Other rescissions:** the FDIC rescinded FIL-22-2017 and FIL-27-2021 — [FDIC press release](https://www.fdic.gov/news/press-releases/2026/agencies-issue-revised-model-risk-guidance). Secondary sources also list OCC Bulletin 1997-24 and the Comptroller's Handbook model risk booklet — [Elevate Consult](https://elevateconsult.com/insights/sr-11-7-rescinded-model-risk-guidance-ai-gap/)

**US – other frameworks**
- **Treasury FS AI RMF:** released 19 Feb 2026 with an AI Lexicon. It is non-binding, adapts the NIST AI RMF to financial services with about 230 control objectives (fraud, bias, model risk, explainability, cybersecurity), was developed with input from more than 100 institutions and agencies, and is the first two of six planned resources — [American Banker](https://www.americanbanker.com/news/treasury-issues-new-ai-risk-tools-for-banks); [ZwillGen](https://www.zwillgen.com/artificial-intelligence/us-treasury-department-publishes-ai-guidance-financial-services/); [Grant Thornton](https://www.grantthornton.com/insights/articles/banking/2026/treasury-guidance-brings-urgency-to-ai-governance); [TCS](https://www.tcs.com/insights/blogs/us-treasury-financial-services-ai-risk-management-framework)
- **NIST AI RMF:** AI RMF 1.0 (Jan 2023) remains the finalised core. Secondary sources report NIST is revising it under the 2025 White House AI Action Plan, with no release date found — [normgrid timeline](https://www.normgrid.com/nist-ai-rmf/timeline/); [nistairmfkit status Oct 2026](https://nistairmfkit.com/ai-rmf-2-0/) (secondary)
- **NIST AI 600-1 (GenAI Profile, July 2024) [older]:** 12 GenAI-specific risks (e.g., confabulation, data privacy, information security, value-chain/component integration) and 200+ actions. It is voluntary, with no certification scheme — [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf); [agentcertified.eu](https://agentcertified.eu/articles/nist-ai-600-1-generative-ai-profile-implementation-guide)

**International standards**
- **ISO/IEC 42001:2023** is the certifiable AI management-system standard, in contrast to the voluntary NIST documents — [SecureW2 comparison](https://securew2.com/blog/nist-ai-rmf-vs-iso-42001); primary: [ISO/IEC 42001](https://www.iso.org/standard/81230.html) [TK – not re-verified: Annex A has 38 controls; companion standards ISO/IEC 42005:2025 (impact assessment) and 42006 (certification-body requirements)]

**UK**
- **PRA SS1/23:** contains no separate AI rules and treats AI and ML models under its general model definition, unlike the US carve-out of GenAI — [Global Policy Watch (Covington), Apr 2026](https://www.globalpolicywatch.com/2026/04/uk-financial-services-regulators-approach-to-artificial-intelligence-in-2026/); [axiom-verity glossary](https://axiom-verity.com/glossary/pra-ss1-23) (secondary)
- **SS1/23 dating conflict:** most sources give publication on 17 May 2023 and effect from 17 May 2024 [TK]. One secondary source says it was amended or republished on 23 Apr 2026 — [jonasosmanabdelghafour.org](https://jonasosmanabdelghafour.org/insights/ai-model-risk-management-2026-pra-ss1-23-validation-governance) — unverified against the PRA site
- **UK supervisory focus:** the Bank of England's 2026 response to the Treasury Committee inquiry on AI in financial services says it will examine AI risks including GenAI explainability and concentration risk in third-party model providers. Industry broadly supports the PRA's principles-based approach — [BoE response to TSC](https://www.bankofengland.co.uk/-/media/boe/files/letter/2026/response-to-tsc-inquiry-report-on-ai-in-financial-services); [Parliament – responses report](https://publications.parliament.uk/pa/cm5901/cmselect/cmtreasy/1791/report.html); [BoE roundtable Oct 2025](https://www.bankofengland.co.uk/-/media/boe/files/prudential-regulation/publication/2025/november/ai-roundtable-oct-2025.pdf)

**EU AI Act**
- **AI Omnibus adoption:** political agreement 7 May 2026; Parliament approved 16 Jun 2026; Council sign-off 29 Jun 2026. Published as **Regulation (EU) 2026/1744** in the OJ on 24 Jul 2026 and in force 27 Jul 2026 — [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-high-risk-deadline-omnibus-20260/); [White & Case](https://www.whitecase.com/insight-alert/eu-ai-omnibus-enters-force-amending-ai-act); [ActuIA](https://www.actuia.com/en/news/ai-act-obligations-in-force-and-delays-under-omnibus-2026-1744/)
- **New high-risk dates:** Annex III standalone high-risk (incl. creditworthiness/credit scoring, employment, essential services) moves from 2 Aug 2026 to **2 Dec 2027**. Annex I product-embedded high-risk moves to **2 Aug 2028** — [Jones Walker](https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html); [HLC](https://www.hlc.com/en/publications/eu-legislators-agree-to-delay-for-highrisk-ai-rules)
- **Transparency:** most Article 50 transparency duties still applied from 2 Aug 2026. Art. 50(2) watermarking has a grace period to 2 Dec 2026 for systems already on the market by 2 Aug 2026 — [Jones Walker](https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html); [Winston Taylor](https://www.winstontaylor.com/insights/ai-act-rules-on-high-risk-ai-delayed-as-ai-digital-omnibus-agreed)
- **GPAI not delayed:** GPAI obligations applied from 2 Aug 2025, and Commission/AI Office enforcement powers, including fines on GPAI providers, applied from 2 Aug 2026. Models placed on the market before 2 Aug 2025 have until 2 Aug 2027 — [McKenna Consultants](https://www.mckennaconsultants.com/the-eu-ai-act-after-the-ai-omnibus-the-timeline-that-now-applies/); [AlicELabs timeline](https://alicelabs.ai/en/insights/eu-ai-act-timeline-2026); [EC AI Act Service Desk FAQ](https://ai-act-service-desk.ec.europa.eu/en/faq)
- **Article 4 (AI literacy) softened:** providers and deployers must now "take measures to support" sufficient AI literacy rather than "ensure" it. There is no mandated certificate, and national market-surveillance authorities enforce it — [OneRange](https://onerange.ai/blog/eu-ai-act-ai-literacy-requirement); [Praxikon](https://www.praxikon.com/en/posts/digital-omnibus-ai-act-what-changes-what-now-2026)
- **Base regulation [TK – not re-verified]:** Regulation (EU) 2024/1689. Article 6(3) provides that an Annex III system is not high-risk where it performs "a narrow procedural task" or improves the result of a previously completed human activity and does not materially influence decision outcomes. Article 14(4)(b) requires high-risk oversight measures to make humans aware of "automation bias" — [EUR-Lex 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)

**Audit-profession context**
- **PCAOB:** there is no standalone AI rule. The amended **AS 1105** requires auditors to evaluate the reliability of information used in technology-assisted analysis (effective for fiscal years beginning on or after 15 Dec 2025). The PCAOB says GenAI does not change due professional care or professional skepticism. It is unclear whether AI tool limitations and training data must be documented — [Fieldguide](https://www.fieldguide.io/resource-articles/pcaob-ai-audit-standards); [JGA CPA](https://www.jgacpa.com/ai-validation-is-the-new-audit-evidence-risk); [CPA Journal, Aug 2026](https://www.cpajournal.com/2026/08/19/leveraging-artificial-intelligence-in-audit-planning/) (secondary)
- **UK FRC:** UK FRC guidance on AI in audit reportedly states that accountability for audit quality is unchanged when AI tools are used. The date, March 2026, is unverified — [finrep.ai](https://www.finrep.ai/blog/ai-in-financial-reporting-audit-risk-the-2026-compliance-map) (secondary)

### Inferences
- **EU classification:** the use case (extracting broker trade data for internal reconciliation) is not an Annex III category. Even if loosely connected to a high-risk process, it fits the Art. 6(3) "narrow procedural task" derogation. So it is **not high-risk**. The firm is a *deployer* of a GPAI-based system with Art. 4 literacy duties. Art. 50 transparency duties are mostly irrelevant, because there is no public-facing interaction or published synthetic content. It should obtain GPAI-provider documentation through procurement, since GPAI providers carry Art. 53 obligations.
- **US classification:** for a US bank, SR 26-2's GenAI carve-out does not mean "no governance". Examiners can still cite unsafe or unsound practices, and third-party risk management (OCC 2023-17 interagency TPRM guidance) still applies to LLM vendors. Pragmatic leading practice is to keep the AI extractor in the model and AI inventory and govern it under SR 26-2-style principles: inventory, tiering, independent validation, effective challenge, ongoing monitoring. GenAI-specific risks are then mapped to NIST AI 600-1 and the Treasury FS AI RMF control objectives.
- **Architectural shortcut:** because the reconciliation engine is deterministic and the LLM only populates inputs, the AI component can arguably be scoped as a *data-capture tool with compensating controls* rather than a "model" making estimates. Under the "LLM authors parsers" pattern, the run-time artefact is ordinary code under SDLC change control, which shrinks the model-risk surface. This framing should be agreed with model risk and internal audit up front.
- **Firm-level AI policy** should cover: approved models and providers list; use-case risk tiering; data-classification rules for what can be sent to which endpoint; human-accountability assignment (a named control owner); change management; incident and error escalation; evidence retention; and AI-literacy training (Art. 4, EU).

### Gaps
- The full SR 26-2 text could not be opened, so the exact wording on vendor-model validation and the "model" definition is unverified.
- A primary source for the reported upcoming US agency RFI on GenAI and agentic AI was not found.
- The PRA SS1/23 2026 amendment claim is unverified.
- No 2026 IAASB-specific guidance on AI-generated audit evidence was found. ISA 500 (Revised) status should be checked separately.

## 5. Data confidentiality: client data in third-party LLMs

### Takeaway
Broker confirmations and statements contain client-identifying and commercially sensitive data. Leading practice is:
- enterprise or API tiers contractually barred from training on customer data;
- zero-data-retention (ZDR) or minimal-retention agreements;
- region-pinned processing for data-residency requirements;
- private-cloud or VPC deployment through hyperscalers, or self-hosted open-weight models for the most sensitive flows.

All of this is governed under third-party/outsourcing risk management, with model-provider concentration risk now explicitly on UK regulators' radar.

### Cited Findings
- **Regulator attention:** the Bank of England has flagged concentration risk from reliance on a small number of third-party AI model providers as a risk it will examine — [BoE response to TSC](https://www.bankofengland.co.uk/-/media/boe/files/letter/2026/response-to-tsc-inquiry-report-on-ai-in-financial-services)
- **US agencies:** SR 26-2 addresses vendor and third-party products, and the Treasury FS AI RMF builds on third-party risk management guidance including OCC 2023-17 — [Federal Reserve SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm); [Ripple Treasury blog](https://treasury.ripple.com/posts/treasury-ai-risk-management-framework) (vendor blog)
- **NIST:** AI 600-1 lists "Data Privacy" and "Value Chain and Component Integration" among the 12 GenAI risks — [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf); [governancedocs.com](https://governancedocs.com/nist-ai-rmf-generative-ai-profile/)
- **Self-hosting enables determinism too:** self-hosted open-weight inference (e.g., vLLM/SGLang) can run batch-invariant kernels. This gives a combined confidentiality and repeatability benefit not available from shared hosted endpoints — [Spheron](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/)

### Inferences
- Controls to require: DPA/contract terms on no training, retention period (ZDR where offered), subprocessors and region; an encryption and key-management stance; logging of what was sent; data minimisation (redact client names and account numbers where not needed for matching, or tokenise and re-identify after extraction); a DPIA under GDPR/UK GDPR where personal data of natural-person clients is involved; and exit and portability planning tied to model-deprecation risk.
- ZDR can conflict with audit-trail needs, because the provider retains nothing. The firm must therefore retain its own complete record: inputs, prompts, outputs and hashes in its own WORM/immutable store.

### Gaps
- Current (Oct 2026) provider ZDR, retention and data-residency terms could not be fetched. They vary by provider and contract tier and must be confirmed during procurement.
- No regulator-issued guidance specific to sending client trade data to external LLM APIs was found.

## 6. Audit trail and lineage design patterns

### Takeaway
Make every reconciliation result traceable, by content hash, to the exact source document, extraction run, model snapshot and parameters, prompt or parser version, validation results, human review actions and reconciliation code version. Store all of it in an append-only (event-sourced, WORM-capable) log. Express lineage in an open standard (OpenLineage for pipeline run/job/dataset events, W3C PROV for provenance semantics) so that a "reproducibility package" can be exported for auditors.

### Cited Findings
- **Regulators expect documentation:** the PCAOB has said AI does not change auditor responsibility, and AS 1105 requires evaluating the reliability of information used in technology-assisted analysis. That implies the auditee must be able to show how AI-derived data was produced and controlled — [Fieldguide](https://www.fieldguide.io/resource-articles/pcaob-ai-audit-standards); [JGA CPA – What regulators expect to see when AI is used](https://www.jgacpa.com/what-regulators-expect-to-see-when-ai-is-used) (secondary)
- **Provider config changes:** `system_fingerprint` exists precisely because provider backend changes can alter outputs. Logging it per call is the minimum provenance for hosted models — [OpenAI Advanced usage](https://developers.openai.com/api/docs/guides/advanced-usage)
- **OpenLineage [TK – not re-verified]:** an open standard (LF AI & Data) defining RunEvent/Job/Dataset entities with extensible "facets" (e.g., schema, data quality assertions, source code version), emitted by pipeline tools to a lineage backend such as Marquez — [OpenLineage spec](https://openlineage.io/docs/spec/object-model)
- **W3C PROV [older, 2013; TK]:** a W3C Recommendation modelling provenance as Entities, Activities and Agents with relations such as wasGeneratedBy, used, wasAttributedTo and wasDerivedFrom. It is well suited to representing "extraction activity used document X and model M, was performed by agent A, and generated record R" — [W3C PROV-Overview](https://www.w3.org/TR/prov-overview/); [PROV-O](https://www.w3.org/TR/prov-o/)
- **Immutable recordkeeping precedent [TK – not re-verified]:** the SEC's 2022 amendments to Rule 17a-4 allow broker-dealers to keep electronic records either in WORM format or under an "audit-trail alternative" that logs every modification or deletion with the original preserved. This is a useful benchmark for designing immutable logs — [SEC Final Rule 34-96034 (Oct 2022)](https://www.sec.gov/rules/final/2022/34-96034.pdf)

### Inferences
- **Minimum per-record lineage payload:**
  - `source_doc_sha256`, source receipt metadata (sender, channel, timestamp), OCR engine and version (if any)
  - `extractor_type` (LLM / parser / human)
  - model provider + snapshot ID + `system_fingerprint` + decoding params + seed, or a container digest and weight hash for self-hosted models
  - prompt template ID + hash, schema version, parser/config commit SHA
  - raw model response (stored verbatim) + parsed output + source-span evidence
  - validation results (each check, pass/fail), confidence or agreement score
  - reviewer ID, decision, timestamp and changed fields (before/after)
  - reconciliation engine commit SHA, input dataset hashes and output hash
- **Event sourcing:** model each step as an immutable event (DocumentReceived, ExtractionProduced, ValidationFailed, ReviewOverride, ReconRun, BreakResolved). Current state is a projection. Corrections are new events, never in-place updates. Hash-chain events (each event includes the previous event's hash) or anchor periodic Merkle roots for tamper evidence. Store events in object storage with retention lock or other WORM capability.
- **Reproducibility package per period:** frozen inputs, frozen extraction outputs, config/prompt/parser versions, golden-set results for the deployed version, control-test evidence, and a script that re-runs the deterministic reconciliation from frozen extractions to a byte-identical output hash. This lets an auditor re-perform the reconciliation without needing the LLM.
- **Versioned configuration:** prompts, schemas, broker mappings and thresholds live in Git with PR review, which supports segregation of duties. Deploys are tagged and each run records the tag.

### Gaps
- Could not verify current OpenLineage spec version or facet names. No AI-specific lineage standard endorsed by financial regulators was found.
- No regulator guidance prescribing specific log fields for AI extraction was found. The payload above is a design inference.

## 7. Human review best practice and automation-bias mitigation

### Takeaway
Human-in-the-loop review is weakened by automation bias. Trained experts also over-rely on AI output, and explanations or transparency features alone do little to reduce it. Effective designs:
- force active verification, e.g. re-keying or confirming critical fields against a highlighted source span instead of a one-click "approve";
- keep the cost of correcting errors low;
- seed known errors (canaries) to measure reviewer vigilance;
- track override and acceptance rates per reviewer.

The EU AI Act explicitly names automation bias as something human oversight must address (for high-risk systems), which makes it a recognised benchmark even for non-high-risk uses.

### Cited Findings
- **Explanations don't reliably help:** a 2025 *AI & Society* systematic review of 35 studies found that explainability and transparency features often fail to reduce automation bias or improve decision accuracy. It found designs that prompt users to actively verify outputs more effective — [AI & Society 2025 review (via longtermwiki)](https://www.longtermwiki.com/resources/a96cbf6f98644f2f) (secondary listing)
- **Trust drives over-reliance [older, 2024]:** a ~9,000-participant, nine-country experiment (Horowitz & Kahn) found trust and confidence in AI are major drivers of automation bias — [longtermwiki listing](https://www.longtermwiki.com/resources/8b736db3fc699115) (secondary)
- **Training alone may not suffice:** a 2025 RCT is testing whether physicians who completed AI-literacy training still over-rely on LLM output. Results were not visible in the retrieved summary — [AAAI/AIES paper](https://ojs.aaai.org/index.php/AIES/article/download/43225/50785/47331)
- **Confirmation bias in oversight:** 2025 work identifies confirmation bias as a challenge for scalable oversight protocols in which humans check AI outputs — [arXiv 2507.19486](https://arxiv.org/pdf/2507.19486)
- **EU AI Act Art. 14:** the AI Act explicitly references automation bias in its human-oversight requirements, and its legal implications are analysed in 2025 scholarship — [arXiv 2502.10036](https://arxiv.org/abs/2502.10036v1); primary text: [EUR-Lex 2024/1689, Art. 14(4)(b)](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) [TK]
- **Effort lowers correction (unverified):** a secondary source cites a 2,784-person experiment in which people corrected AI mistakes less often when correcting took extra effort. It could not be traced to the primary paper — [Taskade wiki](https://www.taskade.com/wiki/productivity/automation-bias) (low weight)
- **Auditor skepticism:** the PCAOB states that use of GenAI does not alter due professional care or professional skepticism — [Fieldguide](https://www.fieldguide.io/resource-articles/pcaob-ai-audit-standards) (secondary)

### Inferences
- **Reviewer UI patterns:**
  - Side-by-side source document and extracted fields, with each field linked to its highlighted bounding box or text span (click a field to scroll the PDF to it).
  - Visually flag fields that failed validation, disagreed between extractors or fall in low-confidence bands.
  - Show the reconciliation counterpart (internal booking) only *after* the reviewer has confirmed the extracted values. Showing it earlier lets the reviewer anchor on the internal record and "confirm" a matching error.
- **Active-verification mechanics:**
  - Blind re-keying of critical fields (ISIN, quantity, amount) on a sample basis.
  - Require explicit per-field confirmation for critical fields rather than whole-document approval.
  - Require a reason code for every override.
  - Disable bulk-approve for high-risk strata.
- **Vigilance measurement:**
  - Inject seeded synthetic errors at a low rate into review queues and measure catch rate per reviewer.
  - Monitor time-on-task and the approve rate. Near-100% approval with very short dwell times signals rubber-stamping.
  - Rotate reviewers, and use four-eyes review for overrides above materiality thresholds.
- **Accountability:** a named control owner signs off periodic QA results. Review evidence (who, what, when, before and after) is logged immutably as part of the audit trail (section 6).
- **Training:** cover known LLM failure modes (fabricated plausible values, column-shift errors in tables, sign or direction flips, date-format confusion, dropped last rows on page breaks). This also satisfies the EU Art. 4 AI-literacy expectation.

### Gaps
- No study was found that directly measures reviewer acceptance of LLM *extraction* errors in financial back-office workflows. The evidence is from clinical, decision-support and general HCI settings.
- Primary sources for the AI & Society review and the Horowitz & Kahn study could not be opened. Citations are via secondary listings.

## 8. Switzerland (auditor based in Switzerland): data protection, AI regulation, EU AI Act reach, audit secrecy, FINMA reference point

### Takeaway
Switzerland has **no horizontal AI law** as of Oct 2026.
- **Federal Council decision (12 Feb 2025):** keep a sector-specific approach and implement the Council of Europe AI Convention (signed 27 Mar 2025) through targeted amendments. A consultation draft was due by end-2026, though one source reports early 2027.
- **Data protection:** the technology-neutral revised FADP (in force 1 Sept 2023) therefore governs any personal data in broker documents. The FDPIC states it applies directly to AI. Cross-border disclosure to cloud LLM providers needs a Federal Council adequacy listing (e.g., EU/EEA; US only for DPF-certified recipients since 15 Sept 2024) or Art. 16(2) safeguards (SCCs + transfer assessment).
- **Professional secrecy:** for a Swiss auditor, client confidentiality is the sharper constraint. Auditors under the Code of Obligations are expressly covered by **Art. 321 StGB**, and whether a cloud or LLM provider is a permissible "auxiliary person" is legally disputed. That pushes towards encryption with customer-held keys, Swiss/EU-hosted or self-hosted models, data minimisation and client consent.
- **EU AI Act:** reaches Swiss firms where they place systems on the EU market or where an AI system's output is used in the EU.
- **FINMA Guidance 08/2024 (Dec 2024):** the best Swiss reference point for AI governance expectations. It is not binding on an audit firm as such, but it applies to supervised audited entities and is relevant to regulatory audit work.

### Cited Findings
**Swiss AI regulation approach**
- **No general AI law:** on 12 Feb 2025 the Federal Council decided against a general cross-sector AI law and to maintain the sector-specific framework. Cross-sector rules are limited to fundamental-rights areas, particularly data protection, supplemented by non-binding measures such as self-declaration or industry solutions — [White & Case AI Watch – Switzerland](https://www.whitecase.com/insight-our-thinking/ai-watch-global-regulatory-tracker-switzerland); [Legal500](https://www.legal500.com/intelligence/european-union/technology/switzerland-sets-its-course-on-ai-legislation-federal-council-outlines-a-lean-regulatory-approach); [Lexology](https://www.lexology.com/library/detail.aspx?g=2d53412b-285e-468e-900b-8aec96141f55)
- **CoE AI Convention:** Switzerland signed the Council of Europe AI Convention on 27 Mar 2025 and intends to ratify, subject to parliamentary approval and possibly an optional referendum — [White & Case](https://www.whitecase.com/insight-our-thinking/ai-watch-global-regulatory-tracker-switzerland); [SIDD Insights](https://www.sidd.swiss/en/insights/ai-regulation-switzerland/)
- **Consultation draft timing:** the FDJP, with DETEC and the FDFA, was mandated to prepare a consultation draft by end-2026 implementing the Convention (transparency, data protection, non-discrimination, oversight), plus a plan for non-legislative measures. One company blog says the government confirmed on 23 Sept 2026 that the draft will come in early 2027. Another source expects the Federal Council dispatch in 2027 and entry into force in 2028 at the earliest — [Chambers AI 2026 – Switzerland](https://practiceguides.chambers.com/practice-guides/artificial-intelligence-2026/switzerland/trends-and-developments); [agenticsis.ch](https://agenticsis.ch/blog/switzerland-ai-convention-ratification-swiss-sme-2027/) (blog; also misdates the signing, so low reliability); [gawel.ch](https://gawel.ch/insights/61-switzerland-ai-regulation-vs-eu-ai-act/). **Status as of Oct 2026 is unconfirmed against admin.ch.**

**Data protection (revised FADP)**
- **FDPIC: FADP applies directly to AI.** The FDPIC says the FADP is technology-neutral and therefore directly applicable to AI-supported processing. Manufacturers, providers and users must give data subjects the greatest possible control over their data. For AI that interacts with users, such as language models, users must be told they are dealing with a machine and whether their data is used to improve the system — [FDPIC – AI and data protection](https://www.edoeb.admin.ch/en/ai-and-data-protection); [Legal500 on FDPIC position](https://www.legal500.com/intelligence/united-kingdom/technology/fdpic-confirms-direct-applicability-of-data-protection-law-to-ai-and-outlines-regulatory-approach)
- **Cross-border disclosure:** under the revised FADP, the **Federal Council** (not the FDPIC) decides which countries are adequate (list in Annex 1 of the Data Protection Ordinance). Absent adequacy, Art. 16(2) safeguards are needed, e.g. FDPIC-recognised SCCs, typically with a transfer impact assessment — [datenschutz-notizen](https://www.datenschutz-notizen.de/the-new-look-of-cross-border-transfers-in-switzerland-4040500/); [SIDD – Swiss DP law internationally](https://www.sidd.swiss/en/insights/swiss-data-protection-law-international-context/); primary: [FADP on Fedlex](https://www.fedlex.admin.ch/eli/cc/2022/491/en) [TK – article numbers not re-verified]
- **US adequacy:** on 14 Aug 2024 the Federal Council recognised US adequacy **only for companies certified under the Swiss-US DPF**, effective 15 Sept 2024. Non-certified US recipients still need SCCs + TIA. The DPF rests on a US Executive Order, a noted political durability risk — [Lenz & Staehelin](https://www.lenzstaehelin.com/news-and-insights/browse-thought-leadership-insights/insights-detail/swiss-us-data-privacy-framework-swiss-adequacy-decision-for-us-certified-data-recipients/); [Schellenberg Wittmer](https://www.swlegal.com/en/insights/newsletter-detail/swiss-us-data-privacy-framework-adequacy-decision-/); [Global Law Experts](https://globallawexperts.com/swissus-data-privacy-framework-compliance-2026/)
- **No LLM-specific FDPIC transfer guidance found:** the searches returned no FDPIC guidance specifically on transfers to cloud LLM providers — [FDPIC – AI and data protection](https://www.edoeb.admin.ch/en/ai-and-data-protection) (general only)
- **Other relevant FADP duties [TK – not re-verified]:**
  - Art. 9 governs processing by processors, so the LLM provider is typically a processor needing a contract and prior authorisation for sub-processors.
  - Art. 7 requires privacy by design and default.
  - Art. 22 requires a DPIA for high-risk processing.
  - Criminal fines up to CHF 250,000 apply to responsible *individuals* for intentional breaches of certain duties (e.g., cross-border disclosure rules, processor requirements). A new Art. 62 penalises breach of professional confidentiality of secret personal data.
  - Source: [FADP (SR 235.1) on Fedlex](https://www.fedlex.admin.ch/eli/cc/2022/491/en)

**Audit secrecy / professional secrecy**
- **Art. 321 StGB covers auditors:** it lists the covered professions, including "Revisoren" bound to secrecy under the Code of Obligations, together with their auxiliary persons ("Hilfspersonen"). A fiduciary is covered only when acting as statutory auditor (Revisionsstelle), not when doing bookkeeping or tax work — [k-i-soft checklist (2026)](https://www.k-i-soft.ch/blog/berufsgeheimnis-und-cloud/); primary: [StGB Art. 321 on Fedlex](https://www.fedlex.admin.ch/eli/cc/54/757_781_799/de) [TK]
- **Is a cloud provider an auxiliary person? Disputed.**
  - **Strict view:** Wohlers' opinion for the Zurich cantonal data protection commissioner says disclosure to an auxiliary may already breach the secret, and without consent is allowed only if indispensable and foreseeable. Consent must be specific, and whether outsourcing is domestic or foreign is irrelevant — [datenrecht.ch on Wohlers](https://datenrecht.ch/en/wohlers-auslagerung-einer-datenbearbeitung-und-das-berufsgeheimnis-art-321-stgb/)
  - **Permissive view:** Rosenthal and the Swiss Bar Association consider effective protection of the data decisive. If data is encrypted and the provider holds no key, there is no "disclosure" — [Rosenthal – Cloud Lawful Access (PDF)](https://www.rosenthal.ch/downloads/Rosenthal-CloudLawfulAccess.pdf); [SAV/FSA Anwaltsrevue 1/2019](https://www.sav-fsa.ch/documents/672183/2086852/09arv0119.pdf/2b3ae2eb-87e5-dcbe-37d7-f59804ed727e?t=1645455492157) [older]
- **US CLOUD Act exposure:** for secrecy-protected data, providers subject to the US CLOUD Act create legal uncertainty that contracts cannot fully resolve — [gawel.ch – cloud contracts](https://gawel.ch/insights/17-cloud-contracts-jurisdiction/); [domenig.law](https://www.domenig.law/blog/cloud-des-berufsgeheimnis-kryptonit) (practitioner commentary)
- **Art. 730b(2) CO [TK – not re-verified; search found no commentary]:** the statutory auditor must keep its findings secret unless legally required to disclose, and must protect the company's business secrets in its reporting — [Code of Obligations on Fedlex](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de)
- **Swiss audit-profession resources on AI:**
  - EXPERTsuisse publishes a White Paper on AI in audit, tax and fiduciary work and a guide on ChatGPT in auditing (member login required; contents not reviewed), and ran 2025 training on "auditing AI" and Swiss/EU AI regulation — [EXPERTsuisse – KI & Digitalisierung](https://expertsuisse.ch/de/publikationen-fachsupport/fachthemen/ki-und-digitalisierung); [EXPERTsuisse course Oct 2025](https://expertsuisse.ch/de/weiterbildungen/2025/10/kuenstliche-intelligenz-einsatz-in-der-wirtschaftspruefung/10515)
  - The Swiss Federal Audit Office (EFK/CDF) has published an audit guide for AI systems ("Leitfaden Audit KI-Systeme") — [EFK Leitfaden Audit KI (PDF)](https://www.efk.admin.ch/wp-content/uploads/publikationen/vorgehen-und-methoden/leitfaden-audit-ki-systems-de.pdf) (contents not reviewed)

**FINMA reference point**
- **FINMA Guidance 08/2024 basics:** "Governance and risk management when using artificial intelligence", issued 18 Dec 2024. It is a supervisory communication, not a binding circular. It applies existing technology-neutral governance and risk rules to AI, proportionate to institution size and application materiality — [Lenz & Staehelin](https://www.lenzstaehelin.com/news-and-insights/browse-thought-leadership-insights/insights-detail/finma-issues-guidance-on-ai-use-in-financial-institutions/); [PwC Switzerland](https://www.pwc.ch/en/insights/fs/ai-in-the-financial-industry.html); [Lexology](https://www.lexology.com/library/detail.aspx?g=d661565d-7d94-4468-bc0d-0b98fb3d0791)
- **Risks and expectations:** FINMA highlights model risks (lack of robustness, correctness, explainability, bias), data quality, IT/cyber risk, third-party dependency, legal and reputational risk, and allocation of responsibility. Its expectations include an AI inventory with risk classification, clear responsibilities, testing and ongoing monitoring, documentation, explainability, and independent review — [Lenz & Staehelin](https://www.lenzstaehelin.com/news-and-insights/browse-thought-leadership-insights/insights-detail/finma-issues-guidance-on-ai-use-in-financial-institutions/); [Charltons Quantum](https://charltonsquantum.com/swiss-finma-issues-guidance-on-governance-and-risk-management-in-ai-applications/); [Modulos summary](https://docs.modulos.ai/frameworks/finma-ai-governance) (secondary; exact wording unverified)
- **Engage FINMA early on critical uses:** FINMA recommends authorised institutions contact it in good time when planning to use AI in critical processes or to calculate regulatory parameters — [FINMA news – AI survey Apr 2025](https://www.finma.ch/en/news/2025/04/20250424-mm-umfrage-ki/)
- **2025 survey [TK – figures not re-verified]:** around half of about 400 surveyed institutions used AI, with generative AI the most common type. FINMA observed governance still being built at many firms — [FINMA news 24 Apr 2025](https://www.finma.ch/en/news/2025/04/20250424-mm-umfrage-ki/)

**EU AI Act reach into Switzerland**
- **Art. 2(1)(a):** covers providers placing AI systems on the EU market irrespective of establishment.
- **Art. 2(1)(c):** covers third-country providers and **deployers** where the system's **output is used in the Union**. Recital 11 frames this as output "intended to be used" in the EU, and commentators diverge on how broad the trigger is — [EC AI Act Service Desk – Art. 2](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-2); [William Fry](https://www.williamfry.com/knowledge/a-practical-guide-to-the-extraterritorial-reach-of-the-ai-act/); [White & Case (2024) – extraterritorial scope pt 2](https://whitecase.com/sites/default/files/2024-05/the-eu-ai-acts-extra-territorial-scope-part-2.pdf)

### Inferences
- **For a Swiss auditor's AI-assisted reconciliation**, the ranked deployment options from a confidentiality/secrecy standpoint are:
  1. self-hosted open-weight model on own or Swiss infrastructure (also best for repeatability, see section 1);
  2. Swiss- or EU-region private deployment with customer-managed keys, contractual no-training/no-retention, and named sub-processors;
  3. a US-headquartered provider's API, even if DPF-certified, which carries residual Art. 321 StGB and CLOUD Act uncertainty and generally needs client consent in the engagement letter plus pseudonymisation of client identifiers before sending.
- **Engagement letters and firm AI policy** should disclose the use of AI tools and third-party processors, obtain client consent where secrecy-protected data leaves the firm's control, and document the legal assessment under Art. 321 StGB, Art. 730b CO and the FADP.
- **EU AI Act exposure for a Swiss audit firm:** reconciliation outputs used in audits of EU entities could make the firm a "deployer" in scope via Art. 2(1)(c). But the use case is not high-risk (section 4), so practical obligations reduce mainly to AI literacy (Art. 4 as softened) and good governance. The firm still relies on GPAI providers' EU compliance.
- **FINMA 08/2024 as a template:** even where it is not directly binding on the audit firm, its expectations map well onto the controls in sections 1–7 (inventory, risk classification, testing and monitoring, documentation, responsibility). When auditing FINMA-supervised clients, auditors can expect FINMA to look for these elements.
- **If the audited entity is a Swiss bank or securities firm**, client-identifying data may also fall under Art. 47 Banking Act / FinIA secrecy and FINMA outsourcing rules (FINMA Circular 2018/3). These were not re-verified here.

### Gaps
- Could not confirm against admin.ch whether the Federal Council released the AI consultation draft in 2026 or postponed it to 2027.
- No FDPIC guidance specific to LLM/cloud-AI cross-border transfers was found. The FDPIC's general AI statement is the only primary item.
- No commentary on Art. 730b CO in the context of AI or cloud tools was found. The contents of the EXPERTsuisse AI white paper and the EFK AI audit guide could not be reviewed.
- Did not verify whether FINMA issued further AI guidance in 2025–2026 beyond 08/2024 and the April 2025 survey release.
- Swiss Federal Audit Oversight Authority (FAOA/RAB) positions on AI in audit were not found.
