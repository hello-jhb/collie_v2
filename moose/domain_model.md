Moose Domain Model v0.2

Purpose

The Moose Domain Model defines how Moose understands commercial real estate investment work.

It is not a software architecture document. It is the conceptual model that agents, prompts, schemas, routing logic, verification rules, and reasoning modules should share.

Moose should not begin with documents. Moose should begin with the work the document supports.

⸻

Core Principle

Commercial real estate investment work is not organized around file types.

It is organized around investment lifecycle, decision scope, functional work, initiatives, documents, evidence, verified facts, and judgment.

A document is only one artifact produced by work.

Moose should interpret every uploaded file through this hierarchy:

Investment Lifecycle
  → Decision Layer
  → Functional Work
  → Initiative
  → Document
  → Evidence
  → Claim
  → Verified Fact
  → Reasoning
  → Recommendation

⸻

1. Investment Lifecycle

The lifecycle describes where the asset or investment is in time.

Acquisition

Work related to evaluating and acquiring an investment.

Common activities:

* deal sourcing
* market analysis
* underwriting
* due diligence
* investment committee approval
* financing
* closing

Development / Value Creation

Work related to creating or improving value.

Common activities:

* development
* redevelopment
* renovation
* repositioning
* lease-up
* capital improvement
* stabilization

Operations / Ownership

Work related to owning and operating the asset.

Common activities:

* business plan execution
* budgeting
* leasing
* property management oversight
* capital project oversight
* cash flow management
* debt management
* reporting
* valuation

Disposition

Work related to exiting an investment.

Common activities:

* hold/sell analysis
* market comps
* broker opinion of value
* broker selection
* offering memorandum / marketing
* LOI review
* PSA negotiation
* buyer due diligence
* closing

⸻

2. Decision Layer

The decision layer describes the scope at which a decision is being made.

Moose should reason about decision scope, not company org charts. Different companies organize teams differently, but the decision layers are relatively stable.

Fund

Decisions about the investment vehicle.

Examples:

* fund strategy
* capital deployment
* distributions
* NAV
* investor reporting
* fund governance

Portfolio

Decisions across multiple assets.

Examples:

* portfolio performance
* capital allocation
* risk concentration
* asset prioritization
* market / sector exposure
* portfolio reporting

Asset

Decisions about a specific investment or property ownership position.

Examples:

* business plan
* budget
* leasing strategy
* refinance
* capital project
* hold/sell
* valuation

Property

Decisions about day-to-day property operations.

Examples:

* maintenance
* vendor oversight
* tenant service
* building operations
* collections
* compliance

Transaction

Decisions related to executing a transaction.

Examples:

* acquisition
* disposition
* financing
* refinancing
* recapitalization
* closing

Transaction decisions often overlap with fund, portfolio, and asset decisions.

⸻

3. Functional Work

Functional work represents the professional discipline being performed.

Initiatives belong under functional work. For example, refinancing is an initiative under debt management; annual budget is an initiative under budgeting; broker selection is an initiative under transaction management or vendor selection.

Acquisition / Transaction Management

Purpose:
Evaluate and execute acquisition or disposition transactions.

Common functional work:

* deal sourcing
* market analysis
* underwriting
* due diligence
* investment committee preparation
* financing coordination
* transaction execution
* LOI review
* PSA review
* closing coordination

Common initiatives:

* acquisition process
* disposition process
* broker selection
* lender selection
* investment committee approval
* due diligence review
* closing

Common documents:

* offering memorandum
* financial model
* investment memo
* due diligence tracker
* appraisal
* loan term sheet
* LOI
* PSA
* closing statement

⸻

Asset Management

Purpose:
Own the investment outcome during the hold period.

Common functional work:

* business planning
* budgeting
* financial performance analysis
* leasing oversight
* property management oversight
* capital project oversight
* cash flow management
* debt management
* market intelligence
* reporting
* valuation
* risk monitoring

Common initiatives:

* annual business plan
* annual budget
* quarterly reforecast
* budget vs actual review
* leasing campaign
* lease renewal program
* tenant retention initiative
* capital project
* refinancing
* lender reporting
* valuation update
* hold/sell review
* property manager review
* insurance renewal
* tax appeal

Common documents:

* business plan
* budget workbook
* operating statement
* variance report
* rent roll
* leasing report
* property management report
* capital project tracker
* refinance model
* appraisal
* lender package
* valuation memo
* asset management report

⸻

Property Management

Purpose:
Operate the property day to day.

Common functional work:

* tenant relations
* building operations
* maintenance
* collections
* service requests
* vendor oversight
* compliance
* operating reporting

Common initiatives:

* tenant satisfaction program
* maintenance project
* vendor selection
* service contract renewal
* CAM reconciliation
* collections campaign
* compliance review
* utility optimization

Common documents:

* property management report
* work order report
* delinquency report
* AR aging
* service contract
* vendor proposal
* inspection report
* CAM reconciliation
* utility report

⸻

Portfolio Management

Purpose:
Manage performance, risk, and capital allocation across assets.

Common functional work:

* portfolio performance monitoring
* asset prioritization
* capital allocation
* risk concentration analysis
* market exposure analysis
* scenario planning
* portfolio reporting
* strategic planning

Common initiatives:

* quarterly portfolio review
* capital allocation review
* risk review
* market exposure review
* portfolio valuation update
* disposition prioritization
* strategic plan

