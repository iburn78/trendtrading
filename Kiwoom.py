import sys
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
import time
import pandas as pd
import xlsxwriter
import os.path
from tabulate import tabulate 

API_REQ_TIME_INTERVAL = 0.3 # min = 0.2
TICKET_SIZE = 3000000 # Target amount to be purchased in KRW
# RUN_WAIT_INTERVAL = 30*60 

WORKING_DIR_PATH = 'C:/Users/user/Projects/trendtrading/'

MARKET_START_TIME = QTime(9, 1, 0)
MARKET_FINISH_TIME = QTime(15, 19, 0)
ACCOUNT_NO = '8135010411' # may create master_book for each account_no

START_CASH = 100000000
FEE_RATE = 0.00015
TAX_RATE = 0.003
MAX_REINVESTMENT = 4 # total 5 investments max

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        self._set_signal_slots()
        self.connect_status = False
        # self.comm_connect()

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self._event_connect)
        self.OnReceiveTrData.connect(self._receive_tr_data)
        self.OnReceiveChejanData.connect(self._receive_chejan_data)
        
    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def _event_connect(self, err_code):
        if err_code == 0:
            self.connect_status = True
            print("Kiwoom API connected")
        else:
            print("Kiwoom API not connected")
        self.login_event_loop.exit()

    def get_master_code_name(self, code):
        code_name = self.dynamicCall("GetMasterCodeName(QString)", code) # code should be str
        return code_name

    def get_server_gubun(self): # returns if the current server is test server (1) or not 
        return self.dynamicCall("KOA_Functions(QString, QString)", "GetServerGubun", "")

    def get_login_info(self, tag):
        return self.dynamicCall("GetLoginInfo(QString)", tag) # tag: "ACCNO" for getting accounts

    def send_order(self, rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no):
        res = self.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        [rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no])
        self.tr_event_loop = QEventLoop()
        self.tr_event_loop.exec_()
        if res == 0 and self.order_number != "": # success  
            # hoga: fixed 00, mkt 03
            self.trade_log_write(" ".join(["[SendOrder]", time.strftime("%Y %m%d %H:%M:%S"), self.order_number, str(rqname), str(screen_no), str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no)]))
            self.chejan_event_loop = QEventLoop()
            self.chejan_event_loop.exec_()
        else:
            self.trade_log_write(" ".join(["--- SendOrder Fail:", "("+str(res)+")", time.strftime("%Y %m%d %H:%M:%S"), self.order_number, str(rqname), str(screen_no), str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no)]))
        time.sleep(API_REQ_TIME_INTERVAL)
        return (res, self.order_number)

    def get_chejan_data(self, fid):
        ret = self.dynamicCall("GetChejanData(int)", fid)
        return ret

    def _receive_chejan_data(self, gubun, item_cnt, fid_list):
        pv = self.get_chejan_data(911) 
        if pv != "": # 911: purchased volume, 302: name, 9001: stockcode, 905: buy or sell, 900: order quantity, 910: transaction price
            oq = self.get_chejan_data(900) 
            stock_name = self.get_chejan_data(302).strip() 
            stock_code = self.get_chejan_data(9001).strip()[1:] 
            bs = self.get_chejan_data(905).strip()
            buy_sell = {'+매수': 'buy', '-매도': 'sell'}[bs]
            tr_price = int(self.get_chejan_data(910))
            tr_time = time.strftime("%Y %m%d %H:%M:%S")
            self.trade_log_write(" - " + tr_time + " " + stock_name + "("+ stock_code + ") "
                  + bs + ", " + pv + "/" + oq + ", at price: " + format(tr_price, ','))
            if pv == oq: 
                try:
                    self.chejan_event_loop.exit()
                except Exception as e: 
                    print("On chejan receive, loop exit error:", e)
                tr_time = time.ctime() # for excel file recognition
                self._write_transaction_to_master_book(stock_code, stock_name, buy_sell, tr_price, pv, tr_time)
    
    def trade_log_write(self, msg):
        ff = open(TRADE_LOG_FILE, 'a')
        ff.write(msg + "\n")
        print(msg)
        ff.close()

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def comm_rq_data(self, rqname, trcode, next_, screen_no):
        self.dynamicCall("CommRqData(QString, QString, int, QString)", rqname, trcode, next_, screen_no)
        self.tr_event_loop = QEventLoop()
        self.tr_event_loop.exec_()
        time.sleep(API_REQ_TIME_INTERVAL)

    def _comm_get_data(self, code, real_type, field_name, index, item_name):
        ret = self.dynamicCall("CommGetData(QString, QString, QString, int, QString)", code,
                               real_type, field_name, index, item_name)
        return ret.strip()

    def _get_comm_data_ex(self, strTrCode, strRecordName): # getting large batch data 
        return self.dynamicCall("GetCommDataEx(QString, QString)", strTrCode, strRecordName)

    def _get_repeat_cnt(self, trcode, rqname):
        ret = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        return ret

    def _receive_tr_data(self, screen_no, rqname, trcode, record_name, next_, unused1, unused2, unused3, unused4):
        if next_ == '2':
            self.remained_data = True
        else:
            self.remained_data = False

        if rqname == "opt10081_req":
            # getting ohlcv
            # '수정주가구분' set '0': price not adjusted, or '1': price adjusted 
            self.ohlcv = {'date': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': []}
            self._opt10081(rqname, trcode)

        elif rqname == "opt10081_req_ex":
            # getting ohlcv using batch process
            self._opt10081_ex(rqname, trcode)

        elif rqname == "opw00001_req":
            # getting d+2 cash
            self._opw00001(rqname, trcode)

        elif rqname == "opw00018_req":
            # getting account details
            self.opw00018_formatted_data = {'single': [], 'multi': []}
            self.opw00018_stocklist = []
            self._opw00018(rqname, trcode)

        elif rqname == "opt10001_req": 
            # getting current price
            self._opt10001(rqname, trcode)
            
        elif rqname == "opt10080_req": 
            self.opt10080_multi_data_set = self._get_comm_data_ex("opt10080", "주식분봉차트조회")
            
        elif rqname == "send_order_req":
            self.order_number = self._comm_get_data(trcode, "", rqname, 0, "주문번호")

        else: 
            print("TR request name not matching: ", screen_no, rqname, trcode, record_name, next_, unused1, unused2, unused3, unused4)

        try:
            self.tr_event_loop.exit()
        except Exception as e: 
            print("On tr receive, loop exit error:", e)

    def _opt10081(self, rqname, trcode):
        data_cnt = self._get_repeat_cnt(trcode, rqname)
        for i in range(data_cnt):
            date = self._comm_get_data(trcode, "", rqname, i, "일자")
            open = self._comm_get_data(trcode, "", rqname, i, "시가")
            high = self._comm_get_data(trcode, "", rqname, i, "고가")
            low = self._comm_get_data(trcode, "", rqname, i, "저가")
            close = self._comm_get_data(trcode, "", rqname, i, "현재가")
            volume = self._comm_get_data(trcode, "", rqname, i, "거래량")

            self.ohlcv['date'].append(date)
            self.ohlcv['open'].append(int(open))
            self.ohlcv['high'].append(int(high))
            self.ohlcv['low'].append(int(low))
            self.ohlcv['close'].append(int(close))
            self.ohlcv['volume'].append(int(volume))

    def _opt10081_ex(self, rqname, trcode):
        multi_data = self._get_comm_data_ex(trcode, "주식일봉차트조회")
        multi_data = [r[1:8] for r in multi_data]
        multi_data = pd.DataFrame(multi_data, columns = ['cur_price', 'vol', 'vol_krw', 'date', 'start', 'high', 'low'])
        multi_data[['cur_price', 'vol', 'vol_krw', 'start', 'high', 'low']] = multi_data[['cur_price', 'vol', 'vol_krw', 'start', 'high', 'low']].astype('int')
        multi_data['date'] = pd.to_datetime(multi_data['date'])
        self.opt10081_multi_data_set = multi_data
        
    def _opw00001(self, rqname, trcode):
        d2_deposit = self._comm_get_data(trcode, "", rqname, 0, "d+2추정예수금")
        self.d2_deposit = Kiwoom.change_format(d2_deposit)

    def _opw00018(self, rqname, trcode):
        # single data
        total_purchase_price = self._comm_get_data(trcode, "", rqname, 0, "총매입금액")
        total_eval_price = self._comm_get_data(trcode, "", rqname, 0, "총평가금액")
        total_eval_profit_loss_price = self._comm_get_data(trcode, "", rqname, 0, "총평가손익금액")
        total_earning_rate = self._comm_get_data(trcode, "", rqname, 0, "총수익률(%)")
        total_earning_rate = round(float(total_earning_rate), 3) 
        total_earning_rate = str(total_earning_rate)
        estimated_deposit = self._comm_get_data(trcode, "", rqname, 0, "추정예탁자산")
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_purchase_price))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_eval_price))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_eval_profit_loss_price))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_earning_rate))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(estimated_deposit))

        # multi data
        rows = self._get_repeat_cnt(trcode, rqname)
        for i in range(rows):
            name = self._comm_get_data(trcode, "", rqname, i, "종목명")
            code = self._comm_get_data(trcode, "", rqname, i, "종목번호")
            quantity = self._comm_get_data(trcode, "", rqname, i, "보유수량")
            purchase_price = self._comm_get_data(trcode, "", rqname, i, "매입가")
            current_price = self._comm_get_data(trcode, "", rqname, i, "현재가")
            invested_amount = self._comm_get_data(trcode, "", rqname, i, "매입금액")
            current_total = self._comm_get_data(trcode, "", rqname, i, "평가금액")
            eval_profit_loss_price = self._comm_get_data(trcode, "", rqname, i, "평가손익")
            earning_rate = self._comm_get_data(trcode, "", rqname, i, "수익률(%)")
            
            # for data handling
            self.opw00018_stocklist.append([name, code, int(quantity), int(purchase_price), int(current_price), int(invested_amount), int(current_total), float(eval_profit_loss_price), float(earning_rate)])

            # for printing
            quantity = Kiwoom.change_format(quantity)
            purchase_price = Kiwoom.change_format(purchase_price)
            current_price = Kiwoom.change_format(current_price)
            invested_amount = Kiwoom.change_format(invested_amount)
            current_total = Kiwoom.change_format(current_total)
            eval_profit_loss_price = Kiwoom.change_format(eval_profit_loss_price)
            earning_rate = Kiwoom.change_format_rate(earning_rate)
            self.opw00018_formatted_data['multi'].append([name, code, quantity, purchase_price, current_price, invested_amount, current_total, eval_profit_loss_price, earning_rate])
    
    def _opt10001(self, rqname, trcode):
        cur_price = self._comm_get_data(trcode, "", rqname, 0, "현재가")
        try: 
            cur_price = abs(int(cur_price))
        except Exception as e:
            # print(e) # error when cur_price = ""
            cur_price = 0
        self.cur_price = cur_price

    @staticmethod
    def change_format(data): 
        strip_data = data.lstrip('-0')
        if strip_data == '':
            strip_data = '0'
        try:
            format_data = format(int(strip_data), ',')
        except:
            format_data = format(float(strip_data))
        if data.startswith('-'):
            format_data = '-' + format_data
        return format_data

    @staticmethod
    def change_format_rate(data): 
        strip_data = data.lstrip('-0')
        if strip_data == '':
            strip_data = '0'
        if strip_data.startswith('.'):
            strip_data = '0' + strip_data
        if data.startswith('-'):
            strip_data = '-' + strip_data
        return strip_data
        
    def get_ohlcv(self, code, start):
        self.set_input_value("종목코드", code)
        self.set_input_value("기준일자", start)
        self.set_input_value("수정주가구분", "1")
        self.comm_rq_data("opt10081_req", "opt10081", 0, "0101")
        df = pd.DataFrame(self.ohlcv, columns=['open', 'high', 'low', 'close', 'volume'],
                       index=self.ohlcv['date'])
        # implement getting-remained-data for longer period. 
        return df

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
        # this function is to be used only in chejan finish
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

    def get_account_stock_list(self):
        self.set_input_value("계좌번호", ACCOUNT_NO)
        self.comm_rq_data("opw00018_req", "opw00018", 0, "2000")
        
        while self.remained_data: # there is almost no chance that there will be remained data 
            self.set_input_value("계좌번호", ACCOUNT_NO)
            self.comm_rq_data("opw00018_req", "opw00018", 2, "2000")

        stock_list = pd.DataFrame(self.opw00018_stocklist, columns=['name', 'code', 'quantity', 'purchase_price', 
            'current_price', 'invested_amount', 'current_total', 'eval_profit_loss_price', 'earning_rate'])

        for i in stock_list.index:
            stock_list.at[i, 'code'] = stock_list['code'][i][1:]   # taking off "A" in front of returned code

        print('My Stock List (up to 50 items): \n', tabulate(stock_list[:50], headers='keys', tablefmt='psql'))
        return stock_list.set_index('code')



