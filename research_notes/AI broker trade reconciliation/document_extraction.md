# AI-Based Extraction of Trade-Level Tabular Data from Heterogeneous Broker Documents (PDF native/scanned, Excel): State of the Art as of Late 2026

> Method note for the report writer: research done 16 Oct 2026 via web search. Direct page fetches of arxiv.org, llamaindex.ai and thinkingmachines.ai failed (DNS errors in the research sandbox). So many arXiv findings below come from search-engine abstracts and snippets, not full-text reads. The specific numbers should be read as "as reported in the abstract or secondary summary". Vendor-run benchmarks are labelled as such. Model names (Claude Opus 4.6, GPT-5.4, Gemini 3.1 Pro, Qwen3-VL, PaddleOCR-VL, etc.) are representative examples only.

## 1. Architectural approaches and their fit for long, multi-page trade tables

### Takeaway
No single architecture dominates. The 2026 leading practice is a hybrid built in layers:
- a deterministic text layer where one exists (native PDF, Excel);
- a specialised layout or table-structure model, or a VLM, for structure and scans;
- an LLM used in a bounded way: for schema mapping, or to *generate* per-format parsing logic that then runs deterministically;
- verification code on top.

Direct "whole document into a frontier LLM" extraction is strong on structure but fragile on long tables. It tends to drop rows and is costly and non-repeatable at scale.

