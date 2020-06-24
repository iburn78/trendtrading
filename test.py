# USAGE OF KIWOOM CLASS
'''
from Kiwoom import *

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
Implementing opt10081 using _get_comm_data_ex
k.set_input_value('종목코드', '005930')
k.set_input_value('틱범위', '1')
k.set_input_value('수정주가구분', '1')
k.comm_rq_data('opt10081_req_ex', 'opt10081', 0, '2000')
print('주식일봉차트조회, opt', k.opt10081_multi_data_set)
print(k.remained_data)
# ---------------------------------

# k.show()
# app.exec_()
app.quit()
'''