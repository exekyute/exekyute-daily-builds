# InvoiceParsimus

InvoiceParsimus reads PDF and image invoices into a sortable, filterable table with running totals, four summary cards, two charts and a CSV export. Tesseract.js runs OCR in the browser, then Google's Gemini API (`gemini-2.5-flash`, called with your own key) turns the OCR text, or the page images when OCR confidence is low, into seven fields per invoice. The key, the settings and the rows live only in the tab's memory, so a refresh clears them.

## Running it

Open the [live demo](https://exekyute.github.io/exekyute-daily-builds/miscellaneous-projects/invoice-parsimus/) or `index.html` from this folder in a browser. There is no build step. Click the gear icon (top right), paste a Gemini API key and click Save & Close, then drop PDF, PNG or JPG files on the drop zone or click it to pick them. Mock: Clean fills the table with sample rows if you have no key or no invoices to hand.

## How a file is read

1. **OCR.** PDF.js draws each PDF page onto a canvas at twice its size, and Tesseract.js reads each page (or the image) with its English model, scoring its confidence from 0 to 100.
2. **Gemini.** The page scores are averaged. Above the OCR Confidence Threshold (default 75), Gemini gets the OCR text. At or below it, Gemini gets the page images as PNG, since a low score means the OCR text is unreliable.

Both requests ask for the same JSON schema, so the row looks the same either way. Files are read one at a time. The Description column records the path, `Auto-Parsed (Text)` or `Auto-Parsed (Vision)` plus the vendor, or says `Manual Review Required` when no vendor came back.

## What it extracts

Gemini returns seven fields: vendor, invoice number, PO number, date, subtotal, tax (GST/HST/VAT) and total. It is told to return null for any field that is smudged, illegible, partly missing or ambiguous instead of guessing, and those cells show N/A with a "Review manually" hint on hover. Dates come back as YYYY-MM-DD and show as DD-MM-YYYY.

A PO number must be exactly as long as the Expected PO Digits setting (default 8), which screens out phone numbers and other stray numbers of a different length. The length counts every character, so `PO-10421` is 8. A wrong-length PO that comes back anyway shows with a warning hint.

## What leaves the browser

The page has no backend. The only request that carries invoice data goes straight from the browser to Google's Gemini endpoint (`generativelanguage.googleapis.com`), holding the OCR text or the page images, with your key in the request URL. The page also loads its libraries and fonts from public CDNs, and Tesseract.js downloads its English language data the same way.

The key lives only in the tab's memory. The page's own code writes nothing to localStorage, cookies or disk apart from a CSV you export. Tesseract.js does keep a copy of its English language data in the browser's IndexedDB.

## The table, cards and charts

- **Table:** eight columns (Date, Vendor, PO #, Invoice #, Description, Subtotal, Tax, Total), newest first. A header click sorts ascending, then descending, then back.
- **Filters:** a box under each header matches any part of the cell. Amounts match their two-decimal value, so `24` finds $24.25 and $124.50. Clear Sort/Filter resets both.
- **Totals:** a row pinned to the bottom sums Subtotal, Tax and Total for the rows that pass the filters.
- **Cards:** Total Invoiced, Total Tax, Processed and Vendors (unique).
- **Spend Timeline:** monthly spend as a line chart, with 1M, 3M, 6M, YTD, 1Y and All (the default) ranges counted back from today.
- **Vendor Distribution:** a pie chart of spend by vendor. Slices of 5% or more are labelled with the name, cut at 8 characters, and the percentage.

The cards and both charts follow the filters.

## Settings

All three settings last for the session only. A refresh or Reset Session restores the defaults.

| Setting | Default | What it controls |
|---|---|---|
| Gemini API Key | empty | Required before any file is read |
| Expected PO Digits | 8 | Exact PO length, 1 to 30 characters |
| OCR Confidence Threshold | 75% | Above it Gemini reads the OCR text, at or below it the page images |

## Mock data, reset and export

- **Mock: Clean** adds six complete sample rows per click, with random subtotals from $30 to $250 and 14% tax.
- **Mock: Messy** adds four broken rows: a wrong-length PO, no vendor, no date, and one with only an invoice number. Either mock button opens an amber "Mock data loaded" banner.
- **Reset Session** returns to the state of a fresh page load: no rows, sort, filters or banner, the timeline on All and the three settings at their defaults. It asks first when there are rows or a key to lose.
- **Export CSV** downloads `InvoiceParsimus_OCR_Export.csv` with the eight table columns for every row, mock rows included, whatever the filters and sort. Missing text is written as N/A and missing amounts as 0.00.

## Limitations

- A key is required and has to be pasted again after every refresh. You can create one in [Google AI Studio](https://aistudio.google.com).
- One file is one invoice. Confidence is averaged across a PDF's pages, so one poor page can send every page as an image.
- Rows can't be edited or deleted one at a time, and a refresh loses them.
- A row with no readable date shows N/A but is filed under the current UTC date for sorting and the timeline. Missing amounts count as zero.
- Amounts are summed with no currency handling. The Total Invoiced card says CAD regardless.
- A file that fails, or is not a PDF or image, adds no row, and any error message is gone once the last file finishes.

## Tech stack

| Tool | What it does |
|---|---|
| HTML5 + Vanilla JavaScript | All logic and structure, no framework needed |
| Tailwind CSS (CDN) | Styling and layout |
| PDF.js (CDN) | Renders PDF pages to canvas so OCR can read them |
| Tesseract.js (CDN) | Runs OCR locally, produces text and a confidence score |
| Gemini API (`gemini-2.5-flash`) | Interprets OCR output or page images and returns structured JSON |
| Chart.js + datalabels plugin | Draws the spend timeline and vendor distribution charts |

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
