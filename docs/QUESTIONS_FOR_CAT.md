# Questions for the Caterpillar Representative

## How to use this

**Asking good questions is itself scored.** Most teams will ask "how many slides?" A question that shows you read the dataset row-by-row and know what VisionLink does marks you out before you have built anything.

Three rules:

1. **Lead with Tier 2 (domain) questions, not logistics.** Open with something that proves you did homework. Ask logistics last or over email.
2. **Never say "your dataset is broken."** Frame every data question as *"which interpretation do you want?"* — same answer, no defensiveness. You want them as an ally, not a defendant.
3. **Pick 5–6 for a live conversation.** Bring the rest in writing. Nobody answers 24 questions standing up.

If you only get one question, ask **Q1**. If you get two, ask **Q1 and Q23**.

---

## Tier 1 — Blocking. These change what we build.

**Q1. Idle hours semantics.** *(The most important question in this document.)*
> "In VisionLink, idle time is normally a subset of engine operating hours — engine running, machine not working. In the sample data, several rows have Idle Hours/Day greater than Engine Hours/Day, and two rows show engine hours of 0 with idle hours above 10. Should we read `Idle Hours/Day` as a **subset** of engine hours, or as **disjoint** time where the asset is sitting unused with the engine off?"

Why it matters: it inverts the meaning of utilization, and it decides whether three of the seven rows are anomalies or normal. We handle both readings, but their answer tells us which one to headline.

**Q2. Is data quality in scope?**
> "Should imperfect telemetry and incomplete records be treated as in-scope for the anomaly detection — the kind of thing a real dealer deals with daily — or should we assume clean, validated data and focus elsewhere?"

Why it matters: this is the diplomatic way to confirm the sample defects are fair game. If they say yes, our entire differentiator is explicitly sanctioned.

**Q3. Missing fields.**
> "The expected outcomes list fuel usage and location under Usage Logging, but the sample schema has neither — only a nullable Site ID. Is simulating those two acceptable, or will a richer dataset be provided?"

**Q4. The dates.**
> "Every record in the sample falls between January and May 2025, so no rental is currently active. Overdue and approaching-return alerts can't fire against the raw data. Are we expected to rebase the timeline onto a simulated current date?"

Why it matters: confirms the virtual clock is the intended reading rather than a workaround.

**Q5. Larger dataset?**
> "Will a larger or updated dataset be provided at the event or at judging? Should our ingestion be built to accept a different schema?"

**Q6. Billing authority.**
> "Where the stated Rental Days and the check-in/check-out date span disagree, which field is authoritative — the dates or the day count?"

Why it matters: it's a real question, and it quietly demonstrates you validated every row.

---

## Tier 2 — Domain credibility. These earn respect.

**Q7. Primary user.**
> "Is the intended primary user the Cat dealer or rental branch, or the customer renting the equipment? The brief says 'help companies,' but the dealer has the fleet-level problem."

**Q8. Relationship to shipped Cat products.** *(High-impact question.)*
> "VisionLink, Product Link, the Cat Rental Store portal and RentalMan already cover asset dashboards, usage logging, per-rental utilization and return alerts. Should we treat those as given and focus on what they don't do, or build the full stack standalone? And would duplicating existing functionality count against us?"

Why it matters: this single question tells you whether your entire strategy is correct, and it proves you researched the company rather than the prompt.

**Q9. SMU.**
> "Should we model hours as SMU — Service Meter Units — the way Cat systems do, or as the simple daily engine hours in the sample?"

**Q10. Rental lifecycle events.**
> "Should we model call-offs and extensions as first-class events? In the Cat Rental Store portal customers can self-serve call-offs and transfers, so it seems like the natural vocabulary."

**Q11. Cross-dealer scope.**
> "Rental fleets are dealer-owned. If one branch has an idle machine and another has unmet demand, is redeployment across dealer boundaries in scope, or should we stay inside a single branch's fleet?"

Why it matters: this is a real commercial constraint most teams won't know exists. Their answer decides whether `MOD-12` ships.

**Q12. Utilization definition.**
> "Which utilization measure do dealers actually get judged on — time utilization (days on rent over days available), or financial utilization? We want our headline KPI to be the one that matters to you."

**Q13. Misuse thresholds.**
> "What idle level would a dealer genuinely consider misuse rather than normal site behaviour? And what can they actually do about it contractually?"

**Q14. Unaccounted equipment — the real process.** *(Best question for the pitch.)*
> "When a machine genuinely goes unaccounted for today, what's the escalation process, and how long does it typically take before anyone notices?"

Why it matters: their answer becomes a number on your slide. *"Today this takes N weeks to detect. We detect it in one screen."* That line is worth more than a feature.

**Q15. Rates.**
> "Are rental rates tiered by day, week and month? Can you give us a realistic ballpark for day rate and inter-site transport cost by machine class, so our cost figures aren't invented?"

---

## Tier 3 — Logistics. Ask last, or by email.

**Q16.** What's the evaluation rubric and its weighting — working demo, innovation, business value, technical depth, presentation?
**Q17.** How long is the demo and pitch? Is there Q&A, and is the panel engineering, business, or both?
**Q18.** Is venue internet reliable enough to depend on during the demo? Are external API calls acceptable?
**Q19.** The brief mentions using our own intelligence alongside AI. Are AI coding assistants permitted, and do you want us to disclose where we used them?
**Q20.** Is the deck submitted before the demo? Is there a template or slide limit?
**Q21.** Is a deployed public URL required, or is a local demo acceptable?
**Q22.** Who owns the IP of submissions?

---

## The two closing questions

Ask these at the end of any conversation with a judge or mentor. They are the highest-yield questions in this document.

**Q23.**
> "Of the seven expected outcomes, which two matter most commercially to Caterpillar?"

This is prioritization intelligence straight from the source. If the answer is forecasting and anomaly detection, our strategy is confirmed. If it's something else, we still have time to shift emphasis.

**Q24.**
> "What would make you say a team genuinely understood this problem, rather than just building the feature list?"

Ask it, then write the answer down verbatim. It is the rubric behind the rubric — and it tells you exactly what to say in your closing line.
