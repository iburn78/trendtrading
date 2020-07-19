import os
import xlsxwriter
import time
import pandas as pd
from Kiwoom import WORKING_DIR_PATH
from trtrader import EXTERNAL_LIST_FILE, EXTERNAL_LIST_BACKUP_FILE
import yfinance as yf
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters # For datetime series converting.... 

RESET_EXTLIST_ON_INITIATION = False # i.e., ignoring existing file if True

# THIS LIST GEN TO BE RUN INDEPENDENTLY FROM TRTRADER
# If 'amount' is set to zero, 'amount' will be set to the actual holding quantity under 'sell' and set to TICKET_SIZE under 'buy'
# If 'amount' is set to a large quantity more than actual holding quantity under 'sell', 'amount' will be set to the actual holding quantity
# ['code', 'amount', 'buy_sell', 'yet/ordered/failed']

# TRENDTRADE_EXCEPT_LIST = ['105560', '078930'] # 
# self.external_list.loc[len(self.external_list)] = ['105560', 34, 'buy', 'yet'] # in EXCEPT 
#                                                   ['006800', 1044, 'buy', 'yet'] # proper buy - may be too much
#                                                   ['096770', 100144, 'buy', 'yet'] # too much quantity / order is not being processed in Kiwoom
#                                                   ['005380', 44, 'buy', 'yet'] # in existing trtrade list
#                                                   ['005930', 1554, 'sell', 'yet'] # selling more
#                                                   ['019550', 1554, 'sell', 'yet'] # not in existing trtrade list
#                                                   ['122630', 500, 'sell', 'yet'] # proper selling 
#                                                   ['078930', 1554, 'sell', 'yet'] # in EXCEPT

# Be careful when adding items to EXTLIST, especially duplicated items: 
# when buying, it will result in duplicated buying
# when selling, second or later selling could be ignored



class ExtListGen():
    def __init__(self):
        self.external_list_initiator()
        register_matplotlib_converters()
    
    def run_(self): 
        self.external_list.loc[len(self.external_list)] = ['000660', 0, 'sell', 'yet'] # in EXCEPT 
        self.external_list.loc[len(self.external_list)] = ['000660', 0, 'sell', 'yet'] # in EXCEPT 
        self.external_list.loc[len(self.external_list)] = ['122630', 0, 'sell', 'yet'] # in EXCEPT 
        self.external_list.loc[len(self.external_list)] = ['122630', 0, 'sell', 'yet'] # in EXCEPT 

        # self.test_plot()
        self.write_external_list_to_Excel(self.external_list) # empty EXTERNAL LIST FILE will be removed
        print(self.external_list)

    def external_list_initiator(self):
        self.external_list = pd.DataFrame({'code':pd.Series([], dtype='str'),
                                           'amount':pd.Series([], dtype='int'),
                                           'buy_sell':pd.Series([], dtype='str'),
                                           'note':pd.Series([], dtype='str')})

        if os.path.exists(EXTERNAL_LIST_FILE) and not RESET_EXTLIST_ON_INITIATION:
            # read el from existing excel and use it as starting point
            el_converters = {'code': str, 'amount': int, 'buy_sell': str, 'note': str}
            existing_el = pd.read_excel(EXTERNAL_LIST_FILE, index_col = None, converters=el_converters)
            if len(existing_el) > 0: 
                self.external_list = self.external_list.append(existing_el)
                print("Items in existing EXTERNAL LIST FILE loaded")
            os.remove(EXTERNAL_LIST_FILE)

        elif os.path.exists(EXTERNAL_LIST_FILE) and RESET_EXTLIST_ON_INITIATION:
            t = time.strftime("_%Y%m%d_%H%M%S")
            n = EXTERNAL_LIST_BACKUP_FILE[:-5]
            os.rename(WORKING_DIR_PATH+EXTERNAL_LIST_FILE, WORKING_DIR_PATH+n+t+'(unexecuted).xlsx')

    def write_external_list_to_Excel(self, el):
        if len(el) > 0: 
            el.to_excel(EXTERNAL_LIST_FILE, index = False)

    
    def test_plot(self):
        sm = yf.Ticker('005930.KS')
        sk = yf.Ticker('000660.KS')
        hst = sm.history(period='max', auto_adjust=False)
        skh = sk.history(period='max', auto_adjust=False)
        fig, (ax1, ax2)= plt.subplots(2, 1, sharex=True)
        plt.setp(ax1.get_xticklabels(), fontsize = 8) 
        plt.setp(ax1.get_yticklabels(), fontsize = 8)
        plt.setp(ax2.get_xticklabels(), fontsize = 8, horizontalalignment = 'left')
        plt.setp(ax2.get_yticklabels(), fontsize = 8) 
        ax1.set_title("Samsung and SK Hy for the last 20 years, " + time.strftime("%Y-%m-%d"), size = 8, fontweight = 'bold')
        ax1.plot(hst.loc['2000-01-01':'2019-12-31', ['Close']], '-b', lw = 0.7, label = 'SM Price')
        ax1.plot(skh.loc['2000-01-01':'2019-12-31', ['Close']], ':r', lw = 0.7, label = 'SK Hy Price')
        ax1.set_ylabel("Price", size = 8)
        ax1.legend(fontsize = 8)
        ax1.grid()

        ax2.set_title("Volume is in number of shares and in 10^6", size = 8)
        ax2.plot((hst.loc['2000-01-01':'2019-12-31', ['Volume']]/(1000000)).astype(int), '-', color = 'b', lw = 0.7, label = 'SM Volume') 
        ax2.plot((skh.loc['2000-01-01':'2019-12-31', ['Volume']]/(1000000)).astype(int), ':', color = 'r', lw = 0.7, label = 'SK Hy Volume') 
        ax2.set_ylabel("Volume", size = 8)
        ax2.set_xlabel("Time", size = 8)
        ax2.legend(fontsize = 8)
        ax2.grid()

        plt.show()

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



