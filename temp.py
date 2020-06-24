from Kiwoom import *
import random

MASTER_BOOK_FILE = 'data/master_book.xlsx'
BOUNDS_FILE = 'bounds.xlsx'
# RUN_WAIT_INTERVAL = 30*60 

START_CASH = 100000000
TICKET_SIZE = 3000000 # Target amount to be purchased in KRW
ACCOUNT_NO = '8135010411' # may create master_book for each account_no
# MAX_REINVESTMENT = 4 # total 5 investments max
FEE_RATE = 0.00015
TAX_RATE = 0.003

class TrTrader(): 
    def __init__(self):
        self.km = Kiwoom()
        self.master_book_initiator(START_CASH, replace = False)
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

        self.trade_stocks()
        # for i in self.buy_list.index: 
        #     tr_time = time.ctime()
        #     self._write_transaction_to_master_book(self.buy_list['code'][i], 'testname'+str(i), 'buy', random.randint(10000,20000), random.randint(100,200), tr_time)

        # for i in self.sell_list.index: 
        #     tr_time = time.ctime()
        #     self._write_transaction_to_master_book(self.sell_list['code'][i], 'testname'+str(i), 'sell', random.randint(1000,2000), random.randint(10,20), tr_time)

        # on closing... 
        self.write_master_book_to_Excel(self.master_book)
        print(self.master_book)

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
                    a = self.km.chejan_finish_data
                    self.km.chejan_finish_data = []
                    self._write_transaction_to_master_book(a[0], a[1], a[2], a[3], a[4], a[5])
                else:
                    print("Errer in order processing")
                    self.buy_list.at[i, "note"] = 'failed'

        for i in self.sell_list.index: 
            if self.sell_list["note"][i] == 'yet' or self.sell_list["note"][i] == 'failed':
                price = 0 # market 
                hoga == '03' # market
                res = self.km.send_order("send_order_req", "0101", ACCOUNT_NO, sell_order, self.sell_list["code"][i], self.sell_list["amount"][i], price, hoga,"")
    
                if res[0] == 0 and res[1] != "":
                    self.sell_list.at[i, "note"] = 'ordered'
                    a = self.km.chejan_finish_data
                    self.km.chejan_finish_data = []
                    self._write_transaction_to_master_book(a[0], a[1], a[2], a[3], a[4], a[5])
                else:
                    print("Errer in order processing")
                    self.sell_list.at[i, "note"] = 'failed'
    
    def master_book_initiator(self, initial_cash_amount, replace = False): 
        if os.path.exists(MASTER_BOOK_FILE) and not replace: 
            print("USING EXISTING MASTER BOOK - master book file already exists")

        else:
            if os.path.exists(MASTER_BOOK_FILE) and replace: 
                t = time.strftime("_%Y%m%d_%H%M%S")
                n = MASTER_BOOK_FILE[:-5]
                os.rename(WORKING_DIR_PATH+MASTER_BOOK_FILE, WORKING_DIR_PATH+n+t+'.xlsx')
            
            mb = xlsxwriter.Workbook(MASTER_BOOK_FILE)
            mbws = mb.add_worksheet() 
            mbws.write('A1', 'code') 
            mbws.write('B1', 'name') 
            mbws.write('C1', 'cur_price') # price at the time of the decision
            mbws.write('D1', 'no_shares') 
            mbws.write('E1', 'no_reinvested') 
            mbws.write('F1', 'LLB') 
            mbws.write('G1', 'LB') 
            mbws.write('H1', 'UB') 
            mbws.write('I1', 'total_invested')  # invested amount after entry fee
            mbws.write('J1', 'cur_value') # value at the time of the decision (after tax and exit fee)
            mbws.write('K1', 'return_rate')
            mbws.write('L1', 'return_realized')  # return resulted due to the decision in the current line
            mbws.write('M1', 'initial_inv_datetime') 
            mbws.write('N1', 'decision_made') # decision that resulted in the current line
            mbws.write('O1', 'decision_datetime') 
            mbws.write('P1', 'active')  # True: for currently holding stocks, False: for record
            mbws.write('Q1', 'cash') # d+2 cash after all tax and fee
            
            mbws.write('A2', '000000')
            mbws.write('B2', 'list_initiated')  
            mbws.write('C2', 0)  
            mbws.write('D2', 0)  
            mbws.write('E2', 0)  
            mbws.write('F2', 0)  
            mbws.write('G2', 0)  
            mbws.write('H2', 0)  
            mbws.write('I2', 0)  
            mbws.write('J2', 0)  
            mbws.write('K2', 0) 
            mbws.write('L2', 0)  
            mbws.write('M2', time.ctime()) 
            mbws.write('N2', 'Initialzied')  
            mbws.write('O2', time.ctime()) 
            mbws.write('P2', False)  
            mbws.write('Q2', initial_cash_amount)  
            mb.close()

        self.master_book = self.read_master_book_from_Excel()

    def read_master_book_from_Excel(self):
        mb_converters = {'code': str, 
                            'name': str, 
                            'cur_price': int, 
                            'no_shares': int, 
                            'no_reinvested': int, 
                            'LLB': float, 
                            'LB': float, 
                            'UB': float, 
                            'total_invested': int, 
                            'cur_value': int, 
                            'return_rate': float, 
                            'return_realized': int, 
                            'initial_inv_datetime': str, 
                            'decision_made': str, 
                            'decision_datetime': str, 
                            'active': bool, 
                            'cash': int }

        master_book = pd.read_excel(MASTER_BOOK_FILE, index_col = None, converters=mb_converters)
        master_book['initial_inv_datetime'] = pd.to_datetime(master_book['initial_inv_datetime'])
        master_book['decision_datetime'] = pd.to_datetime(master_book['decision_datetime'])

        return master_book
    
    def write_master_book_to_Excel(self, master_book):
        master_book.to_excel(MASTER_BOOK_FILE, index = False)

    def _write_transaction_to_master_book(self, code, name, buy_sell, price, quantity, tr_time):
        # this function is to be used only after SendOrder success
        mb_active = self.master_book.loc[self.master_book["active"]]
        active_line = mb_active[mb_active['code'] == code]

        if buy_sell == 'buy': 
            if len(active_line) == 0: 
                new_line = pd.DataFrame(columns = self.master_book.columns)
                new_line.at[0, 'code'] = code
                new_line.at[0, 'name'] = name
                new_line.at[0, 'cur_price'] = price
                new_line.at[0, 'no_shares'] = quantity
                new_line.at[0, 'no_reinvested'] = nr = 0 
                [LLB, LB, UB] = self.bounds(nr)
                new_line.at[0, 'LLB'] = LLB
                new_line.at[0, 'LB'] = LB
                new_line.at[0, 'UB'] = UB
                new_line.at[0, 'total_invested'] = v1 = price*quantity*self.tax_fee_adjustment('buy')
                new_line.at[0, 'cur_value'] = v2 = price*quantity*self.tax_fee_adjustment('sell')
                new_line.at[0, 'return_rate'] = (v2-v1)/v1 
                new_line.at[0, 'return_realized'] = 0
                new_line.at[0, 'initial_inv_datetime'] = tr_time
                new_line.at[0, 'decision_made'] = 'new_entry'
                new_line.at[0, 'decision_datetime'] = tr_time
                new_line.at[0, 'active'] = True
                new_line.at[0, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] - v1
                if ch < 0: 
                    raise Exception("Negative Cash Balance") 

            elif len(active_line) == 1:
                idx = list(active_line.index)[0]
                self.master_book.at[idx, 'active'] = False
                new_line = active_line
                # new_line.at[idx, 'code'] = code # should be the same
                # new_line.at[idx, 'name'] = name 
                new_line.at[idx, 'cur_price'] = price # price update
                new_line.at[idx, 'no_shares'] = ns = new_line.at[idx, 'no_shares'] + quantity # repurchase
                new_line.at[idx, 'no_reinvested'] = nr = new_line.at[idx, 'no_reinvested'] + 1
                [LLB, LB, UB] = self.bounds(nr)
                new_line.at[idx, 'LLB'] = LLB
                new_line.at[idx, 'LB'] = LB
                new_line.at[idx, 'UB'] = UB
                new_line.at[idx, 'total_invested'] = v1 = new_line.at[idx, 'total_invested'] + price*quantity*self.tax_fee_adjustment('buy') 
                new_line.at[idx, 'cur_value'] = v2 = (price*ns)*self.tax_fee_adjustment('sell')
                new_line.at[idx, 'return_rate'] = (v2-v1)/v1 
                new_line.at[idx, 'return_realized'] = 0
                # new_line.at[0, 'initial_inv_datetime'] = tr_time # does not change
                new_line.at[idx, 'decision_made'] = 'reinvested'
                new_line.at[idx, 'decision_datetime'] = tr_time # update time
                new_line.at[idx, 'active'] = True
                new_line.at[idx, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] - v1
                if ch < 0: 
                    raise Exception("Negative Cash Balance") 

            else: 
                raise Exception("ERROR in Master_Book Integrity - buy")

        else: # buy_sell == 'sell':
            if len(active_line) == 1: 
                idx = list(active_line.index)[0]
                self.master_book.at[idx, 'active'] = False
                new_line = active_line
                # new_line.at[idx, 'code'] = code
                # new_line.at[idx, 'name'] = name
                new_line.at[idx, 'cur_price'] = price # price update
                original_quantity = new_line.at[idx, 'no_shares']
                new_line.at[idx, 'no_shares'] = remained_quantity = original_quantity - quantity
                # new_line.at[idx, 'no_reinvested'] = nr = 0 
                # new_line.at[idx, 'LLB'] = 0  #### function of nr
                # new_line.at[idx, 'LB'] = 0  #### 
                # new_line.at[idx, 'UB'] = 0  #### 
                avg_price = new_line.at[idx, 'total_invested'] / original_quantity
                new_line.at[idx, 'total_invested'] = v1 = avg_price*remained_quantity 
                new_line.at[idx, 'cur_value'] = v2 = price*remained_quantity*self.tax_fee_adjustment('sell')
                new_line.at[idx, 'return_rate'] = (v2-v1)/v1 
                v3 = price*quantity*self.tax_fee_adjustment('sell')
                new_line.at[idx, 'return_realized'] = v3 - avg_price*quantity
                # new_line.at[idx, 'initial_inv_datetime'] = tr_time # does not change
                if remained_quantity == 0: 
                    new_line.at[idx, 'decision_made'] = 'all_sold' 
                    new_line.at[idx, 'active'] = False
                else: 
                    new_line.at[idx, 'decision_made'] = 'partial_sold'
                    new_line.at[idx, 'active'] = True
                new_line.at[idx, 'decision_datetime'] = tr_time
                new_line.at[idx, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] + v3 
                if remained_quantity < 0: 
                    raise Exception("Netagive remained quantity")
            else: 
                raise Exception("ERROR in Master_Book Integrity - sell")
        
        new_line.index = [len(self.master_book)]
        self.master_book = self.master_book.append(new_line)
    
    def bounds(self, nr): # nr = number of repurchase
        # Trend trading logic
        # if hits LLB, suspend trading until it reaches LB
        # if in between LLB and LB, sell (at loss)
        # if in between LB and UB, hold
        # if hits UB, repurchase
        # define max reinvestment 
        bounds = pd.read_excel(BOUNDS_FILE, index_col=None).iloc[29:32, 1:13]
        bounds.columns = ['var', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        UB = bounds.iat[0, nr+1]
        LB = bounds.iat[1, nr+1]
        LLB = bounds.iat[2, nr+1]
        return [LLB, LB, UB]

    def tax_fee_adjustment(self, buy_sell):
        if buy_sell == 'buy': 
            return 1+FEE_RATE # when buying, you may additional cash for fee
        else: # buy_sell == 'sell':
            return 1-(FEE_RATE + TAX_RATE) # when selling, your cash is dedcuted by tax and fee

        
if __name__ == "__main__": 
    app = QApplication([''])
    trtrader = TrTrader()
    