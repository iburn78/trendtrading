from Kiwoom import *
import random

MASTER_BOOK_FILE = 'data/master_book.xlsx'
BOUNDS_FILE = 'bounds.xlsx'
TRADE_LOG_FILE = WORKING_DIR_PATH + 'data/trendtrading_log.txt'

class TrTrader(): 
    def __init__(self):
        self.km = Kiwoom()
        # self.km.comm_connect()
        self.km.master_book_initiator(START_CASH, replace = False)
        # should develop master_book integrity checker
        # ensure cash > 0 in master_book

        # buy_list to be generated either from master_book analysis (reinv) or from outside (new purchase)
        self.buy_list = pd.DataFrame(columns = ['code', 'amount', 'note'])
        self.buy_list.loc[len(self.buy_list)] = ['005930', 1, 'yet']
        self.buy_list.loc[len(self.buy_list)] = ['017670', 1, 'yet']
        self.buy_list.loc[len(self.buy_list)] = ['090430', 1, 'yet']

        # sell_list to be generated only from master_book analysis
        self.sell_list = pd.DataFrame(columns = ['code', 'amount', 'note'])
        self.sell_list.loc[len(self.sell_list)] = ['005930', 1, 'yet']
        self.sell_list.loc[len(self.sell_list)] = ['017670', 1, 'yet']
        self.sell_list.loc[len(self.sell_list)] = ['090430', 1, 'yet']

        # self.trade_stocks()
        for i in self.buy_list.index: 
            tr_time = time.ctime()
            self.km._write_transaction_to_master_book(self.buy_list['code'][i], 'testname'+str(i), 'buy', random.randint(10000,20000), random.randint(100,200), tr_time)

        for i in self.sell_list.index: 
            tr_time = time.ctime()
            self.km._write_transaction_to_master_book(self.sell_list['code'][i], 'testname'+str(i), 'sell', random.randint(1000,2000), random.randint(10,20), tr_time)

        # on closing... 
        self.km.write_master_book_to_Excel(self.km.master_book)
        print(self.km.master_book)

    def trade_stocks(self):
        buy_order = 1  
        sell_order = 2
            
        for i in self.buy_list.index:
            if self.buy_list["note"][i] == 'yet' or self.buy_list["note"][i] == 'failed':
                price = 0 # market 
                hoga = '03' # market 
                res = self.km.send_order("send_order_req", "0101", ACCOUNT_NO, buy_order, self.buy_list["code"][i], self.buy_list["amount"][i], price, hoga,"")
    
                if res[0] == 0 and res[1] != "":
                    self.buy_list.at[i, "note"] = 'ordered'
                else:
                    print("Errer in order processing")
                    self.buy_list.at[i, "note"] = 'failed'
                
                # if success, upload to master book...

        for i in self.sell_list.index: 
            if self.sell_list["note"][i] == 'yet' or self.sell_list["note"][i] == 'failed':
                price = 0 # market 
                hoga == '03' # market
                res = self.km.send_order("send_order_req", "0101", ACCOUNT_NO, sell_order, self.sell_list["code"][i], self.sell_list["amount"][i], price, hoga,"")
    
                if res[0] == 0 and res[1] != "":
                    self.sell_list.at[i, "note"] = 'ordered'
                else:
                    print("Errer in order processing")
                    self.sell_list.at[i, "note"] = 'failed'
    
if __name__ == "__main__": 
    app = QApplication([''])
    trtrader = TrTrader()
    