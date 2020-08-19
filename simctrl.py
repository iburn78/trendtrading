from trsettings import *
from trtrader import *
from speedychecker import *


class SimController():
    def __init__(self): # only called once for the whole simulation (backtesting) 
                        # use this to set global variables to be used commonly throughout the backtesting
        try:
            os.system("del data\*.txt data\*.html data\*.xlsx")
        except Exception as e: 
            pass
        self.initial_cash = START_CASH
        self.target_data = get_target_data(code_to_test, start_date, end_date)
        self.sim_time = time.asctime(time.strptime(start_date, "%Y-%m-%d"))
        self.queue = multiprocessing.Queue()
        self.plot_proc = multiprocessing.Process(target=self.data_plot, args=(self.target_data,self.queue), kwargs={'name':code_to_test}, daemon=True)
        self.plot_proc.start()
        self.execute_ext_list_gen = True # executed at TrTrader when USE_SIMULATION = True

    def run_(self): # this function is to define the simulation scheme  
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
        sm_print("Simulation Done - close plot to finish")
        self.plot_proc.join()

    def run_speedy_(self): 
        self.cur_price = self.target_data.iloc[0][0]
        self.tt = TrTrader(self)  # a new TrTrader is created only once for the whole period
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
        sm_print(self.tt.master_book)
        self.mb_lastline = self.tt.master_book.iloc[-1].copy()
        self.tt.close_()
        del self.tt
        self.queue.put(["Done",])
        sm_print("Simulation Done")
        sm_print("Speedy Checker running")
        self.speedychecker_run()
        sm_print("Speedy Checker done")
        self.plot_proc.join()
        
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
                        sm_print(f"{comm_obj[3]}: {str(format(comm_obj[2][1]/1000, '.1f'))} k/ {str(format(comm_obj[2][0]/1000000, '.1f'))}m({r_}%)")
                    else: 
                        # ax1.text(pt.index[0], pt[0], 'sell')
                        pass
                plt.pause(PLT_PAUSE_DURATION)
        plt.savefig("data\data_plot.png", dpi = 300)
        plt.pause(PLT_SHOW_DURATION)

    def speedychecker_run(self): 
        sc = speedychecker()
        sc.run_()
        if sc.stat['cash'] == self.mb_lastline['cash'] and sc.stat['t_inv'] == self.mb_lastline['invtotal']:
            sm_print(f"checking success cash {format(sc.stat['cash'], ',')} and total invested principal {format(sc.stat['t_inv'], ',')}")
        else: 
            sm_print("SPEEDY CHECKER MISMATCHES ######################################")

if __name__ == "__main__":
    if not USE_SIMULATOR: 
        sys.exit("Turn USE_SIMULATOR")
    sc = SimController()
    # sc.run_()
    sc.run_speedy_()