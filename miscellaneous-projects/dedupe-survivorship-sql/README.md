# Customer Dedupe Queries

Five SQLite queries that merge customer records from a web shop and a till into one record per customer, matched on the name in lower case with each run of spaces collapsed to one, and on the digits of the phone number. Each customer's records are ranked with ROW_NUMBER by a stated rule, newest first, then the web shop, then the lower record number, so the record kept is one that exists. The quick merge, MAX() of every column, builds 7 of the sample's 11 merged customers out of names, emails, phone numbers, addresses and consent answers that no single record holds together, and says yes to marketing email for 3 customers whose newest answer is no.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-match-keys.sql` | How many customers the records make under six ways of matching them, and how many of those customers hold two names that differ in more than letter case and the length of a run of spaces, two phone numbers, or a record with no number beside another. |
| `sql/02-max-per-column.sql` | The quick merge: MAX() of every column for each customer with more than one record, how many rows SELECT DISTINCT keeps of the same records, and whether any record holds the merged row, the date aside. |
| `sql/03-survivor-row.sql` | One whole record per customer, ranked by the stated rule, with the part of the rule that settled it. |
| `sql/04-survivor-fields.sql` | One record per customer built field by field, each value printed beside the record it came from. |
| `sql/05-approaches.sql` | What each approach keeps and drops: rows, customers still doubled, rows no record holds, known values left blank, and a yes kept where the customer's newest answer is no. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/dedupe-survivorship-sql
python run.py
```

That prints all five reports against the sample file. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Six on the sample cover the six ways of matching, the quick merge, the whole record kept, the record built field by field, and the approaches side by side. The sixth prints all five reports and checks their column names, a rule as wide as each column, how many rows each prints and the first of them, that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message, and that a blank value prints as a blank cell.

Four more go past the sample as loaded. The first runs on a log built for the suite that holds pairs of records that differ in letter case, a run of two or three spaces, or each of the six characters a phone number may hold besides its digits, alone or all together, with a leading 1 or without, and every query has to join each pair; it also holds two records with no number, one name at two numbers, and a name starting é against the same name starting É, which every query has to keep apart, and with no email or address on any record, the MAX() row of each pair has to be one of its records. The second runs on built ties: the web shop has to beat a lower till number on the same day, record 99 has to beat record 100, a newer till record has to beat an older web shop one, a same-day no has to win the consent field whichever source gives it, one customer's fields have to come from four different records, and both the web shop's name beside the till's newer email and a MAX() row that matches a record in all but its yes have to count as no record.

The third loads the sample backwards and with the till's records first, and all five reports have to come out the same. The fourth runs 20000 records, each its own customer with an email, an address and a +1 number, through every query inside the step budget, beside a query that would run for ever, which the budget stops.

Eight exercise the loader and the command line. They refuse the included bad file, which has a phone number typed with a letter O for a zero, and a record listed twice, naming the row it first appeared on. They refuse a name holding a digit, a < or >, a bar, a comma, a non-breaking space, a tab, a zero-width space, the combining grapheme joiner, a Hangul filler or a Khmer inherent vowel, one with no letters, one past 50 characters once NFC has joined what it can, a blank one, and one over four times that limit, refused unread so a long run of combining marks never reaches NFC, and an address holding a semicolon, a non-breaking space or an Arabic-Indic digit, one with no letters or digits and one past 60 characters. Apostrophes straight or curly, hyphens, full stops, runs of spaces, the zero-width joiner and non-joiner, all three direction marks, other scripts with their vowel marks, a name of 50 characters, an accent typed as a separate mark, an address with # and / in it or of 60 characters, and a blank address all load, each kept as typed except that NFC joins an accent typed as a separate mark to its letter.

They refuse an email with no name or no domain, a domain with no dot or with an underscore, a space, an accent, two @ signs or past 60 characters, and a phone number with a letter, too few or too many digits, a first digit of 1 or 0 once any leading 1 is set aside, a slash, an extension, or past 25 characters. An email in capitals loads as typed, as do one of 60 characters, numbers written with a plus sign, brackets, dots, a leading 1 or enough spacing to bring the number to 25 characters, and a blank email or phone. They refuse a source other than web or pos, a record number that is 0, padded, a fraction, ten digits long, negative or blank, an opt_in other than yes or no, and a date written another way, one that does not exist, one before 1970 and one later than tomorrow.

