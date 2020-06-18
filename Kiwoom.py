import sys
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5 import uic
import time, datetime
import pandas as pd
import sqlite3
from pandas import ExcelWriter, ExcelFile
import xlsxwriter
import os.path
from tabulate import tabulate 
import random

MARKET_KOSPI   = 0
MARKET_KOSDAQ  = 10
AUTO_RECONNECT = False
API_REQ_TIME_INTERVAL = 0.2
AUTOTRADE_INTERVAL = 2*60 # seconds
ALLOCATION_SIZE = 3000000 # Target amount to be purchased in KRW
MIN_STOCK_PRICE = 10000 

WORKING_DIR_PATH = 'C:/Users/user/Projects/autotrading/'
EXCEL_BUY_LIST = 'data/buy_list.xlsx'
EXCEL_SELL_LIST = 'data/sell_list.xlsx'
TRADE_LOG_FILE = WORKING_DIR_PATH + 'log/trade_log.txt'

RUN_AUTOTRADE = True
RUN_ANYWAY_OUT_OF_MARKET_OPEN_TIME = False
WAIT_UNTIL_CHEJAN_FININSH = True
MARKET_START_TIME = QTime(9, 1, 0)
MARKET_FINISH_TIME = QTime(15, 20, 0)

HOGA_LOOKUP = {"fixed": "00", "mkt": "03"}
CODE_MIN_LENGTH = 6

