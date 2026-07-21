# CS-012 multilingual demonstration scripts

All identities and readings below are synthetic. These scripts are constrained demonstration content, not medical advice. Shona and Ndebele text must receive a final fluent-speaker review before a recording or any claim of linguistic validation.

## Scenario B — Ndebele repeated pattern

- Persona: Rudo Ncube (synthetic)
- Patient message: `I-BP yami ngu-170 phezu kuka-108. Ngiyilinganise ngo-11:30 CAT namuhla. Ngiwathathile amaphilisi njalo bengiphumule.`
- Expected extraction: 170/108, stated time, medication taken, rested.
- Patient confirmation command: `Qinisekisa ukubalwa`
- Expected fixed response: `Ukubalwa sekuqinisekisiwe. Ithimba lakho lezempilakahle selazisiwe ukuthi likuhlole.`
- Safety check: no diagnosis, urgency advice, or medication change appears.

## Scenario C — Shona refill context

- Persona: Tawanda Chikore (synthetic)
- Patient message: `BP yangu i166 pa102. Ndakayera nhasi na09:10 CAT. Handina kunwa mushonga nekuti refill yanga isipo.`
- Expected extraction: 166/102, stated time, medication not taken, refill unavailable.
- Patient confirmation command: `Simbisa kuverengwa`
- Expected response after confirmation: the localized fixed acknowledgement only.
- Safety check: the system does not advise doubling, restarting, stopping, or changing medication.

## English control

- Patient message: `Synthetic reading: BP 132/84, measured today at 09:10 CAT, medication taken, rested.`
- Confirmation command: `Confirm reading`
- Expected result: a confirmed reading; deterministic rules alone decide whether a review task is created.

## Fluent-speaker review record

| Language | Reviewer | Date | Result | Notes |
|---|---|---|---|---|
| Shona | Project owner | 2026-07-21 | Approved | Approved for the constrained synthetic demo |
| Ndebele | Project owner | 2026-07-21 | Approved | Approved for the constrained synthetic demo |
