from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
import time
import pandas as pd
from tabulate import tabulate 
import json

################################################################################################
TRTRADER_SETTINGS_FILE = 'trtrader_settings.dat'
API_REQ_TIME_INTERVAL = 0.3 # min: 0.2
################################################################################################
with open(TRTRADER_SETTINGS_FILE) as f:
    tsf = json.load(f)
    WORKING_DIR_PATH = tsf['WORKDING_DIR'] 
################################################################################################
TRADE_LOG_FILE = WORKING_DIR_PATH + 'data/trade_log.txt'
def tl_print(*args, **kwargs):
    ff = open(TRADE_LOG_FILE, 'a')
    msg = str(args[0])
    for i in args[1:]: 
        msg += " " + str(i)
    ff.write(msg + "\n")
    print(*args, **kwargs)
    ff.close()

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        self._set_signal_slots()
        self.connect_status = False
        self.chejan_finish_data = []
        self._chejan_avg_price_data = []
        self.comm_connect()

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
            tl_print("Kiwoom API connected")
        else:
            tl_print("Kiwoom API not connected")
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
            tl_print("[SendOrder]", time.strftime(" %m%d %H:%M:%S"), self.order_number, str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no))
            self.chejan_event_loop = QEventLoop()
            self.chejan_event_loop.exec_()
        else:
            tl_print("--- SendOrder Fail:", "("+str(res)+")", time.strftime(" %m%d %H:%M:%S"), self.order_number, str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no))
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
            tr_time = time.strftime("%m%d %H:%M:%S")
            self._chejan_avg_price_data.append([int(pv), tr_price])
            tl_print(" " + tr_time + " " + stock_name + "("+ stock_code + ") "
                  + bs + ", " + pv + "/" + oq + ", at price: " + format(tr_price, ','))
            if pv == oq: 
                tr_time = time.ctime() # for excel file recognition
                if len(self._chejan_avg_price_data) == 1:
                    avg_price = tr_price
                else: 
                    p_sum = self._chejan_avg_price_data[0][0]*self._chejan_avg_price_data[0][1]
                    for i in range(1, len(self._chejan_avg_price_data)):
                        p_sum = p_sum + (self._chejan_avg_price_data[i][0] - self._chejan_avg_price_data[i-1][0])*self._chejan_avg_price_data[i][1]
                    avg_price = int(p_sum/int(oq))
                self.chejan_finish_data = [stock_code, stock_name, buy_sell, avg_price, int(pv), tr_time]
                self._chejan_avg_price_data = []
                tl_print(" average price: " + format(avg_price, ','))
                try:
                    self.chejan_event_loop.exit()
                except Exception as e: 
                    tl_print("Exception: On chejan receive, loop exit error: " + str(e))

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
            tl_print("TR request name not matching: ", screen_no, rqname, trcode, record_name, next_, unused1, unused2, unused3, unused4)

        try:
            self.tr_event_loop.exit()
        except Exception as e: 
            tl_print("Exception: On tr receive, loop exit error: " + str(e))

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
        multi_data = pd.DataFrame(multi_data, columns = ['cprice', 'vol', 'vol_krw', 'date', 'start', 'high', 'low'])
        multi_data[['cprice', 'vol', 'vol_krw', 'start', 'high', 'low']] = multi_data[['cprice', 'vol', 'vol_krw', 'start', 'high', 'low']].astype('int')
        multi_data['date'] = pd.to_datetime(multi_data['date'])
        self.opt10081_multi_data_set = multi_data
        
    def _opw00001(self, rqname, trcode):
        d2_deposit = self._comm_get_data(trcode, "", rqname, 0, "d+2추정예수금")
        self.d2_deposit = d2_deposit
        # self.d2_deposit = Kiwoom.change_format(d2_deposit)

    def _opw00018(self, rqname, trcode):
        # single data
        total_purchase_price = self._comm_get_data(trcode, "", rqname, 0, "총매입금액")
        total_eval_price = self._comm_get_data(trcode, "", rqname, 0, "총평가금액")
        total_ret = self._comm_get_data(trcode, "", rqname, 0, "총평가손익금액")
        total_retrate = self._comm_get_data(trcode, "", rqname, 0, "총수익률(%)")
        estimated_deposit = self._comm_get_data(trcode, "", rqname, 0, "추정예탁자산")
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_purchase_price))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_eval_price))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_ret))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(total_retrate))
        self.opw00018_formatted_data['single'].append(Kiwoom.change_format(estimated_deposit))

        # multi data
        rows = self._get_repeat_cnt(trcode, rqname)
        for i in range(rows):
            name = self._comm_get_data(trcode, "", rqname, i, "종목명")
            code = self._comm_get_data(trcode, "", rqname, i, "종목번호")
            quantity = self._comm_get_data(trcode, "", rqname, i, "보유수량")
            purchase_price = self._comm_get_data(trcode, "", rqname, i, "매입가")
            current_price = self._comm_get_data(trcode, "", rqname, i, "현재가")
            invested_amount = self._comm_get_data(trcode, "", rqname, i, "매입금액") # before any tax/fee
            current_total = self._comm_get_data(trcode, "", rqname, i, "평가금액") # before any tax/fee
            ret = self._comm_get_data(trcode, "", rqname, i, "평가손익") # after all tax/fee
            retrate = self._comm_get_data(trcode, "", rqname, i, "수익률(%)") # ret over invested_amount (so this is not exact return rate, exact return rate = ret over (inveted_amount + buy_fee))
            
            # for data handling
            self.opw00018_stocklist.append([name, code, int(quantity), int(purchase_price), int(current_price), int(invested_amount), int(current_total), int(ret), float(retrate)])

            # for printing
            quantity = Kiwoom.change_format(quantity)
            purchase_price = Kiwoom.change_format(purchase_price)
            current_price = Kiwoom.change_format(current_price)
            invested_amount = Kiwoom.change_format(invested_amount)
            current_total = Kiwoom.change_format(current_total)
            ret = Kiwoom.change_format(ret)
            retrate = Kiwoom.change_format_rate(retrate)
            self.opw00018_formatted_data['multi'].append([name, code, quantity, purchase_price, current_price, invested_amount, current_total, ret, retrate])

        if self.remained_data: 
            tl_print("Exception: REMAINED STOCK EXISTS - IN OPW00018")
            raise Exception()
    
    def _opt10001(self, rqname, trcode):
        cprice = self._comm_get_data(trcode, "", rqname, 0, "현재가")
        try: 
            cprice = abs(int(cprice))
        except Exception as e:
            # print(e) # error when cprice = ""
            cprice = 0
        self.cprice = cprice

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
    
    def get_price(self, code): 
        self.set_input_value('종목코드', code)
        self.comm_rq_data('opt10001_req', 'opt10001', 0, '2000')
        return self.cprice # cprice will return integer value. 0 will be returned when API returns ""

    def get_account_stock_list(self, ACCOUNT_NO):
        self.set_input_value("계좌번호", ACCOUNT_NO)
        self.comm_rq_data("opw00018_req", "opw00018", 0, "2000")
        
        while self.remained_data: # there is almost no chance that there will be remained data 
            self.set_input_value("계좌번호", ACCOUNT_NO)
            self.comm_rq_data("opw00018_req", "opw00018", 2, "2000")

        stock_list = pd.DataFrame(self.opw00018_stocklist, columns=['name', 'code', 'nshares', 'pur_price', 
            'cprice', 'invtotal', 'cvalue', 'ret', 'retrate'])

        for i in stock_list.index:
            stock_list.at[i, 'code'] = stock_list['code'][i][1:]   # taking off "A" in front of returned code

        # print('My Stock List (up to 75 items): \n', tabulate(stock_list[:75], headers='keys', tablefmt='psql'))
        return stock_list

    def get_cash(self, ACCOUNT_NO):
        self.set_input_value('계좌번호', ACCOUNT_NO)
        self.comm_rq_data('opw00001_req', 'opw00001', 0, '2000')
        return self.d2_deposit

if __name__ == "__main__":
    app = QApplication([''])
    km = Kiwoom()
    del km
    app.quit()


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