########## USAGE OF KIWOOM CLASS ##########
'''
app = QApplication([''])
k = Kiwoom()

# ---------------------------------
k.set_input_value('종목코드', '005930')
k.set_input_value('기준일자', '20200619')
k.set_input_value('수정주가구분', '1')
k.comm_rq_data('opt10081_req', 'opt10081', 0, '2000')
a = pd.DataFrame(k.ohlcv)

while k.remained_data:
    k.set_input_value('종목코드', '005930')
    k.set_input_value('기준일자', '20200619')
    k.set_input_value('수정주가구분', '1')
    k.comm_rq_data('opt10081_req', 'opt10081', 2, '2000')
    a = pd.DataFrame(k.ohlcv)

print(k.get_ohlcv('005930', '20200619'))
# ---------------------------------

# ---------------------------------
k.set_input_value('계좌번호', ACCOUNT_NO)
k.comm_rq_data('opw00001_req', 'opw00001', 0, '2000')
print(k.d2_deposit)

k._comm_get_data('opw00001', '', 'opw00001_req', 0, "예수금")
print(k.remained_data)
# ---------------------------------

# ---------------------------------
k.set_input_value('계좌번호', ACCOUNT_NO)
k.comm_rq_data('opw00018_req', 'opw00018', 0, '2000')

a = pd.DataFrame(k.opw00018_stocklist) # contains numeric data
b = pd.DataFrame(k.opw00018_formatted_data['single']) # all data is in str format
c = pd.DataFrame(k.opw00018_formatted_data['multi']) # all data is in str format

while k.remained_data:
    k.set_input_value('계좌번호', ACCOUNT_NO)
    k.comm_rq_data('opw00018_req', 'opw00018', 2, '2000')
    a = pd.DataFrame(k.opw00018_stocklist)
# ---------------------------------

# ---------------------------------
k.set_input_value('종목코드', '005930')
k.comm_rq_data('opt10001_req', 'opt10001', 0, '2000')
print(k.cur_price)
# ---------------------------------

# ---------------------------------
k.set_input_value('종목코드', '005930')
k.set_input_value('틱범위', '1')
k.set_input_value('수정주가구분', '1')
k.comm_rq_data('opt10080_req', 'opt10080', 0, '2000')
print('주식분봉차트조회, opt', k.opt10080_multi_data_set)
# ---------------------------------

# ---------------------------------
# Implementing opt10081 using _get_comm_data_ex
STOCK_CODE_TO_GET = '005930'
DATE_TO_CHECK_UPTO = '20200619'
k.set_input_value('종목코드', STOCK_CODE_TO_GET)
k.set_input_value('기준일자', DATE_TO_CHECK_UPTO)
k.set_input_value('수정주가구분', '1')
k.comm_rq_data('opt10081_req_ex', 'opt10081', 0, '2000')
res = k.opt10081_multi_data_set
print('res')
print(res)
time.sleep(API_REQ_TIME_INTERVAL)

NUMBER_TO_RECEIVE_NEXTPAGE = 10
for i in range(NUMBER_TO_RECEIVE_NEXTPAGE):
    if k.remained_data:
        k.set_input_value('종목코드', STOCK_CODE_TO_GET)
        k.set_input_value('기준일자', DATE_TO_CHECK_UPTO)
        k.set_input_value('수정주가구분', '1')
        k.comm_rq_data('opt10081_req_ex', 'opt10081', 2, '2000')
        res = res.append(k.opt10081_multi_data_set)
        print('res', i)
        print(k.opt10081_multi_data_set)
        time.sleep(API_REQ_TIME_INTERVAL)

# ---------------------------------

# k.show()
# app.exec_()
# app.quit()
'''