They also count rows past blank lines, name a stray quote by its own row, refuse rows with too many or too few fields and a bad, renamed or reordered header, refuse an empty file, one that is not UTF-8 from its first line or only far down, a folder, a read that gives way partway and a line past 1000000 characters, and stop a file past 20000 records as it is read. On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the file before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --customers data/invalid-customers.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is the exception: the file is decoded about 8 KB at a time, so a bad byte is reported first, with no row, when a problem sits above it in the same stretch of the file. On the included bad file:

```
invalid-customers.csv row 21: phone '(902) 555-O147' is not a phone number: ten digits, the first 2 to 9, with or without a 1 in front, and only spaces, hyphens, dots, brackets or a plus sign besides, at most 25 characters
```

## Where the quick merge goes wrong

Query 02 groups the records on the match key and takes MAX() of every column. MAX() on text returns whatever sorts last, so each column can come from a different record, each for its own reason. Mary Ellen Doucet has three records: the web shop's from 2023 with her old email and address, the till's from 2024 with her name typed as `mary ellen  doucet` and her number as 902.555.0114, and the web shop's from 2026 with a new email, a new address and a no to marketing email. The merge takes the till's lower-case name and dotted number, the 2026 email and the 2023 address, since 7 Pleasant St sorts after 114 Robie St, adds a yes, and dates the result 2026-02-20.

That record exists nowhere. Seven of the 11 customers with more than one record come out with a name, email, phone number, address and consent answer that no record holds together, and 9 do once the date is counted too. Ben Kowalski's takes his 2024 email from the till, bkowalski@example.net, because bk sorts after be, and sets it beside his 2026 date. Yes sorts after no, so Mary Ellen Doucet, Graham MacKinnon and Fiona Chisholm all come out as a yes, though each one's newest answer is no (for Fiona Chisholm, a yes and a no on the same day, which query 04 reads as no).

SELECT DISTINCT fails the other way. Compared on name, email, phone, address and consent as typed, `COLIN O'BRIEN` and `Colin O'Brien` are two rows, and so are Hugh Cameron's two web shop accounts, which differ only in the case of the email and in hyphens against spaces in the phone number. It keeps 32 of the 33 records, merging only Priya Nair's two, which differ in nothing but their source and record number.

## Choosing the match key

Query 01 counts the customers that six ways of matching make, from each record alone to the match key. Email alone joins Marie and Dan Boudreau, who share boudreaus@example.com, lumps the 8 records with no email into one customer, and splits Mary Ellen Doucet across three, since her email changed and the till never took one. The phone number alone joins the Boudreaus again, who share a landline, and lumps together the 3 records with no number. The name alone joins the two Sarah MacLeans, one in Truro and one in Antigonish, who have different numbers.

The match key uses both: the name lower-cased with each run of spaces collapsed, and the phone number's digits with a leading 1 dropped, so +1 902 555 0189 and 902-555-0189 are one number. A blank number is the trap left. Matched like any other value, it joins the two John MacDonalds, one in Sydney and one in Yarmouth, neither of whom gave a number. So a record with no number gets its own record reference in place of one and matches nothing but itself.

The key makes 21 customers, 11 of them from more than one record, and none holds two names that differ in more than letter case and the length of a run of spaces, two numbers, or a record with no number among others. Spaces collapse without a loop: every space becomes `<>`, the `><` pairs a run of spaces leaves are dropped, and the `<>` left from each run becomes one space. The loader refuses < and > in a name, so the trick cannot eat part of one.

## Keeping one whole record

Query 03 ranks each customer's records with ROW_NUMBER: the most recently updated first, then on the same day the web shop's before the till's, then the lower record number. A source never uses a record number twice, so no tie is left over, and the suite loads the sample in two other orders to check the reports do not move. Fiona Chisholm and Priya Nair were updated in both systems on one day, and the web shop wins. Hugh Cameron's two web shop accounts were updated on one day, and the lower number wins.

