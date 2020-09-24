import xlsxwriter
import random
import urllib.request
from bs4 import BeautifulSoup
from trsettings import *
from Kiwoom import *
from simulator import * 

################################################################################################
EXTERNAL_LIST_FILE = TRTRADER_DATA_DIR+'external_list.xlsx'
EXTERNAL_LIST_BACKUP_FILE = TRTRADER_DATA_BACKUP_DIR+'external_list.xlsx'
STATUS_REPORT_FILE = TRTRADER_DATA_DIR+'trtrader_status.txt'
STATUS_REPORT_MOBILE = TRTRADER_DATA_DIR+'trtrader_status_brief.txt'
EXTERNAL_COMMAND_URL = "http://13.209.99.197/command.html"
EXT_COMM_SUSPEND_SLEEPING_TIME = 10
################################################################################################
CREATE_NEW_MASTER_BOOK = False  # False is recommended as loading from existing stock list involves guessing on nreinv and bounds
                                # Note: refer to the note below TRENDTRADE_EXCEPT_LIST
                                # Or, you may leave this as False, and simply delete the existing master book file / or manually move the file to 
                                # back-up folder with filename change 
TRENDTRADE_EXCEPT_LIST = []
                                # Codes in this list are not loaded into master_book (regardless whether you actually have this stock or not in the account)
                                # Note: When adding to or subtract from TRENDTRADE_EXCEPT_LIST, CREATE_NEW_MASTER_BOOK should be set to True, or 
                                # the master book should be newly created (e.g., there should be no previous master book excel file, so that it can be created) 
                                # Otherwise, integrity checker could fail (i.e., if you already have the stock in the EXC-LIST in the master_book, 
                                # checker will raise error as the master book has a stock in the EXC-LIST. However, if the master book does not have the stock, 
                                # there will be no error raised.)
EXTERNAL_COMMAND_LIST = ['suspend', 'resume', 'stop', 'ping']
                                # Only the first and the second lines matter in the external command file
                                # Only when the command input time is later than the current trtrader initiation time or last execution time, the command will be accepted
                                # - External commands only works for an already running trtrader 
                                # - However, future time can be set if you want to enforce the command
                                # - You can only suspend or stop for a running trtrader
                                # - For a suspended trtrader, you can resume or stop
                                # - Although you stop a trtrader, controller could continue running as trtrader run by a multiprocess
                                # - For ping, prints whether trtrader is active or not (not about controller)
                                # Format:
                                # YYYYMMDD HH:MM:SS
                                # one_word_command
                                # (other lines are ignored)
################################################################################################

# items in dec_made: new_ent (new_ent), reinv (reinvested), a_sold (a_sold), p_sold (partial_sold), 
#                    SUSPEND (LLB_suspend), released (suspend_release), bd_elev (bound_elevated), loaded, EXCEPT (loading_exception)
ABRIDGED_DICT = {'new_ent':  'N', 'reinv': 'R', 'a_sold': 'S', 'p_sold': 'P', 'SUSPEND': 'U', 'released': 'A', 'bd_elev': 'B', 'loaded': 'L', 'EXCEPT': 'E'}

# Note: 
# - External list is loaded and added to trtrade_list, and erased (moved to backup/) when Python code starts 
# - All 'yet' item in trtrade_list are tried only once
# - Trtrade_list is lost when Python code finishes  
# - Therefore, external list could lost without any successful execution if the Python code runs/finishes during out of market open time
# - So, be careful not to lose external_list items 
# (THIS MAY NEED TO BE IMPROVED - NOT TO AUTOMATICALLY LOSE EXTERNAL ITMES)
# 
# - On the other hand, automatically generated items in trtrade_list by trendtrading_mainlogic are safe to lose as long as CREATE_NEW_MASTER_BOOK == False, 
#   as they will be re-created when trendtrading_mainlogic is re-run


