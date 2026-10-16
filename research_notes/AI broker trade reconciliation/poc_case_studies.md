# AI-Enabled Document-to-Data Reconciliation in Financial Services and Audit: Case Studies, Reference Architectures and PoC Practice

> Research method note: The Tavily search API returned HTTP 403 and all direct page fetches (WebFetch and curl) were blocked by the proxy (DNS failure / CONNECT 403). Every finding below comes from WebSearch result summaries of the cited pages, not from full-text reads. Treat exact figures as "as reported in search summaries of the cited page". Where a claim came only from a secondary blog, that is stated. Vendor figures are self-reported marketing claims unless noted otherwise.

## 1. Published case studies (2023-2026) of AI/IDP in trade confirmations, broker statement reconciliation, derivative confirmations, bank confirmations and audit evidence: metrics and lessons

### Takeaway
Published "case studies" for confirmation and reconciliation automation are almost all from vendors or cloud providers. They report high STP and match rates (90-99%), but they give no baselines, no independent measurement and little failure analysis. I found no independent, peer-reviewed or auditor-published study of GenAI reconciling broker confirmations to a client trade list. The most credible evidence for audit-specific AI comes from Big Four announcements about full-population testing, and the details there are thin.

### Cited Findings
**Derivative / trade confirmations (sell-side and buy-side operations)**
- Xceptor, a vendor, says its multi-asset confirmations product delivers "90%+" STP across commodities, rates, credit, FX, money markets and derivatives. It cites a 95% STP client result. A client story (ICBC Standard Bank) quotes an executive saying the project was completed "in just a few short months". AI is used to flag clause mismatches. — [Xceptor Confirmations](https://www.xceptor.com/solutions/confirmations); [Xceptor product sheet](https://www.xceptor.com/resources/product-sheets/confirmations); [Xceptor client story](https://www.xceptor.com/resources/client-story/automating-trade-confirmations)
- AWS published an end-to-end derivative-confirms workflow for a bank, built on Amazon Textract and serverless services. The bank "expects" STP to rise to over 90%, so this is a forward-looking expectation, not a measured result. Schema mappings for new counterparties are handled through a human-in-the-loop UI. This is a useful design lesson: new broker formats are onboarded by people, not inferred by the model. — [AWS ML Blog: Automate derivative confirms processing](https://aws.amazon.com/blogs/machine-learning/automate-derivative-confirms-processing-using-aws-ai-services-for-the-capital-markets-industry/)
- OSTTRA (the post-trade venture of CME and IHS Markit, now S&P) launched an AI tool that extracts key economic terms, such as notional and strike, from PDF ("paper") confirmations for investment managers on OSTTRA Trade Manager. It rolled out first for FX options and equity swaps, with commodity swaps to follow. The article's date is unclear and it may be several years old. — [Finadium: OSTTRA using AI to digitize paper confirmations](https://finadium.com/osttra-using-ai-to-digitize-paper-confirmations-for-otc-derivatives/)
- ISDA's April 2024 whitepaper names confirmation processing as a GenAI use case because it is "time-consuming and manually intensive, particularly for complex or non-standard trades". It also covers regulatory considerations. The excerpts I saw contained no deployment outcomes. — [ISDA: GenAI in the Derivatives Market: A Future Perspective (Apr 2024)](https://www.isda.org/a/PbwgE/GenAI-in-the-Derivatives-Market-A-Future-Perspective.pdf)
- Duco, a vendor, frames the problem for OTC confirmations as deal data being "locked in PDFs, requiring manual rekeying". — [Duco OTC confirmations](https://du.co/solutions/otc-confirmations/)
- NeoXam, a vendor, says its AI-driven matching and exception handling lifts match rates from about 95% to "98.5%+". — [NeoXam OTC derivatives reconciliation](https://www.neoxam.com/aro/otc-derivatives-reconciliation-software/)
- FIS reports auto-match rates of over 99% for cleared-derivatives reconciliations and uses AI to suggest match rules. This product works on structured data and is not a GenAI document deployment. — [FIS cleared derivatives reconciliations product sheet](https://www.fisglobal.com/-/media/fisglobal/files/pdf/product-sheet/cleared-derivatives-reconciliations-product-sheet.pdf)
- Indico Data (2021) argues that banks are turning to IDP for confirmations mainly because document layouts vary so much across counterparties. — [Indico Data blog](https://indicodata.ai/blog/automating-the-trade-confirmation-process-with-intelligent-document-processing/)
- Pre-AI history: confirmation automation has been rules- and template-based for a long time. Examples are Standard Bank's 2008 Murex confirmation automation and Thunderhead/IBM's pattern of routing "conditions" to an exception process when a trade cannot go straight through. — [Smart Communications / Standard Bank case study](https://www.smartcommunications.com/wp-content/uploads/2016/04/Standard-Bank-and-Smart-Communications-Case-Study-V2.0.pdf); [Thunderhead derivatives confirmation brief](https://public.dhe.ibm.com/software/data/information-agenda/Thunderhead_Derivatives_Confirmation_psp_FIN_09.pdf)

**Audit confirmations and audit evidence**
- Baseline time data from pre-AI electronic confirmation adoption: Zinman & Co staff spent about 10-15 minutes per bank account on paper confirmations, and a client with 23 accounts took about 5 hours to confirm manually. — [Confirmation.com case study: Zinman & Co](https://www.confirmation.com/media/53080/case-study_zinman-co_final.pdf)
- After moving to electronic confirmations, Schaffner, Knight, Minnaugh & Co reported faster responses and fewer bank errors, such as wrong dates or balances. This shows that the counterparty's response can itself be wrong, so it is not a perfect ground truth. — [Confirmation.com: SKM case study](https://www.confirmation.com/resources/case-studies/schaffner,-knight,-minnaugh--co.aspx)
- An academic longitudinal study analysed Confirmation.com data from 2006-2015, including user error rates. — [ResearchGate: Bank Confirmation Process Automation: A Longitudinal Study](https://www.researchgate.net/publication/346227891_An_Exploration_of_Bank_Confirmation_Process_Automation_A_Longitudinal_Study)
- Wolters Kluwer presents open banking, meaning client-authorised direct data access, as an alternative to confirmations. It notes that banks cannot always confirm everything requested. — [Wolters Kluwer: automated bank confirmations](https://www.wolterskluwer.com/en/expert-insights/delivering-reimagined-efficiencies-to-audit-firms-through-automated-bank-confirmations)
- A KPMG Luxembourg press release (Dec 2025) says KPMG Clara AI enabled full-population testing across millions of transactions for a financial services client. — [KPMG Luxembourg press release, Dec 2025](https://kpmg.com/lu/en/home/media/press-releases/2025/12/talent-tech-trust-kpmg-shaping-future-value.html)
- KPMG planned to pilot "orchestration agents" that oversee other AI tools in audit, with full agent deployment on certain routine tests planned for the following year. — [Bloomberg Tax: KPMG to test advanced AI agents](https://news.bloombergtax.com/financial-accounting/kpmg-to-test-advanced-ai-agents-in-next-phase-for-audits); [Going Concern](https://www.goingconcern.com/kpmg-plans-to-hand-routine-testing-off-to-ai/)
- Secondary, unverified blog claims: EY's agentic framework in EY Canvas reaches about 130,000 assurance professionals and 160,000 engagements, with agents that "examine entire populations rather than samples". Deloitte launched an agentic network in Omnia on 24 June 2026 for about 85,000 practitioners. PwC expects an end-to-end AI audit solution in 2026. — [ChatFin blog](https://chatfin.ai/blog/big-4-ai-agents-ey-kpmg-deloitte-pwc-finance-teams-2026/); [AgentMarketCap blog](https://agentmarketcap-1.onbex.co/blog/2026/07/11/ai-agents-big-four-audit-assurance); [Thomson Reuters](https://tax.thomsonreuters.com/blog/how-do-different-accounting-firms-use-ai-tri/)

**Invoice / statement matching and finance-operations AI (adjacent evidence)**
- In a freight/AP human-in-the-loop deployment, the vendor reported 99% data accuracy and 50% lower processing cost, but stated no baseline. In a Tipalti case, exceptions and complex cases go to staff while routine items are automated. — [Parseur: HITL case studies that name the customer](https://parseur.com/blog/hitl-case-studies)
- In the "Better Bill GPT" study, top LLMs reached 92% accuracy on invoice-level legal-billing decisions, against 72% for the best human reviewers. This is a billing-compliance task, not reconciliation. — [arXiv 2504.02881](https://arxiv.org/html/2504.02881v1)
- An academic multi-agent prototype for SME invoice reconciliation matched 9 PDF invoices from 3 vendors against a QuickBooks Online expense summary for Q1 2025. The authors stress that extraction errors propagate into audit trails and misstatements. The sample is very small. — [ResearchGate: Scalable Invoice Reconciliation for SMEs](https://www.researchgate.net/publication/392226522_Scalable_Invoice_Reconciliation_for_SMEs_Edge-Deployed_LLMs_in_Multi-Agent_Systems)
- FinBalance (2026) introduces a multi-document accounting reconciliation benchmark. I could not retrieve its results. — [arXiv 2606.15949](https://arxiv.org/pdf/2606.15949)
- A vendor blog describes fraud cases in which bank-detail changes were auto-approved by automated invoice flows. This is a cautionary example for setting auto-accept thresholds, and it is anecdotal. — [Peakflo: HITL AI for Finance governance framework](https://peakflo.co/blog/human-in-the-loop-ai-finance-governance-framework)

### Inferences
- The "90%+ STP" figures are measured against operations workflows where a confirmation is matched to the firm's own booking and any break goes to an ops analyst. An auditor's tolerance differs: one false match, where a broker trade is wrongly accepted as agreeing to a client trade, is an audit-evidence failure. Vendor STP rates therefore do not transfer directly as PoC targets.
- The AWS and Xceptor patterns both treat onboarding a new counterparty or format as a human-mediated step. A PoC should measure "time to onboard a new broker format" as an explicit metric.
- The Confirmation.com experience shows that counterparty documents contain errors. A reconciliation tool must report "document says X, client says Y". It must not "correct" the document, and ground truth should be defined as what the document says.
- Big Four messaging has shifted from sampling to full-population testing with AI. The details of these claims cannot be verified publicly.

### Gaps
- I found no published case study with independent metrics for GenAI reconciling broker confirmations or statements of open derivative positions to a client trade register, in either operations or audit.
- There were no quantified Big Four outcomes, such as hours saved, exception rates or false-match rates, for AI confirmation or reconciliation procedures.
- No commodity-trader case study with metrics was found.
- Full texts of the AWS, Xceptor, ISDA and KPMG pages could not be read because fetches were blocked. Details such as the AWS bank's identity and the exact architecture components are unverified beyond the summaries.

## 2. Reference architectures for IDP plus reconciliation with human-in-the-loop and lineage; agentic patterns and critiques

### Takeaway
Cloud reference architectures converge on a fixed staged pipeline: ingestion, OCR/parse, classify, extract, validate (business rules), human-in-the-loop review, then export. The LLM is used inside bounded steps. Anthropic's guidance and the high cancellation rates Gartner forecasts for agentic projects both argue for deterministic workflows with LLM steps over open-ended agents when the process is well defined and auditable, as reconciliation is.

### Cited Findings
- The AWS GenAI IDP Accelerator (open source, v0.5.0, March 2026) offers two runtime-switchable modes: Bedrock Data Automation for standard documents and a "Bedrock Pipeline" mode for complex ones. It includes built-in human-in-the-loop review and business-rule validation. — [AWS ML Blog: Accelerate IDP with generative AI on AWS](https://aws.amazon.com/blogs/machine-learning/accelerate-intelligent-document-processing-with-generative-ai-on-aws); mirror: [HKU AI Hub](https://aihub.hkuspace.hku.hk/2025/08/23/accelerate-intelligent-document-processing-with-generative-ai-on-aws/)
- The accelerator's pipeline stages are ingestion, OCR (e.g., Textract), classification, extraction, validation, summarisation, HITL evaluation and data export. This comes from a commentary source. — [Deep Analysis: Built on Bedrock](https://www.deep-analysis.net/?p=49657)
- A separate AWS pattern runs a fully serverless pipeline: Bedrock Data Automation, AWS Step Functions for orchestration and Amazon Augmented AI (A2I) for human review tasks. — [HKU AI Hub mirror of AWS post: Scalable IDP using Bedrock Data Automation](https://aihub.hkuspace.hku.hk/?p=4290); [AWS BDA blog category](https://aws.amazon.com/blogs/machine-learning/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/bda)
- The AWS derivative-confirms architecture uses Textract with serverless components and a HITL UI for mapping new counterparty schemas. — [AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/automate-derivative-confirms-processing-using-aws-ai-services-for-the-capital-markets-industry/)
- Anthropic separates "workflows", where LLMs and tools follow predefined code paths, from "agents", where the LLM directs its own steps and tool use. It advises "finding the simplest solution possible, and only increasing complexity when needed", which "might mean not building agentic systems at all". It also notes that agentic systems trade latency and cost for task performance. — [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- A secondary summary of the same guidance: workflows give predictability and consistency for well-defined tasks, while agents suit cases that need flexibility and model-driven decisions at scale. — [Medium/Accredian summary](https://medium.com/accredian/building-effective-ai-agents-a-guide-from-anthropic-e66b533ff091)
- Gartner (June 2025) forecasts that over 40% of agentic AI projects will be cancelled by end-2027 because of escalating costs, unclear business value or inadequate risk controls. Analyst Anushree Verma said most are early-stage experiments or PoCs "mostly driven by hype" and "often misapplied". Gartner estimates only about 130 of the thousands of "agentic AI" vendors are real ("agent washing"). — [New Electronics](https://www.newelectronics.co.uk/content/news/over-40-of-agentic-ai-projects-could-be-cancelled-by-2027); [Outlook Business](https://www.outlookbusiness.com/artificial-intelligence/over-40-of-agentic-ai-projects-will-be-scrapped-by-2027-says-gartner)
- Research on multi-agent and HITL pipelines for documents and finance includes "Team of Rivals" multi-agent coherence, MADP (a multi-agent document pipeline with HITL) and LAVA (logic-aware validation for large-scale financial document auditing). I saw only their titles and abstracts in search results. — [arXiv 2601.14351](https://arxiv.org/pdf/2601.14351); [arXiv 2605.17159](https://arxiv.org/pdf/2605.17159); [arXiv 2608.16763](https://arxiv.org/pdf/2608.16763)
- Scale AI argues that as automation gets cheap, the design question becomes which work is worth routing to a human. Human review should be targeted, not blanket. — [Scale: HITL routing](https://scale.com/blog/hitl-routing)
- Field-level confidence is not the same as decision correctness. A confidence-driven production invoice system measures whether a field was read correctly, not whether the reconciliation decision is right. — [Parseur HITL case studies](https://parseur.com/blog/hitl-case-studies) (summary of a 2025 paper cited there)
- Trustworthiness scoring for LLM structured outputs is an active research area for deciding which extracted fields to route to review. — [arXiv 2603.18014: Real-Time Trustworthiness Scoring for LLM Structured Outputs](https://arxiv.org/pdf/2603.18014)

### Inferences
Suggested reference flow for the auditor PoC, synthesised from the patterns above:
1. **Ingestion and evidence register.** Record each broker document's hash, source (received directly from the broker or via the client), received timestamp and broker ID. These are immutable originals.
2. **Parse.** Convert PDF, email or Excel into text and tables with page coordinates (Docling, pdfplumber or PyMuPDF), with OCR fallback for scans.
3. **Classify.** Identify the broker or format and the document type (open-position statement or individual confirmation).
4. **Extract.** An LLM produces a JSON schema per trade (trade ID or broker ref, trade date, product, buy/sell, quantity or notional, price or strike, expiry or maturity, currency, counterparty, account). Each field carries a page and bounding-box citation.
5. **Validate and normalise.** Use deterministic code: date and number formats, units (lots vs contracts vs notional), sign conventions, mapping to a canonical product and reference data. Check document totals and row counts so no rows are silently dropped.
6. **Match.** Use deterministic keys first, such as broker ref or trade ID. Then apply rule-based tolerance matching. Any LLM-suggested match is only a proposal, and a human accepts it.
7. **Exceptions.** Classify each as unmatched broker trade, unmatched client trade, field difference or one-to-many.
8. **Reviewer UI.** Show the source snippet beside the extracted value.
9. **Audit trail.** Record model and prompt versions, every reviewer override with reason, and a re-performable output.
10. **Monitoring.** Track drift per broker format and the exception rate.

An "agent" adds the most value at the edges, such as triaging an unknown format or drafting exception explanations. It should not sit in the matching decision itself, which needs to be deterministic and re-performable for audit evidence. This is consistent with Anthropic's guidance and Gartner's warnings about misapplied agents.

### Gaps
- I could not retrieve Azure (Document Intelligence) or Google (Document AI) reference architectures specifically for reconciliation.
- I found no published reference architecture that explicitly covers audit-grade lineage, meaning evidence linking each matched row to the document coordinates, as opposed to generic HITL.
- I found no independent critique comparing agent and pipeline performance on financial reconciliation with quantitative results.

## 3. Why GenAI PoCs fail to reach production in finance and audit: surveys and figures

### Takeaway
Major surveys from 2024-2026 agree that most GenAI pilots fail to show P&L impact. The causes given are integration and workflow fit, data quality, risk controls, cost and unclear value, rather than model capability. Finance-function adoption plateaued at about 58-59% in 2024-2025, with mostly low or moderate impact.

### Cited Findings
- MIT NANDA's "The GenAI Divide: State of AI in Business 2025" (Aug 2025) found about 5% of AI pilots achieve rapid revenue acceleration, while "the vast majority stall, delivering little to no measurable impact on P&L". — [Fortune, 18 Aug 2025](https://fortune.com/2025/08/18/mit-report-95-percent-generative-ai-pilots-at-companies-failing-cfo/); [Computing](https://computing.co.uk/news/2025/ai/mit-report-95pc-corporate-generative-ai-pilots-fail)
- The MIT study's methodology is described inconsistently. Press coverage cites 150 leader interviews, a 350-employee survey and 300 public deployments. A later analysis cites more than 300 public initiatives, 52 organisations interviewed and 153 senior leaders surveyed, and stresses that the 95% figure is from a preliminary research programme, not a universal failure rate. The authors attribute the gap to brittle workflows, weak contextual learning and poor fit with daily operations, not model quality. Lead author Aditya Challapally noted that some large companies and younger startups are "really excelling". — [Let's Data Science analysis](https://letsdatascience.com/news/mit-report-documents-genai-pilot-roi-gap-e0924d7d); [Yahoo Finance](https://finance.yahoo.com/news/mit-report-95-generative-ai-105412686.html)
- Gartner (29 July 2024) predicted at least 30% of GenAI projects would be abandoned after proof of concept by end-2025, because of poor data quality, inadequate risk controls, escalating costs or unclear business value. Rita Sallam said organisations struggle to prove and realise value after the hype. — [Gartner press release](https://www.gartner.com/en/newsroom/press-releases/2024-07-29-gartner-predicts-30-percent-of-generative-ai-projects-will-be-abandoned-after-proof-of-concept-by-end-of-2025)
- Gartner (2025) forecasts that more than 40% of agentic AI projects will be cancelled by end-2027, for the cost, value and risk-control reasons in section 2. — [New Electronics](https://www.newelectronics.co.uk/content/news/over-40-of-agentic-ai-projects-could-be-cancelled-by-2027)
- McKinsey State of AI 2025 (published 5 Nov 2025):
  - 88% use AI in at least one function, but only about one-third are scaling it enterprise-wide.
  - Only 39% report any enterprise-level EBIT impact, and most of those attribute less than 5% of EBIT to AI.
  - About 6% are "AI high performers", defined as more than 5% of EBIT from AI.
  - 62% are at least experimenting with agents, and 23% are scaling agents somewhere.

  These are secondary summaries. — [CFA UK Connect discussion](https://connect.cfauk.org/discussion/the-state-of-ai-in-2025-agents-innovation-and-transformation-mckinsey-co); [The Right Stack](https://therightstack.com/cloud-developer-and-cloud-security-surveys/mckinseys-2025-state-of-ai-survey-its-all-agents-these-days); [CX Today](https://www.cxtoday.com/ai-automation-in-cx/mckinseys-state-of-ai-the-scaling-gap-is-now-cxs-problem/)
- An unverified secondary report says McKinsey's 2026 survey found 37% attributing any EBIT impact to AI, flat on 2025. Among companies with more than $1B revenue, 40% were scaling agents, up from 27%. — [ValueAdd VC (citing The Register)](https://valueaddvc.com/pulse/mckinsey-enterprise-ai-roi-2026-survey-data)
- Gartner's AI in Finance survey (published 18 Nov 2025; 183 CFOs and senior finance leaders, surveyed May-June 2025):
  - 59% of finance teams use AI, against 58% in 2024 and 37% in 2023.
  - 67% are more optimistic than a year earlier.
  - The largest obstacles are data literacy and technical skills, and inadequate data quality or availability.
  - One summary reports 91% saw low or moderate initial impact.

  — [Gartner press release](https://www.gartner.com/en/newsroom/press-releases/2025-11-18-gartner-survey-shows-finance-ai-adoption-remains-steady-in-2025); [CFO Dive](https://www.cfodive.com/news/cfos-ai-adoption-slows-challenges-mount-gartner/805949/); [CFO.com](https://www.cfo.com/news/cfo-optimism-around-ai-rises-as-adoption-levels-off-gartner-/805868/)
- A June 2026 Gartner release reports 84% of finance organisations have implemented or are planning AI, using the same cohort. This includes planned use, so it is not comparable to the 59% figure. Gartner urges CFOs to adopt structured finance AI roadmaps. — [Gartner, 8 Jun 2026](https://www.gartner.com/en/newsroom/press-releases/2026-06-08-gartner-says-cfos-need-structured-finance-ai-roadmaps)
- Deloitte's Q4 2025 CFO Signals: 87% of CFOs expect AI to be extremely or very important to finance operations in 2026, and 54% say integrating AI agents into finance is a transformation priority. — [Deloitte press release](https://www.deloitte.com/us/en/about/press-room/deloitte-q4-2025-cfo-signals-survey.html)
- Kyndryl's "Beyond the pilot" (Dec 2024) addresses the move from pilot to production. Its content was not retrieved. — [Kyndryl](https://www.kyndryl.com/perspectives/articles/2024/12/beyond-the-pilot.html)

### Inferences
- The failure causes most relevant to an auditor's reconciliation PoC are:
  - unclear value or success criteria, so acceptance thresholds and a baseline should be fixed before building;
  - data access and quality, meaning getting broker documents and client trade lists in usable form under agreed data-handling terms;
  - risk controls and governance, meaning methodology and QA sign-off and independence clearance;
  - workflow fit, meaning the output must slot into existing working papers rather than add a parallel tool.
- MIT's finding that implementation, not model quality, drives the gap suggests the PoC should spend as much effort on the reviewer workflow and evidence pack as on extraction accuracy.

### Gaps
- I found no survey figures specific to audit firms on PoC-to-production conversion.
- KPMG's 2026 Global AI in Finance Report and EY/PwC audit-AI surveys were referenced in search results, but their figures were not retrieved.
- I found no Gartner follow-up confirming whether the 30%-abandoned-by-2025 prediction came true.

## 4. How to design the PoC: sample selection, ground truth, phase gates, quantitative and qualitative acceptance criteria

### Takeaway
The public literature has little auditor-specific PoC design guidance. The IDP evaluation literature does give concrete, transferable practices: build a labelled ground-truth set, and score at both field and document or row level, because field accuracy overstates readiness. Measure parse and extraction variance across formats, and calibrate confidence-based routing against measured error rates rather than vendor scores.

### Cited Findings
- A structured-outputs benchmark reported GPT-5 at 0.949 field-level accuracy but only 0.700 whole-document accuracy on financial entity extraction. High per-field accuracy can still leave many documents with at least one error. My attribution to arXiv 2603.18014 comes from the search summary and could not be confirmed against the full text. — [arXiv 2603.18014](https://arxiv.org/pdf/2603.18014)
- A hybrid OCR-LLM study made three findings:
  - Docling's table-based method reached near-perfect F1 on PDF extraction at about 1.6s latency, while another method failed completely on PDFs.
  - Direct LLM extraction was over 40x slower than table-based approaches.
  - PDF extraction showed the most extreme performance variance, so format compatibility matters as much as model choice.

  — [arXiv 2510.10138](https://arxiv.org/html/2510.10138v1)
- A small single-author test (June 2025) on dense pages from 10 public filings ranked Docling best for structure and accuracy, though no library was perfect. It recommends pairing OCR with an LLM and adding arithmetic checks, such as verifying that table totals add up. — [Newtuple](https://www.newtuple.com/post/finance-friendly-ocr-how-docling-dolphin-others-tackle-wall-street-pdfs)
- A study of multi-structured financial documents found that pre-processing tools materially affect LLM comprehension. — [arXiv 2506.05182](https://arxiv.org/pdf/2506.05182)
- A vendor evaluation guide defines "FieldCompleteness" (no required field missing) and "FieldCoverage" (share of expected output produced). These map to row and field completeness metrics. — [FutureAGI IDP guide](https://futureagi.com/glossary/intelligent-document-processing/)
- A vendor offers field-level confidence scores in its extraction product. I found no independent evaluation of how well such scores are calibrated. — [LlamaIndex: Best AI for PDF table extraction (2026)](https://www.llamaindex.ai/insights/best-ai-for-pdf-table-extraction)
- Vendor accuracy claims such as "99% data accuracy" often have no stated baseline and should be treated as hypotheses. — [Parseur](https://parseur.com/blog/hitl-case-studies)
- Counterparty-supplied documents contain errors such as wrong dates or balances, so ground truth must record what the document says, and that may differ from the true position. — [Confirmation.com SKM case study](https://www.confirmation.com/resources/case-studies/schaffner,-knight,-minnaugh--co.aspx)

### Inferences
The following PoC design is synthesised by me from the findings above plus general practice. It is not sourced to a published auditor PoC.

**Sample selection**
- Stratify brokers by format difficulty:
  - Easy: native-text PDF with a clean table, or a CSV/XLSX statement.
  - Medium: multi-page tables, merged cells, multiple accounts.
  - Hard: scanned or faxed documents, free-text confirmations, multi-leg or structured products, non-English, password-protected.
- Include at least one broker per major product type, such as listed futures and options, OTC swaps and FX forwards.
- Deliberately seed known breaks: missing trades, quantity, price or date differences, sign flips, duplicates, trades that were closed but still appear.

**Ground truth**
- Have two people label the data independently and adjudicate disagreements.
- Labels should cover:
  - per-document trade-level JSON;
  - expected match outcomes per client trade (matched, unmatched or field-break with the field named);
  - a record of when the document itself is wrong.
- Freeze a held-out test set, and do not tune prompts on it.

**Phase gates**
- Gate 0: data access, independence and security approvals in place, with synthetic data only.
- Gate 1: extraction accuracy on the labelled set.
- Gate 2: end-to-end reconciliation accuracy, with zero false matches.
- Gate 3: parallel run against the manual process on a live engagement, with the reviewer re-performing a sample.
- Gate 4: methodology and QA review of the evidence pack.

**Quantitative acceptance criteria (suggested)**
- Field-level accuracy, reported per critical field.
- Document- and row-level exact-match rate, following the 0.949 vs 0.700 lesson.
- Row completeness: 100% of broker rows captured, reconciled to document totals and counts.
- False-match rate of zero, where a false match is a broker trade auto-matched to the wrong client trade or a break reported as agreed.
- Recall of seeded breaks of 100%.
- Repeatability: identical output across reruns with pinned model, prompt and seed. Any nondeterminism must be caught by validation.
- Throughput and cost per document.
- Reviewer minutes per broker versus the manual baseline. The pre-AI confirmation data (about 10-15 minutes per account) shows how such a baseline can be framed.
- Time to onboard a new broker format.

**Qualitative criteria**
- Reviewer trust and usability, gathered through a structured questionnaire.
- Explainability: every value links to its source location in the document.
- The evidence pack meets the firm's documentation standard and is re-performable by a reviewer.
- Exception explanations are accurate.

### Gaps
- I found no published PoC plan or acceptance criteria from an audit firm for AI reconciliation of confirmations.
- I found no published guidance on minimum sample sizes or broker counts for IDP PoCs in capital markets.
- I found no independent benchmark of LLM extraction accuracy on broker confirmations or derivative statements specifically.

## 5. Organisational and process considerations: methodology sign-off, independence, client and broker data handling, IT/security, and the move from sampling to full-population testing

### Takeaway
New PCAOB amendments on technology-assisted analysis now apply. They are effective for fiscal years beginning on or after 15 Dec 2025, so they cover calendar-2026 audits. They raise expectations for evaluating the reliability of electronic information and for investigating items identified in full-population analyses. The IESBA Code applies whatever tool is used, and client data for AI training needs explicit authorisation. Where independence rules apply to auditor-built or licensed AI tools remains debated.

### Cited Findings
- The PCAOB amended AS 1105 (Audit Evidence) and AS 2301 (Responses to Risks of Material Misstatement) to address technology-assisted analysis. The SEC approved them by order dated 20 Aug 2024 (Release No. 34-100774). They are effective for audits of fiscal years beginning on or after 15 Dec 2025. Their purpose is to reduce the risk that auditors relying on technology-assisted analysis issue opinions without sufficient appropriate evidence. — [PCAOB: What Was Changed](https://pcaobus.org/oversight/standards/implementation-resources-PCAOB-standards-rules/amendments-related-to-aspects-of-designing-and-performing-audit-procedures-that-involve-technology-assisted-analysis-of-information-in-electronic-form); [SEC approval order](https://sec.gov/files/rules/pcaob/2024/34-100774.pdf); [PCAOB adopting release 2024-007](https://assets.pcaobus.org/pcaob-dev/docs/default-source/rulemaking/docket-052/2024-007-adoptingrelease.pdf); [NYSSCPA](https://nysscpa.org/news/1048563-sec-approves-3-pcaob-actions-focusing-on-auditor-responsibilities-2024-08-21)
- The PCAOB implementation page references a policy statement, PCAOB Release No. 2025-004, on implementing AS 1105 paragraph .10A. Its content was not retrieved. — [PCAOB implementation resources](https://pcaobus.org/oversight/standards/implementation-resources-PCAOB-standards-rules/amendments-related-to-aspects-of-designing-and-performing-audit-procedures-that-involve-technology-assisted-analysis-of-information-in-electronic-form)
- IESBA's technology snapshot (June 2026) says the Code's fundamental principles, including confidentiality, apply regardless of tool. Using client data for purposes such as AI model training requires proper authorisation with clear consent boundaries. The material is non-authoritative guidance. — [IESBA Snapshot: Ethics and Independence Approach to the Use of Technology](https://www.ethicsboard.org/news-events/2026-06/iesba-snapshot-ethics-and-independence-approach-use-technology); [ICAS summary](https://www.icas.com/news-insights-events/news/ethics/iesba-issues-snapshot-on-the-ethical-implications-of-using-technology-including-ai)
- The IESBA technology revisions, effective December 2024, address self-review threats, the risk of assuming management responsibility, and commercial dependencies when technology is used to deliver services. — [ICAS](https://www.icas.com/news-insights-events/news/ethics/iesba-issues-snapshot-on-the-ethical-implications-of-using-technology-including-ai); [Audit Conduct newsletter](https://www.auditconduct.com/newsletters/iesba-update-technology-auditor-independence-and-proposed-strategy-work-plan)
- Opinion: a commentary piece argues it is unclear when licensing an AI audit tool creates an independence conflict. It suggests documenting, per tool, who owns the vendor, whether the vendor also serves the client, fees, and whether the vendor may train on client data. — [Accounting Weekly: AI Audit Tools and the Independence Gap](https://www.accountingweekly.com/trending-news/ai-audit-tools-and-the-independence-gap-nobody-fixed)
- Big Four firms are positioning AI for full-population testing. KPMG Clara AI was used for full-population testing across millions of transactions for an FS client, and secondary sources say EY agents examine "entire populations rather than samples". — [KPMG Luxembourg](https://kpmg.com/lu/en/home/media/press-releases/2025/12/talent-tech-trust-kpmg-shaping-future-value.html); [ChatFin (secondary)](https://chatfin.ai/blog/big-4-ai-agents-ey-kpmg-deloitte-pwc-finance-teams-2026/)
- ISDA's GenAI paper covers regulatory considerations for GenAI in derivatives processes. — [ISDA Apr 2024](https://www.isda.org/a/PbwgE/GenAI-in-the-Derivatives-Market-A-Future-Perspective.pdf)

### Inferences
- **Independence.** If the auditor builds the tool and runs it on documents the auditor obtained, the tool is part of the audit procedure. The tool and its outputs should stay with the auditor and not be handed to the client for their own reconciliation, to avoid self-review and management-responsibility threats. This should be confirmed with the firm's independence function.
- **Provenance.** Broker documents should come directly from the broker where possible, as with confirmations, to preserve the reliability of the evidence. The pipeline's evidence register should record provenance.
- **PCAOB reliability.** Under the amended standards, the auditor will need to evaluate the reliability of the client's internal trade list as electronic information. The auditor must also investigate all items the full-population reconciliation flags, rather than treating it as a sample.
- **Data handling.** Confirm that the LLM API contract has zero data retention and no training on inputs, and check data residency. Check whether the engagement letter or client consent covers processing by third-party AI. Synthetic or anonymised data should be used until approvals are in place, consistent with IESBA's consent principle.
- **Methodology sign-off.** Involve the firm's methodology and QA teams from Gate 0. Their acceptance of the evidence pack is a hard gate, not an afterthought.

### Gaps
- I found no specific PCAOB, FRC, ICAEW or ISA (IAASB) guidance on sending client data to external LLM APIs.
- I found no published firm policy on auditor-built AI tools and independence.
- IAASB ISA 500/505 developments on technology and external confirmations were not covered by my searches.
- The content of PCAOB Release 2025-004 was not retrieved.

## 6. Practical tooling stack for a quick prototype, and synthetic data generation

### Takeaway
The evidence supports a hybrid approach. A layout-aware open-source parser such as Docling handles tables. A frontier LLM with JSON-schema structured outputs extracts the fields. Deterministic validation and matching follow in Python/SQL, and a lightweight review UI sits on top. Direct LLM-on-PDF extraction is slower and more variable than table-first parsing.

### Cited Findings
- Docling's table-based method reached near-perfect F1 on PDFs at about 1.6s per document. Direct LLM extraction was over 40x slower. Format compatibility drives the variance. — [arXiv 2510.10138](https://arxiv.org/html/2510.10138v1)
- In a small test on financial filings, Docling ranked best overall but no tool was perfect. The test recommends OCR plus LLM with total-checks. — [Newtuple](https://www.newtuple.com/post/finance-friendly-ocr-how-docling-dolphin-others-tackle-wall-street-pdfs); [Medium: Docling pipelines](https://medium.com/@sanikachavan1806/docling-is-quietly-changing-how-we-build-ai-document-pipelines-4ee9e6f57164)
- One vendor round-up of PDF table extraction tools reports a 93.6% Docling table accuracy figure with no traceable methodology, so that figure should not be relied on. — [LlamaIndex (vendor)](https://www.llamaindex.ai/insights/best-ai-for-pdf-table-extraction)
- Cloud-managed alternatives include Amazon Textract, Bedrock Data Automation and the open-source AWS GenAI IDP Accelerator with HITL. — [AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/accelerate-intelligent-document-processing-with-generative-ai-on-aws)
- Trustworthiness or confidence scoring for structured outputs can drive review routing, but it must be calibrated against your own ground truth. — [arXiv 2603.18014](https://arxiv.org/pdf/2603.18014)

### Inferences
The following stack is a vendor-neutral suggestion from my synthesis. Specific libraries beyond Docling were not evaluated in the sources retrieved.

**Prototype stack**
- Parse: Docling, pdfplumber or PyMuPDF for native PDFs, Tesseract or a cloud OCR as fallback, and openpyxl or pandas for XLSX/CSV.
- Extract: a frontier LLM via API in JSON-schema structured-output mode. Use a Pydantic schema per trade, require a page and quote citation for each field, and set temperature to 0.
- Validate and normalise: Pydantic validators, plus a broker-specific mapping config in YAML.
- Store: DuckDB or Polars for canonical tables, holding the client trade list, broker extracts and match results.
- Match: SQL joins on keys, then tolerance rules, with every rule logged.
- Review: a Streamlit app showing the PDF page image with the highlighted source snippet next to the extracted row, with accept, override and reason fields.
- Audit trail: append-only JSONL or DuckDB logging document hash, model ID, prompt version, outputs and reviewer actions.
- Evidence pack: an Excel or PDF export for the working papers.

**Synthetic data**
- Generate a synthetic client trade register in Python (Faker plus domain rules for futures, options, swaps and FX forwards).
- Render broker-style PDFs from it in several layouts with HTML-to-PDF or reportlab, including deliberately scanned or rotated variants, multi-page tables and different date and number locales.
- Inject controlled breaks into the broker side, such as missing trades, quantity or price deltas, sign flips and duplicates.
- Because the generator knows the truth, it yields a ground-truth match file automatically. This allows end-to-end scoring, including the false-match rate, before any client data is touched.

### Gaps
- I found no source benchmarking specific frontier LLM APIs on broker confirmation extraction.
- I found no published synthetic broker-confirmation dataset or generator.
- I found no published examples of Streamlit (or similar) reviewer UIs for audit reconciliation.
- I found no data on determinism or repeatability of LLM structured outputs across reruns for financial extraction.
