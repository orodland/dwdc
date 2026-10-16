# Deterministic Reconciliation and Matching of Exchange-Traded and OTC Derivatives (Broker/Clearer Statements vs Internal Records)

Research note scope: industry practice for normalizing and deterministically matching commodity futures, options on futures and FX forwards between broker/clearer statements and internal trade records. Vendor-neutral and current to October 2026. Methodology caveat: several primary-source domains (fia.org, xceptor.com, docs.oracle.com) could not be fetched directly from this environment, and the Tavily extractor returned 403. Findings therefore rely on search-result excerpts of primary documents (CME, FIA/DMIST, ANNA-DSB, FIX dictionaries, Oracle and Infor docs, a USPTO patent) plus secondary sources. Field-level detail should be checked against the full primary documents before it is hard-coded. Items labelled "background knowledge" in Inferences were not verified in this session.

## Q1. Match keys, comparison fields, position vs trade reconciliation, aggregation, give-ups, average price (APS), allocations, splits and partial fills

### Takeaway
Industry practice runs two layers. The first is trade-level matching on instrument identity, account, side, quantity, price and trade date, often run T+1. The second is end-of-day open-position reconciliation per instrument and account, typically at zero tolerance. Give-ups, allocations and average-price trades break the simple one-to-one assumption: a broker statement can show one average-price trade, or allocated sub-quantities, where the internal book holds the original street fills. Clearing-house identifiers (allocation group IDs, average-price group IDs, original order IDs and client references) are the main tools for linking them.

