# Data 360 & Agent Grounding — Data Architecture

> Sources: [Salesforce Data 360 Architecture](https://developer.salesforce.com/docs/data/data-cloud-dev/guide/dc-architecture.html), [Trailhead Data Cloud for Agentforce](https://trailhead.salesforce.com/content/learn/modules/data-cloud-powered-agentforce/), [Salesforce Architect](https://architect.salesforce.com/fundamentals/data-360-architecture)
> Content was rephrased for compliance with licensing restrictions.

## Data 360 Overview

Data 360 (formerly Data Cloud) is the real-time data engine that unifies fragmented data from Salesforce and external systems into trusted profiles. It powers every Agentforce agent with context — agents are only as good as the data they can access.

## Data 360 Architecture for Agentforce

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA 360 PLATFORM                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                     DATA INGESTION LAYER                      │     │
│  │                                                               │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │     │
│  │  │Salesforce│ │ External │ │ Zero-Copy│ │ Unstructured   │  │     │
│  │  │CRM Data  │ │ APIs     │ │ from     │ │ Data           │  │     │
│  │  │          │ │ (MuleSoft│ │ Warehouse│ │ (PDFs, Slack,  │  │     │
│  │  │ Accounts │ │  REST)   │ │ /Lake    │ │  Teams msgs)   │  │     │
│  │  │ Contacts │ │          │ │          │ │                │  │     │
│  │  │ Cases    │ │ ERP, HR  │ │ Snowflake│ │ Knowledge      │  │     │
│  │  │ Opps     │ │ Billing  │ │ BigQuery │ │ Articles       │  │     │
│  │  │ Custom   │ │ Telemetry│ │ Redshift │ │                │  │     │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬────────┘  │     │
│  │       └─────────────┴────────────┴───────────────┘            │     │
│  └───────────────────────────────┬───────────────────────────────┘     │
│                                  │                                      │
│  ┌───────────────────────────────┴───────────────────────────────┐     │
│  │                   DATA PROCESSING LAYER                       │     │
│  │                                                               │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │     │
│  │  │  Identity    │  │  Data        │  │  Calculated      │   │     │
│  │  │  Resolution  │  │  Transforms  │  │  Insights        │   │     │
│  │  │              │  │              │  │                   │   │     │
│  │  │  Match &     │  │  Clean,      │  │  Segments,       │   │     │
│  │  │  merge       │  │  normalize,  │  │  scores,         │   │     │
│  │  │  records     │  │  enrich      │  │  predictions     │   │     │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │     │
│  └───────────────────────────────┬───────────────────────────────┘     │
│                                  │                                      │
│  ┌───────────────────────────────┴───────────────────────────────┐     │
│  │                   UNIFIED PROFILE LAYER                       │     │
│  │                                                               │     │
│  │  ┌─────────────────────────────────────────────────────┐     │     │
│  │  │              UNIFIED CUSTOMER PROFILE                │     │     │
│  │  │                                                      │     │     │
│  │  │  360° view: CRM + external + unstructured data      │     │     │
│  │  │  Real-time updates                                   │     │     │
│  │  │  Golden record (with Informatica MDM)               │     │     │
│  │  │  Data lineage & provenance                          │     │     │
│  │  └─────────────────────────────────────────────────────┘     │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                   ACTIVATION LAYER                            │     │
│  │                                                               │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │     │
│  │  │ Vector   │  │ Data Graphs  │  │ Prompt Builder         │ │     │
│  │  │ Search   │  │              │  │ Integration            │ │     │
│  │  │          │  │ Multi-object │  │                        │ │     │
│  │  │ Semantic │  │ JSON view    │  │ Merge fields pull      │ │     │
│  │  │ retrieval│  │ of customer  │  │ real-time data into    │ │     │
│  │  │ for RAG  │  │ data         │  │ prompt templates       │ │     │
│  │  └────┬─────┘  └──────┬───────┘  └───────────┬────────────┘ │     │
│  │       └───────────────┼──────────────────────┘               │     │
│  └───────────────────────┼───────────────────────────────────────┘     │
│                          │                                              │
└──────────────────────────┼──────────────────────────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │   AGENTFORCE AGENT       │
              │                          │
              │   Atlas Reasoning Engine  │
              │   uses Data 360 for:     │
              │                          │
              │   • Context grounding    │
              │   • Knowledge retrieval  │
              │   • Customer 360 view    │
              │   • Real-time signals    │
              └──────────────────────────┘
```

## Two Layers of Data 360 for Agentforce

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  LAYER 1: ENABLEMENT                                        │
│  (Required foundation — turn on Data 360)                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  • Enable Data Cloud in your org                    │    │
│  │  • Configure Einstein Trust Layer                   │    │
│  │  • Set up data streams from source systems          │    │
│  │  • Define data model objects (DMOs)                 │    │
│  │  • Configure identity resolution rules              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  LAYER 2: IMPLEMENTATION                                    │
│  (Agent-specific data configuration)                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  • Create Data Graphs for agent context             │    │
│  │  • Configure vector search indexes                  │    │
│  │  • Build prompt templates with merge fields         │    │
│  │  • Set up RAG pipelines for knowledge retrieval     │    │
│  │  • Define data access permissions per agent         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Graph → Agent Prompt Flow

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
  │  Account     │     │  DATA GRAPH  │     │  PROMPT TEMPLATE │
  │  Contact     │────►│              │────►│                  │
  │  Cases       │     │  Single JSON │     │  {!DataGraph.    │
  │  Opportunities│     │  structure   │     │   AccountName}   │
  │  Financial   │     │  with all    │     │                  │
  │  Accounts    │     │  related     │     │  Merge fields    │
  │  Transactions│     │  records     │     │  inject real     │
  └──────────────┘     └──────────────┘     │  customer data   │
                                            └────────┬─────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │  ATLAS REASONING │
                                            │  ENGINE          │
                                            │                  │
                                            │  Grounded,       │
                                            │  personalized    │
                                            │  response        │
                                            └──────────────────┘
```
