from trsettings import *

class Simulator():
    def __init__(self, simctrl):
        self.connect_status = True
        self.simctrl = simctrl

    def get_master_code_name(self, code):  
        if code in list(code_dict.keys()):
            return code_dict[code]
        return 'name_na'    

    def send_order(self, rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no): 
        tl_print("[SendOrder]", time.strftime(" %m%d %H:%M:%S"), '---', str(acc_no), str(order_type), str(code), str(quantity), str(price), str(hoga), str(order_no))
        stock_name = self.get_master_code_name(code)
        buy_sell = {'1': 'buy', '2': 'sell'}[str(order_type)]
        avg_price = self.get_price(code)
        pv = oq = quantity
        tr_time = self.simctrl.sim_time # for excel file recognition, it is required to use ctime format
        self.chejan_finish_data = [code, stock_name, buy_sell, avg_price, int(pv), tr_time]   
        bs = {'1': '+매수', '2': '-매도'}[str(order_type)]
        tr_time = time.strftime("%y%m%d %H:%M:%S", time.strptime(tr_time))
        tl_print(" " + tr_time + " " + stock_name + "("+ code + ") " + bs + ", " + str(pv) + "/" + str(oq) + ", at price: " + format(avg_price, ','))
        return (0, '---') # returns success
    
    def get_price(self, code):
        return self.simctrl.cur_price

    def get_account_stock_list(self, ACCOUNT_NO): 
        stock_list = pd.DataFrame(columns = ['code', 'name', 'cprice', 'nshares', 'invtotal', 'cvalue', 'retrate'])
        return stock_list

    def get_cash(self, ACCOUNT_NO):   
        return self.simctrl.initial_cash