import sys, os.path
from Kiwoom import *
import xlsxwriter
import random

MASTER_BOOK_FILE = 'data/master_book.xlsx'
MASTER_BOOK_BACKUP_FILE = 'data/backup/master_book.xlsx'
BOUNDS_FILE = 'data/bounds.xlsx'
EXTERNAL_LIST_FILE = 'data/external_list.xlsx'
EXTERNAL_LIST_BACKUP_FILE = 'data/backup/external_list.xlsx'
# RUN_WAIT_INTERVAL = 30*60 

START_CASH = 300000000
TICKET_SIZE = 3000000       # Target amount to be purchased in KRW
MIN_CASH_FOR_PURCHASE_RATE = 1.5
MIN_CASH_FOR_PURCHASE = TICKET_SIZE*MIN_CASH_FOR_PURCHASE_RATE
ACCOUNT_NO = '8135010411'   # may create master_book for each account_no
MAX_REINVESTMENT = 4        # total 5 investments max
MAX_ELEVATION = 10          # do not change this const unless bounds.xlsx is modified
# FEE_RATE = 0.00015        # real FEE_RATE
# TAX_RATE = 0.003          # real TAX_RATE (may differ by KOSDAQ/KOSPI and by product type, e.g., cheaper tax for derivative products)
FEE_RATE = 0.0035           # for simulation
TAX_RATE = 0.0025           # for simulation (may differ by KOSDAQ/KOSPI and by product type, e.g., cheaper tax for derivative products) 
CREATE_NEW_MASTER_BOOK = True # False is recommended as loading from existing stock list involves guessing on nreinv and bounds
# dec_made_DICTIONARY: new_ent (new_ent), reinv (reinvested), a_sold (a_sold), p_sold (partial_sold), SUSPEND (LLB_suspend), released (suspend_release), bd_elev (bound_elevated), loaded, EXCEPT (loading_exception)

TRENDTRADE_EXCEPT_LIST = ['105560', '078930']  # CODES IN THIS LIST ARE NOT LOADED INTO MASTER_BOOK
# Note: When adding to or subtract from TRENDTRADE_EXCEPT_LIST, CREATE_NEW_MASTER_BOOK should be set to True. Otherwise, integrity checker will fail


