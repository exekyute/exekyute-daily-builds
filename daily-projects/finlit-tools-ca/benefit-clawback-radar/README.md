# Benefit Clawback Radar

> Visualize the Effective Marginal Tax Rate that low- and middle-income Canadians actually keep on the next dollar, once CCB and GIS clawbacks land on top of income tax.

## What it does
- **Disposable Income Rollercoaster**: keep-rate curve across $0–$120K, with an amber "Invisible Cliff Edge" zone where the combined bite is steepest. Hover or tap to inspect any income point live.
- **Leaky Pipeline**: a hypothetical $2,500 raise stripped by federal tax, provincial tax, CCB reduction, and GIS reduction in sequence.
- **Live explainer card**: plain-English narration that adapts to profile, province, and RRSP usage.
- **Three summary cards**: Gross Raise on Paper / True Net Take-Home / Effective Marginal Rate.
- **RRSP Escape Hatch**: a contribution lever with a dashed "without RRSP" ghost curve, plus the tax refund + restored benefit value of the contribution.

## Why it's useful
- Reveals clawbacks that never show up on a paystub.
- Combines federal + provincial brackets, CCB Tier 1 and Tier 2 phase-outs, AND the GIS earnings exemption + 50% clawback in one view.
- Six provinces baked in (ON, BC, AB, QC, NS, MB).
- Turns the diagnosis into a dial via the RRSP lever.

## How to run it
Double-click `index.html`. Or use the hosted hub at the repo root.

## How to use it
1. Pick a profile preset (Single Parent / Working Family / Senior).
2. Override anything that doesn't match: income field, ± steppers for kids, province.
3. Hover or tap the curve to inspect any income point; click to commit it as your bracket.
4. Scroll to the RRSP Escape Hatch and dial up a contribution. The dashed ghost curve is your "before"; the solid curve is your "after."
5. Close the tab whenever. Your inputs come back next visit.

## Canadian rules it follows
- **CCB (July 2026 – June 2027):** max $8,157/yr per child under 6, $6,883/yr per child age 6–17. Tier 1 threshold $38,237. Tier 2 threshold $82,847. Tier 1 phase-out rates 7% / 13.5% / 19% / 23% for 1–4+ kids; Tier 2 rates 3.2% / 5.7% / 8% / 9.5%.
- **GIS (Q1 2026 single-senior reference):** max $1,105.43/month. First $5,000 of employment income fully exempt; next $10,000 50% exempt; 50% clawback above.
- **Income tax:** 2026-indexed federal brackets + Basic Personal Amount credit. Provincial brackets for ON, BC, AB, QC, NS, MB.
- **RRSP impact:** reduces AFNI for CCB, reduces GIS-clawback income at the federal level, reduces taxable income for federal + provincial tax.

## What it does NOT model
- Provincial low-income tax reductions (e.g. Ontario LIFT).
- Health premiums or surtaxes (e.g. Ontario Health Premium).
- Quebec-specific deductions (QPP, QPIP, abatement).
- Shared custody or non-standard family structures.
- RRSP contribution room limits (input is uncapped).
- GST/HST credit, provincial child benefits, disability benefits.
- Childcare expense deduction.

## Tech notes
One self-contained HTML file. Vanilla JavaScript, inline SVG, Tailwind via CDN, Inter font via Google Fonts. State persists in `localStorage` (key `clawback_radar_state_v3`). All math lives in a `window.BenefitMath` module, open DevTools to spot-check, e.g. `BenefitMath.ccbBenefit(55000, { type:'family', kidsUnder6:1, kids6to17:0 })`.

## Disclaimer
Illustrative only. Uses 2026-indexed estimates and does not capture every credit, deduction, or family structure. Verify in **CRA My Account** and **Service Canada** and consult a Certified Professional Accountant before making income decisions. Not tax, legal, or investment advice.
