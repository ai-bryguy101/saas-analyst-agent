      *================================================================*
      *  BRXCUST  -  BRINDLE DATA SYSTEMS CUSTOMER MASTER                *
      *  LAST CHANGED 03/14/97 HP  (ADDED CREDIT-LIMIT)                  *
      *  RECFM=FB LRECL=150                                              *
      *================================================================*
       01  BRX-CUST-REC.
           05  CUST-NO                 PIC 9(6).
           05  CUST-NAME               PIC X(40).
           05  CUST-ADDR1              PIC X(30).
           05  CUST-CITY               PIC X(20).
           05  CUST-STATE              PIC X(2).
           05  CUST-ZIP                PIC 9(5).
           05  CUST-PHONE              PIC X(12).
           05  CUST-STATUS             PIC X(1).
               88  CUST-ACTIVE                 VALUE 'A'.
               88  CUST-INACTIVE               VALUE 'I'.
               88  CUST-SUSPENDED              VALUE 'S'.
           05  CUST-OPEN-DATE          PIC 9(7).
      *        CYYMMDD  C=0 FOR 19XX, C=1 FOR 20XX
           05  CUST-CREDIT-LIMIT       PIC S9(7)V99.
           05  CUST-BALANCE            PIC S9(7)V99.
           05  CUST-REP                PIC X(3).
           05  FILLER                  PIC X(6).