class TrTrader(): 
    def __init__(self):
        self.km = Kiwoom()
        if not self.km.connect_status: 
            sys.exit("System Exit")
        self.bounds_prep()
        self.master_book_initiator(START_CASH, replace = CREATE_NEW_MASTER_BOOK)
        self.master_book_integrity_checker()
        self.trtrade_list = pd.DataFrame(columns = ['code', 'amount', 'buy_sell', 'note'])
    
    def close_(self):
        self.write_master_book_to_Excel(self.master_book)
        self.status_print()
        self.status_summary_report()

    def run_(self):
        cash = self.trendtrading_mainlogic() # returns cash amount if all trtrade_list buy_sells are executed
        self.load_external_list(cash)
        self.trade_stocks()

    def load_external_list(self, cash): 
        # check exception list (stocks in exception list as well as stocks in master_book: exclude any existing stocks)
        # check cash
        if os.path.exists(EXTERNAL_LIST_FILE):
            el = TrTrader.read_external_buysell_list()
            bk = self.km.get_account_stock_list(ACCOUNT_NO)

            for i in el.index: 
                if el.at[i, 'code'] in TRENDTRADE_EXCEPT_LIST:
                    print("*** WARNING: External buysell list contains item in TRENDTRADE_EXCEPT_LIST: ", el.at[i, 'code'], " - this item ignored")
                    el = el.drop(i)
                    continue

                cprice = self.km.get_price(el.at[i,'code'])
                if el.at[i, 'buy_sell'] == 'buy': 
                    if el.at[i, 'code'] in list(bk['code']):
                        print("*** WARNING: External list contains item in current trtrading list: ", el.at[i, 'code'], " - this item ignored")
                        el = el.drop(i)
                        continue

                    ticket = int(cprice*el.at[i, 'amount']*self.tax_fee_adjustment('buy'))
                    if cash > ticket*MIN_CASH_FOR_PURCHASE_RATE: 
                        cash = cash - ticket
                    else:
                        ######################################################
                        # CHECK IF KIWOOM API WOULD LET THIS CONTINUE... 
                        # IF NOT, THIS MAY RAISE EXCEPTION TO HALT THE SYSTEM
                        print("*** WARNING: Cash is not enough for external list purchase: ", el.at[i, 'code'], " - continue anyway") 
                else: 
                    if el.at[i,'code'] not in list(bk['code']):
                        print("*** WARNING: External list contains sell item not in current trtrading list: ", el.at[i, 'code'], " - this item ignored")
                        continue
                    ci = bk.loc[bk['code'] == el.at[i, 'code']]
                    if el.at[i, 'amount'] > int(ci['nshares']):
                        print("*** WARNING: External list contains item with sell quantity exceeding current quantity: ", el.at[i, 'code'], " - sell quanity set to max") 
                        el.at[i, 'amount'] = int(ci['nshares'])
                    ticket = int(cprice*el.at[i, 'amount']*self.tax_fee_adjustment('sell'))
                    cash = cash + ticket

            if len(el) > 0: 
                print('External buy_sell list loaded')
                self.trtrade_list = self.trtrade_list.append(el)
            
        else: 
            print('No external buy_sell list')
            pass


    def trade_stocks(self):
        ##################################################
        # MODIFY TO SELL FIRST AND THEN BUY
        bs_lookup = {'buy': 1, 'sell': 2}
        for i in self.trtrade_list.index:
            if self.trtrade_list["note"][i] == 'yet': # or self.trtrade_list["note"][i] == 'failed': ############################### For failed, re running of tr-mainlogic would result in adding the same item
                res = self.km.send_order("send_order_req", "0101", ACCOUNT_NO, bs_lookup[self.trtrade_list["buy_sell"][i]], 
                        self.trtrade_list["code"][i], self.trtrade_list["amount"][i], 0, '03', "") # trade in market price, price = 0, hoga = '3'
    
                if res[0] == 0 and res[1] != "":
                    self.trtrade_list.at[i, "note"] = 'ordered'
                    a = self.km.chejan_finish_data
                    self.km.chejan_finish_data = []
                    self._write_transaction_to_master_book(a[0], a[1], a[2], a[3], a[4], a[5])
                else:
                    print("Errer in order processing")
                    self.trtrade_list.at[i, "note"] = 'failed'

    def trendtrading_mainlogic(self):
        # Trend trading logic
        # [step 0] for active set copy, do the following
        mb_active = self.master_book.loc[self.master_book['active']]
        cash = self.master_book.at[self.master_book.index[-1], 'cash']
        
        # [step 1] update cprice, cvalue, retrate
        for i in mb_active.index:
            updated_price = self.km.get_price(mb_active.at[i, 'code'])
            updated_value = int(updated_price*mb_active.at[i, 'nshares']*self.tax_fee_adjustment('sell'))
            updated_rr = round(updated_value/mb_active.at[i, 'invtotal'] - 1, 4)
            mb_active.at[i, 'cprice'] = updated_price
            mb_active.at[i, 'cvalue'] = updated_value
            mb_active.at[i, 'retrate'] = updated_rr
            
        # [step 2] for dec_made == SUSPEND or EXCEPT, check if rr is back up to LB
                # then dec_made = released, update dec_time
                # otherwise, leave it as is
            if mb_active.at[i, 'dec_made'] == "SUSPEND" or mb_active.at[i, 'dec_made'] == "EXCEPT": 
                if updated_rr >= mb_active.at[i, 'LB']:
                    mb_active.at[i, 'dec_made'] = "released"
                    mb_active.at[i, 'dec_time'] = time.ctime()
                else: 
                    self.master_book.loc[i,:] = mb_active.loc[i,:]
        # [step 3] for dec_made != SUSPEND and != "EXCEPT": compare rr with LLB, LB, UB
            if mb_active.at[i, 'dec_made'] != "SUSPEND" and mb_active.at[i, 'dec_made'] != "EXCEPT":
                # if hits LLB, suspend trading until it reaches LB: dec_made = SUSPEND, update dec_time
                if updated_rr <= mb_active.at[i, 'LLB']:
                    mb_active.at[i, 'dec_made'] = "SUSPEND"
                    mb_active.at[i, 'dec_time'] = time.ctime()
                    self.master_book.loc[i,:] = mb_active.loc[i,:]

                # if in between LLB and LB, sell (at loss): add this item to the trtrade_list (sell), code and quantity, DO NOT CHANGE MASTER BOOK 
                else:
                    if updated_rr <= mb_active.at[i, 'LB']:
                        self.trtrade_list.loc[len(self.trtrade_list)] = [self.master_book.at[i, 'code'], int(self.master_book.at[i, 'nshares']), 'sell', 'yet']
                        cash = cash + updated_value
                # if in between LB and UB: hold 
                    elif updated_rr < mb_active.at[i, 'UB']:
                        self.master_book.loc[i,:] = mb_active.loc[i,:]
                # if hits UB: 
                    else:
                    # elif no_repurchase = MAX_ELEVATION: add this item to the trade_list (sell), DO NOT CHANGE MASTER BOOK
                        nr = mb_active.at[i, 'nreinv'] 
                        if nr == MAX_ELEVATION:
                            self.trtrade_list.loc[len(self.trtrade_list)] = [self.master_book.at[i, 'code'], int(self.master_book.at[i, 'nshares']), 'sell', 'yet']
                            cash = cash + updated_value
                        else: 
                        # check cash, 
                            # if cash > MIN_CASH_FOR_PURCHASE and no_repurchase < MAX_REINVESTMENT: add this item to trade_list (buy), DO NOT CHANGE MASTER BOOK
                            if cash > MIN_CASH_FOR_PURCHASE and nr < MAX_REINVESTMENT:
                                self.trtrade_list.loc[len(self.trtrade_list)] = [self.master_book.at[i, 'code'], int(TICKET_SIZE/updated_price), 'buy', 'yet']
                                cash = cash - TICKET_SIZE
                            # else elevate bounds 1 steps, and update no_repurchase, dec_made = "bd_elev" and dec_time 
                            else: 
                                mb_active.at[i, 'nreinv'] = nr + 1
                                [LLB, LB, UB] = self.bounds(nr+1)
                                mb_active.at[i, 'LLB'] = LLB
                                mb_active.at[i, 'LB'] = LB
                                mb_active.at[i, 'UB'] = UB
                                mb_active.at[i, 'dec_made'] = 'bd_elev'
                                mb_active.at[i, 'dec_time'] = time.ctime()
                                self.master_book.loc[i,:] = mb_active.loc[i,:]

        return cash

    def master_book_integrity_checker(self): 
        bk = self.km.get_account_stock_list(ACCOUNT_NO)
        for exception_code in TRENDTRADE_EXCEPT_LIST: 
            bk = bk[bk['code'] != exception_code]
        bk = bk.reset_index(drop=True)
        ch = int(self.km.get_cash(ACCOUNT_NO))
        print('Cash in Kiwoom Account is: ', format(ch, ','))
                
        if CREATE_NEW_MASTER_BOOK == True:
            if ch < START_CASH - bk['invtotal'].sum()*self.tax_fee_adjustment('buy'):
                raise Exception('INSUFFICIENT CASH TO START TREND TRADING')
            entries = pd.DataFrame(columns = self.master_book.columns)
            entries[['code', 'name', 'cprice', 'nshares', 'invtotal', 'cvalue', 'retrate']]  = bk[['code', 'name', 'cprice', 'nshares', 'invtotal', 'cvalue', 'retrate']]
            entries['invtotal'] = round(entries['invtotal']*self.tax_fee_adjustment('buy'))
            entries['cvalue'] = round(entries['cvalue']*self.tax_fee_adjustment('sell'))
            entries = entries.astype({'invtotal': 'int', 'cvalue': 'int'})
            entries['ret'] = 0
            entries['retrate'] = round((entries['cvalue']-entries['invtotal'])/entries['invtotal'], 4)
            entries['init_invtime'] = entries['dec_time'] = time.ctime()
            entries['dec_made'] = 'loaded'
            entries['active'] = True
            for i in bk.index:
                res = self.nreinv_find(entries.at[i, 'retrate'])
                if res[0] == -1:
                    entries.at[i, 'dec_made'] = 'EXCEPT'
                    print(' - ', entries.at[i,'code'], entries.at[i, 'name'], ' > EXCEPT')
                entries.at[i, 'nreinv'] = nr = res[1]
                [LLB, LB, UB] = self.bounds(nr)
                entries.at[i, 'LLB'] = LLB
                entries.at[i, 'LB'] = LB
                entries.at[i, 'UB'] = UB
                if i == 0: 
                    entries.at[i, 'cash'] = int(START_CASH - entries.at[i,'invtotal'])
                else: 
                    entries.at[i, 'cash'] = int(entries.at[i-1, 'cash'] - entries.at[i,'invtotal'])
            self.master_book = self.master_book.append(entries)
            self.master_book = self.master_book.reset_index(drop=True)
            print('[Initiation success]: Existing stock list from Kiwoom API loaded into master_book')

        else: 
            #############################################
            # Loading existing book 
            # master_book active items should match bk items
            mb_cash = self.master_book.at[len(self.master_book)-1, 'cash']
            if mb_cash > ch: 
                raise Exception("Master_book loading error - cash balance insufficient")
            mb_active = self.master_book.loc[self.master_book['active']] # selected subset of DataFrame is already a deep copy of original DataFrame 
            if len(mb_active) != len(bk): 
                raise Exception("Master_Book integrity check: error (1)") # this error could occur when releasing and adding to TRENDTRADE_EXCEPT_LIST 
            for i in bk.index: 
                mt = mb_active[mb_active['code'] == bk.at[i, 'code']]
                if len(mt) != 1: 
                    raise Exception("Master_Book integrity check: error (2)") 
                l = list(mt.index)[0]
                if mt.at[l, 'nshares'] != bk.at[i, 'nshares']: 
                    raise Exception("Master_Book integrity check: error (3)") 
                if (mt.at[l, 'invtotal'] - bk.at[i, 'invtotal']*self.tax_fee_adjustment('buy'))/mt.at[l, 'invtotal'] > 0.01:
                    raise Exception("Master_Book integrity check: error (4)") 
            print('[Initiation success]: Existing stock list from Kiwoom API matches with master_book') 

    def master_book_initiator(self, initial_cash_amount, replace = False): 
        if os.path.exists(MASTER_BOOK_FILE) and not replace: 
            print("USING EXISTING MASTER BOOK - master book file already exists")

        else:
            if os.path.exists(MASTER_BOOK_FILE) and replace: 
                t = time.strftime("_%Y%m%d_%H%M%S")
                n = MASTER_BOOK_BACKUP_FILE[:-5]
                os.rename(WORKING_DIR_PATH+MASTER_BOOK_FILE, WORKING_DIR_PATH+n+t+'.xlsx')
            
            mb = xlsxwriter.Workbook(MASTER_BOOK_FILE)
            mbws = mb.add_worksheet() 
            mbws.write('A1', 'code') 
            mbws.write('B1', 'name') 
            mbws.write('C1', 'cprice') # price at the time of the decision, current_price
            mbws.write('D1', 'nshares') # number of shares
            mbws.write('E1', 'nreinv') # number of reinvestements
            mbws.write('F1', 'LLB') # Limit Lower Bound
            mbws.write('G1', 'LB')  
            mbws.write('H1', 'UB') 
            mbws.write('I1', 'invtotal')  # invested total amount after entry fee
            mbws.write('J1', 'cvalue') # value at the time of the decision (after tax and exit fee) current_value
            mbws.write('K1', 'retrate') # return_rate
            mbws.write('L1', 'ret')  # return resulted due to the decision in the current line
            mbws.write('M1', 'init_invtime') 
            mbws.write('N1', 'dec_made') # decision that resulted in the current line
            mbws.write('O1', 'dec_time') 
            mbws.write('P1', 'active')  # True: for currently holding stocks, False: for record
            mbws.write('Q1', 'cash') # d+2 cash after all tax and fee
            
            mbws.write('A2', '-')
            mbws.write('B2', 'init')  
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
            mbws.write('N2', '-')  
            mbws.write('O2', time.ctime()) 
            mbws.write('P2', False)  
            mbws.write('Q2', initial_cash_amount)  
            mb.close()

        self.master_book = self.read_master_book_from_Excel()

    def read_master_book_from_Excel(self):
        mb_converters = {'code': str, 
                            'name': str, 
                            'cprice': int, 
                            'nshares': int, 
                            'nreinv': int, 
                            'LLB': float, 
                            'LB': float, 
                            'UB': float, 
                            'invtotal': int, 
                            'cvalue': int, 
                            'retrate': float, 
                            'ret': int, 
                            'init_invtime': str, 
                            'dec_made': str, 
                            'dec_time': str, 
                            'active': bool, 
                            'cash': int }

        master_book = pd.read_excel(MASTER_BOOK_FILE, index_col = None, converters=mb_converters)
        master_book['init_invtime'] = pd.to_datetime(master_book['init_invtime'])
        master_book['dec_time'] = pd.to_datetime(master_book['dec_time'])

        return master_book
    
    @staticmethod
    def read_external_buysell_list():
        el_converters = {'code': str, 
                         'amount': int, 
                         'buy_sell': str, 
                         'note': str}
        el = pd.read_excel(EXTERNAL_LIST_FILE, index_col = None, converters=el_converters)

        t = time.strftime("_%Y%m%d_%H%M%S")
        n = EXTERNAL_LIST_BACKUP_FILE[:-5]
        os.rename(WORKING_DIR_PATH+EXTERNAL_LIST_FILE, WORKING_DIR_PATH+n+t+'.xlsx')

        return el

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
                new_line.at[0, 'cprice'] = price
                new_line.at[0, 'nshares'] = quantity
                new_line.at[0, 'nreinv'] = nr = 0 
                [LLB, LB, UB] = self.bounds(nr)
                new_line.at[0, 'LLB'] = LLB
                new_line.at[0, 'LB'] = LB
                new_line.at[0, 'UB'] = UB
                new_line.at[0, 'invtotal'] = v1 = int(price*quantity*self.tax_fee_adjustment('buy'))
                new_line.at[0, 'cvalue'] = v2 = int(price*quantity*self.tax_fee_adjustment('sell'))
                new_line.at[0, 'retrate'] = round((v2-v1)/v1, 4)
                new_line.at[0, 'ret'] = 0
                new_line.at[0, 'init_invtime'] = tr_time
                new_line.at[0, 'dec_made'] = 'new_ent'
                new_line.at[0, 'dec_time'] = tr_time
                new_line.at[0, 'active'] = True
                new_line.at[0, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] - v1

            elif len(active_line) == 1:
                idx = list(active_line.index)[0]
                self.master_book.at[idx, 'active'] = False
                new_line = active_line
                # new_line.at[idx, 'code'] = code # should be the same
                # new_line.at[idx, 'name'] = name 
                new_line.at[idx, 'cprice'] = price # price update
                new_line.at[idx, 'nshares'] = ns = new_line.at[idx, 'nshares'] + quantity # repurchase
                new_line.at[idx, 'nreinv'] = nr = new_line.at[idx, 'nreinv'] + 1
                if nr > MAX_ELEVATION:  
                    raise Exception("Do not attmpt to purchase over MAX_ELEVATION")
                [LLB, LB, UB] = self.bounds(nr)
                new_line.at[idx, 'LLB'] = LLB
                new_line.at[idx, 'LB'] = LB
                new_line.at[idx, 'UB'] = UB
                new_line.at[idx, 'invtotal'] = v1 = new_line.at[idx, 'invtotal'] + int(price*quantity*self.tax_fee_adjustment('buy'))
                new_line.at[idx, 'cvalue'] = v2 = int((price*ns)*self.tax_fee_adjustment('sell'))
                new_line.at[idx, 'retrate'] = round((v2-v1)/v1, 4)
                new_line.at[idx, 'ret'] = 0
                # new_line.at[0, 'init_invtime'] = tr_time # does not change
                new_line.at[idx, 'dec_made'] = 'reinv'
                new_line.at[idx, 'dec_time'] = tr_time # update time
                new_line.at[idx, 'active'] = True
                new_line.at[idx, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] - v1

            else: 
                raise Exception("ERROR in Master_Book Integrity - buy")

        else: # buy_sell == 'sell':
            if len(active_line) == 1: 
                idx = list(active_line.index)[0]
                self.master_book.at[idx, 'active'] = False
                new_line = active_line
                # new_line.at[idx, 'code'] = code
                # new_line.at[idx, 'name'] = name
                new_line.at[idx, 'cprice'] = price # price update
                original_quantity = new_line.at[idx, 'nshares']
                new_line.at[idx, 'nshares'] = remained_quantity = original_quantity - quantity
                # new_line.at[idx, 'nreinv'] = nr = 0 
                # new_line.at[idx, 'LLB'] = 0  #### function of nr
                # new_line.at[idx, 'LB'] = 0  #### 
                # new_line.at[idx, 'UB'] = 0  #### 
                avg_price = new_line.at[idx, 'invtotal'] / original_quantity
                new_line.at[idx, 'invtotal'] = v1 = avg_price*remained_quantity 
                new_line.at[idx, 'cvalue'] = v2 = int(price*remained_quantity*self.tax_fee_adjustment('sell'))
                if v1 != 0:  # remained_quantity is not zero
                    new_line.at[idx, 'retrate'] = round((v2-v1)/v1, 4)
                else: 
                    new_line.at[idx, 'retrate'] = 0
                v3 = (price*quantity*self.tax_fee_adjustment('sell'))
                new_line.at[idx, 'ret'] = v3 - avg_price*quantity
                # new_line.at[idx, 'init_invtime'] = tr_time # does not change
                if remained_quantity == 0: 
                    new_line.at[idx, 'dec_made'] = 'a_sold' 
                    new_line.at[idx, 'active'] = False
                else: 
                    new_line.at[idx, 'dec_made'] = 'p_sold'
                    new_line.at[idx, 'active'] = True
                new_line.at[idx, 'dec_time'] = tr_time
                new_line.at[idx, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] + v3 
                if remained_quantity < 0: 
                    raise Exception("Netagive remained quantity")
            else: 
                raise Exception("ERROR in Master_Book Integrity - sell")
        
        new_line.index = [len(self.master_book)]
        self.master_book = self.master_book.append(new_line)
    
    def bounds_prep(self):
        self.bounds_table = pd.read_excel(BOUNDS_FILE, index_col=None).iloc[29:32, 1:13]
        self.bounds_table.columns = ['var', 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.bounds_table = self.bounds_table.set_index('var')

    def bounds(self, nr): # nr = number of repurchase
        UB = round(self.bounds_table.at['UB', nr], 4)
        LB = round(self.bounds_table.at['LB', nr], 4)
        LLB = round(self.bounds_table.at['LLB', nr], 4)
        return [LLB, LB, UB]
    
    def nreinv_find(self, rr): 
        res = [0, 0]
        if rr <= self.bounds_table.at['LLB', 0]: 
            # raise Exception("Current return rate is even lower than LLB for initial investment")
            # print("Return rate is even lower than LLB for initial investment")
            res[0] = -1
        elif rr <= self.bounds_table.at['LB', 0]:  
            # raise Exception("Current return rate is even lower than LB for initial investment")
            # print("Return rate is even lower than LB for initial investment") 
            res[0] = -1
        else: 
            pass 

        for i in self.bounds_table.columns: 
            if rr <= self.bounds_table.at['LB', i]:
                res[1] = max(i-1, 0)  
                return res
        res[1] = MAX_ELEVATION
        return res

    def tax_fee_adjustment(self, buy_sell):
        if buy_sell == 'buy': 
            return 1+FEE_RATE # when buying, you pay additional cash for fee
        else: # buy_sell == 'sell':
            return 1-(FEE_RATE + TAX_RATE) # when selling, your cash is dedcuted by tax and fee
    
    def status_summary_report(self):
        # Cash at ACCOUNT
        # Cash at TrTrading
        # Total invested amount accross all items
        # Current value total across all items
        # Return rate of TrTrading
        # Realized return total 
        # Number of active items
        cash_account = format(int(int(self.km.get_cash(ACCOUNT_NO))/1000), ',')
        mb_active = self.master_book.loc[self.master_book['active']]
        cash_trtrading = format(int(mb_active.at[mb_active.index[-1], 'cash']/1000), ',')
        tr_invested_total = mb_active['invtotal'].sum()
        tr_cvalue_total = mb_active['cvalue'].sum()
        if tr_invested_total > 0: 
            tr_return_rate = tr_cvalue_total/tr_invested_total -1
        else: 
            tr_return_rate = 0
        tr_invested_total = format(int(tr_invested_total/1000), ',')
        tr_cvalue_total = format(int(tr_cvalue_total/1000), ',')
        tr_return_rate = format(tr_return_rate*100, '.2f')
        tr_realized_return_total = format(int(mb_active['ret'].sum()/1000), ',')
        no_active = len(mb_active)
        t = time.strftime("%Y%m%d %H:%M:%S") 

        self.km.trade_log_write("[Trend Trade Summary - " + t + "]")
        self.km.trade_log_write(" - Kiwoom Cash(k): " + cash_account + ' | TrTrading Cash(k): ' + cash_trtrading)
        self.km.trade_log_write(' - Return(%): ' + tr_return_rate + ' | #items: ' + str(no_active))
        self.km.trade_log_write(" - Total invested(k): " + tr_invested_total + ' | Current Value(k): ' + tr_cvalue_total)
        self.km.trade_log_write(' - Realized Return Total(k): ' + tr_realized_return_total + ' | Exception List: ' + str(TRENDTRADE_EXCEPT_LIST))
        self.km.trade_log_write("-----------------------------------------")


    def status_print(self):
        l = ['code', 'name', 'cpr', 'vol', 'nr', 'LL(%)', 'L(%)', 'U(%)', 'invt(k)', 'cval(k)', 'ret(%)', 'ret(k)', 'dec', 'act', 'cash(k)']
        if len(self.master_book) > 0:
            mb_print = self.master_book.copy()
            mb_print = mb_print.astype(str)
            for i in mb_print.index:
                mb_print.at[i, 'name'] = mb_print.at[i, 'name'][:4]
                mb_print.at[i, 'cprice'] = format(int(mb_print.at[i, 'cprice']), ',')
                mb_print.at[i, 'nshare'] = format(int(mb_print.at[i, 'nshares']), ',')
                mb_print.at[i, 'LLB'] = format(float(mb_print.at[i, 'LLB'])*100, '.1f')
                mb_print.at[i, 'LB'] = format(float(mb_print.at[i, 'LB'])*100, '.1f')
                mb_print.at[i, 'UB'] = format(float(mb_print.at[i, 'UB'])*100, '.1f')
                mb_print.at[i, 'invtotal'] = format(int(int(mb_print.at[i, 'invtotal'])/1000), ',')
                mb_print.at[i, 'cvalue'] = format(int(int(mb_print.at[i, 'cvalue'])/1000), ',')
                mb_print.at[i, 'ret'] = format(int(int(mb_print.at[i, 'ret'])/1000), ',')
                mb_print.at[i, 'cash'] = format(int(int(mb_print.at[i, 'cash'])/1000), ',')
                mb_print.at[i, 'retrate'] = format(float(mb_print.at[i, 'retrate'])*100, '.1f')
            mb_print = mb_print.rename(columns={'cprice': 'cpr', 'nshares': 'vol', 'nreinv': 'nr', 'LLB': 'LL(%)', 'LB': 'L(%)', 'UB': 'U(%)', 
                                        'invtotal': 'invt(k)', 'cvalue': 'cval(k)', 'retrate':'ret(%)', 'ret': 'ret(k)', 'dec_made': 'dec', 'active': 'act', 'cash': 'cash(k)'})
            print('MASTER_BOOK (up to last 75 items): \n', tabulate(mb_print.loc[-75:, l], headers='keys', tablefmt='psql')) 
        else: 
            print('Master_book empty')
        if len(self.trtrade_list) > 0:
            print('trtrade_list (up to last 75 items): \n', tabulate(self.trtrade_list.loc[-75:, :], headers='keys', tablefmt='psql'))
        else: 
            print('trtrade_list empty')

        
if __name__ == "__main__": 
    app = QApplication(sys.argv)
    trtrader = TrTrader()
    trtrader.run_() 
    trtrader.close_()