# Earlier additional-recording test

This supporting record retains the table and detailed explanation moved from the main AEA manuscript on 14 November 2026. It was Table 2 before relocation. The table numbers in the current manuscript may differ.

The presentation change preserves every original result, first-delivery count and interval. It does not rerun models, EEG processing, scoring or interval calculations. The original manuscript section is retained in [original-main-text.tex](original-main-text.tex).

## Original 120-session comparison

Before the final two maintenance repairs, the 8 November resource snapshot was evaluated on 20 requests using ten additional EEG records from EEG During Mental Arithmetic Tasks and Mumtaz 2016. Three paired repetitions produced 120 first deliveries, with 60 per condition. These EEG records were absent from retained earlier project model runs. Both data sources and all 19 task families had been used previously. The protocol used Haiku 5.5 with disabled thinking and medium effort.

Result-field correctness was the prespecified primary endpoint. Differences and approximate 95% crossed task-family/EEG-record intervals are in percentage points.

| Endpoint | With AEA | Without AEA | Difference | Approximate 95% interval |
| --- | --- | --- | --- | --- |
| Result fields (primary) | 57/60 | 52/60 | +8.33 | -13.09 to 38.79 |
| Complete contract | 57/60 | 44/60 | +21.67 | -4.64 to 48.72 |

Both differences were positive, but both intervals included zero. The prespecified improvement criterion was not met.

The three AEA result-field failures comprised two sample-entropy calculations with mismatched template positions and one correct variance ranking delivered with shortened channel names.

The unchanged [result summary](records/original-120/RESULTS.json), [120 session rows](records/original-120/RUN_METRICS.csv), [frozen protocol](records/original-120/PROTOCOL_FROZEN.json), [independent counts](records/original-120/INDEPENDENT_COUNT_CHECK.json), [final acceptance](records/original-120/FINAL_ACCEPTANCE.json) and [environment record](records/original-120/ENV_REUSE.json) accompany this table.

## Separate 12-session engineering retest

After routing the affected tasks through the checked execution entry, a separate engineering retest used the two known requests with three fresh paired repetitions. Both conditions passed 6/6 result-field and deterministic-contract checks. All six AEA sessions actually invoked the repaired entry. No additional model judge or generalized-effect interval was computed for this engineering check. These sessions do not replace or alter any of the original 120 first deliveries.

The unchanged [result summary](records/engineering-12/RESULTS.json), [12 session rows](records/engineering-12/RUN_METRICS.csv), [frozen protocol](records/engineering-12/PROTOCOL_FROZEN.json), [independent counts](records/engineering-12/INDEPENDENT_COUNT_CHECK.json), [final acceptance](records/engineering-12/FINAL_ACCEPTANCE.json) and [environment record](records/engineering-12/ENV_REUSE.json) retain the engineering evidence separately.

## Sampling and analysis methods

Five healthy eyes-closed Mumtaz 2016 EEG records and five EEG During Mental Arithmetic Tasks records were selected by ascending identifier before new reference values or model outputs were available. Each record supplied two requests. The unavailable Mumtaz H S18 file was replaced by H S21 with researcher approval before execution. The schedule, resource snapshot and protocol were frozen before the first session.

The 120-session comparison retained the 8 November repair snapshot. Models, scientific plans, numerical environment, paired allocations and acceptance rules matched that repair retest. The result-field endpoint and complete contract remained separate. Effects averaged three paired differences within each request and then weighted the twenty requests equally. Approximate 95% intervals used 10,000 crossed task-family/EEG-record draws and seed 20261029. The prespecified criterion required a positive effect and positive lower interval endpoint.

The subsequent engineering retest addressed two affected requests with six fresh sessions per condition. Both received the original scientific settings in explicit machine-readable form. AEA additionally supplied the repaired entry and relevant procedures, including the existing common-template sample-entropy helper. Settings remained Haiku 5.5, disabled thinking, medium effort and MNE 1.8.0, with 1 CPU and 4 GiB per condition. The unchanged independent verifier checked first-delivery results and arrays. Function traces, executed code, saved source copies and successful self-checks established entry use. No model judge or interval estimation was used. The engineering deliveries were not pooled with or substituted for earlier results.

The original Methods subsection is preserved unchanged in [original-methods.tex](original-methods.tex).

## Source and scope

The files are copied unchanged from paper/source-data/additional-recordings-20261110 and paper/source-data/engineering-retest-20261110. Their dates and publication flags describe the original runs. Original source paths inside the JSON files identify retained server records.

These compact projections contain protocols, summaries, per-session metrics and saved acceptance records. Full native model conversations and raw EEG remain outside this projection. Source-provider access and licence conditions continue to apply. The original record directories and all original first deliveries remain retained. The later maintenance-freeze evaluation on twenty other new EEG records is reported separately in the main manuscript.