Common documents:

* portfolio dashboard
* asset summary
* portfolio report
* valuation rollforward
* market exposure report
* risk report
* capital allocation memo

⸻

Fund Management

Purpose:
Manage the fund vehicle and investor obligations.

Common functional work:

* fund strategy
* capital raising
* capital deployment
* investor reporting
* NAV management
* distributions
* fund accounting
* fund governance

Common initiatives:

* capital raise
* capital call
* distribution
* investor reporting
* NAV update
* audit
* fund valuation
* advisory committee / board reporting

Common documents:

* fund model
* investor report
* capital call notice
* distribution notice
* fund financial statements
* NAV package
* audit report
* advisory committee materials

⸻

Vendor / Advisor Selection

Purpose:
Select and oversee third-party parties who contribute to execution.

This work may occur inside acquisition, asset management, property management, portfolio management, or fund management.

Common functional work:

* scope definition
* RFP preparation
* proposal review
* vendor comparison
* fee analysis
* contract negotiation
* performance oversight

Common initiatives:

* investment sales broker selection
* leasing broker selection
* property manager selection
* general contractor selection
* architect selection
* engineer selection
* environmental consultant selection
* ESG consultant selection
* insurance broker selection
* tax consultant selection
* legal counsel selection
* technology vendor selection

Common documents:

* RFP
* proposal
* fee schedule
* scope of work
* vendor comparison
* service agreement
* engagement letter
* performance report

⸻

4. Initiatives

Initiatives are specific business efforts that occur within functional work.

They are not the top-level organizing principle. They are contextual actions under functional work.

Examples:

* acquisition process
* disposition process
* annual budget
* annual business plan
* leasing campaign
* lease renewal program
* refinancing
* capital project
* tax appeal
* insurance renewal
* vendor selection
* monthly reporting
* quarterly portfolio review
* investor reporting
* NAV update
* hold/sell review

Each initiative should declare:

* parent functional work
* lifecycle stage
* decision layer
* expected documents
* expected evidence
* likely outputs

⸻

5. Documents

Documents are artifacts produced by functional work and initiatives.

Moose should classify documents by purpose and authority, not just file format.

Each document type should declare:

* purpose
* likely formats
* parent functional work
* related initiatives
* lifecycle stage
* decision layer
* authoritative information
* expected evidence
* recommended pipeline

Example document types:

* financial model
* operating statement
* rent roll
* lease
* loan agreement
* appraisal
* offering memorandum
* investment memo
* business plan
* budget workbook
* variance report
* property management report
* leasing report
* capital project tracker
* portfolio report
* investor report
* fund model
* NAV package
* RFP
* vendor proposal
* service agreement

⸻

6. Evidence

Evidence is information found inside documents.

Examples:

* metrics
* assumptions
* clauses
* dates
* parties
* obligations
* risks
* explanations
* comments
* relationships
* trends

Evidence is not automatically trusted.

⸻

7. Claims

Claims are structured interpretations of evidence.

Examples:

* Purchase Price = $25.5M
* Debt Amount = $14.0M
* Occupancy = 94%
* Lease expires on 2028-12-31
* The loan has a floating interest rate
* Budget assumes 3% rent growth
* NOI is below budget due to occupancy decline

Every claim must include:

* claim type
* value or assertion
* source document
* source location
* evidence quote or cell reference
* confidence
* reasoning
* extraction method

⸻

8. Verified Facts

A claim becomes a verified fact only after the Trust Engine validates it.

The Trust Engine is code-based verification, not a GPT agent.

Verification should evaluate:

* grounding: does the cited evidence exist?
* value match: does the cited value match the claim?
* identity: is the metric or clause correctly identified?
* authority: is this the right source?
* consistency: does it reconcile with related facts?
* unit / scale: are units interpreted correctly?
* contradiction: does another source disagree?

Verification statuses:

* verified
* verified_with_caveat
* needs_review
* contradicted
* rejected

Only verified or caveated facts should be used for reasoning.

⸻

9. Reasoning

Reasoning combines verified facts to answer professional questions.

Examples:

* How are we tracking?
* What changed?
* Why did it change?
* Is the business plan working?
* Is refinancing feasible?
* Is basis attractive?
* Is the lease risk material?
* Should this asset be prioritized?
* What action is needed?

Reasoning should always reference verified facts.

⸻

10. Recommendations

Recommendations are Moose’s action-oriented conclusions.

A recommendation should include:

* conclusion
* supporting verified facts
* risks
* caveats
* suggested next step
* confidence
* open questions

Moose should not provide recommendations based on unverified claims.

⸻

11. Relationship to Metric Catalog

The Domain Model does not replace the metric catalog.

The Domain Model answers:

* What work is being performed?
* What decision is being supported?
* What documents matter?
* What evidence should be expected?

The Metric Catalog answers:

* Which metric is this?
* What aliases identify it?
* What units are expected?
* What validation rules apply?
* What formulas or reconciliations verify it?

The Metric Catalog should attach to the Evidence and Claim layers of the Domain Model.

⸻

12. Operating Rule for Agents

All Moose agents should follow this rule:

1. Identify the document.
2. Map it to lifecycle, decision layer, functional work, and initiative.
3. Extract claims only within that context.
4. Send claims to the Trust Engine.
5. Reason only from verified facts.

GPT may interpret.

Code must verify.

GPT may reason only after verification.