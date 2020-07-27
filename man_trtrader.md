# TrendTrader Manual - Version 0.1 

As of 2020-07-26

## Overview of the structure

Key components of the TrendTrader (trtrading):

- **controller**: defines a schedule to check the version of Kiwoom API and to run the trtrader (mainly to cope with Kiwoom's infrequent API updates while automating trtrader as much as possible)
- **Kiwoom**: defines functions for utilizing Kiwoom API 
- **trtrader**: defines trtrader main DB (master_book) and main logic
- **extlistgen**: provides a buy-and-sell list of stocks that is created externally from the trtrader 
- **bounds.xlsx**: provides various levels of LLB, LB, UB per the number of reinvestments

## controller
- Main tasks of controller are to run Kiwoom API before the market open time for version check, and to keep running trtrader while the market is open
- Running sequence: 
    - if executed before the version check time, controller will run Kiwoom API and connect to the Kiwoom server at the version check time (by using multiprocessing); if the version check is unsuccessful, controller exits with an error (if option is set so)
    - if executed after the version check time and before the market open time, controller will run trtrader (by using multiprocessing) at the trtrader run time (that is market open time for trtrader)
    - if executed after the trtrader run time, controller will run trtrader immediately if the current time is before the market close time
    - a single trtrader run will finish once the market closes 
    - at each day's market close, controller will be in a wait mode for until the next day's version check time, and the daily routine repeats
- controller uses multiprocessing module to cope with Kiwoom API version check (if not using multiprocessing, Kiwoom API is not unloaded properly after each execution)

## Kiwoom
- Functions related with Kiwoom API are implemented (refer to Slack autotrading section for description or the original book on wikidocs.net)

## trtrader
- Fundamental principle of trtrader
    
    Select target and timing, and when the decision is right make follow-up investments to maximize earning and when not minimize loss 

    | Overview of the algorithm |
    | --- |
    | Look for targets that have high potential of substantial price increase (value) in the near future (timing) |
    | Make a test investment of a ticket size into each of the targets |
    | If the choice of the target and the investment timing are both turn out to be right, the target's price should increase: if the price hits a certain level (UB), then make a follow-up reinvestment of a ticket size |
    | On the other hand, if either the choice of the target or the timing turns out to be wrong then the price should decrease: if the price hits a certain level (LB), then sell all shares of the target at a loss |
    | The loss should be small as it is a loss with respect to the initial investment of a ticket size; consider this as the price for the wrong decision |
    | However, as trtrader will only trade during the market open time, there could be a price jump between market close and open, and sometimes there could be a large price decline without time to react |
    | In such a case, it is most likely due to a macro event affecting overall market, so resultant rash selling based on the algorithm should be avoided: therefore, if price hits a certain level (LLB) lower than LB, the selling should be suspended |
    | Once suspended, the stock should be held until the price recovers back to higher than LB, and then it could be traded normally under the trtrader logic |
    | For stocks that are reinvested, they follow the same logic as described above with the bounds (UB, LB, LLB) are updated accordingly |
    | Max number of reinvestment is predefined, and max number of bounds elevation is also predefined (as there could be bounds elevation without making any reinvestment) |
    

- Database structure
    - Transaction history is managed in master_book DataFrame: loaded from an excel file (or newly created) and saved to an excel file
        - Active items in master_book are the current account stock list
        - Actual Kiwoom API transaction results are appended into master_book (including reinvestments) as a new record (a new row)
        - Bounds elevation, changing status to suspend due to hitting LLB, releasing from suspend status, and etc which adjust records in master_book and do not involve actual Kiwoom API transactions are handled in trendtrading_mainlogic
    - trtrade_list is a run-time DataFrame which contains orders to be executed in Kiwoom API trade_stocks
    - external_list is a DataFrame that is loaded from an excel file and appended to trtrade_list
    - Kiwoom trade_log file is a separate log file created by the Kiwoom class

- Procedure of trtrader running
    - Kiwoom API is connected to the Kiwoom server (currently test server) with an account number defined in an external credential file
    - Bounds are loaded from an external excel file (which contains an original logic)
    - master_book is loaded or created
        - Refer to the comments in trtrader next to the definition of CREATE_NEW_MASTER_BOOK
        - If newly created, an excel file with column names and START_CASH amount is generated and master_book is then loaded from the excel file
    - master_book integrity is checked
        - If master_book is newly created, integrity checker will load the account stock list to the master_book
        - Trtrader cash level is checked whether the actual account cash is larger than START_CASH minus the total investment amount of the account stock list, and set the trtrader cash level in master_book to START_CASH minus investment total (plus buying fee)
        - If master_book is loaded from an existing master_book excel file, then the integrity checker checks whether the records in master_book matches the current account stock list 
        - Tax and fee are adjusted when the above matching is performed as the tax/fee calculation method for master_book is different from the way for the data received through Kiwoom API
        - The integrity checker always ignores items in EXCEPT_LIST, and raises Exception if master_book contains items in EXCEPT_LIST (note that it is not an explicit checking as it checks if the lengths of active items match between master_book and the account stock list) 
    - tax and fee adjustments
        - tax: 0.25%, fee: 0.35% for buy and sell each under the Kiwoom test server
        - when buying, buying fee is deducted from cash while the total investment (invtotal) is not affected
        - for evaluating the current portfolio total value (cvalue), tax and selling fee are deducted
    - main procedure: run_(), trendtrading_mainlogic_(), trade_stocks()
        1. run_ executes trendtrading_mainlogic that would append buy/sell orders to the existing trtrade_list by examining master_book (for details about trendtrading_mainlogic, refer to the comments in the code; basically it is implemented the trtrading algorithm described above)
        2. run_ checks if there is an external_list and loads it into trtrade_list if exists
        3. run_ executes trade_stocks for "yet" items in trtrade_list
        4. "failed" items in trtrade_list would not be retried for execution  
            - This might be fine if an item in the trtrade_list is generated through trendtrading_mainlogic
            - If an item is loaded from the external list, "failed" item might be lost when the process exits as trtrade_list is not saved to a file
    
    - closing procedure: close_()
        - saves master_book to the excel file (it overwrites and previous excel file is lost - which is of no concern as master_book contains all the previous transaction related data)
        - prints master_book in an easier readable format 
        - prints the result summary (e.g., overall return rate of the account)

    - Dictionary for dec_made
        - ABRIDGED_DICT = {'new_ent':  'N', 'reinv': 'R', 'a_sold': 'S', 'p_sold': 'P', 'SUSPEND': 'U', 'released': 'A', 'bd_elev': 'B', 'loaded': 'L', 'EXCEPT': 'E'}

- External command
    - TrTrader can be controlled through external command: suspend, resume, stop, ping
    - Detailed comments are provided in the code

## extlistgen
- generates an excel file to be loaded by trtrader which contains a list of orders to be executed by the Kiwoom API trade_stocks function
- trtrader adjusts each order according to the following rules: 
    - codes in EXCEPT_LIST are ignored
    - codes for buying currently portfolio stocks are ignored
    - codes for buying with zero volume is set to buy a ticket size
    - if cash (which is internally calculated based on START_CASH) is not enough for buying, system raises Exception
    - codes for selling stocks that are not in account are ignored
    - codes for selling with quantity either zero or more than holding amount are adjust to sell max quantity


## bounds.xlsx
- Location is defined in trtrader
- Defines the levels of LLB, LB, UB according to the number of reinvestments 
- Later this excel file has to be incorporated into trtrader or converted to a python code for parameter optimization 