Every value in the kept record comes from one record, as loaded. That is its cost too. Graham MacKinnon's newest record is from the till, with no email and no address, so the kept record has neither, though his web shop record has both. Across the sample the whole record leaves 4 known values blank.

## Field by field

Query 04 takes each field by its own rule and prints the record it came from beside it. The name comes from the web shop first, where customers type their own, which turns `GRAHAM MACKINNON` back into Graham MacKinnon; within one customer the spellings differ only in letter case and the length of runs of spaces, so this rule picks a spelling, not a person. Email, phone and address come from the newest record that has one, with the same tie-breaks as query 03. For consent the newest record's answer wins, and when two records from the same day disagree, no wins: Fiona Chisholm's web shop record said yes and the till said no on the same day, so she is a no, taken from the till.

The result can still be a combination no single record holds. Graham MacKinnon's comes out with the web shop's email and address beside the till's number and its newer no, and 4 customers in all come out that way. The difference from MAX() is that each value was picked by a stated rule and names its record.

## Side by side

Query 05 counts what each approach keeps and drops, on the same match key.

| Approach | Rows kept | Customers still doubled | Rows no record holds | Known values left blank | Yes where the newest answer is no |
| --- | --- | --- | --- | --- | --- |
| As loaded | 33 | 11 | 0 | 10 | 4 |
| SELECT DISTINCT | 32 | 10 | 0 | 10 | 4 |
| MAX() per column | 21 | 0 | 7 | 0 | 3 |
| Whole record | 21 | 0 | 0 | 4 | 1 |
| Field by field | 21 | 0 | 4 | 0 | 0 |

A row no record holds is compared on name, email, phone, address and consent, the date aside, and SELECT DISTINCT compares the same five. A known value left blank is an email or address that another record of the same customer has. The whole record keeps one yes over a same-day no, Fiona Chisholm's. The last column reads the newest answer as query 04 does, so field by field shows 0 there by construction.

## Sample data

33 records of fictional customers, 19 exported from a web shop and 14 from a till: `customers.csv`. Eleven customers have more than one record, one of them three, and their records differ in letter case, runs of spaces, the case of an email and the way a phone number is written, with emails, addresses and consent changed at different times in different systems. Three pairs of different people sit where a looser key would join them: the Boudreaus, who share an email and a landline, two Sarah MacLeans at different numbers, and two John MacDonalds with no number at all. Phone numbers are in the 555-0100 to 555-0199 range set aside for fiction.

## Known limits

- SQLite's lower() folds only A to Z. A name typed with a capital É at the till and a lower-case é on the web shop stays two customers; the sample keeps each accented name in one case, and the suite pins the split.
- The key needs the same name up to letter case and the length of a run of spaces. A nickname, a changed surname, a space dropped or added, a hyphen for a space, a curly apostrophe against a straight one, or an invisible joiner, direction mark or variation selector on one copy only keeps two records apart.
- A record with no phone number matches nothing, so a real duplicate without one stays a customer of its own. Two people who share a name and a number, such as a parent and child on one landline, become one customer.
- Phone numbers are read on the North American plan: ten digits whose area code starts with 2 to 9, and a 1 in front at most. Only those rules are checked, so a number from elsewhere whose digits happen to fit is matched as a North American one; an eleven-digit Chinese mobile starting with 1 loses the 1 like any other.
- Dates belong to a whole record, not to a field. A till record updated for a new address counts as newest for its email too, so a stale email on it wins the email rule.
- Emails are plain ASCII, so comparing them in lower case is exact. A file holds at most 20000 records, names 50 characters, emails 60, phone numbers 25 and addresses 60, and a record dated later than tomorrow is refused.
- The match key is written out in each of the five queries. Changing it means changing every copy.
- Rows print in match-key order, which puts Émilie Thériault last, since É sorts after every ASCII letter. Columns are padded by character count, so a name in a script printed at double width, such as Chinese, pushes the rest of its row out of line.
- A query that runs past a hundred million SQLite steps is stopped with an error. The costliest file found within the limits takes under a third of that, on 3.31 and 3.34 as on 3.50, and each query names each step of its chain once, since SQLite before 3.35 works a named CTE out again at every mention.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
