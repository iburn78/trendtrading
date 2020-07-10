import os
import xlsxwriter
import time
import pandas as pd
from Kiwoom import WORKING_DIR_PATH
from trtrader import EXTERNAL_LIST_FILE, EXTERNAL_LIST_BACKUP_FILE, TICKET_SIZE, TRENDTRADE_EXCEPT_LIST

RESET_EXTLIST_ON_INITIATION = True

# THIS LIST GEN TO BE RUN INDEPENDENTLY FROM TRTRADER

class ExtListGen():
    def __init__(self):
        self.external_list_initiator()
    
    def run_(self):
        # TEST CODES: ALL SEEMS WORKING FINE
        # TRENDTRADE_EXCEPT_LIST = ['105560', '078930'] # 
        # self.external_list.loc[len(self.external_list)] = ['105560', 34, 'buy', 'yet'] # in EXCEPT 
        # self.external_list.loc[len(self.external_list)] = ['006800', 1044, 'buy', 'yet'] # proper buy - may be too much
        # self.external_list.loc[len(self.external_list)] = ['096770', 100144, 'buy', 'yet'] # too much quantity / order is not being processed in Kiwoom
        # self.external_list.loc[len(self.external_list)] = ['005380', 44, 'buy', 'yet'] # in existing trtrade list
        # self.external_list.loc[len(self.external_list)] = ['005930', 1554, 'sell', 'yet'] # selling more
        # self.external_list.loc[len(self.external_list)] = ['019550', 1554, 'sell', 'yet'] # not in existing trtrade list
        # self.external_list.loc[len(self.external_list)] = ['122630', 500, 'sell', 'yet'] # proper selling 
        # self.external_list.loc[len(self.external_list)] = ['078930', 1554, 'sell', 'yet'] # in EXCEPT
        self.external_list.loc[len(self.external_list)] = ['005380', 30, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['006800', 1044, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['017670', 226, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['035720', 12, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['036570', 4, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['078930', 171, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['090430', 301, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['122630', 12, 'sell', 'yet']
        self.external_list.loc[len(self.external_list)] = ['207940', 5, 'sell', 'yet']
        self.write_external_list_to_Excel(self.external_list)
        print(self.external_list)

    def external_list_initiator(self):
        if os.path.exists(EXTERNAL_LIST_FILE) and not RESET_EXTLIST_ON_INITIATION:
            print("Adding to the existing EXTERNAL LIST FILE")

        else:
            if os.path.exists(EXTERNAL_LIST_FILE) and RESET_EXTLIST_ON_INITIATION:
                t = time.strftime("_%Y%m%d_%H%M%S")
                n = EXTERNAL_LIST_BACKUP_FILE[:-5]
                os.rename(WORKING_DIR_PATH+EXTERNAL_LIST_FILE, WORKING_DIR_PATH+n+t+'(unexecuted).xlsx')

            print("Generating a new EXTERNAL LIST FILE")
            el = xlsxwriter.Workbook(EXTERNAL_LIST_FILE)
            elws = el.add_worksheet() 
            elws.write('A1', 'code') 
            elws.write('B1', 'amount') 
            elws.write('C1', 'buy_sell') 
            elws.write('D1', 'note') 
            el.close()

        el_converters = {'code': str, 'amount': int, 'buy_sell': str, 'note': str}
        self.external_list = pd.read_excel(EXTERNAL_LIST_FILE, index_col = None, converters=el_converters)

    def write_external_list_to_Excel(self, el):
        if len(el) > 0: 
            el.to_excel(EXTERNAL_LIST_FILE, index = False)
        else:
            os.remove(EXTERNAL_LIST_FILE) # empty file is being deleted
    

class FinancialAnalysis():
    pass

class OwnershipAnalysis():
    pass
    # Composition of shareholders
    # Trade_share analysis w/ average enter_price/purchase_price and return
    # Behavior analysis per each group in relation w/ enter_price (e.g., purpose, expected/target return)
    # Trade volume analysis

class ClassesOfStocks():
    pass 
    # e.g., 
    # class A: Value stocks
    # class B: purely experimental
    # class C: Top 100 in mkt cap
    
if __name__ == "__main__": 
    list_gen = ExtListGen()
    list_gen.run_() 



