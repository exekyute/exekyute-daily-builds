# io-pdf-builder

A single HTML file with a fillable insertion order form on the left and a live preview on the right. The Print button saves a one-page PDF you can upload straight to DocuSign.

## Why I built this

This is a follow-up to yesterday's [gsheets-io-pdf](https://github.com/exekyute/gsheets-io-pdf) project. That one used Google Sheets and Apps Script to turn rows of data into PDFs. I wanted to try a different angle: a frontend form that builds one IO at a time, with no spreadsheet, no Apps Script, and no backend.

The visual template came from Claude Design. I asked it to design a generic insertion order layout, then wrapped that HTML with a form so the fields could be filled in and previewed live before printing.

DocuSign is the natural endpoint for a signed IO, so I added hidden anchor tags next to each signature, name, date, and title line. After uploading the PDF, DocuSign's Auto-Place can drop the right fields in automatically.

## What it does

- Renders a fillable insertion order form on the left side of the page.
- Shows a live preview of the document on the right that updates as you type.
- Caps placements at 4 rows so the signature block always fits on page 1.
- Computes line totals, subtotal, HST, and total due automatically.
- Embeds hidden DocuSign anchor tags next to every signature, name, date, and title line, so Auto-Place will recognize them on upload.
- Saves the IO as a one-page PDF through the browser's Print dialog.

Three buttons:

- **Prefill** loads a sample Northwind Media IO into the form, so you can see what a filled document looks like.
- **Clear** wipes the form, but leaves three defaults in place: HST 14%, payment terms "Net 30, payable on invoice", and the attachment label "Appendix A: Additional Placements". These are conventions, not sample data.
- **Print / Save PDF** opens the browser print dialog.

## Setup

There is nothing to install. You need a browser.

1. Download `index.html` from this repo.
2. Double-click it. It opens in your default browser.

The file is self-contained. No build step, no external dependencies, no internet required.

## Usage

1. Open `index.html` in Chrome, Edge, Safari, or Firefox.
2. Fill out the publisher info in the left sidebar, then advertiser, campaign, and placements. The preview on the right updates as you type.
3. Click **Print / Save PDF** at the top of the form, pick "Save as PDF" as the destination, and choose where to save the file.
4. Upload the resulting PDF to DocuSign.
5. In DocuSign, use Auto-Place with these anchor strings:
   - Advertiser: `\sig_advertiser\`, `\name_advertiser\`, `\date_advertiser\`, `\title_advertiser\`
   - Publisher: `\sig_publisher\`, `\name_publisher\`, `\date_publisher\`, `\title_publisher\`
6. Route the envelope to both signers and send.

If you want to start from sample data, click **Prefill** before filling anything else in.

## Placement types and rate models

Placement rows use dependent dropdowns. Picking a Placement Type filters the Format options and decides whether the line is priced by CPM or by flat rate.

| Placement Type | Rate model | Quantity unit |
|---|---|---|
| Display Banner, Native, Video Pre-Roll, Video Mid-Roll, Mobile Interstitial, Social | CPM | impressions |
| Newsletter / Email | Flat | sends |
| Podcast / Audio | Flat | episodes |
| Sponsorship / Takeover | Flat | days |

CPM rows compute as `(quantity / 1000) * rate`. Flat rows compute as `quantity * rate`. The subtotal, HST, and total due all recompute on every edit.

## Customizing

Everything lives in `index.html`. The pieces most likely to need editing:

- `PLACEMENT_TYPES` near the top of the script. Add, remove, or rename placement types and their valid formats here.
- `SAMPLE_FIELDS` and `SAMPLE_PLACEMENTS` hold the Prefill button's data. Replace with your own company and a representative campaign.
- `PRESERVED_DEFAULTS` holds the three values the Clear button leaves in place.
- `MAX_PLACEMENTS` is set to 4 to guarantee one page. Raising it will likely push the signature block onto page 2.
- The CSS variables in the `<style>` block (`--accent`, `--ink`, and the rest) control colors.

## License

MIT. See `LICENSE`.

Kevin Yu, [github.com/exekyute](https://github.com/exekyute)