### Cited Findings
**Trade vs position reconciliation**
- Position reconciliation compares the units held per security per account between the firm's system and the custodian or clearing firm. It typically runs daily from end-of-day files with zero tolerance. Trade reconciliation matches at transaction level on security, quantity, price, trade date and settlement date, is often run T+1, and treats an unmatched transaction on either side as a break. — [claudeskills.info reconciliation skill (secondary, practitioner write-up)](https://claudeskills.info/skills/joellewis/finance_skills/reconciliation/)
- For futures, vendors describe splitting the work into intraday trade matching and an end-of-day step that identifies breaks in total open positions across exchange-traded products. — [Hedgeweek, Quintillion Q-Match for CTAs](https://hedgeweek.com/quintillion-launches-reconciliation-suite-q-match-cta-sector)
- One clearing-firm reconciliation tool compares prices, symbols and quantities and reports discrepancies, but "reconciliation of fees is not currently supported". Fees and commissions are often a separate reconciliation. — [PropReports Reconciliation Overview](https://propreports.atlassian.net/wiki/x/XAAJ)
- For commodity CTAs, administrators also reconcile the mark-to-market value of open commodity futures positions (open trade equity) to the clearing brokers, as a separate check from quantity. — [Hedgeweek](https://www.hedgeweek.com/?p=10186)
- A practitioner guide for agricultural hedging notes that prices and quantities should agree between internal records and the broker statement. The realized P&L section of a statement can show the originating price alongside the closing price, which helps trace differences. — [Agvance Help Center](https://agvancehelpcenter.knowledgeowl.com/home/pdfexport/id/621e98f511380d10127b2427)

**Exchange and clearing fields that serve as match keys (futures and options)**
- The MIAX Futures (MGEX) TRX clearing file specification carries fields useful for matching: opposite broker, trade price, quantity, account ID, give-up and allocation indicators, a give-up group ID and execution time. — [MIAX TRX file specification](https://miaxglobal.com/trx_file_specification.pdf)
- CME STP FIXML TradeCaptureReport carries:
  - **AllocInd:** values 0 to 5, plus 100 for an SGX offset. Value 1 means "allocation is required for a give-up trade, but allocation information was not provided (incomplete)".
  - **AvgPxInd:** 0 means no average pricing; 1 means the trade is in an average price group identified by SideAvgPxGroupID.
  - **GrpID2:** a clearing-assigned allocation group ID that ties together trades marked for allocation in the same group, plus the offset trades once the group's allocations are claimed.
  - Sample messages carry TrdID and ExecID attributes.
  — [CME STP FIXML TradeCaptureReport, Futures and Options](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/599196174/CME+STP+FIXML+-+TradeCaptureReport+-+Futures+and+Options); [CME TrdCapRptSideGrp](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/599064941); [CME Clearing Advisory 18-290](https://www.cmegroup.com/notices/clearing/2018/07/Chadv18-290.pdf)
- FIX instrument fields used for derivatives identity:
  - StrikePrice (202) is used for options and covered warrants.
  - ContractMultiplier (231): when used, quantities are expressed as contracts rather than shares.
  - SecurityExchange (207) identifies the market.
  - CFICode (461), not OptAttribute (206), indicates option type.
  - PutOrCall (201), StrikeMultiplier (967) and StrikeValue (968) also exist.
  — [FIXimate FIX 5.0 SP2 / 4.4 dictionary](https://fiximate.fixtrading.org/legacy/en/FIX.5.0SP2/body_50485051.html?find=Side); [OnixS FIX Instrument component](https://www.onixs.biz/fix-dictionary/latest/compBlock_Instrument.html); [B2BITS FIXopaedia Instrument block](https://www.b2bits.com/fixopaedia/fixdic50-sp2/block_Instrument.html)

**Give-ups and average pricing**
- FIA's best-practice recommendations for average pricing (indirect clearing) recognize the need to give up average-price trades across clearing members and position accounts. They describe the venue output as the original street fills, offsetting reversals, and one average-price trade. Trade fills should hold the original order ID and the client order reference. — [FIA Best Practice Recommendations for Average Pricing (indirect clearing)](https://fia.org/sites/default/files/2019-10/3%20%28i%29%20-%20Best%20Practice%20Recommendations%20for%20Average%20Pricing%20%28indirect%20clearing%29.pdf)
- FIA's standards body DMIST (formed 2022) published a final timeliness standard for give-ups and allocations in 2023. It sets 30-minute timeframes for steps in the allocation process, with defined start and stop points from order confirmation to trade booking. — [Mondo Visione, DMIST trade allocations standard](https://mondovisione.com/media-and-resources/news/fia-dmist-publishes-trade-allocations-standard-and-launches-consultation-on-av-2023615/); [The TRADE](https://www.thetradenews.com/fia-provides-three-recommendations-to-improve-trading-processes/)
- DMIST's average pricing consultation (June 2023; comment period extended to 12 October 2023) addressed inconsistent average-pricing functionality across CCPs, which delays give-ups and allocations and can force manual intervention. — [FIA, DMIST extends comment period](https://www.fia.org/fia/articles/dmist-extends-comment-period-average-pricing-standard); [FIA Operations Division comment](https://www.fia.org/ops-america/articles/fia-operations-division-comment-dmist-consultation-paper-average-pricing)
- The final DMIST Average Pricing Standard requires CCPs to adopt minimum average-pricing functionality. It contains a 16-point Functionality Table covering General Standards, Average Price Grouping and Cash Residuals, plus a roadmap for CCPs without on-CCP average pricing. — [A-Team Insight](https://a-teaminsight.com/?p=68738); [Regulation Asia (paywalled)](https://new.regulationasia.com/articles/fia-dmist-publishes-new-standards-on-average-pricing)
- CME Rule 553 lets clearing firms, in defined circumstances, confirm average prices when an order is executed at multiple prices. Source is a 2016 glossary entry. — [FIA search excerpt](https://www.fia.org/marketvoice/articles/fia-updates-standard-agreements-give-ups)
- CME STP data includes a residual price for APS transactions and a corresponding CashResidualAmount position type. The cash residual from rounding the average price is therefore a separate data item. — [OnixS CME STP Handler, PositionAmountType](https://ref.onixs.biz/net-cme-stp-handler-guide/p-onixs-cmestphandler-positionamountdata-positionamounttype.html)
- FIA's standard give-up agreement templates were last substantively revised in 2017. — [FIA, updates standard agreements for give-ups](https://www.fia.org/marketvoice/articles/fia-updates-standard-agreements-give-ups)
- At the LME, give-up matching depends on a customer code agreed by both members and entered in the public reference field of LMEMS. — [LME Rules on Give-Ups](https://www.lme.com/-/media/Files/Company/Market-regulation/Key-compliance-notices/Rules-Powers-and-Functions/00-383-A376-R010-Rules-on-LME-Give-Ups.pdf)
- In a Canadian give-up model, the executing broker sends its invoice to the clearing broker, which reconciles the give-up transactions against its own records. — [MB Securities documentation](https://docs.mbsecurities.ca/msc/oe/en/104556/1/document.do)
- A FIX Trading Community forum thread discusses how to report the actual average price for futures allocations, which signals that practice is not uniform. — [FIX forum](https://forum.fixtrading.org/t/reporting-the-actual-average-price-for-futures-allocations/11866)

**FX forwards**
- Oracle Treasury's MT300 confirmation-matching rules match on:
  - counterparty
  - booking (trade) date
  - value date
  - bought currency and amount
  - sold currency and amount
  - exchange rate
  - common reference

  The "Full Match" option makes counterparty, booking date, value date and bought currency/amount mandatory. — [Oracle Banking Treasury, Confirmation Rule Maintenance](https://docs.oracle.com/en/industries/financial-services/banking-treasury-management/14.7.3.0.0/trfxm/confirmation-rule-maintenance-details.html)
- MT300 covers FX forwards, NDFs and swaps. Its 2013 enhancements added structured fields for Dodd-Frank and EMIR trade reporting. — [SWIFT](https://www.swift.com/ja/node/309886)
- A 2007 NY Fed FXC/EMTA guide puts trade date in MT300 field 30T and the currency/amount legs in 32B/33B (NDF context). — [NY Fed FXC](https://www.newyorkfed.org/medialibrary/microsites/fxc/files/2007/fxc070629a.pdf)
- GFXD issued recommendations on populating MT300 fields 17F, 17O, 14S, 57 and 58. — [GFMA GFXD, 2020](https://www.gfma.org/wp-content/uploads/2020/07/20200716-gfxd-recommendations-for-fx-confirmations-swift-mt300-fields-17f-17o-14s-57-and-58.pdf)

### Inferences
- **Recommended exact match keys (normalized):**
  - Listed futures: [account, normalized instrument key (exchange MIC + product root + contract month/year), side, trade date].
  - Options on futures: add [put/call, strike normalized to a common price unit, expiry or contract month, exercise style where both sources carry it].
  - FX forwards: [counterparty/account, buy ccy, sell ccy, value date, trade date].
- **Tolerance-free comparison fields:** quantity and price for futures and options. For FX forwards, the notional on the dealt leg and the rate, with a small rounding allowance only on the derived contra amount. Rationale: Oracle's MT300 "Full Match" treats the bought amount as mandatory, and in background market practice the contra amount is computed from rate × notional.
- **Position recon as a second layer:** because brokers and clearers often report net positions per contract/account while internal systems keep lots, run a position reconciliation separately. Aggregate internal lots to (account, instrument) and compare net signed quantity exactly; this is the zero-tolerance position check described above. Then optionally compare average open price or mark-to-market (OTE).
- **Average-price/APS cases:** a deterministic engine should support a one-to-many link (one broker APS line to many internal fills). Bind the group with an explicit group key (AvgPx group ID, original order ID, or client order reference) where present. Check Σqty exactly and the VWAP of fills against the APS price. Allow a rounding allowance bounded by the tick or cash residual, and report the cash residual as a separate component rather than hiding it in a tolerance.
- **Give-ups and allocations:** match at the allocated (post-give-up) level to the clearing statement. Keep the executing-broker leg separately keyed by allocation group ID (e.g., CME GrpID2). Treat an AllocInd value of "incomplete" as its own exception type, not a quantity break.
- **Partial fills and splits:** internal systems may hold an order with child fills while the broker shows fills individually, or the reverse. A deterministic many-to-one pass grouped on (account, instrument, side, trade date, order ref) with an exact Σqty constraint handles most cases.

### Gaps
- Could not retrieve the full DMIST Average Pricing Standard text (16-point table), its effective date, or CCP adoption status.
- No authoritative published "standard match key" list for broker-statement reconciliation exists. Practice is platform and firm specific.
- Exercise style is rarely present on broker statements (inference). No source confirmed how commonly statements carry it.
- No source confirmed CME TrdID and ExecID semantics in prose.

## Q2. Normalization challenges and reference data standards

### Takeaway
Most matching failures are representation differences, not real economic breaks. The usual culprits are symbology (exchange, Bloomberg/Reuters and broker codes), month codes, price units and fractional displays, multipliers, date conventions and sign conventions. Normalize to a canonical instrument key built from exchange (MIC), product root, contract month/year and, for options, put/call and strike, and translate prices to a single unit. Standards (CFI, ISIN, FIGI, UPI, FIX/FIXML, ISDA CDM) help, but none covers every broker statement, so a maintained mapping table remains necessary.

### Cited Findings
**Month codes**
- Standard futures month letters: F Jan, G Feb, H Mar, J Apr, K May, M Jun, N Jul, Q Aug, U Sep, V Oct, X Nov, Z Dec. Sources disagree on whether the convention originated with Reuters and on how universal it is. — [Peter L. Brandt](https://www.peterlbrandt.com/symbols-months-futures-contracts/); [J. D. A. Wiseman](https://www.jdawiseman.com/papers/trivia/futures.html); [MRCI symbols](https://www.mrci.com/web/help-pages/symbols-codes-a-contracts.html)

**Price formats and units**
- CME Treasury futures are quoted in points and fractions of a point, with the increment varying by contract: 32nds for Bond and Ultra Bond, halves of 32nds for the 10Y and Ultra 10Y, quarters for 5Y and 3Y, eighths for 2Y. "116 and 27/32nds" can appear as 116.270 or 116-270, and "+" marks half-ticks. — [CME Treasury futures price rounding conventions](https://cmegroup.com/trading/interest-rates/files/treasury-futures-price-rounding-conventions-2020.pdf); [CME fractional pricing display examples](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457573111/Fractional+Pricing+-+Display+Examples)
- Instrument definitions expose main_fraction, sub_fraction and price_display_format. Corn at 498.25 (cents/bushel) displays as 498'2. — [Databento, fractional prices](https://databento.com/docs/examples/instrument-definitions/fractional-prices)
- Grain futures quote in cents per bushel: corn 442.0 means $4.42/bu. Dollar value per point differs from contract size: corn is $50 per point (cents) on 5,000 bu, consistent with the $12.50 quarter-cent tick. — [FlashAlpha, CME futures contract multipliers](https://flashalpha.com/articles/cme-futures-contract-multipliers-quote-conventions)

**FX value dates**
- Spot is T+2 for most pairs and T+1 for USD/CAD, USD/TRY, USD/PHP and USD/RUB. T+2 is computed per currency against each holiday calendar. — [Wikipedia, FX date conventions](https://en.wikipedia.org/wiki/Foreign_exchange_date_conventions)
- Forward dates roll from spot with modified following and end-of-month rules. — [Wikipedia, FX date conventions](https://en.wikipedia.org/wiki/Foreign_exchange_date_conventions)
- Platforms differ on holiday treatment. The CME/EBS calendar says trade dates are unaffected by currency holidays. NEX/OSTTRA says intervening USD holidays are "Good Local Days" that do not postpone the value date. — [CME EBS value date calendar](https://www.cmegroup.com/content/dam/cmegroup/documents/ebs_value-date-calendar.pdf); [OSTTRA SEF document](https://osttra.com/wp-content/uploads/2025/09/2019-07-sef-unexpected-event-impact.pdf)

**Reference data standards**
- **CFI (ISO 10962):**
  - Six-letter code describing an instrument's structure and function.
  - Assigned at issuance alongside an ISIN; normally does not change over the instrument's life.
  - First letter is the category: F = futures, O = listed options, H = non-listed/OTC options. FF = financial futures, FC = commodity futures. X = not applicable.
  - Current edition is ISO 10962:2021.

  — [ISO 10962:2021 catalogue](https://iteh.es/catalog/standards/iso/71b3a722-c42d-453a-9cfb-c53bafba2381/iso-10962-2021); [FIX Appendix 6-D](https://www.b2bits.com/fixopaedia/appendices/appendix_6-d.html); [Wikipedia ISO 10962](https://EN.wikipedia.com/wiki/ISO_10962)
- **FIGI:** a 12-character identifier with no embedded semantics; descriptive data sits in metadata. Covers futures and options. OpenFIGI's API supports derivative symbologies such as OPRA and OCC symbols and a unique ID for future options. — [OpenFIGI about FIGI](https://openfigi.com/about/figi); [OpenFIGI features](https://openfigi.com/about/features); [Bloomberg FIGI allocation rules](https://cdp.bloomberg.com/assets/local/figi-allocation-rules.pdf)
- **UPI and OTC ISIN (ANNA-DSB):**
  - The FSB designated the DSB as sole UPI provider.
  - The UPI service was scheduled to go live in July 2022.
  - G20 reporting mandates using the UPI rolled out through 2024 and 2025.
  - The OTC-derivative ISIN was designed to align with the UPI.
  - ANNA reports the DSB launched real-time OTC-derivative ISIN creation in full production on 5 December 2025.

  — [Markets Media, DSB UPI timeline](https://www.marketsmedia.com/derivatives-service-bureau-announces-upi-timeline); [ANNA-DSB consultation](https://www.anna-dsb.com/?p=31240); [ANNA response to DG FISMA, Aug 2025](https://anna-web.org/wp-content/uploads/2025/08/ANNA-response_DG-FISMA.pdf); [ANNA, Dec 2025](https://anna-web.org/?p=5082)
- **ISDA CDM:**
  - A standardized, machine-readable and machine-executable model of products and lifecycle events, now hosted at FINOS.
  - Pitched as reducing the reconciliation caused by firms representing lifecycle events differently.
  - "NOT an application in and of itself".
  - In October 2025 ISDA and Tokenovate launched a FINOS taskforce for a production-ready open-source CDM function library, starting with interest rate resets.

  — [FINOS CDM overview](https://cdm.finos.org/docs/cdm-overview); [Mondo Visione, Oct 2025](https://mondovisione.com/media-and-resources/news/isda-and-tokenovate-launch-taskforce-to-develop-smart-contract-framework-within-20251021/)
- **FIX:** ContractMultiplier (231) and CFICode (461) give a machine-readable way to carry multiplier and instrument class (see Q1). — [OnixS FIX Instrument](https://www.onixs.biz/fix-dictionary/latest/compBlock_Instrument.html)

### Inferences
- **Canonical instrument key design (recommended):**
  - Futures: `{MIC}|{product_root}|{YYYYMM}`.
  - Options on futures: `{MIC}|{product_root}|{underlying YYYYMM}|{P/C}|{strike_in_canonical_units}|{expiry_date}`.
  - FX forward: `{ccy_bought}|{ccy_sold}|{value_date}`, or an ordered pair plus a direction flag.

  Store the raw source code next to the key for lineage, and resolve broker codes such as "ZCZ6", "C Z26" or "CN Dec26" through a versioned symbology map. Handle single-digit years (Z6) with a decade-disambiguation rule anchored to the trade date.
- **Price normalization:** decode fractional displays (116-270, 498'2) into decimal points. Convert cents to dollars per unit using a per-product price-unit table. Compare in a single canonical unit. Compute notional as qty × multiplier × price only where needed.
- **Side/sign normalization:** convert B/S, Buy/Sell, +/- quantity and long/short to a single signed-quantity convention. For FX, express each deal as bought ccy/amt and sold ccy/amt so "EURUSD buy 10m" and "USD sell / EUR buy" reconcile.
- **Background standards (not verified in this session):**
  - ISO 10383 MIC for venue.
  - ISO 4217 for currency codes and minor-unit decimals; relevant to rounding.
  - ISO 17442 LEI for legal entities. Account/counterparty naming usually still needs an internal alias table because statements carry broker account numbers, not LEIs.
- **Where standards stop helping:** CFI is assigned with an ISIN, but many listed commodity futures are identified operationally by exchange code plus month rather than ISIN. A broker-code-to-exchange-code map is therefore unavoidable (inference from the CFI/ISIN coupling above).

### Gaps
- FIA statement-format standards for broker-to-client futures statements (e.g., FIA's former "standard file format" work) could not be retrieved or confirmed as current.
- I did not verify the exact CFI attribute positions for futures and options (e.g., what FFCPSX or OCAFPS encode).
- No source quantified how often symbology versus price-unit issues cause breaks.

## Q3. How reconciliation engines structure rules: tiers, cardinality, precedence, tolerances, ambiguity control and determinism

### Takeaway
Enterprise and open-source engines converge on a waterfall. Exact one-to-one rules run first, followed by progressively looser composite-key, tolerance and date-window rules, then one-to-many, many-to-one and many-to-many grouping rules, each with its own tolerance. Matched records leave the pool. Ambiguity is handled by marking matches "suggested" rather than "confirmed", or by prohibiting rules from firing when more than one candidate qualifies. Probabilistic (Fellegi-Sunter style) scoring exists in record linkage but is gated by thresholds and a manual-review band.

### Cited Findings
- A USPTO patent on reconciling financial transactions describes selecting matching rules "from the strictest to the least strict", each with its own tolerance, chaining one-to-many, many-to-one and many-to-many rules. — [USPTO patent 8103561](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8103561)
- Auto-reconciliation guidance: run exact matches before fuzzy logic or tolerance thresholds. Order is one-to-one exact, then many-to-one grouping, then exception and catch-all rules last. — [Aspire Systems, rule sequences](https://www.aspiresys.com/blog/oracle/erp-implementation/recommended-sequence-for-auto-reconciliation-rules-setup/)
- Oracle Account Reconciliation (Transaction Matching):
  - Supports 1-to-1, 1-to-many, many-to-1, many-to-many and adjustment rules.
  - Each rule produces "suggested" or "confirmed" matches, with variants that prohibit ambiguous results.

  — [Oracle, About Match Rules](https://docs.oracle.com/en/cloud/saas/account-reconcile-cloud/suarc/admin_trans_match_about_match_rules.html)
- Infor auto-reconcile: amount matching is one-to-one with exact amounts unless a tolerance is set. Differences within tolerance are reconciled and a distribution is posted for the difference. Many-to-many totals may not balance and may need manual intervention. — [Infor auto-reconcile](https://docs.infor.com/ss/6.3.x/en-us/ssolh/lsm1457708138608.html); [Infor detail recon match rules](https://docs.infor.com/ifsm/2025.x/en-us/ifsmolh/ifsmfinsetupag/zfa1557820017597.html)
- Open-source example (Reconcile.Net): an exact-reference pass first, then fuzzier passes using a composite key, an amount tolerance and a date window on what remains, plus one-to-many grouping (e.g., one payout covering many invoices minus fees). — [Reconcile.Net on NuGet](https://www.nuget.org/packages/Reconcile.Net)
- **Probabilistic matching (Splink / Fellegi-Sunter):**
  - Blocking rules limit candidate pairs.
  - Each comparison contributes a log-likelihood "partial match weight"; weights sum to a match score or probability.
  - Parameters are estimated by expectation-maximization without labelled data.
  - Classic Fellegi-Sunter uses two thresholds: match above the upper, non-match below the lower, and clerical review in between.

  — [UK Gov Data blog, Splink](https://dataingovernment.blog.gov.uk/2022/09/23/splink-fast-accurate-and-scalable-record-linkage/); [Real World Data Science, Splink case study](https://realworlddatascience.net/applied-insights/case-studies/posts/2023/11/22/splink.html); [US Census RR84-27](https://census.gov/content/dam/Census/library/working-papers/1984/adrm/rr84-27.pdf); [starling threshold-selection vignette](https://erised.las.iastate.edu/CRAN/web/packages/starling/vignettes/threshold-selection.Rmd)
- Electra Reconciliation 6.0 combines machine learning, research-data integration and a fuzzy-matching algorithm to speed root-cause analysis of trade breaks. This is a vendor announcement. — [Hedgeweek, Electra](https://www.hedgeweek.com/electra-adds-new-capabilities-reconciliation-platform/)
- One vendor-perspective blog recommends flagging ambiguous matches as "Review Required" instead of forcing a confident answer, and attaching the matching logic and a confidence class to every match. — [Confidence and audit trails in AI reconciliation (vendor blog)](https://portalint.lovable.app/writing/confidence-and-audit-trails-in-ai-reconciliation/)

### Inferences
- **Recommended deterministic tier structure** (synthesized from the waterfall sources):
  1. **T0:** shared unique reference (broker trade ID, exchange ExecID or TrdID, or internal ID echoed in the broker's client-ref field) plus full economic equality.
  2. **T1:** full composite key and exact economics (account, instrument key, side, trade date, qty, price).
  3. **T2:** composite key with a price rounding allowance of one tick or less, or a decimal-place difference.
  4. **T3:** many-to-one or one-to-many with exact Σqty and VWAP within one tick (APS, partial fills, splits).
  5. **T4:** position-level net agreement for whatever remains unmatched, which explains timing and aggregation residue.
  6. **Residual:** classified exceptions.

  Each tier only sees records not consumed by earlier tiers.
- **Ambiguity control:** within a tier, if a record has more than one candidate counterpart, do not auto-match. Either (a) mark it AMBIGUOUS, or (b) break the tie deterministically only when the candidates are economically interchangeable (identical key and economics, e.g., two identical 1-lot fills). In case (b), pair them by stable rank: sort both sides by (key, trade time, source row ID) and zip by row_number() within the key partition. This makes the output reproducible and auditable.
- **Determinism guarantees:**
  - Fixed rule order.
  - Pure functions for normalization.
  - Total ordering with a tie-breaker that always ends in an immutable source row ID.
  - One-to-one assignment by consuming matched IDs.
  - Versioned rule and reference-data snapshots stored with each run.
  - Run hashes, i.e. a hash of inputs plus config, so a rerun reproduces identical results.
- **Combinatorial grouping:** many-to-many subset-sum matching is combinatorially explosive. Restrict it to small blocks (same key, same day) with a cap on group size, or require an explicit group key (order ID, allocation group ID). Otherwise route the block to manual review; Infor notes many-to-many totals often need manual intervention.
- **Probabilistic scoring in an audit tool:** treat it as a suggestion layer outside the deterministic match set. Show partial weights for explainability, keep a review band, and require human confirmation, mirroring Oracle's "suggested vs confirmed" pattern.

### Gaps
- Could not fetch Oracle's full doc text for exact semantics of the "no ambiguous" variants.
- No vendor-neutral published benchmark compares tier designs.
- Did not find specific open-source libraries focused on trade (as opposed to cash or invoice) reconciliation beyond general record-linkage tools.

## Q4. Exception taxonomies, investigation workflows, break rates and root causes

### Takeaway
Breaks cluster into a small set of categories:
- unmatched on one side (missing or late booking, timing)
- quantity break
- price break
- date or value-date break
- instrument or static-data mismatch
- account or counterparty or SSI mismatch
- duplicates
- incomplete allocation or give-up
- ambiguous or grouped matches

Root causes are mostly upstream: manual booking, reference-data gaps, timing and late confirmations, partial fills and system integration failures. Reliable, publicly cited break-rate statistics for trade reconciliation are scarce. Most published "automation rates" are vendor marketing.

### Cited Findings
- **Break types and causes by stage:**
  - Front-to-back breaks are tied to partial fills, manual booking errors and system integration failures.
  - Firm-to-counterparty breaks commonly involve quantity discrepancies, price differences (especially OTC), settlement-date mismatches and SSI mismatches.
  - Firm-to-custodian breaks are tied to position reconciliation, unbooked trades and corporate actions.

  — [Operational risk skill (practitioner write-up, secondary)](https://skills.cat/skills/joellewis/finance-skills/operational-risk)
- Discrepancy sources cited by a vendor: manual booking, mismatched security masters, late counterparty confirmations and corporate actions. Reference-data gaps drive recurring static-data breaks; timing differences produce temporary breaks. — [Digiqt, trade break resolution agent (vendor)](https://digiqt.com/ai-agent/financial-services/trade-reconciliation/trade-break-resolution-ai-agent-for-trade-reconciliation-in-financial-services/)
- Root-cause review should determine whether a break came from a process deficiency, a technology issue, inadequate training or an individual's error. — [Operational risk skill](https://claudeskills.info/skills/joellewis/finance_skills/operational-risk/)
- Cash-break causes: valuation errors, errors in own cash balances, forward cashflow forecasting errors and trade booking errors. A break "shines a spotlight on a failure in an upstream process". — [The OTC Space](https://theotcspace.com/?p=172463)
- Clearing-specific exception: CME AllocInd=1 signals a give-up requiring allocation where allocation information was not provided (incomplete). — [CME STP FIXML TrdCapRptSideGrp](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/599064941)
- **Automation and break-rate figures (all low-grade evidence):**
  - A vendor argues headline "70% automation rate" figures mostly reflect easy matching; the remaining roughly 30% (exceptions, reversals, timing differences, multi-line matches) consumes most staff time. — [insightsoftware (vendor blog)](https://insightsoftware.com/resources/the-reconciliation-lie-why-most-ai-reconciliation-still-dumps-work-on-your-team/)
  - Citi says AI-based receivables matching typically needs three to four months to reach straight-through rates in the 90% range. This is receivables, not trades. — [Citi TTS, AI Machine Learning](https://www.citigroup.com/tts/solutions/receivables/assets/docs/AI-Machine-Learning.pdf)
  - Aggregator pages cite 85–95% straight-through match rates and 5–15% exception queues, attributed to IOFM/BlackLine. I could not verify these and do not recommend citing them. — [StealthAgents](https://stealthagents.com/research/ai-payment-reconciliation-automation-statistics-2026)
- **Manual reliance (adjacent sectors):**
  - AutoRek (Feb 2024): 84% of UK/US payment firms rely heavily on manual tasks and spreadsheets for reconciliation; 86% say their data lacks transparency and standardization. — [Financial IT](https://financialit.net/news/payments/86-payment-firms-say-their-data-lacks-transparency-and-standardization-needed)
  - AutoRek (2026): only 14% of insurers have fully integrated AI into financial operations. — [Business Wire, Feb 2026](https://www.businesswire.com/news/home/20260226381834/en)
- Gresham describes the investigation process (gathering context, resolving and documenting exceptions) as the main efficiency lever. — [Gresham blog](https://www.greshamtech.com/blog/improving-efficiency-in-the-reconciliation-investigation-process)

### Inferences
- **Recommended exception taxonomy codes:**

  | Code | Meaning |
  |---|---|
  | UNMATCHED_INTERNAL | Internal record with no broker counterpart |
  | UNMATCHED_BROKER | Broker record with no internal counterpart |
  | QTY_BREAK | Key matched; quantity differs |
  | PRICE_BREAK | Key matched; price outside zero or rounding allowance |
  | SIDE_BREAK | Side or sign mismatch |
  | DATE_BREAK | Trade or value date mismatch |
  | INSTRUMENT_MISMATCH | Symbology mapping missing or conflicting |
  | ACCOUNT_MISMATCH | Account or counterparty mapping missing or conflicting |
  | DUPLICATE_INTERNAL / DUPLICATE_BROKER | Same economics and reference appearing twice in one source |
  | MISSING_FIELD / PARSE_ERROR | Required field absent or unparseable |
  | AMBIGUOUS | More than one equally valid candidate |
  | GROUP_SUM_BREAK | Many-to-one where Σqty matches but VWAP or price does not, or the reverse |
  | ALLOC_INCOMPLETE | Give-up awaiting allocation |
  | POSITION_BREAK | Net position differs after trade-level matching |
  | FEE_BREAK | Fees or commissions differ, if in scope |

  Each exception should carry its rule tier, the candidate IDs considered and field-level diffs.
- **Separate representation from economics:** distinguish normalization failures (MISSING_FIELD, INSTRUMENT_MISMATCH) from economic breaks, so auditors can tell "data couldn't be compared" apart from "data disagrees".
- **Timing breaks** (e.g., late-day trades booked next day internally, or broker cut-off differences) can be auto-annotated by looking for the same economics within ±1 business day. Leave them as exceptions with a "probable timing" label rather than matching them.

### Gaps
- No credible, recent, public statistic on typical break rates for listed-derivatives broker reconciliation (e.g., percentage of trades breaking per day). Vendors cite match rates but methods are undisclosed.
- No authoritative industry taxonomy (ISDA/FIA/DTCC) of break categories was found.

## Q5. Where AI/ML is credibly applied versus where deterministic logic is insisted upon

### Takeaway
Credible AI/ML use in reconciliation sits around the matching core:
- suggesting matches and rules
- classifying root causes of breaks
- prioritizing and routing exceptions
- emerging agentic investigation

The confirmed match set is still produced by deterministic, auditable rules. Regulated institutions apply model-risk governance (SR 11-7 and OCC 2011-12) to ML, which pushes ML outputs into a "suggested, human-confirmed" role with audit trails.

### Cited Findings
- Electra Reconciliation 6.0 uses machine learning plus fuzzy matching to speed root-cause analysis of trade breaks for investment managers. — [Hedgeweek](https://www.hedgeweek.com/electra-adds-new-capabilities-reconciliation-platform/)
- SmartStream has announced agentic AI that investigates and resolves reconciliation exceptions autonomously, citing T+1 settlement and budget pressure. The coverage argues AI's highest returns are in predictable, data-rich post-trade workflows. — [Webull/news syndication](https://www.webull.com/news/15626383484142592)
- Xceptor positions AI around exception management and measuring automation value at scale (title-level evidence only; page could not be fetched). — [Xceptor blog](https://www.xceptor.com/blogs/scaling-reconciliation-operations-ai-exception-management-and-measuring-automation-value)
- Citi reports ML matching for receivables reaching around 90% straight-through after three to four months of pattern learning, and up to 80% less staff keying. This is vendor/bank marketing in an adjacent domain. — [Citi TTS](https://www.citigroup.com/tts/solutions/receivables/assets/docs/AI-Machine-Learning.pdf)
- Regulators expect ML models to meet SR 11-7 and OCC 2011-12. Validation covers conceptual soundness, process verification, ongoing monitoring and outcomes analysis. — [Protiviti, validating ML models](https://www.protiviti.com/sites/default/files/2022-04/validating-machine-learning-models-whitepaper-protiviti.pdf)
- EY flags the black-box nature of ML and lack of explainability as challenges under model-risk guidance. — [EY, MRM for AI/ML](https://ey.com/content/dam/ey-unified-site/ey-com/en-us/insights/banking-capital-markets/documents/ey-mrm-ai-ml.pdf)
- An FDIC AI RFI response says unresolved items should go to an operator, with an audit trail. — [FDIC 2021 AI RFI comment](https://www.fdic.gov/regulations/laws/federal/2021/2021-rfi-financial-institutions-ai-3064-za24-c-019.pdf)
- A vendor critique: many "AI reconciliation" products still leave the hard 30% (reversals, timing, multi-line) to humans. — [insightsoftware](https://insightsoftware.com/resources/the-reconciliation-lie-why-most-ai-reconciliation-still-dumps-work-on-your-team/)

### Inferences
- **Credible AI uses for an audit reconciliation tool:**
  - Column and header mapping of new broker statement layouts. Propose the mapping; a human confirms; the confirmed mapping is frozen as config.
  - Proposing symbology map entries (e.g., broker code to exchange product).
  - Explaining and classifying residual breaks (timing vs booking vs static data).
  - Drafting investigation notes.
  - Suggesting candidate pairs for AMBIGUOUS or unmatched items, with explicit scores.

  None of these should alter the deterministic match result without a recorded human decision.
- **Deterministic-only zone:** the matching rules, tolerances, tie-breaking and match status that feed audit evidence. Audit reproducibility requires identical outputs on rerun; this follows from the model-risk and audit-trail expectations above. LLM or ML outputs are non-deterministic, or at least version-sensitive.
- **Logging for AI suggestions:** model and version, prompt or feature inputs, output, confidence, reviewer and decision. This makes AI suggestions auditable artifacts rather than hidden logic.

### Gaps
- No rigorous 2023–2026 industry survey (e.g., from FIA, ISDA, DTCC or analyst firms) quantifying AI adoption specifically in derivatives reconciliation was retrievable.
- Evidence for agentic AI outcomes is announcement-level only.

## Q6. Scale and performance patterns (hundreds of thousands to millions of records)

### Takeaway
At 10^5–10^7 records, exact-key matching is a hash-join problem and runs in seconds on a single machine with columnar engines (DuckDB, Polars). Cost is driven by candidate generation for looser tiers, so use blocking keys (account + instrument + date) to keep the comparison space linear. Engines differ in speed and memory; benchmarks conflict and should be re-run on representative data.

### Cited Findings
- A single-author test on a 16 GB laptop: DuckDB 1.5.5 joined 300 M rows against a 5 M-row dimension in 1.72 s using 0.70 GB. Polars 1.44.1's default engine needed 10.5 GB for the same join; Polars runtime was not reported. Single run, single machine. — [Python in Plain English (Medium)](https://python.plainenglish.io/i-gave-a-16-gb-mac-a-26-gb-dataset-duckdb-answered-in-440-mb-of-ram-58db5f5acd4b)
- At 10 M rows, Polars completed 5 benchmark joins in 3.16 s versus 11.85 s for pandas and 10.46 s for DuckDB. With 50 M rows under a 5.84 GiB memory cap, pandas failed at load, Polars completed 9 of 10 queries and DuckDB all 10. — [Uvik, Polars vs pandas](https://uvik.net/blog/polars-vs-pandas/)
- Other comparative benchmarks of pandas, Polars, DuckDB and PySpark exist with mixed results by workload. — [Pipeline2Insights](https://pipeline2insights.substack.com/p/pandas-vs-polars-vs-duckdb-vs-pyspark-benchmarking-real-experiments); [The Data Toolbox](https://thedatatoolbox.substack.com/p/duckdb-vs-fireducks-vs-polars-which-one-is-the-fastest); [grantmcdermott/duckdb-polars](https://github.com/grantmcdermott/duckdb-polars)
- Splink uses blocking rules to restrict pairwise comparisons and runs on scalable SQL backends. Blocking is the standard method for keeping record linkage tractable. — [UK Gov Data blog, Splink](https://dataingovernment.blog.gov.uk/2022/09/23/splink-fast-accurate-and-scalable-record-linkage/)

### Inferences
- **Recommended execution pattern:**
  1. Normalize into typed columnar tables (Parquet or Arrow).
  2. Compute the canonical key and a hash of the economic fields.
  3. Run T0/T1 as equi-joins on (key, economic hash).
  4. Remove consumed IDs via anti-joins.
  5. For grouped tiers, aggregate with GROUP BY on the blocking key and join the aggregates.
  6. Use window functions, e.g. `row_number() over (partition by key order by trade_time, source_row_id)`, for deterministic pairing of interchangeable duplicates.
- **Engine choice:** DuckDB and Polars both handle millions of rows on one node. DuckDB's out-of-core behavior makes it safer under memory limits, per the cited benchmarks. Spark is only needed beyond single-node memory and disk, or for distributed pipelines.
- **Deterministic parallel execution:** never rely on implicit row order from parallel engines. Always apply an explicit ORDER BY with a unique tie-breaker before any "first match wins" logic. Parallel hash joins and aggregations do not guarantee output order.
- **Bounded many-to-many:** the grouped tiers need a per-block size cap (e.g., at most N candidates per side). Beyond it, mark the block for review rather than running subset-sum search.

### Gaps
- No public benchmark specific to trade reconciliation workloads (multi-tier matching with tolerances) was found.
- The cited engine benchmarks are single-author and version-specific, and conflict on Polars vs DuckDB join speed.