### Cited Findings
- **Classical OCR / rule-based PDF tools (pdfplumber, Camelot, Tabula, PyMuPDF).** A comparative study (arXiv 2410.09871, 2024) found that the accuracy of rule-based tools varies by document category. Transformer-based Table Transformer was more consistent across categories. — [A Comparative Study of PDF Parsing Tools Across Diverse Document Categories](https://arxiv.org/pdf/2410.09871)
- Traditional OCR outputs cell contents as a linear text stream, so rows and columns must be rebuilt heuristically. — [Edge of Context: Definitive Guide to OCR in 2026](https://slavadubrov.github.io/blog/2026/03/04/ocr-guide/)
- **Layout-aware / table-structure models (TATR, TableFormer/Docling, POTATR).** A secondary review cites the TableFormer model card at about 93.6 TEDS, against 73.0 for Camelot and 88.3 for EDD. This is a secondhand figure. — [Thunderbit Docling review](https://thunderbit.com/blog/docling-review)
- A 2025 benchmark on heterogeneous scientific PDFs (arXiv 2511.16134) reports Docling as the strongest rule-free option, well ahead of PDFPlumber. Exact metric columns were not visible in the snippet. — [Benchmarking Table Extraction from Heterogeneous Scientific PDF Documents](https://arxiv.org/pdf/2511.16134)
  - Conflicting evidence: the PDFBench write-up reports pdfplumber with the highest table TEDS (93.4%) of the parsers it tested. — [LiveInTheFuture PDF-to-Markdown benchmark](https://liveinthefuture.org/stories/pdf-to-markdown-conversion-token-formatting-benchmark.html)
- There is an open Docling GitHub issue (#3698) about merged rows and columns being mishandled. Simple colspan/rowspan cases worked in a hands-on test. — [Thunderbit Docling review](https://thunderbit.com/blog/docling-review)
- POTATR (2026) is a 29M-parameter image-to-graph table model. It reportedly outperforms all tested models, frontier MLLMs included, on PubTables-v2 Single Pages (GriTS_Con 0.964), and runs about 130x faster at about 300x lower cost. — [POTATR summary (chatpaper)](https://chatpaper.com/paper/297232); [POTATR arXiv 2606.09788](https://arxiv.org/pdf/2606.09788)
- **Multimodal LLMs vs. TATR+OCR.** An ACL XLLM 2025 workshop paper (Fraunhofer AICOS / NOVA IMS) compared TATR+OCR with GPT-4o, Phi-3 Vision and Granite Vision 3.2 on PubTables-1M using GriTS.
  - CV models keep "a slight edge" on structural layout, while MLLMs are "far better" on cell text content. — [ACL Anthology 2025.xllm-1.2](https://aclanthology.org/2025.xllm-1.2)
  - A search summary of the same paper reports that Granite missed about 7.9% of table rows and that GPT-4o had the best overall accuracy. — [ACL Anthology PDF](https://aclanthology.org/2025.xllm-1.2.pdf)
- **Frontier MLLMs on multi-page tables.** The PubTables-v2 paper (Kensho, Dec 2025 onward) reports that frontier models clearly beat small specialised models on full-document multi-page extraction (gap of about 0.354 GriTS_Con). The gap shrinks or reverses on cropped-table tasks after targeted training. — [awesomepapers summary of arXiv 2512.10888](https://awesomepapers.io/similarity-search/papers/2512.10888); [Kensho announcement](https://kensho.com/news/introducing-pubtables-v2-kenshos-new-dataset-empowering-next-gen-ai-for-table-extraction)
  - The POTATR paper's Table 5 (PubTables-v2 full documents with multi-page tables) reports Claude Opus 4.6 at GriTS_Top 0.9116 / GriTS_Con 0.9079 and GPT-5.4 at 0.8865 / 0.8847. — [arXiv 2606.09788](https://arxiv.org/pdf/2606.09788)
  - On page-level results, Gemini 3.1 Pro leads at GriTS 0.942 (search summary). — [PubTables-v2 v3](https://arxiv.org/html/2512.10888v3)
- **The hybrid "compile once, run deterministically" approach.** "Compiled AI" (arXiv 2604.05150, 2026) compiles workflow orchestration deterministically. The LLM is called only as a bounded tool, with prompt, schema and triggers fixed at compile time. Results on DocILE:
  - pure regex ran about 4,915x faster than a direct LLM call but reached only 20.3% key-field accuracy;
  - the hybrid matched the direct LLM on key fields (80.0%) and had the best line-item accuracy (80.4%), with about 2.3x lower latency. — [Compiled AI (arXiv 2604.05150)](https://arxiv.org/html/2604.05150v1)
- Microsoft ISE recommends separating deterministic extraction from LLM inference after single-prompt designs gave inconsistent outputs. Their fix: prefer the source value whenever the LLM disagrees with a deterministically extracted field. — [Microsoft ISE blog](https://devblogs.microsoft.com/ise/separating-deterministic-extraction-from-ai-inference/)
- LlamaIndex (a vendor) itself says that fixed-format, high-volume documents are often better and cheaper served by traditional parsing or structured OCR. LLM parsing suits variable layouts. — [LlamaIndex glossary: prompt-based document parsing](https://www.llamaindex.ai/glossary/prompt-based-document-parsing)
- **Managed "IDP" / document AI services** typically pair LLM extraction with grounding and confidence. Microsoft's Content Understanding 1.0 went GA with GPT-5-series support and "improved grounding and confidence scoring", and a CU 2.0 preview was announced in October 2026. — [Microsoft Foundry blog, Oct 2026](https://devblogs.microsoft.com/foundry/more-than-a-schema-content-understanding-prebuilt-analyzers/)
- **Specialised small open models are closing the gap.** On OmniDocBench, vendor-reported 2026 results include:
  - PaddleOCR-VL 1.6 at 0.931 Table TEDS, and Sarvam Vision 2.1 at 0.890 Table TEDS. — [Sarvam Vision 2.1 blog](https://www.sarvam.ai/blogs/sarvam-vision-2-1)
  - In an independent check, Mistral OCR 3 scored 70.9% Table TEDS against 93.5% for PaddleOCR-VL. — [CodeSOTA Mistral OCR 3 benchmark](https://codesota.com/ocr/mistral-ocr-3-benchmark)

### Inferences
- For broker statements, the likely best fit is per-broker-format parsing. Statements are semi-fixed layouts that repeat per broker, at high volume. One approach: an LLM or engineer, assisted by an LLM, writes a template or parser per broker/format once; a human reviews it; then it runs deterministically, with an LLM/VLM fallback for unseen formats and scans. This matches the "Compiled AI" and Microsoft ISE patterns, and the vendor's own advice on fixed formats.
- Specialised table-structure models (TATR/TableFormer/POTATR-class) are far cheaper per page than frontier VLMs. They are competitive or better on single-page structure, while frontier MLLMs are better at stitching tables across pages. A practical design is a page-level structure model plus deterministic cross-page merging (repeated-header detection), with the VLM reserved for hard pages.
- Whole-document LLM extraction is the weakest option for statements with thousands of rows (see section 2 on dropped rows and output limits).

### Gaps
- I found no published benchmark specific to derivatives broker statements or confirmations (multi-page trade blotters). All the evidence is from general or financial-report tables, invoices or scientific tables.
- I found no peer-reviewed evaluation of "LLM generates a per-template parser" for financial statements specifically. Compiled AI is the closest, and it targets invoices (DocILE).

## 2. Benchmarks, accuracy evidence and known failure modes

### Takeaway
Table-structure benchmarks on clean pages are near saturation (about 0.93–0.96 TEDS/GriTS for the best models). Real-world financial and long-document benchmarks show markedly lower scores. Two failure modes stand out: on long documents, **dropped or truncated records** rather than misreads; and on numbers, **plausible-looking hallucinated values**. Independent-leaning evidence on complex derivatives text puts single-prompt LLM extraction at about 80–90%. Vendor claims of 95–99% come with undisclosed methodology.

### Cited Findings
- **OmniDocBench (CVPR 2025, Shanghai AI Lab).** It covers nine document sources and scores tables with TEDS. v1.5 expanded it to 1,355 pages. — [OmniDocBench CVPR 2025 paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.pdf); [arXiv 2412.07626](https://arxiv.org/html/2412.07626v2)
  - One practitioner critique: TEDS conflates formatting with structure, so identical table contents can score differently depending on HTML header wrappers. — [Pulse: table extraction benchmarks](https://www.runpulse.com/blog/table-extraction-benchmarks)
- **Leaderboard numbers (vendor-reported).** GLM-OCR 94.62 and PaddleOCR-VL-1.5 94.5 overall on OmniDocBench v1.5. Versions differ, so the numbers are not directly comparable. — [regolo.ai](https://regolo.ai/?p=2301); [CodeSOTA OmniDocBench](https://www.codesota.com/benchmark/omnidocbench)
- **PubTables-v2 (Kensho)** is the first large-scale benchmark for multi-page table structure recognition. See section 1 for the frontier-model GriTS of about 0.89–0.94. — [PubTables-v2 arXiv 2512.10888v1](https://arxiv.org/html/2512.10888v1)
- **FinixDoc / FinixDocBench (arXiv 2608.22842, Aug 2026).** It argues that existing benchmarks are saturated in a "Benchmark-Converged" zone (digital-native, normal-size pages). Real financial documents (scanned, phone-captured, ultra-large pages) are underexplored.
  - Its 4B model (on Qwen3-VL-4B) scores 81.43 overall on FinixDocBench, 5.13 points ahead of the next-best open model.
  - The training uses "homoglyph-aware" contrastive learning, which points to character-confusion errors as a key financial-parsing problem. — [FinixDoc arXiv](https://arxiv.org/pdf/2608.22842); [besthub summary](https://www.besthub.dev/articles/finixdoc-tackles-hard-financial-document-parsing-with-a-4b-model-and-open-source-benchmark-b7b86d892275)
- **ParseBench (LlamaIndex, 2026; vendor-run but open).** About 2,000 human-verified pages from about 1,211 enterprise documents (insurance, finance, government), with a 503-page table subset. Tables are scored with GTRM (GriTS + TableRecordMatch). The best system (the vendor's own LlamaParse Agentic) scored 84.9% overall. — [LlamaIndex ParseBench blog](https://www.llamaindex.ai/blog/parsebench); [hyper.ai arXiv 2604.08538](https://hyper.ai/papers/2604.08538)
- **RD-TableBench (Reducto, vendor-run).** 1,000 complex table images. Reported scores: Reducto 90.2%, Azure 82.7%, AWS Textract 80.9%, Google Document AI 64.6%. Nutrient notes that Reducto designed and runs the benchmark itself. — [Reducto blog](https://reducto.ai/blog/evaluating-llamaparse-for-pdf-parsing); [Nutrient comparison](https://www.nutrient.io/blog/best-document-parser-llamaparse-unstructured-reducto/)
- **Long documents and dropped rows (ExtractBench).** LlamaIndex's ExtractBench includes long single tables and cross-page continuations, up to 26,725 rows in repeated-record tests. Most systems do well on short documents and differ mainly on long ones. — [LlamaIndex ExtractBench](https://www.llamaindex.ai/blog/introducing-extractbench)
  - The ExtractBench paper (arXiv 2607.29677) finds that systems tend to **drop records rather than misread them**. It attributes this to context limits: systems without an iteration strategy stop early and truncate. — [arXiv 2607.29677](https://arxiv.org/pdf/2607.29677)
  - Note: a different paper, also called "ExtractBench" (arXiv 2602.12247), covers complex structured extraction. The two should not be conflated. — [arXiv 2602.12247](https://arxiv.org/pdf/2602.12247)
- **micro1 LongExtractionBench** (225 documents averaging 358 pages; vendor-run) reports direct frontier LLM calls as less robust than dedicated extraction systems. — [micro1 LongExtractionBench](https://www.micro1.ai/benchmark/long-extraction)
- **Hallucinated numbers.** The PP-OCRv6 paper (vendor's own benchmark, 2026) reports 93.2% hallucination-free accuracy for its specialised OCR model, against 72.6–85.0% for four general VLMs (Kimi-K2.6 85.0%, Qwen3-VL-235B 80.6%, MiniMax-M3 72.6%). It flags financial documents as a sensitive use case. — [PP-OCRv6 arXiv 2606.13108](https://arxiv.org/pdf/2606.13108)
- VLM errors look plausible but are wrong (e.g., a receipt total silently changed), so they slip past spell-checks. Recommended mitigations are sum-to-total checks and a traditional OCR pass on financial figures as a cross-check. — [Edge of Context OCR guide 2026](https://slavadubrov.github.io/blog/2026/03/04/ocr-guide/); [DEV: OCR vs VLM, hybrid approaches](https://dev.to/kesimo/ocr-vs-vlm-why-you-need-both-and-how-hybrid-approaches-win-5bo4)
- **FAITH (arXiv 2508.05201, ACM ICAIF '25)** measures intrinsic tabular hallucination in finance with masked numeric spans from S&P 500 annual reports. The authors argue that existing benchmarks rarely capture context-dependent numerical financial tables. — [FAITH arXiv](https://arxiv.org/abs/2508.05201v1)
- An ICAIF '25 workshop paper on LLM extraction from complex fiscal-document tables notes that traditional OCR fails because of inconsistent encoding of text and numbers. — [arXiv 2511.10659](https://arxiv.org/html/2511.10659v2)
- **Merged cells.** Markdown-only table output cannot represent merged cells. Reducto cites this as a LlamaParse failure (vendor critique of a competitor). — [Reducto blog](https://reducto.ai/blog/evaluating-llamaparse-for-pdf-parsing)
- **Derivatives-specific accuracy.** CompatibL's 2024 TradeEntry.ai hackathon (older, 2024) found:
  - a single well-crafted prompt peaks at about 90–95% on simple trade texts and falls to about 80% on complex inputs;
  - a notable failure was models "doing too much", i.e. applying transformations not valid for the trade.
  - Vendor claims (unaudited): Xceptor says single-prompt LLMs top out around 80% and claims "high 90s" with multi-step validation; V7 claims 99%. — [search summary of Xceptor Confirmations Agents PDF](https://www.xceptor.com/hubfs/Xceptor%20Confirmations%20Agents.pdf); [V7 brokerage agent](https://www.v7labs.com/agents/brokerage-operations-agent); [V7 swap confirmations](https://www.v7labs.com/automations/swap-confirmations)
- ISDA's study of GenAI extraction of CSA clauses found several LLMs above 90% accuracy when prompted with CSA-specific information (contract clauses, not trade tables). — [ISDA paper](https://www.isda.org/a/PQfgE/ISDA-Publishes-Paper-Exploring-Use-of-Generative-AI-to-Extract-and-Digitize-CSA-Clauses.pdf)
- **Mixed OCR-vs-VLM evidence in other domains.** In a medical-document study, traditional OCR scored mean S_CER 0.654 and VLMs with base prompting 0.660, i.e. comparable. A newspaper study found VLMs inconsistent on dense pages. — [DISCO arXiv 2603.23511](https://arxiv.org/pdf/2603.23511); [Institutional Newspapers Pipeline arXiv 2608.18972](https://arxiv.org/pdf/2608.18972)

### Inferences
- For audit reconciliation, an 80–95% field accuracy is not acceptable without verification layers. The main risk in long statements is **silent omission of rows**. Completeness controls (row counts, control totals) matter at least as much as field-accuracy controls.
- Failure modes to design for:
  - row truncation or drops at output/context limits;
  - cross-page table breaks (header repeated or lost);
  - merged and multi-row headers;
  - homoglyph and digit confusion on scans (O/0, l/1, 5/S);
  - hallucinated plausible numbers;
  - sign and number-format errors (parenthesised negatives, thousand/decimal separators across locales);
  - over-normalisation ("doing too much").
- Clean-page TEDS/GriTS scores overstate real-world accuracy on scanned or phone-captured statements (FinixDoc's argument).

### Gaps
- I found no published digit-level error rates (e.g., transposition rate per 1,000 numeric cells) for VLMs vs. OCR on scanned financial tables.
- The full ExtractBench (2607.29677) and PubTables-v2 result tables could not be read directly (fetch failures). Per-system row-recall figures are not captured here.
- I found no published evidence on handling locale number formats (1.234,56 vs 1,234.56), on date-format ambiguity (DD/MM vs MM/DD) in extraction benchmarks, or on how often these errors occur.

## 3. Grounding and provenance techniques

### Takeaway
Leading practice returns, for every extracted value, a pointer to its source: page plus bounding box or polygon (for PDFs/scans), or sheet!cell (for Excel). Where a text layer exists, it also checks *deterministically* that the value occurs verbatim in that region. Totals and counts are then cross-footed against the statement's own control figures. Managed services now expose per-field grounding natively. For self-built pipelines, the pattern is "LLM returns the literal value, then code locates it in the PDF text layer".

### Cited Findings
- **PyMuPDF/Artifex pattern.** If the PDF has a text layer, have the LLM return the literal value, then locate it with PyMuPDF `search_for`. Text positions in the PDF are the "source of record". Enumerate all occurrences and pick the one in the correct table region. This does not work on scanned PDFs, which need OCR or vision. — [Artifex: Grounding in document extraction](https://artifex.com/blog/grounding-in-document-extraction); [Medium/PyMuPDF](https://medium.com/@pymupdf/grounding-in-document-extraction-ada1bb367af5)
- **Hosted per-field citations.** Extend returns a page reference, polygon coordinates and citation text for each extracted field when `citationsEnabled` is true. It uses an additional citation-focused model, which adds moderate latency. — [Extend docs: citations](https://docs.extend.ai/product/extraction/citations)
- **Microsoft Content Understanding.** Grounding ties each value to a region of the source. The Studio lets reviewers inspect bounding boxes and confidence. Guidance is to review the source location when confidence is low. — [Microsoft Learn: analyzer improvement](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/document/analyzer-improvement); [Foundry blog](https://devblogs.microsoft.com/foundry/more-than-a-schema-content-understanding-prebuilt-analyzers/)
  - A blog names the parameter `estimateFieldSourceAndConfidence` for per-field source and confidence; this should be checked against the API reference. — [Medium hands-on guide](https://medium.com/@sergems18/mastering-azure-content-understanding-a-complete-hands-on-guide-04a3a5eeeb52)
- **Research on grounding for closed-box LLMs without OCR.** ViG-LLM (Amazon Science) builds localisation via multi-agent layout deconstruction and was tested on FATURA/CORD invoices. LLM-Optic numbers candidate boxes and has the model choose among them. — [ViG-LLM](https://assets.amazon.science/fd/6b/a4aca97f48cdbe7254710af202aa/scipub-approval152129-42061971-vigllm-enhancing-visual-grounding-capabilities-in-closedbox-llms-for-document-information-extraction-without-ocr-dependencies.pdf); [LLM-Optic arXiv 2405.17104](https://arxiv.org/pdf/2405.17104)
- **Parser-level visual references.** LingDT-VL-OCR (2026) does structure-aware document parsing with "fine-grained visual reference", which ties parsed output to image regions. — [arXiv 2603.11044](https://arxiv.org/pdf/2603.11044)
- **Arithmetic reconciliation.** Checking that line items sum to stated totals is the recommended guard against plausible-but-wrong VLM numbers. — [Edge of Context OCR guide](https://slavadubrov.github.io/blog/2026/03/04/ocr-guide/)
- **Prefer the source value on conflict.** The Microsoft ISE pattern takes the deterministically extracted source value when the LLM disagrees. — [Microsoft ISE blog](https://devblogs.microsoft.com/ise/separating-deterministic-extraction-from-ai-inference/)
- **Vendor positioning.** Trade-confirmation offerings market "citations and confidence scores" plus validation loops as their main differentiators. — [LlamaIndex trade confirmation OCR page](https://www.llamaindex.ai/services/trade-confirmation-ocr)

### Inferences
Recommended provenance record per extracted trade row: `source_file_hash`, `page`, `bbox` per cell (or `sheet`, `cell_ref` for Excel), `extraction_method` and version, `model_id` snapshot, `prompt/template hash`, and `verbatim_match: true/false`. With this, auditors can trace any reconciled figure back to the evidence (this aligns with the audit-evidence documentation expectations covered elsewhere in the report).

Control checks to automate:
- the number of rows extracted per page/section equals the statement's stated trade count, where one exists;
- the sum of quantities, notionals, commissions and cash amounts equals the statement totals;
- the opening position plus trades equals the closing position;
- uniqueness of trade IDs, and no duplicates across page boundaries;
- every numeric cell matches the text layer verbatim (native PDF);
- the dual-OCR value equals the VLM value (scans).

### Gaps
- I found no published measurement of how much verbatim text-layer verification reduces residual error in financial extraction.
- There is no standard schema for extraction provenance (e.g., an industry spec). Practice is vendor-specific.

## 4. Confidence, uncertainty and routing to human review

### Takeaway
Single-model confidence signals (token logprobs, verbalised confidence) are poorly calibrated for document extraction, at about 0.70 ROC AUC. Better practice fuses several signals:
- disagreement between two independent extractions (different methods or models);
- OCR and image-quality signals;
- deterministic validation failures.

Thresholds should be calibrated on in-domain labelled data, for example with conformal prediction, and low-confidence or failed-check items routed to human review.

### Cited Findings
- **"Beyond Logprobs" (arXiv 2606.24420, June 2026)**, on DocILE (55-field invoices):
  - mean logprob gives only 0.705 ROC AUC and degrades to an all-positive classifier at practical thresholds; verbalised confidence was similar;
  - five-sample self-consistency reaches only 0.744 AUC at about 5x cost;
  - the cause is that many errors come from things the model cannot observe (OCR noise).
  - Its proposed ExtractConf fuses cross-call disagreement, LLM-internal uncertainty, OCR, image-quality and spatial-layout signals. Its two calls have complementary failure modes: one hallucinates values for absent fields, the other misses visually non-salient ones. — [arXiv 2606.24420](https://arxiv.org/pdf/2606.24420)
  - A mirror reports 0.928 AUC for ExtractConf; this figure is unverified. — [chatpaper mirror](https://chatpaper.com/pt/paper/303132)
- **Calibration depends on document type.** In clinical extraction with GPT-4.1 and Llama 4 Maverick, models were underconfident on structured FDA labels and overconfident on free-text radiology reports. The authors propose conformal prediction to route between auto-accept and human review. — [arXiv 2603.00924](https://arxiv.org/html/2603.00924v1)
- **ConfBench** targets VLM confidence calibration on documents. It applies 20 controlled degradation pipelines to create 1,346 variants. — [Hugging Face paper 2608.01792](https://huggingface.co/papers/2608.01792)
- **Practitioner advice.** A Microsoft forum answer suggests using per-token probabilities as a confidence score to trigger human review. The research above indicates this is insufficient on its own. — [Microsoft Tech Community](https://techcommunity.microsoft.com/discussions/azurepartners/evaluating-the-quality-of-ai-document-data-extraction-with-small-and-large-langu/4157719/replies/4396626)
- **Managed service confidence.** Content Understanding gives 0–1 confidence per field, intended to decide straight-through processing vs. human validation. — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/document/analyzer-improvement); [ITMagination overview](https://www.itmagination.com/technologies/azure-ai-content-understanding)
- **Multi-step validation.** Vendor claims that it lifts derivatives-confirmation accuracy from about 80% (single prompt) to the "high 90s" are unaudited. — [Xceptor](https://www.xceptor.com/hubfs/Xceptor%20Confirmations%20Agents.pdf)
- A self-correcting trade-capture workflow (NVIDIA technical blog) is an example of LLM extraction plus validation-and-retry loops in trading operations. — [NVIDIA developer blog](https://developer.nvidia.com/blog/streamline-trade-capture-and-evaluation-with-self-correcting-ai-workflows)

### Inferences
- **Dual extraction.** The strongest practical design for audit runs two genuinely independent paths, e.g. (a) a deterministic text-layer or template parse and (b) a VLM/LLM extraction, or two different model families. Each field is then compared. Agreement plus passed control totals means auto-accept; any disagreement, missing grounding or control-total break means human review.
  - Independence matters: Beyond Logprobs shows that resampling the same model (self-consistency) adds little.
- Calibrate thresholds per broker/format on a labelled sample. Report the review rate and post-review residual error as control metrics.

### Gaps
- I found no published financial-statement-specific calibration study.
- I found no quantified evidence of how much dual-model agreement reduces undetected error rates in tabular extraction; the evidence is invoice/clinical-domain only.

## 5. Determinism and repeatability

### Takeaway
Temperature 0 does **not** give repeatable outputs on typical inference stacks. The main cause is batch-dependent numerics, not sampling. Batch-invariant kernels can make self-hosted inference bit-reproducible at a throughput cost, but hosted APIs generally do not guarantee it. Model snapshots also retire on 2–12-month horizons.

For audit, leading practice is therefore:
- **extract once and freeze**: store outputs, inputs and hashes as the evidence of record;
- pin model snapshots and log versions;
- keep a regression or canary set;
- where possible, use the LLM to **generate deterministic parsing code or templates**, which are reviewed, versioned and re-run, instead of calling the LLM on every run.

### Cited Findings
- **Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference" (Horace He, Sept 2025).** LLM APIs are non-deterministic even at temperature 0, and so is self-hosted vLLM/SGLang. The root cause is that kernels are not batch-invariant: batch composition changes reduction order in matmul, RMSNorm and attention. Batch-invariant computation makes inference fully deterministic. — [Thinking Machines blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference); [TechCrunch coverage](https://www.techcrunch.com/2025/09/10/thinking-machines-lab-wants-to-make-ai-models-more-consistent)
  - The reported experiment ran 1,000 identical Qwen3-235B prompts at temperature 0. They gave 80 unique completions by default and 1,000 identical ones with batch-invariant kernels (via secondary sources). — [Spheron: vLLM batch invariance](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/); [Medium: Defeating nondeterminism in practice](https://medium.com/@siddhantg314/defeating-nondeterminism-in-llm-inference-in-practice-38a7dd1e4112)
- **Self-hosted fixes.** vLLM added a `VLLM_BATCH_INVARIANT` flag. SGLang's deterministic mode cost an average 34.35% throughput (SGLang's benchmarks, cited secondhand). vLLM async scheduling can still break invariance with the flag on. — [Spheron](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/)
- Practitioner write-ups document "flapping" test cases and the cost of building pipelines on non-deterministic inference. One secondhand claim says a major provider still had no seed parameter in May 2026 (unverified). — [tianpan.co: Temperature zero is not determinism](https://tianpan.co/blog/2026-06-30-temperature-zero-is-not-determinism); [tianpan.co: Non-determinism tax](https://tianpan.co/blog/2026-04-10-non-determinism-tax-production-llm); [memx: 29 flapping cases](https://memx.app/blog/llm-determinism-is-a-lie-29-flapping-cases/)
- **Version pinning and retirement.** Providers distinguish dated snapshot IDs (fixed, with a published retirement date) from rolling aliases. Commentary cites retirement roughly 12 months after a successor ships. Notice periods reportedly range from about 60 days minimum (one provider) to about 12 months for flagship API models, and as little as one month for some third-party models on a cloud platform. Retired models fail requests. — [tianpan.co: Model EOL clock](https://tianpan.co/blog/2026-04-16-model-eol-clock-provider-dependency-management); [DeepInfra: model deprecation](https://deepinfra.com/blog/model-deprecation-llm-apps)
- **Pinned is not frozen.** Providers may push server-side behaviour changes even to pinned snapshots. The countermeasure is a canary suite of about 50–100 prompts run regularly against both the pinned and the current model. — [tianpan.co: Ship-and-pin trap](https://tianpan.co/blog/2026-04-23-ship-and-pin-trap-model-deprecation-debt)
- **Deterministic code generation.** Compiled AI fixes prompt, schema and triggers at compile time and confines the LLM to bounded calls, which yields deterministic orchestration (see section 1). — [Compiled AI](https://arxiv.org/html/2604.05150v1)
- The ISE pattern of separating deterministic extraction from AI inference was motivated by run-to-run inconsistency of single-prompt outputs. — [Microsoft ISE](https://devblogs.microsoft.com/ise/separating-deterministic-extraction-from-ai-inference/)

### Inferences
- **Audit-grade pattern:**
  1. Hash each source file.
  2. Run extraction once.
  3. Persist the structured output, provenance, model snapshot ID, prompt/template version and validation results as an immutable artifact.
  4. Downstream reconciliation reads only the frozen artifact.
  5. Re-extraction is a new, versioned run with a diff report, not a silent overwrite.
- Where a broker format recurs, prefer an LLM-authored but human-reviewed parser or template under version control. Determinism then comes from code, not from the model. Keep the LLM only for mapping or classification of new formats and for fallback.
- Constrained structured output (section 6) improves structural repeatability (always-valid JSON), but not value-level determinism.

### Gaps
- I could not verify from primary provider documentation which hosted APIs currently offer seed or deterministic modes, or what they guarantee.
- I found no published measurement of run-to-run variance specifically for table extraction (e.g., the percentage of cells that change across repeated temperature-0 runs).

## 6. Schema-constrained / structured-output extraction

### Takeaway
Constrained decoding (JSON Schema / grammar) guarantees structurally valid output. It does **not** guarantee correct values, and research shows it can *lower* accuracy on complex schemas. Leading practice uses a simple, flat row schema with strict types and enums; lets the model "draft" or reason before the constrained output, or extracts in chunks; and validates semantically in code afterwards.

### Cited Findings
- **JSONSchemaBench (arXiv 2501.10868; ICML 2025)** tests six constrained-decoding frameworks on 10K real-world schemas. Constrained decoding guarantees compliance by masking invalid tokens. Frameworks differ in coverage and efficiency. — [JSONSchemaBench](https://arxiv.org/pdf/2501.10868); [ICML 2025](https://icml.cc/virtual/2025/51849)
- **The "Constraint Tax" (preprint, 2026).** Hard answer-only schema decoding raised validity from 61.5% to 100% but cut answer accuracy from 19.7% to 11.0%; the error is semantic, not structural. — [alphaXiv 2605.26128](https://www.alphaxiv.org/abs/2605.26128.md)
- **ExtractBench (arXiv 2602.12247).** Structured-output mode reduced both validity and accuracy relative to prompt-based extraction on complex schemas: overall validity fell from 51% (107/210) to 37% (77/210). The suggested cause is competition between constraint overhead and attention to document content. — [arXiv 2602.12247](https://arxiv.org/pdf/2602.12247)
- **Draft-Conditioned Constrained Decoding (arXiv 2603.03305)**: generating an unconstrained draft first, then decoding under constraint, improved a 1B model from 15.24% to 39.0% strict accuracy (GSM8K). — [arXiv 2603.03305](https://arxiv.org/html/2603.03305v1)
- A practitioner overview of grammar-constrained generation as an output-reliability technique. — [tianpan.co: Grammar-constrained generation](https://tianpan.co/blog/2026-04-16-grammar-constrained-generation-output-reliability)

### Inferences
- For trade rows, use a flat per-row schema (trade_id, trade_date, settle_date, instrument / ISIN / contract code, side, quantity, price, currency, counterparty, page, bbox). Keep raw-string and normalised fields separate (e.g., `price_raw: "1.234,50"`, `price: 1234.50`), so normalisation is done by deterministic code and can be audited. This also limits the "doing too much" failure.
- Enforce business rules outside the decoder: ISO 4217 currency codes, date validity, price × quantity × multiplier ≈ notional, side enum.

### Gaps
- I found no benchmark of constrained vs. unconstrained decoding specifically on long tabular financial extraction.

## 7. Excel-specific handling

### Takeaway
For Excel, deterministic parsing with libraries (openpyxl/pandas-class) should read the actual cell values and formats. This is lossless and exact, with no OCR risk. An LLM is best confined to *structure understanding*:
- locating table regions and header rows across sheets;
- mapping broker-specific column names to the canonical schema;
- interpreting multi-row or merged headers.

The output of that step should be a mapping or config that code then applies.

### Cited Findings
- **SpreadsheetLLM (Microsoft Research, arXiv 2407.09025, 2024 — older).** Its SheetCompressor encoding (structural-anchor compression, inverse-index translation, data-format-aware aggregation) improved spreadsheet table detection by 25.6% over vanilla encoding for GPT-4 in-context learning. A fine-tuned model reached 78.9% F1 (state of the art, +12.3%) at about 25x compression. — [Microsoft Research](https://www.microsoft.com/en-us/research/publication/encoding-spreadsheets-for-large-language-models/); [arXiv 2407.09025](https://arxiv.org/html/2407.09025v1)
  - Implication: even purpose-built LLM encodings get table-region detection only about 79% right, so LLM structure inference on spreadsheets needs verification.
- **Merged cells.** A merged range stores its value only in the top-left cell. pandas reads the rest as NaN, so forward-fill or unmerge logic is needed; openpyxl exposes `ws.merged_cells.ranges`. — [LlamaIndex glossary: merged cell extraction](https://www.llamaindex.ai/glossary/merged-cell-extraction); [LlamaIndex glossary: messy spreadsheet parsing](https://www.llamaindex.ai/glossary/messy-spreadsheet-parsing)
- **Irregular headers.** A common deterministic pattern reads with `header=None`, finds the real header row by pattern matching, then slices. Reusable agent "skills" encode this for multi-sheet workbooks, unknown header positions and merged cells. — [OpenSpace irregular-excel-parsing skill](https://tessl.io/registry/skills/github/HKUDS/OpenSpace/irregular-excel-parsing); [SkillsBench xlsx-parsing](https://tessl.io/registry/skills/github/benchflow-ai/skillsbench/xlsx-parsing/review)
- **`pandas.read_excel()` pitfalls** (silent type coercion, header assumptions) are a known risk when it is used blindly. — [Alibaba Office guide](https://office.alibaba.com/officesoftware/how-to-read-excel-file-in-python)

### Inferences
- Recommended Excel pattern:
  1. Openpyxl-class inspection captures sheets, merged ranges, number formats, hidden rows/sheets and formulas vs. cached values.
  2. Heuristics and/or an LLM propose the header row and a column→schema mapping per broker template.
  3. A human approves it once and stores it as config.
  4. Deterministic code extracts all rows.
  5. Control totals are checked against any footer totals or summary sheets.
- Excel-specific risks to control:
  - displayed vs. stored precision (number formats hide decimals);
  - dates stored as serial numbers (1900/1904 epochs);
  - text-formatted numbers;
  - formulas whose cached values are stale;
  - hidden rows and filtered views;
  - subtotal rows mixed into trade rows.

(These are general Excel facts and inferences; I found no dedicated source benchmarking them for broker files.)

### Gaps
- I found no published evaluation of LLM header/column mapping accuracy on financial broker spreadsheets.

## 8. Scale and cost for hundreds of thousands of rows

### Takeaway
Cost and throughput strongly favour running deterministic code or small specialised models per page, and calling frontier LLMs only for format onboarding, exceptions and verification. Managed parsers cost roughly $0.004–$0.045 per page. Frontier-LLM per-page extraction is far more expensive and is constrained by output-token limits that cause truncation on long tables. Batch APIs typically halve LLM cost.

### Cited Findings
- **Managed parser list prices (2026, vendor/secondary):**
  - Reducto about $0.015/page standard and $0.03/page complex (agentic OCR);
  - LlamaParse Premium about $45 per 1,000 pages;
  - Docling free to self-host, with a managed IBM tier around $4 per 1,000 pages;
  - for 10k pages/month, one estimate gives Reducto at $100–500 vs. Docling on a CPU VM at $20–40, excluding engineering time. — [Reducto vs open source (CodeSOTA)](https://codesota.com/ocr/reducto-vs-open-source); [Moda: Docling alternatives](https://moda.app/blog/docling-alternatives); [Moda: Unstructured alternatives](https://moda.app/blog/unstructured-alternatives)
- **Specialised models vs. frontier MLLMs.** POTATR runs about 130x faster at about 300x lower cost than frontier MLLMs on single-page table extraction, with better single-page GriTS. — [POTATR summary](https://chatpaper.com/paper/297232)
- **Deterministic vs. LLM extraction speed.** Regex extraction was about 4,915x faster than a direct LLM call; the hybrid was about 2.3x lower latency than a direct LLM. — [Compiled AI](https://arxiv.org/html/2604.05150v1)
- **Hosted LLM PDF limits (example provider; third-party sources, conflicting):**
  - a 32 MB request payload, with page caps of 100 or 600 pages per request depending on model context size;
  - batch processing at a 50% discount on input and output tokens;
  - a reported beta raising batch output to 300k tokens per request for some models (unverified). — [jztan blog: LLM API PDF page limits](https://blog.jztan.com/llm-api-pdf-page-limits/); [fast.io Claude PDF limit](https://fast.io/resources/claude-pdf-limit/); [ClaudeLog pricing](https://www.claudelog.com/claude-pricing/); [gaugr blog](https://gaugr.app/fr/blog/claude-api-300k-output-tokens-batch-api-complete-guide); official reference: [Claude PDF support docs](https://docs.claude.com/en/docs/build-with-claude/pdf-support)
- **Truncation.** Systems without an iteration or chunking strategy truncate long record lists at context or output limits. — [ExtractBench arXiv 2607.29677](https://arxiv.org/pdf/2607.29677); [DEV: extracting data from long PDFs with an LLM](https://dev.to/felipe_anyformat/how-to-extract-data-from-long-pdfs-with-an-llm-3mnd)
- **Deterministic-inference cost.** Self-hosted batch-invariant inference costs about 34% throughput (SGLang). — [Spheron](https://www.spheron.network/blog/vllm-batch-invariance-why-temperature-0-isnt-deterministic/)

### Inferences
- At hundreds of thousands of rows (likely tens of thousands of pages), per-run frontier-LLM extraction of every row is costly and hard to reproduce. Template or deterministic extraction is roughly free per page and repeatable. A rough split: an LLM for format onboarding (tens of broker formats), specialised OCR/table models for scans, and an LLM/VLM second pass only on flagged pages or a sample. That likely cuts LLM spend by orders of magnitude (directional inference, not a measured figure).
- If LLMs must extract rows, chunk page by page or table by table, with explicit row counts per chunk and continuation markers. Reconcile chunk row counts against page-level detections to catch truncation.

### Gaps
- There is no authoritative, provider-verified 2026 per-page cost figure for frontier VLM extraction of dense tables. It depends on image tokens per page and output tokens per row, and I could not fetch primary pricing pages.
- I found no published financial-services case study with audited throughput and cost numbers for broker-statement extraction at this scale; available case studies are vendor marketing (e.g., the Koch/ipushpull chat-to-booking claims of 85% faster entry and over 90% accuracy on 50k+ trades). — [ipushpull case study](https://ipushpull.com/case-studies/koch-energy-services-and-ipushpull-automate-physical-gas-trade-booking-through-chat)
