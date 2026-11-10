BRIX EXPORT - READ ME FIRST
===========================
Written by H. Penhallow, Mainframe Ops, 06/2011, before the box goes away.

These are the final extracts from BRIX (Brindle Recurring Invoicing eXchange)
before billing moves to the new Ledger system on 7/1/2011.

* BRXCUST.TXT  - customer master. I pulled this one with FTP in ASCII
                 mode so you can read it in Notepad. Signed numbers come
                 out with the sign punched into the last digit, e.g.
                 0001234{ = +123.40   0001234} = -123.40
                 Status A=active I=inactive S=suspended (credit hold).
* BRXINV.Yyyyy - invoice history, one file per year. These are BINARY
                 (EBCDIC, packed decimal). Do NOT open in Notepad and
                 save, you will wreck them. Use the copybook BRXINV.CPY.
                 1994 and 1995 are not here - those tapes would not read.
* Dates are CYYMMDD. C=0 means 1900s, C=1 means 2000s.
  Some January 2000 rows went out before the Y2K patch was applied to
  the late-fee job and have C=0. They are really 2000. Sorry.
* Sales tax was only charged on licenses shipped to Ohio addresses.

Questions -> Harold x214 (until 3/2012)
