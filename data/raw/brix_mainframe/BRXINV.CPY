      *================================================================*
      *  BRXINV  -  INVOICE HISTORY  (ONE FILE PER CALENDAR YEAR)        *
      *  RECFM=FB LRECL=80   TRANSFER IN BINARY MODE ONLY !!!            *
      *  Y2K REMEDIATION 11/99 - DATES NOW CYYMMDD  (HP)                 *
      *================================================================*
       01  BRX-INV-REC.
           05  INV-REC-TYPE            PIC X(1).
               88  INV-IS-INVOICE              VALUE 'I'.
               88  INV-IS-CREDIT               VALUE 'C'.
               88  INV-IS-TRAILER              VALUE 'T'.
           05  INV-CUST-NO             PIC 9(6).
           05  INV-NO                  PIC 9(8).
           05  INV-DATE                PIC 9(7).
           05  INV-PERIOD-END          PIC 9(7).
           05  INV-DESC                PIC X(30).
           05  INV-AMT                 PIC S9(9)V99 COMP-3.
           05  INV-TAX                 PIC S9(7)V99 COMP-3.
           05  INV-STATUS              PIC X(1).
      *        P=PAID  O=OPEN  V=VOID  W=WRITTEN OFF
           05  INV-PAID-DATE           PIC 9(7).
           05  FILLER                  PIC X(2).
      *  TRAILER: INV-CUST-NO=999999, INV-NO=RECORD COUNT,
      *           INV-AMT=SUM OF INV-AMT FOR THE FILE
