from Kiwoom import tl_print
import pandas as pd
import time
import yfinance as yf
from trtrader import *
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters # For datetime series converting.... 
import multiprocessing
HR_DICT = {'Open': '09:00', 'Low': '11:00', 'High': '13:00', 'Close': '15:30'}
SIM_OUTPUT_FILE = 'data/sim_output.txt'
PLT_PAUSE_DURATION = 0.1

class SimController():
    def __init__(self): # only called once for the whole simulation (backtesting) 
                        # use this to set global variables to be used commonly throughout the backtesting
        try:
            os.system("del data\*.txt data\*.html data\*.xlsx")
        except Exception as e: 
            pass
        self.initial_cash = START_CASH
        self.code_dict = {'005930': '삼성전자'}
        self.code_to_test = '005930.ks'
        self.start_date = '2019-07-06'
        self.end_date = time.strftime("%Y-%m-%d")
        target = yf.Ticker(self.code_to_test)
        self.sim_time = time.asctime(time.strptime(self.start_date, "%Y-%m-%d"))
        self.target_data = target.history(start = self.start_date, end=self.end_date, auto_adjust=False) # volume in number of stocks
        self.queue = multiprocessing.Queue()
        self.plot_proc = multiprocessing.Process(target=self.data_plot, args=(self.target_data,self.queue), kwargs={'name':self.code_to_test}, daemon=True)
        self.plot_proc.start()
        self.execute_ext_list_gen = True # executed at TrTrader when USE_SIMULATION = True

    def run_(self): # this function is to define simulation scheme  
        for cur_date in self.target_data.index:
            self.tt = TrTrader(self)  # a new TrTrader is created each day and exits
            for time_of_day in ['Open', 'Low', 'High', 'Close']:
                self.sim_time = time.asctime(time.strptime(cur_date.strftime("%Y-%m-%d")+" "+ HR_DICT[time_of_day], "%Y-%m-%d %H:%M"))
                self.cur_price = int(self.target_data.loc[cur_date][time_of_day])
                if self.tt.run_():
                    # tr_data: [stock_code, stock_name, buy_sell, avg_price, int(pv), tr_time, [invtotal, ret]]
                    for i in self.tt.tr_data:
                        if i[2] == 'sell':
                            self.execute_ext_list_gen = True
                        self.queue.put([cur_date.strftime("%Y-%m-%d"), i[2], i[6], self.sim_time])
            self.tt.close_()
            del self.tt
        self.queue.put(["Done",])
        print("Simulation Done - close plot to finish")
        # self.plot_proc.join()

    def run_speedy_(self): # this function is to define simulation scheme  
        self.cur_price = self.target_data.iloc[0][0]
        self.tt = TrTrader(self)  # a new TrTrader is created each day and exits
        for cur_date in self.target_data.index:
            for time_of_day in ['Open', 'Low', 'High', 'Close']:
                self.sim_time = time.asctime(time.strptime(cur_date.strftime("%Y-%m-%d")+" "+ HR_DICT[time_of_day], "%Y-%m-%d %H:%M"))
                self.cur_price = int(self.target_data.loc[cur_date][time_of_day])
                if self.tt.run_(): # if trade happens
                    # tr_data: [stock_code, stock_name, buy_sell, avg_price, int(pv), tr_time, [invtotal, ret]]
                    for i in self.tt.tr_data:
                        if i[2] == 'sell':
                            self.execute_ext_list_gen = True
                        self.queue.put([cur_date.strftime("%Y-%m-%d"), i[2], i[6], self.sim_time])
        self.tt.close_()
        del self.tt
        self.queue.put(["Done",])
        print("Simulation Done - close plot to finish")
        # self.plot_proc.join()
        
    def ext_list_gen(self): 
        external_list = pd.DataFrame({'code':pd.Series([], dtype='str'),
                                   'amount':pd.Series([], dtype='int'),
                                   'buy_sell':pd.Series([], dtype='str'),
                                   'note':pd.Series([], dtype='str')})
        if self.execute_ext_list_gen:
            external_list.loc[len(external_list)] = ['005930', 0, 'buy', 'yet']
            self.execute_ext_list_gen = False
        return external_list 

    def data_plot(self, data, queue, name="<target_name>"):
        register_matplotlib_converters()
        fig, (ax1, ax2)= plt.subplots(2, 1, sharex=True)
        plt.setp(ax1.get_xticklabels(), fontsize = 9) 
        plt.setp(ax1.get_yticklabels(), fontsize = 9)
        plt.setp(ax2.get_xticklabels(), fontsize = 9, horizontalalignment = 'right')
        plt.setp(ax2.get_yticklabels(), fontsize = 9) 

        ax1.plot(data['Close'], '-b', lw = 0.8) 
        ax1.set_title(f"Close price for {name}", size = 9, fontweight = 'bold')
        ax1.set_ylabel("Price", size = 9)
        ax1.grid()

        ax2.bar(data.index, (data['Volume']/(10**6)).astype(int), color = 'black')
        ax2.set_title("Volume is in number of shares and in 10^6", size = 9)
        ax2.set_ylabel("Volume", size = 9)
        ax2.set_xlabel("Time", size = 9)
        ax2.grid()
        fig.autofmt_xdate()
        while 1: 
            comm_obj = queue.get()
            if comm_obj[0] == "Done": 
                break
            else:
                cdata = data.loc[data.index == comm_obj[0]]
                pt = pd.Series([cdata['Close'], ], index = [pd.Timestamp(comm_obj[0]),])
                if comm_obj[1] == 'buy':
                    ax1.axvline(x = cdata.index[0], color='g', ls ='--', lw=0.8)
                    ax1.plot(pt, 'go')
                    # ax1.text(pt.index[0], pt[0], 'buy')
                else: # 'sell'
                    ax1.plot(pt, 'r^')
                    ax1.axvline(x = cdata.index[0], color='r', ls ='--', lw=0.8)
                    if len(comm_obj[2]) == 2:
                        r_ = format(comm_obj[2][1]/comm_obj[2][0]*100, '.1f')
                        # ax1.text(pt.index[0], pt[0], 'sell: ' + str(format(comm_obj[2][1]/1000, '.1f')) + 'k/'+ str(format(comm_obj[2][0]/1000000, '.1f')) + 'm(' + r_ +'%)' )
                        print(f"{comm_obj[3]}: {str(format(comm_obj[2][1]/1000, '.1f'))} k/ {str(format(comm_obj[2][0]/1000000, '.1f'))}m({r_}%)")
                    else: 
                        # ax1.text(pt.index[0], pt[0], 'sell')
                        pass
                plt.pause(PLT_PAUSE_DURATION)
        plt.savefig("data\data_plot.png", dpi = 300)
        plt.show()

class Simulator(SimController):
    def __init__(self, simctrl):
        self.connect_status = True
        self.simctrl = simctrl

    def get_master_code_name(self, code):  
        if code in list(self.simctrl.code_dict.keys()):
            return self.simctrl.code_dict[code]
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



if __name__ == "__main__":
    sc = SimController()
    # sc.run_()
    sc.run_speedy_()