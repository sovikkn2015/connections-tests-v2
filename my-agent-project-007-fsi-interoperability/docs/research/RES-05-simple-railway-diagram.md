# Project 007: The FSI Railway — Simple Diagram

> The whole thing on one page.

---

```
╔══════════════════════════════════════════════════════════════════════╗
║                    THE FSI RAILWAY — SIMPLE MAP                     ║
╚══════════════════════════════════════════════════════════════════════╝


                         P L A T F O R M S
            (where people board — channels they already use)

    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │ Slack  │ │WhatsApp│ │  Web   │ │Bloombg │ │ Teams  │
    └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
        └──────────┴──────────┴─────┬────┴──────────┘
                                    │
                              ┌─────┴─────┐
                              │  TICKET   │
                              │  GATE     │
                              │ (who are  │
                              │  you?)    │
                              └─────┬─────┘
                                    │
                              ┌─────┴─────┐
                              │  SWITCH   │
                              │  YARD     │
                              │ (what do  │
                              │  you need?)│
                              └──┬──┬──┬──┘
                     ┌───────────┘  │  └───────────┐
                     │              │              │
                     ▼              ▼              ▼

═══════════════════════════════════════════════════════════════════════
                        5   L I N E S
═══════════════════════════════════════════════════════════════════════

LINE 1 ━━ RESEARCH EXPRESS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Deep dive on NVIDIA"
●━━━━●━━━━●━━━━●━━━━●━━━━●━━━━●
     SEC   Mkt   News  LLM  Brief  CRM
     EDGAR Data        Synth      Publish

LINE 2 ━━ CLIENT SERVICE LOCAL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Prep me for Henderson meeting"
●━━━━●━━━━●━━━━●━━━━●━━━━●
     CRM   Port- Plan  LLM  Deliver
           folio ning  Synth

LINE 3 ━━ COMPLIANCE INSPECTOR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Any MNPI violations this week?"
●━━━━●━━━━●━━━━●━━━━●
     Restr MNPI  Audit Report
     List  Track Log

LINE 4 ━━ EXECUTION EXPRESS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Trim Henderson's NVDA by 30%"
●━━━━●━━━━██████━━━━●━━━━●━━━━●
     Compl HITL      Exec  Conf  CRM
     Check GATE      ute   irm   Update
           (STOP!)

LINE 5 ━━ ONBOARDING & KYC ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Run KYC on new prospect Jane Smith"
●━━━━●━━━━●━━━━●━━━━██████━━━━●
     KYC   Sanc- Risk HITL      Acct
     Scrn  tions Score GATE     Open
                      (STOP!)

═══════════════════════════════════════════════════════════════════════
                     S T A T I O N S
            (enterprise systems — already installed)
═══════════════════════════════════════════════════════════════════════

  RESEARCH          CLIENT DATA        COMPLIANCE       EXECUTION
  ┌─────────┐       ┌─────────┐       ┌─────────┐     ┌─────────┐
  │Bloomberg│       │Salesforce│       │  NICE   │     │   FIX   │
  │FactSet  │       │  FSC    │       │Actimize │     │ Bridge  │
  │SEC EDGAR│       │Orion    │       │Smarsh   │     │Schwab   │
  │Morningst│       │Envestnet│       │RIA Box  │     │Fidelity │
  │News     │       │Aladdin  │       │ComplySci│     │Pershing │
  │MSCI     │       │Eze      │       │         │     │MuleSoft │
  │         │       │Wealthbox│       │         │     │iRebal   │
  │         │       │eMoney   │       │         │     │SWIFT    │
  └─────────┘       └─────────┘       └─────────┘     └─────────┘

  Each station = 1 MCP server wrapping 1 vendor system
  Enterprise picks which stations to connect (5-8 per firm)
  New station = new MCP server, zero agent changes

═══════════════════════════════════════════════════════════════════════
                     S I G N A L S
              (trust engine — at every junction)
═══════════════════════════════════════════════════════════════════════

  ● GREEN    Proceed. Authorized. Compliant.
  ● YELLOW   Caution. Flagged but allowed. Log extra.
  ● RED      Stop. Not authorized. Blocked. Logged.
  █ HITL     Stop. Human must approve. No exceptions.

  Same junction, different signal per archetype:

  "Access holdings"  ->  Bank: RED (Chinese wall)
                         AM: YELLOW (check restricted list)
                         Wealth: GREEN (own client)
                         RIA: GREEN (fiduciary)
                         HF: RED (pod isolation)

═══════════════════════════════════════════════════════════════════════
                     T I C K E T S
              (agent identity — who can go where)
═══════════════════════════════════════════════════════════════════════

  ┌──────────────────────────────────────────────────────┐
  │ TICKET: Sarah Chen, Advisor, Tier 3                  │
  │ Lines: 1,2,3(own),4(HITL),5                          │
  │ Stations: SF, Orion, eMoney (own clients)            │
  │ Cannot: other advisors' clients, trades without HITL │
  ├──────────────────────────────────────────────────────┤
  │ TICKET: Mike Torres, CCO, Tier 3                     │
  │ Lines: 3(ALL clients, ALL agents), 1(read-only)      │
  │ Stations: Audit logs, restricted list, Smarsh (all)  │
  │ Cannot: execute trades, access financial plans       │
  ├──────────────────────────────────────────────────────┤
  │ TICKET: James Park, PM, Tier 5, Pod Alpha            │
  │ Lines: 1, 4(HITL)                                    │
  │ Stations: Bloomberg, Eze (Pod Alpha ONLY)            │
  │ Cannot: other pods, firm-wide positions, LP data     │
  └──────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
                  T H E   K E Y   I D E A
═══════════════════════════════════════════════════════════════════════

  The stations already exist (Salesforce, Orion, Bloomberg...).
  The passengers already exist (advisors, analysts, PMs...).
  The rules already exist (FINRA, fiduciary, Chinese walls...).

  What's missing is the RAILWAY.

  007 is the railway.

  ┌──────────────────────────────────────────────────────┐
  │                                                      │
  │  Tracks  = MCP protocol (standardized gauge)         │
  │  Signals = Trust engine (the moat — nobody has this) │
  │  Tickets = Agent identity (encoded authority)        │
  │  Lines   = Specialized agent routes                  │
  │  Stations= MCP servers wrapping existing systems     │
  │                                                      │
  │  Build the signals first. Everything else is         │
  │  plumbing.                                           │
  │                                                      │
  └──────────────────────────────────────────────────────┘
```