####### 
# May need to assign account number directly
####### 

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        self._set_signal_slots()
        self.chejan_received = False
        self.order_chejan_finished = False

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self._event_connect)
        self.OnReceiveTrData.connect(self._receive_tr_data)
        self.OnReceiveChejanData.connect(self._receive_chejan_data)
        self.OnReceiveRealData.connect(self._receive_real_data)
        
    def _receive_real_data(self, scode, srealtype, srealdata):
        # print("현재가", self._get_comm_real_data(scode, 10)) 
        print(scode, srealtype, srealdata)
        pass

    def _get_comm_real_data(self, scode, nfid):
        ret = self.dynamicCall("GetCommRealData(QString, int)", scode, nfid)
        return ret

    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def _event_connect(self, err_code):
        if err_code == 0:
            print("connected")
        else:
            print("disconnected")

        self.login_event_loop.exit()

    def get_code_list_by_market(self, market):
        code_list = self.dynamicCall("GetCodeListByMarket(QString)", market)
        code_list = code_list.split(';')
        return code_list[:-1]

    def get_master_code_name(self, code):
        code_name = self.dynamicCall("GetMasterCodeName(QString)", code)
        return code_name

    def get_connect_state(self):
        ret = self.dynamicCall("GetConnectState()")
        return ret

    def get_server_gubun(self):
        ret = self.dynamicCall("KOA_Functions(QString, QString)", "GetServerGubun", "")
        return ret

    def get_login_info(self, tag):
        ret = self.dynamicCall("GetLoginInfo(QString)", tag)
        return ret

    def send_order(self, rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no):
        res = self.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        [rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no])
        self.tr_event_loop = QEventLoop()
        self.tr_event_loop.exec_()
        if res == 0 and self.order_number != "": # success  
            self.trade_log_write(" ".join(["SendOrder:", "Order Number-", self.order_number, time.ctime(time.time()), str(rqname), str(screen_no), str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no)]))
            #############################################################
            if WAIT_UNTIL_CHEJAN_FININSH: 
                self.chejan_event_loop = QEventLoop()
                self.chejan_event_loop.exec_()
            #############################################################
        else:
            self.trade_log_write(" ".join(["-- SendOrder Fail:", "("+str(res)+")", time.ctime(time.time()), str(rqname), str(screen_no), str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no)]))
        time.sleep(API_REQ_TIME_INTERVAL)
        return (res, self.order_number)

    def get_chejan_data(self, fid):
        ret = self.dynamicCall("GetChejanData(int)", fid)
        return ret

    def _receive_chejan_data(self, gubun, item_cnt, fid_list):
        if self.get_chejan_data(911) != "":
            self.trade_log_write(time.ctime(time.time()) + " [" + self.get_chejan_data(9201).strip() + "]: " + self.get_chejan_data(302).strip() + "("+self.get_chejan_data(9001).strip() + ") "
                  + self.get_chejan_data(905) + ", " + self.get_chejan_data(911) + "/" + self.get_chejan_data(900) + ", tr price: " + self.get_chejan_data(910))
        #############################################################
            if WAIT_UNTIL_CHEJAN_FININSH:
                if self.get_chejan_data(911) == self.get_chejan_data(900):
                    try:
                        self.chejan_event_loop.exit()
                    except Exception as e: 
                        print("On chejan receive, loop exit error:", e)
                    self.order_chejan_finished = True
        #############################################################
    
    def trade_log_write(self, msg):
        ff = open(TRADE_LOG_FILE, 'a')
        ff.write(msg + "\n")
        print(msg)
        ff.close()

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def set_real_reg(self, strScreenNo, strCodeList, strFidList, strOptType):
        self.dynamicCall("SetRealReg(QString, QString, QString, QString)", strScreenNo, strCodeList, strFidList, strOptType)

    def comm_rq_data(self, rqname, trcode, next_, screen_no):
        self.dynamicCall("CommRqData(QString, QString, int, QString)", rqname, trcode, next_, screen_no)
        # print(rqname, trcode, next_, screen_no)
        self.tr_event_loop = QEventLoop()
        self.tr_event_loop.exec_()
        time.sleep(API_REQ_TIME_INTERVAL)

    def _comm_get_data(self, code, real_type, field_name, index, item_name):
        ret = self.dynamicCall("CommGetData(QString, QString, QString, int, QString)", code,
                               real_type, field_name, index, item_name)
        return ret.strip()

    def _get_comm_data_ex(self, strTrCode, strRecordName):
        ret = self.dynamicCall("GetCommDataEx(QString, QString)", strTrCode, strRecordName)
        return ret

    def _get_repeat_cnt(self, trcode, rqname):
        ret = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        return ret

    def _receive_tr_data(self, screen_no, rqname, trcode, record_name, next_, unused1, unused2, unused3, unused4):
        if next_ == '2':
            self.remained_data = True
        else:
            self.remained_data = False

        if rqname == "opt10081_req":
            self.ohlcv = {'date': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': []}
            self._opt10081(rqname, trcode)

        elif rqname == "opw00001_req":
            # self.d2_deposit
            self._opw00001(rqname, trcode)

        elif rqname == "opw00018_req":
            self.opw00018_output = {'single': [], 'multi': []}
            self.opw00018_rawoutput = []
            self._opw00018(rqname, trcode)

        elif rqname == "opt10001_req": 
            self.cur_price = 0
            self._opt10001(rqname, trcode)
            
        elif rqname == "opt10080_req": 
            self.opt10080_multi_data_set = self._get_comm_data_ex("opt10080", "주식분봉차트조회")
            # print('주식분봉차트조회, opt', opt10080_multi_data_set)
            
        elif rqname == "send_order_req":
            self.order_number = ""
            self._send_order_req(rqname, trcode)

        else: 
            print(screen_no, rqname, trcode, record_name, next_, unused1, unused2, unused3, unused4)

        try:
            self.tr_event_loop.exit()
        except Exception as e: 
            print("On tr receive, loop exit error:", e)


    def _send_order_req(self, rqname, trcode):
        order_number = self._comm_get_data(trcode, "", rqname, 0, "주문번호")
        self.order_number = order_number

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
    
    def _opw00001(self, rqname, trcode):
        d2_deposit = self._comm_get_data(trcode, "", rqname, 0, "d+2추정예수금")
        self.d2_deposit = Kiwoom.change_format(d2_deposit)

    def _opw00018(self, rqname, trcode):
        # self.reset_opw00018_output()
        # single data
        total_purchase_price = self._comm_get_data(trcode, "", rqname, 0, "총매입금액")
        total_eval_price = self._comm_get_data(trcode, "", rqname, 0, "총평가금액")
        total_eval_profit_loss_price = self._comm_get_data(trcode, "", rqname, 0, "총평가손익금액")
        total_earning_rate = self._comm_get_data(trcode, "", rqname, 0, "총수익률(%)")
        if self.get_server_gubun():  # 1 if test_server
            total_earning_rate = round(float(total_earning_rate), 3) # seems this discrepancy is fixed
        else: 
            total_earning_rate = round(float(total_earning_rate), 3)
        total_earning_rate = str(total_earning_rate)
        estimated_deposit = self._comm_get_data(trcode, "", rqname, 0, "추정예탁자산")
        self.opw00018_output['single'].append(Kiwoom.change_format(total_purchase_price))
        self.opw00018_output['single'].append(Kiwoom.change_format(total_eval_price))
        self.opw00018_output['single'].append(Kiwoom.change_format(total_eval_profit_loss_price))
        self.opw00018_output['single'].append(Kiwoom.change_format(total_earning_rate))
        self.opw00018_output['single'].append(Kiwoom.change_format(estimated_deposit))

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
            
            self.opw00018_rawoutput.append([name, code, int(quantity), int(purchase_price), int(current_price), int(invested_amount), int(current_total), float(eval_profit_loss_price), float(earning_rate)])

            quantity = Kiwoom.change_format(quantity)
            purchase_price = Kiwoom.change_format(purchase_price)
            current_price = Kiwoom.change_format(current_price)
            invested_amount = Kiwoom.change_format(invested_amount)
            current_total = Kiwoom.change_format(current_total)
            eval_profit_loss_price = Kiwoom.change_format(eval_profit_loss_price)
            earning_rate = Kiwoom.change_format2(earning_rate)

            self.opw00018_output['multi'].append([name, code, quantity, purchase_price, current_price, invested_amount, current_total, eval_profit_loss_price, earning_rate])
    

    def _opt10001(self, rqname, trcode):
        cur_price = self._comm_get_data(trcode, "", rqname, 0, "현재가")
        try: 
            cur_price = abs(int(cur_price))
        except Exception as e:
            # print(e)
            cur_price = 0
        self.cur_price = cur_price

    @staticmethod
    def change_format(data): 
        strip_data = data.lstrip('-0')
        if strip_data == '':
            strip_data = '0'

        try:
            format_data = format(int(strip_data), ',d')
        except:
            format_data = format(float(strip_data))

        if data.startswith('-'):
            format_data = '-' + format_data

        return format_data

    @staticmethod
    def change_format2(data): 
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
        self.set_input_value("수정주가구분", 1)
        self.comm_rq_data("opt10081_req", "opt10081", 0, "0101")

        df = pd.DataFrame(self.kiwoom.ohlcv, columns=['open', 'high', 'low', 'close', 'volume'],
                       index=self.kiwoom.ohlcv['date'])
        return df

    def excelfile_initiator(self):
        if not os.path.exists(EXCEL_BUY_LIST): 
            # create buy list
            bl = xlsxwriter.Workbook(EXCEL_BUY_LIST)
            blws = bl.add_worksheet() 
    
            blws.write('A1', 'Date') # Date / Time when the item is added
            blws.write('B1', 'Time') 
            blws.write('C1', 'Name') 
            blws.write('D1', 'Code') 
            blws.write('E1', 'Order_type') # 시장가 ('mkt') vs 지정가 ('fixed')
            blws.write('F1', 'Tr') # yet: not, done: done
            blws.write('G1', 'Price') # latest price when the list is populated
            blws.write('H1', 'Amount') 
            # blws.write('I1', 'Invested_total') # Before any fee and tax 
            # blws.write('J1', 'Date_Trans') # Date / Time when the item is purchased 
            # blws.write('K1', 'Time_Trans') 
            bl.close()
    
        if not os.path.exists(EXCEL_SELL_LIST): 
            # create sell list
            sl = xlsxwriter.Workbook(EXCEL_SELL_LIST)
            slws = sl.add_worksheet() 
    
            slws.write('A1', 'Date') # Date / Time when the item is added
            slws.write('B1', 'Time') 
            slws.write('C1', 'Name') 
            slws.write('D1', 'Code') 
            slws.write('E1', 'Order_type') # 시장가 ('mkt') vs 지정가 ('fixed')
            slws.write('F1', 'Tr') # yet: not, done: done
            slws.write('G1', 'Price') # latest price when the list is populated
            slws.write('H1', 'Amount') # Amount to sell
            # slws.write('I1', 'Fee_Tax')
            # slws.write('J1', 'Harvested_total') # After fee and tax  
            # slws.write('K1', 'Date_Trans') # Date / Time when the item is purchased 
            # slws.write('L1', 'Time_Trans') 
            sl.close()

    def get_my_stock_list(self):
        account_number = self.get_login_info("ACCNO")
        account_number = account_number.split(';')[0]

        self.set_input_value("계좌번호", account_number)
        self.comm_rq_data("opw00018_req", "opw00018", 0, "2000")
        
        while self.remained_data:
            self.set_input_value("계좌번호", account_number)
            self.comm_rq_data("opw00018_req", "opw00018", 2, "2000")

        stock_list = pd.DataFrame(self.opw00018_rawoutput, columns=['name', 'code', 'quantity', 'purchase_price', 
            'current_price', 'invested_amount', 'current_total', 'eval_profit_loss_price', 'earning_rate'])
        for i in stock_list.index:
            stock_list.at[i, 'code'] = stock_list['code'][i][1:]   # taking off "A" in front of returned code
        print('My Stock List (up to 50 items): \n', tabulate(stock_list[:50], headers='keys', tablefmt='psql'))
        return stock_list.set_index('code')

    def update_buy_list(self, buy_list_code, buy_list_price):
        buy_list_excel = pd.read_excel(EXCEL_BUY_LIST, index_col=None, converters={'Code':str})

        for i, code in enumerate(buy_list_code):
            name = self.get_master_code_name(code) 
            today = datetime.datetime.today().strftime("%Y%m%d")
            time_ = datetime.datetime.now().strftime("%H:%M:%S")
            amount = round(ALLOCATION_SIZE/buy_list_price[i])
            buy_list_excel = buy_list_excel.append({'Date': today, 'Time': time_, 'Name': name, 'Code': code, 
                'Order_type': 'mkt', 'Tr': 'yet', 'Price': buy_list_price[i], 'Amount': amount }, ignore_index=True)

        print('Buy List Excel (lastest 50 items): \n', tabulate(buy_list_excel[-30:], headers='keys', tablefmt='psql'))
        buy_list_excel.to_excel(EXCEL_BUY_LIST, index=False)

    def update_sell_list(self, sell_list): 

        sell_list_excel = pd.read_excel(EXCEL_SELL_LIST, index_col=None, converters={'Code':str})
        
        for i in range(len(sell_list)):
            today = datetime.datetime.today().strftime("%Y%m%d")
            time_ = datetime.datetime.now().strftime("%H:%M:%S")
            sell_list_excel = sell_list_excel.append({'Date': today, 'Time': time_, 'Name': sell_list.iloc[i]["name"], 'Code': sell_list.index[i],
                'Order_type': 'mkt', 'Tr': 'yet', 'Price': sell_list.iloc[i]["current_price"], 'Amount': sell_list.iloc[i]["quantity"] }, ignore_index=True)

        print('Sell List Excel (lastest 50 items): \n', tabulate(sell_list_excel[-30:], headers='keys', tablefmt='psql'))
        sell_list_excel.to_excel(EXCEL_SELL_LIST, index=False)