class TrTrader():   
    def __init__(self, simctrl_instance = None):  
        self.ext_command_last_excution_time_ = datetime.now() # last execution set to __init__ time initiation 
        if USE_SIMULATOR: 
            self.km = Simulator(simctrl_instance)
        else:
            self.km = Kiwoom()
        if not self.km.connect_status: 
            tl_print("System exits")
            sys.exit()
        self.bounds_table = bounds_prep()
        self.prev_mbf_exists = os.path.exists(MASTER_BOOK_FILE)
        self.trtrade_list = pd.DataFrame(columns = ['code', 'amount', 'buy_sell', 'note'])
        self.master_book_initiator(START_CASH, replace = CREATE_NEW_MASTER_BOOK)
        if not USE_SIMULATOR:
            self.master_book_integrity_checker() 
    
    def close_(self):
        self.write_master_book_to_Excel(self.master_book)
        self.status_print(to_file = True)
        if not USE_SIMULATOR:
            self.status_print(to_file = False) # print to screen too

    def __del__(self):
        del self.km

    def run_(self):
        self.execute_external_control_command() # web-based control through AWS
        cash = self.trendtrading_mainlogic() # returns cash amount if all trtrade_list buy_sells are executed
        self.load_external_trade_list(cash)
        trtrade_list_yetitems = self.trtrade_list.loc[self.trtrade_list['note']=='yet']
        if len(trtrade_list_yetitems) == 0: 
            if PRINT_TO_SCREEN:
                print(time.strftime("t%M:%S"), end="\r")  # Exception for trade_log_print (tl_print)
            if USE_SIMULATOR:
                return False
        else: 
            self.trade_stocks()
            self.status_print(to_file = False) # print to screen too
            if USE_SIMULATOR:
                return True
        self.status_print(to_file = True)

    def load_external_trade_list(self, cash): 
        # if a file that contains a list of stocks to be traded exists, load it
        if os.path.exists(EXTERNAL_LIST_FILE):
            el = TrTrader.read_external_buysell_list()
            self.external_list_prep(cash, el)

        # when USE_SIMULATOR, each run_() run will load external list created at SimController
        if USE_SIMULATOR:
            self.external_list_prep(cash, self.km.simctrl.ext_list_gen()) 
    
    def external_list_prep(self, cash, el):
        bk = self.km.get_account_stock_list(ACCOUNT_NO)
        for i in el.index: 
            if el.at[i, 'code'] in TRENDTRADE_EXCEPT_LIST:
                tl_print("*** WARNING: External buysell list contains item in TRENDTRADE_EXCEPT_LIST: ", el.at[i, 'code'], " - this item ignored")
                el = el.drop(i)
                continue

            cprice = self.km.get_price(el.at[i,'code'])
            if cprice == 0: 
                tl_print("*** WARNING: External list contains item with zero current price: ", el.at[i, 'code'], " - this item ignored")
                el = el.drop(i)
                continue

            if el.at[i, 'buy_sell'] == 'buy': 
                if el.at[i, 'code'] in list(bk['code']):
                    tl_print("*** WARNING: External list contains item in current trtrading list: ", el.at[i, 'code'], " - this item ignored")
                    el = el.drop(i)
                    continue
                if el.at[i, 'amount'] == 0:
                    el.at[i, 'amount'] = int(round(TICKET_SIZE/cprice))
                    tl_print("*** External list contains item with buy quantity set to zero: ", el.at[i, 'code'], " - buy quanity set to TICKET_SIZE") 
                ticket = int(round(cprice*el.at[i, 'amount']*self.tax_fee_adjustment('buy')))
                if cash > ticket*MIN_CASH_FOR_PURCHASE_RATE: 
                    cash = cash - ticket
                else:
                    tl_print("Exception: Cash is not enough for external list purchase: " + el.at[i, 'code'])
                    raise Exception()
            else: # 'sell'
                if el.at[i,'code'] not in list(bk['code']):
                    tl_print("*** WARNING: External list contains sell item not in current trtrading list: ", el.at[i, 'code'], " - this item ignored")
                    continue
                ci = bk.loc[bk['code'] == el.at[i, 'code']]
                if el.at[i, 'amount'] == 0:
                    el.at[i, 'amount'] = int(ci['nshares'])
                    tl_print("*** External list contains item with sell quantity set to zero: ", el.at[i, 'code'], " - sell quanity set to max") 
                elif el.at[i, 'amount'] > int(ci['nshares']):
                    el.at[i, 'amount'] = int(ci['nshares'])
                    tl_print("*** WARNING: External list contains item with sell quantity exceeding current quantity: ", el.at[i, 'code'], " - sell quanity set to max") 
                else: 
                    pass
                ticket = int(round(cprice*el.at[i, 'amount']*self.tax_fee_adjustment('sell')))
                cash = cash + ticket

        if len(el) > 0: 
            tl_print('External buy_sell list loaded')
            self.trtrade_list = self.trtrade_list.append(el)
            self.trtrade_list = self.trtrade_list.reset_index(drop = True)


    def trade_stocks(self):
        ##################################################
        # MAY NEED TO MODIFY TO SELL FIRST AND THEN BUY
        bs_lookup = {'buy': 1, 'sell': 2}
        self.tr_data = []
        self.tr_data_res_ = []
        for i in self.trtrade_list.index:
            if self.trtrade_list["note"][i] == 'yet': # or self.trtrade_list["note"][i] == 'failed': ############################### For failed, re running of tr-mainlogic would result in adding the same item
                res = self.km.send_order("send_order_req", "0101", ACCOUNT_NO, bs_lookup[self.trtrade_list["buy_sell"][i]], 
                        self.trtrade_list["code"][i], self.trtrade_list["amount"][i], 0, '03', "") # trade in market price, price = 0, hoga = '3'
    
                if res[0] == 0 and res[1] != "": # success
                    self.trtrade_list.at[i, "note"] = 'ordered'
                    self._write_transaction_to_master_book(self.km.chejan_finish_data[0],   
                                                           self.km.chejan_finish_data[1],   
                                                           self.km.chejan_finish_data[2], 
                                                           self.km.chejan_finish_data[3], 
                                                           self.km.chejan_finish_data[4], 
                                                           self.km.chejan_finish_data[5])
                    self.km.chejan_finish_data.append(self.tr_data_res_)
                    self.tr_data.append(self.km.chejan_finish_data)
                    self.km.chejan_finish_data = []
                    # self.tr_data = [stock_code, stock_name, buy_sell, avg_price, int(pv), tr_time, [invtotal, ret]]
                else:
                    tl_print("--- Error in order processing: ", self.trtrade_list['code'][i])
                    self.trtrade_list.at[i, "note"] = 'failed'

    def trendtrading_mainlogic(self):
        # Trend trading logic
        # [step 0] for active set copy, do the following
        mb_active = self.master_book.loc[self.master_book['active']]
        cash = self.master_book.at[self.master_book.index[-1], 'cash'] # to be cash after the trtrade_list generated by a trendtrading_mainlogic run is excuted 
        book_cash = cash # cash to be written at the last line of master_book 
        if USE_SIMULATOR: 
            tr_time = self.km.simctrl.sim_time
        else: 
            tr_time = time.ctime()
        
        # [step 1] update cprice, cvalue, retrate
        for i in mb_active.index:
            updated_price = self.km.get_price(mb_active.at[i, 'code'])
            updated_value = int(round(updated_price*mb_active.at[i, 'nshares']*self.tax_fee_adjustment('sell')))
            updated_rr = round(updated_value/mb_active.at[i, 'invtotal'] - 1, 4) # return rate
            mb_active.at[i, 'cprice'] = updated_price
            mb_active.at[i, 'cvalue'] = updated_value
            mb_active.at[i, 'retrate'] = updated_rr
            
        # [step 2] for dec_made == SUSPEND or EXCEPT, check if rr is back up to LB
                # then dec_made = released, update dec_time
                # otherwise, leave it as is
            if mb_active.at[i, 'dec_made'] == "SUSPEND" or mb_active.at[i, 'dec_made'] == "EXCEPT": 
                if updated_rr >= mb_active.at[i, 'LB']:
                    mb_active.at[i, 'dec_made'] = "released"
                    mb_active.at[i, 'dec_time'] = tr_time 
                    self.master_book.loc[i, 'active'] = False
                    new_line = mb_active.loc[mb_active.index == i]
                    new_line.at[i, 'cash'] = book_cash
                    new_line.index = [len(self.master_book)]
                    self.master_book = self.master_book.append(new_line)
        # [step 3] for dec_made != SUSPEND and != "EXCEPT": compare rr with LLB, LB, UB
            else: # if mb_active.at[i, 'dec_made'] != "SUSPEND" and mb_active.at[i, 'dec_made'] != "EXCEPT":
                # if hits LLB, suspend trading until it reaches LB: dec_made = SUSPEND, update dec_time
                if updated_rr <= mb_active.at[i, 'LLB']:
                    mb_active.at[i, 'dec_made'] = "SUSPEND"
                    mb_active.at[i, 'dec_time'] = tr_time
                    self.master_book.loc[i, 'active'] = False
                    new_line = mb_active.loc[mb_active.index == i]
                    new_line.at[i, 'cash'] = book_cash
                    new_line.index = [len(self.master_book)]
                    self.master_book = self.master_book.append(new_line)

                # if in between LLB and LB, sell (at loss): add this item to the trtrade_list (sell), code and quantity, DO NOT CHANGE MASTER BOOK 
                else:
                    if updated_rr <= mb_active.at[i, 'LB']:
                        self.trtrade_list.loc[len(self.trtrade_list)] = [self.master_book.at[i, 'code'], int(self.master_book.at[i, 'nshares']), 'sell', 'yet']
                        tl_print("Situation 1 - lower than LB: ", self.master_book.at[i, 'code'], " sell" ) #########################
                        cash = cash + updated_value
                # if in between LB and UB: hold 
                    elif updated_rr < mb_active.at[i, 'UB']:
                        pass
                # if hits UB: 
                    else:
                    # elif no_repurchase = MAX_ELEVATION: add this item to the trade_list (sell), DO NOT CHANGE MASTER BOOK
                        nr = mb_active.at[i, 'nreinv'] 
                        if nr == MAX_ELEVATION:
                            self.trtrade_list.loc[len(self.trtrade_list)] = [self.master_book.at[i, 'code'], int(self.master_book.at[i, 'nshares']), 'sell', 'yet']
                            tl_print("Situation 2 - more than MAX_ELEVATION: ", self.master_book.at[i, 'code'], " sell" ) ##########################
                            cash = cash + updated_value
                        else: 
                        # check cash, 
                            # if cash > MIN_CASH_FOR_PURCHASE and no_repurchase < MAX_REINVESTMENT: add this item to trade_list (buy), DO NOT CHANGE MASTER BOOK
                            if cash > MIN_CASH_FOR_PURCHASE and nr < MAX_REINVESTMENT:
                                self.trtrade_list.loc[len(self.trtrade_list)] = [self.master_book.at[i, 'code'], int(round(TICKET_SIZE/updated_price)), 'buy', 'yet']
                                tl_print("Situation 3 - higher than UB: ", self.master_book.at[i, 'code'], " buy" ) ##########################
                                cash = cash - TICKET_SIZE
                            # else elevate bounds 1 steps, and update no_repurchase, dec_made = "bd_elev" and dec_time 
                            else: 
                                mb_active.at[i, 'nreinv'] = nr + 1
                                [LLB, LB, UB] = self.bounds(nr+1)
                                mb_active.at[i, 'LLB'] = LLB
                                mb_active.at[i, 'LB'] = LB
                                mb_active.at[i, 'UB'] = UB
                                mb_active.at[i, 'dec_made'] = 'bd_elev'
                                mb_active.at[i, 'dec_time'] = tr_time
                                self.master_book.loc[i, 'active'] = False
                                new_line = mb_active.loc[mb_active.index == i]
                                new_line.at[i, 'cash'] = book_cash
                                new_line.index = [len(self.master_book)]
                                self.master_book = self.master_book.append(new_line)
        return cash

    def master_book_integrity_checker(self): 
        bk = self.km.get_account_stock_list(ACCOUNT_NO)
        for exception_code in TRENDTRADE_EXCEPT_LIST: 
            bk = bk[bk['code'] != exception_code]
        bk = bk.reset_index(drop=True)
        ch = int(self.km.get_cash(ACCOUNT_NO))
        tl_print('Cash in Kiwoom Account is: ', format(ch, ','))
                
        if self.prev_mbf_exists == False or CREATE_NEW_MASTER_BOOK == True:
            if ch < START_CASH - bk['invtotal'].sum()*self.tax_fee_adjustment('buy'):
                tl_print('Exception: INSUFFICIENT CASH TO START TREND TRADING')
                raise Exception()
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
            for i in entries.index:
                res = self.nreinv_find(entries.at[i, 'retrate'])
                if res[0] == -1:
                    entries.at[i, 'dec_made'] = 'EXCEPT'
                    tl_print(' - ', entries.at[i,'code'], entries.at[i, 'name'], ' > EXCEPT')
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
            tl_print('[Initiation success]: Existing stock list from Kiwoom API loaded into master_book')

        else: 
            #############################################
            # Loading existing book 
            # master_book active items should match bk items
            mb_cash = self.master_book.at[len(self.master_book)-1, 'cash']
            if mb_cash > ch: 
                tl_print("Exception: Master_book loading error - cash balance insufficient")
                raise Exception()
            mb_active = self.master_book.loc[self.master_book['active']] # selected subset of DataFrame is already a deep copy of original DataFrame 
            if len(mb_active) != len(bk): 
                tl_print("Exception: Master_Book integrity check: error (1)")
                raise Exception() # this error could occur when releasing from and adding to TRENDTRADE_EXCEPT_LIST 
            for i in bk.index: 
                mt = mb_active[mb_active['code'] == bk.at[i, 'code']]
                if len(mt) != 1: 
                    tl_print("Exception: Master_Book integrity check: error (2)")
                    raise Exception() 
                l = list(mt.index)[0]
                if mt.at[l, 'nshares'] != bk.at[i, 'nshares']: 
                    tl_print("Exception: Master_Book integrity check: error (3)")
                    raise Exception() 
                if (mt.at[l, 'invtotal'] - bk.at[i, 'invtotal']*self.tax_fee_adjustment('buy'))/mt.at[l, 'invtotal'] > 0.01:
                    tl_print("Exception: Master_Book integrity check: error (4)")
                    raise Exception() 
            tl_print('[Initiation success]: Existing stock list from Kiwoom API matches with master_book') 

    def master_book_initiator(self, initial_cash_amount, replace = False): 
        if self.prev_mbf_exists and not replace: 
            # tl_print("Using existing master book - master book file exists")
            pass

        else:
            if self.prev_mbf_exists and replace: 
                t = time.strftime("_%Y%m%d_%H%M%S")
                n = MASTER_BOOK_BACKUP_FILE[:-5]
                os.rename(MASTER_BOOK_FILE, n+t+'.xlsx')

            self.prev_mbf_exists = False 
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
        os.rename(EXTERNAL_LIST_FILE, n+t+'.xlsx')

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
                new_line.at[0, 'invtotal'] = v1 = int(round(price*quantity*self.tax_fee_adjustment('buy')))
                new_line.at[0, 'cvalue'] = v2 = int(round(price*quantity*self.tax_fee_adjustment('sell')))
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
                new_line.at[idx, 'cprice'] = price # price update
                new_line.at[idx, 'nshares'] = ns = new_line.at[idx, 'nshares'] + quantity # repurchase
                new_line.at[idx, 'nreinv'] = nr = new_line.at[idx, 'nreinv'] + 1
                if nr > MAX_REINVESTMENT:  
                    tl_print("Exception: Do not attmpt to purchase over MAX_ELEVATION")
                    raise Exception()
                [LLB, LB, UB] = self.bounds(nr)
                new_line.at[idx, 'LLB'] = LLB
                new_line.at[idx, 'LB'] = LB
                new_line.at[idx, 'UB'] = UB
                repv = int(round(price*quantity*self.tax_fee_adjustment('buy')))
                new_line.at[idx, 'invtotal'] = v1 = new_line.at[idx, 'invtotal'] + repv
                new_line.at[idx, 'cvalue'] = v2 = int(round((price*ns)*self.tax_fee_adjustment('sell')))
                new_line.at[idx, 'retrate'] = round((v2-v1)/v1, 4)
                new_line.at[idx, 'ret'] = 0
                # new_line.at[0, 'init_invtime'] = tr_time # does not change
                new_line.at[idx, 'dec_made'] = 'reinv'
                new_line.at[idx, 'dec_time'] = tr_time # update time
                new_line.at[idx, 'active'] = True
                new_line.at[idx, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] - repv

            else: 
                tl_print("Exception: ERROR in Master_Book Integrity - buy")
                raise Exception()

        else: # buy_sell == 'sell':
            if len(active_line) == 1: 
                idx = list(active_line.index)[0]
                self.master_book.at[idx, 'active'] = False
                new_line = active_line
                new_line.at[idx, 'cprice'] = price # price update
                original_quantity = new_line.at[idx, 'nshares']
                new_line.at[idx, 'nshares'] = remained_quantity = original_quantity - quantity
                avg_price = new_line.at[idx, 'invtotal'] / original_quantity
                new_line.at[idx, 'invtotal'] = v1 = avg_price*remained_quantity 
                new_line.at[idx, 'cvalue'] = v2 = int(round(price*remained_quantity*self.tax_fee_adjustment('sell')))
                if v1 != 0:  # remained_quantity is not zero
                    new_line.at[idx, 'retrate'] = round((v2-v1)/v1, 4)
                else: 
                    new_line.at[idx, 'retrate'] = 0
                v3 = int(round(price*quantity*self.tax_fee_adjustment('sell')))
                new_line.at[idx, 'ret'] = v3 - avg_price*quantity
                if remained_quantity == 0: 
                    new_line.at[idx, 'dec_made'] = 'a_sold' 
                    new_line.at[idx, 'active'] = False
                    #################################################################
                    # tr_data saves results only when a_sold
                    self.tr_data_res_ = [self.master_book.at[idx,'invtotal'], new_line.at[idx, 'ret']]
                else: 
                    new_line.at[idx, 'dec_made'] = 'p_sold'
                    new_line.at[idx, 'active'] = True
                new_line.at[idx, 'dec_time'] = tr_time
                new_line.at[idx, 'cash'] = ch = self.master_book.at[len(self.master_book)-1, 'cash'] + v3 
            else: 
                tl_print("Exception: ERROR in Master_Book Integrity - sell")
                raise Exception()
        
        new_line.index = [len(self.master_book)]
        self.master_book = self.master_book.append(new_line)
    
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

    def execute_external_control_command(self):
        [command_time, ext_command] = self.read_external_command()
        if ext_command != '':
            tl_print('External command ['+ext_command+'] recognized at time: '
                + datetime.now().strftime("%Y%m%d %H:%M:%S")+' (command created at: '+command_time+')')
            if ext_command == 'suspend':
                tl_print("*****************************************************")
                tl_print("PROCESS SUSPENDED PER THE EXTERNAL COMMAND: [suspend]")
                tl_print("*****************************************************")
                while 1: 
                    # tl_print("System suspended - waiting for", EXT_COMM_SUSPEND_SLEEPING_TIME, "seconds until recheck")    
                    time.sleep(EXT_COMM_SUSPEND_SLEEPING_TIME)
                    [command_time, ext_command] = self.read_external_command()
                    if ext_command == 'resume':
                        tl_print('External command ['+ext_command+'] recognized at time: '
                            + self.ext_command_last_excution_time_.strftime("%Y%m%d %H:%M:%S")+' (command created at: '+command_time+')')
                        tl_print("*****************************************************")
                        tl_print("PROCESS RESUMED PER THE EXTERNAL COMMAND: [resume]")
                        tl_print("*****************************************************")
                        break
                    elif ext_command == 'stop':
                        tl_print('External command ['+ext_command+'] recognized at time: '
                            + self.ext_command_last_excution_time_.strftime("%Y%m%d %H:%M:%S")+' (command created at: '+command_time+')')
                        break
                    elif ext_command == 'ping':
                        tl_print("ping > trtrader is suspended")
            elif ext_command == 'resume':
                tl_print("[resume] command not executed in suspend status is ignored")
            elif ext_command == 'ping':
                tl_print("ping > trtrader is running")

            if ext_command == 'stop':
                tl_print("*****************************************************")
                tl_print("PROCESS EXITS PER THE EXTERNAL COMMAND: [stop]")
                tl_print("*****************************************************")
                tl_print("System exits")
                sys.exit()

    def read_external_command(self):
        try:
            html = urllib.request.urlopen(EXTERNAL_COMMAND_URL).read()
            soup = BeautifulSoup(html, features='lxml')
            text = soup.get_text()
            lines = [line.strip() for line in text.splitlines()]  # strips spaces before and after each word 
            command_time = datetime.strptime(lines[0], "%Y%m%d %H:%M:%S")
            ext_command = lines[1]
            if command_time > self.ext_command_last_excution_time_:
                # only if command time is later than init time or last execution time, the command will be executed
                if ext_command in EXTERNAL_COMMAND_LIST:
                    self.ext_command_last_excution_time_ = command_time
                    return [lines[0], ext_command]
            return ['', '']
        except Exception as e: 
            # tl_print("Excpetion: Error in read_external_command - ignored: " + str(e))
            return ['', '']
            # Any kinds of errors are ignored
        

    def status_print(self, to_file = False):
        mb_print = self.master_book.copy()
        mb_print = mb_print.astype(str)
        for i in mb_print.index:
            mb_print.at[i, 'name'] = mb_print.at[i, 'name'][:6]
            mb_print.at[i, 'cprice'] = format(int(mb_print.at[i, 'cprice']), ',')
            mb_print.at[i, 'nshare'] = format(int(mb_print.at[i, 'nshares']), ',')
            mb_print.at[i, 'LLB'] = format(float(mb_print.at[i, 'LLB'])*100, '.1f')
            mb_print.at[i, 'LB'] = format(float(mb_print.at[i, 'LB'])*100, '.1f')
            mb_print.at[i, 'UB'] = format(float(mb_print.at[i, 'UB'])*100, '.1f')
            mb_print.at[i, 'invtotal'] = format(int(round(float(mb_print.at[i, 'invtotal'])/1000)), ',')
            mb_print.at[i, 'cvalue'] = format(int(round(float(mb_print.at[i, 'cvalue'])/1000)), ',')
            mb_print.at[i, 'ret'] = format(int(round(float(mb_print.at[i, 'ret'])/1000)), ',')
            mb_print.at[i, 'cash'] = format(int(round(float(mb_print.at[i, 'cash'])/1000)), ',')
            mb_print.at[i, 'retrate'] = format(float(mb_print.at[i, 'retrate'])*100, '.1f')
        mb_print = mb_print.rename(columns={'cprice': 'cpr', 'nshares': 'vol', 'nreinv': 'nr', 'LLB': 'LL(%)', 'LB': 'L(%)', 'UB': 'U(%)', 
                                    'invtotal': 'inv(k)', 'cvalue': 'cval(k)', 'retrate':'rt(%)', 'ret': 'rt(k)', 'dec_made': 'dec', 'active': 'act', 'cash': 'cash(k)'})
        mb_print.drop([0], inplace = True)
        l = ['code', 'cpr', 'vol', 'nr', 'LL(%)', 'L(%)', 'U(%)', 'inv(k)', 'cval(k)', 'rt(%)', 'rt(k)', 'dec', 'act', 'cash(k)', 'name']

        mb_mobile = mb_print.copy()

        mb_mobile['dec'] = mb_mobile['dec'].map(ABRIDGED_DICT)
        mb_mobile['act'] = mb_mobile['act'].map({'True': 'A', 'False': 'F'})
        mb_mobile['DA'] = mb_mobile['dec'] + mb_mobile['act']

        lm = ['code', 'inv(k)', 'nr', 'rt(%)', 'DA', 'name']

        if to_file == True: 
            f = open(STATUS_REPORT_FILE, 'w')
            f.write('master_book (up to last 75 items): \n')
            f.write(tabulate(mb_print.loc[-75:, l], headers='keys', showindex=False, tablefmt='simple')) 
            f.write('\n')
            f.close()

            m = open(STATUS_REPORT_MOBILE, 'w')
            m.write('master_book (last 75 items): \n')
            m.write(tabulate(mb_mobile.loc[-75:, lm], headers='keys', showindex=False, tablefmt='simple')) 
            m.write('\n')
            m.close()

        else: 
            tl_print('MASTER_BOOK (up to last 75 items): \n', tabulate(mb_print.loc[-75:, l], headers='keys', showindex=False, tablefmt='psql'))

        if len(self.trtrade_list) > 0:
            trtrade_list_print = self.trtrade_list.copy()
            for i in trtrade_list_print.index: 
                trtrade_list_print.at[i, 'name'] = self.km.get_master_code_name(trtrade_list_print.at[i, 'code'])

            if to_file == True: 
                f = open(STATUS_REPORT_FILE, 'a')
                f.write('trtrade_list (up to last 75 items): \n')
                f.write(tabulate(trtrade_list_print.loc[-75:, :], headers='keys', showindex=False, tablefmt='simple'))
                f.write('\n')
                f.close()

                m = open(STATUS_REPORT_MOBILE, 'a')
                m.write('trtrade_list (last 75 items): \n')
                m.write(tabulate(trtrade_list_print.loc[-75:, :], headers='keys', showindex=False, tablefmt='simple'))
                m.write('\n')
                m.close()
            else: 
                tl_print('trtrade_list (up to last 75 items): \n', tabulate(trtrade_list_print.loc[-75:, :], headers='keys', showindex=False, tablefmt='psql'))
        else: 
            if to_file == True: 
                f = open(STATUS_REPORT_FILE, 'a')
                f.write('trtrade_list empty \n')
                f.close()
                m = open(STATUS_REPORT_MOBILE, 'a')
                m.write('trtrade_list empty \n')
                m.close()
            else: 
                tl_print('trtrade_list empty')

        self.status_summary_report(to_file)

    def status_summary_report(self, to_file = False):
        # Cash at ACCOUNT
        # Cash at TrTrading
        # Total invested amount accross all items
        # Current value total across all items
        # Return rate of TrTrading
        # Realized return total 
        # Number of active items
        cash_account = format(int(round(int(self.km.get_cash(ACCOUNT_NO))/1000)), ',')
        mb_active = self.master_book.loc[self.master_book['active']]
        cash_trtrading = format(int(round(self.master_book.at[self.master_book.index[-1], 'cash']/1000)), ',') # there might not be any active item.
        tr_invested_total = mb_active['invtotal'].sum()
        tr_cvalue_total = mb_active['cvalue'].sum()
        if tr_invested_total > 0: 
            tr_return_rate = tr_cvalue_total/tr_invested_total -1
        else: 
            tr_return_rate = 0
        tr_invested_total = format(int(round(tr_invested_total/1000)), ',')
        tr_cvalue_total = format(int(round(tr_cvalue_total/1000)), ',')
        tr_return_rate = format(tr_return_rate*100, '.2f')
        tr_realized_return_total = format(int(round(self.master_book['ret'].sum()/1000)), ',')
        no_active = len(mb_active)
        t = time.strftime("%Y%m%d %H:%M:%S") 

        if to_file == True:
            f = open(STATUS_REPORT_FILE, 'a')
            f.write("[TrTrade Summary - " + t + "]" + "\n")
            f.write("- Kiwoom Cash(k): " + cash_account + "\n")
            f.write("- TrTrade Cash(k): " + cash_trtrading + "\n")
            f.write('- Return(%): ' + tr_return_rate + "\n")
            f.write('- #items: ' + str(no_active) + "\n")
            f.write("- Total invested(k): " + tr_invested_total + "\n")
            f.write("- Current Value(k): " + tr_cvalue_total + "\n")
            f.write('- Realized Return Total(k): ' + tr_realized_return_total + "\n")
            f.write('- Exception List: ' + str(TRENDTRADE_EXCEPT_LIST) + "\n")
            f.close()
            m = open(STATUS_REPORT_MOBILE, 'a')
            m.write("[TrTrade Summary - " + t + "]" + "\n")
            m.write("- Kiwoom Cash(k): " + cash_account + "\n")
            m.write("- TrTrade Cash(k): " + cash_trtrading + "\n")
            m.write('- Return(%): ' + tr_return_rate + "\n")
            m.write('- #items: ' + str(no_active) + "\n")
            m.write("- Total invested(k): " + tr_invested_total + "\n")
            m.write("- Current Value(k): " + tr_cvalue_total + "\n")
            m.write('- Realized Return Total(k): ' + tr_realized_return_total + "\n")
            m.write('- Exception List: ' + str(TRENDTRADE_EXCEPT_LIST) + "\n")
            m.close()
        else: 
            tl_print("[TrTrade Summary - " + t + ']')
            tl_print("- Kiwoom Cash(k): " + cash_account)
            tl_print("- TrTrade Cash(k): " + cash_trtrading)
            tl_print('- Return(%): ' + tr_return_rate)
            tl_print('- #items: ' + str(no_active))
            tl_print("- Total invested(k): " + tr_invested_total)
            tl_print("- Current Value(k): " + tr_cvalue_total)
            tl_print('- Realized Return Total(k): ' + tr_realized_return_total)
            tl_print('- Exception List: ' + str(TRENDTRADE_EXCEPT_LIST))
        
if __name__ == "__main__": 
    app = QApplication(sys.argv)
    USE_SIMULATOR = False
    trtrader = TrTrader()
    trtrader.run_() 
    trtrader.close_()