import os.path
import xlsxwriter
import time
import pandas as pd
from Kiwoom import WORKING_DIR_PATH
from trtrader import EXTERNAL_LIST_FILE, EXTERNAL_LIST_BACKUP_FILE, TICKET_SIZE

RESET_EXTLIST_ON_INITIATION = True

class ListGen():
    def __init__(self):
        self.external_list_initiator()
    
    def run_(self):
        # MAY NEED TO CHECK IF THE CURRENT CODE IS IN MARKET CODE
        self.external_list.loc[len(self.external_list)] = ['105560', 34, 'buy', 'yet'] # in EXCEPT 
        self.external_list.loc[len(self.external_list)] = ['006800', 1044, 'buy', 'yet'] # proper buy - may be too much
        self.external_list.loc[len(self.external_list)] = ['096770', 101044, 'buy', 'yet'] # proper buy - may be too much
        self.external_list.loc[len(self.external_list)] = ['005380', 44, 'buy', 'yet'] # in existing trtrade list
        self.external_list.loc[len(self.external_list)] = ['005930', 1554, 'sell', 'yet'] # selling more
        self.external_list.loc[len(self.external_list)] = ['019550', 1554, 'sell', 'yet'] # not in existing trtrade list
        self.external_list.loc[len(self.external_list)] = ['122630', 500, 'sell', 'yet'] # proper selling 
        self.external_list.loc[len(self.external_list)] = ['078930', 1554, 'sell', 'yet'] # in EXCEPT
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
        el.to_excel(EXTERNAL_LIST_FILE, index = False)
    
if __name__ == "__main__": 
    list_gen = ListGen()
    list_gen.run_() 
