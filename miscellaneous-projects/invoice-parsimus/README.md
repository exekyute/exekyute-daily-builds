# 🧾 InvoiceParsimus

**A private, browser-based invoice parser and financial dashboard powered by Gemini AI.**

InvoiceParsimus lets you drag and drop PDF invoices or scanned images directly into your browser. It runs OCR locally on your machine, routes the result to Google's Gemini AI for intelligent field extraction, and organizes everything into a sortable, filterable ledger. No accounts. No uploads. No server. Your documents and your API key never leave your control.

## 🎯 What It Does

Drop a PDF or image invoice into the app and it extracts:

* 📅 **Date** (normalized to DD-MM-YYYY)
* 🏢 **Vendor name**
* 🆔 **PO Number** (validated against your configured digit length)
* 🔢 **Invoice Number**
* 💰 **Subtotal, Tax (GST/HST/VAT), and Total**

If Gemini cannot confidently read a field, it returns null rather than guessing. The app marks those cells as **N/A** with a small icon you can hover over, reminding you to review manually. Nothing gets silently dropped or fabricated.

## ⚙️ How the Pipeline Works

Every file you drop goes through a two-stage process:

🔄 **Stage 1 - Local OCR (Tesseract.js)**
Tesseract reads the document entirely inside your browser and produces a raw text string plus a confidence score from 0 to 100.

🧠 **Stage 2 - Gemini interpretation (your API key)**
* If Tesseract's confidence is **above your threshold** (default 75%), the extracted text is sent to Gemini. This is the fast path for clean, readable invoices.
* If Tesseract's confidence is **at or below your threshold**, the original page images are sent to Gemini Vision instead. This handles blurry scans, low-contrast documents, and stylized fonts where raw OCR text would be unreliable.

Either path returns the same structured JSON, so the table, charts, and export all work identically regardless of which route was taken.

## ✨ Features

📊 **Invoice Table**
* Eight columns: Date, Vendor, PO #, Invoice #, Description, Subtotal, Tax, Total
* Click any column header to sort ascending, descending, or back to default
* Type in the filter row under each header to narrow results by substring. Works on dollar amounts too (typing "24" matches $24.25 and $124.50)
* A sticky totals row at the bottom always shows the sum of whatever is currently visible
* A "Clear Sort/Filter" button resets everything in one click

🃏 **Dashboard Cards**
* Four summary cards: Total Invoiced, Total Tax, Processed count, and Unique Vendors
* Update in real time as you apply filters

📈 **Charts**
* **Spend Timeline (line chart):** monthly spend over time with range toggles for 1 Month, 3 Months, 6 Months, YTD, 1 Year, or All time
* **Vendor Distribution (pie chart):** each vendor's share of total spend, labeled with name and percentage directly on the slice

🛠️ **Settings Panel**
* Gear icon in the top-right header opens the Settings modal
* All three settings are session-only and reset to defaults on refresh or Reset Session:
  * 🔑 **Gemini API Key:** your personal Google AI Studio key, held only in the tab's memory
  * 📏 **Expected PO Digits:** tells Gemini how many characters a valid PO number must be. Helps avoid false positives like phone numbers being mistaken for PO numbers (default: 8)
  * 📉 **OCR Confidence Threshold:** the cutoff that decides whether Gemini reads text or images (default: 75%)

🧪 **Mock Data**
* **Mock: Clean** loads six fully-parsed sample rows so you can explore the dashboard without real documents. Each click adds another six rows on top.
* **Mock: Messy** loads four deliberately broken rows demonstrating how the table renders missing or invalid fields: a wrong-length PO, an unreadable vendor, an illegible date, and a fully blank invoice.
* A collapsible amber warning banner appears when mock data is loaded to prevent you from mixing test data with real invoices.

🧹 **Reset Session**
* Wipes all invoices, sort, filters, and every in-memory setting back to defaults. Equivalent to refreshing the page. Nothing is ever written to disk so there is nothing to undo.

📥 **Export**
* One-click CSV export covering all parsed invoices, ready to import into Excel or accounting software.

🔒 **Privacy**
* Everything runs inside your browser. Your invoices and your Gemini API key never touch a server you don't control. Tesseract runs entirely client-side. The only outbound request is the one you explicitly opt into: your document text or images going directly to Google's Gemini API using your own key.
* The API key is stored only in the JavaScript memory of the current tab. Refresh the page or click Reset Session and it is gone.

## 🚀 Live Demo

🔗 [**Launch InvoiceParsimus**](https://exekyute.github.io/exekyute-daily-builds/miscellaneous-projects/invoice-parsimus/)

## 📖 How to Use

1. Open the live dashboard link above (or open `index.html` directly in your browser).
2. Click the gear icon ⚙️ and paste in your Gemini API key. Set your preferred PO digit length and confidence threshold if the defaults don't match your documents.
3. Drag and drop a PDF invoice or image file into the drop zone, or click the zone to browse.
4. Watch the status message: it shows which OCR page is being scanned, then whether the text or image path was taken to Gemini.
5. The extracted data populates the table automatically. Fields that could not be confirmed show as N/A with a hover hint.
6. Use the column filters, sort headers, and range toggles to explore your data.
7. Click **Export CSV** when you are ready to take the data elsewhere.

## ⚠️ Current Limitations

🔑 **Gemini API key required.** The app will not process files without a key configured in Settings. You can get a free key at [aistudio.google.com](https://aistudio.google.com). The key is never stored; you re-enter it each session.

📄 **Gemini's extraction is only as good as the document.** Heavily damaged scans, handwritten invoices, and documents with no standard field labels may still produce N/A results even with the Vision path. The N/A pill and manual-review hint are there for exactly this situation.

🔤 **Stylized fonts can trip up OCR.** Tesseract works best on clean printed text. Decorative logos or script typefaces in headers may affect the confidence score and push the document to the Vision path.

## 📂 Other Document Types This Approach Handles

The same OCR-to-AI pipeline works well for any structured document where you need to pull out specific fields. Some natural extensions:

* 🧾 **Expense receipts** - extract merchant, date, amount, and payment method from till receipts and email receipts
* 📦 **Purchase orders** - read vendor-issued POs to match against your own records
* 🚚 **Delivery notes and packing slips** - capture item counts, shipment reference numbers, and delivery dates
* ⚡ **Utility and telecom bills** - pull account number, billing period, usage, and total due
* 🏥 **Medical bills and EOBs** - extract provider, service date, billed amount, and patient responsibility
* 💳 **Bank and credit card statements** - parse transaction dates, descriptions, and amounts into a ledger
* ⏳ **Contractor timesheets** - capture hours, rates, and project codes from submitted invoices
* 🛡️ **Insurance claim documents** - extract claim number, policy number, incident date, and settlement amounts

Core pattern remains the same: insert doc, let OCR read it locally, let Gemini interpret intelligently, and get back clean structured data.

## 🛠️ Tech Stack

| Tool | What it does |
|---|---|
| 🌐 HTML5 + Vanilla JavaScript | All logic and structure, no framework needed |
| 🎨 Tailwind CSS (CDN) | Styling and layout |
| 📄 PDF.js (CDN) | Renders PDF pages to canvas so OCR can read them |
| 🔍 Tesseract.js (CDN) | Runs OCR locally, produces text and a confidence score |
| 🤖 Gemini API (`gemini-2.5-flash`) | Interprets OCR output or page images and returns structured JSON |
| 📊 Chart.js + datalabels plugin | Powers the spend timeline and vendor distribution charts |
