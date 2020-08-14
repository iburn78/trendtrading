import pandas as pd
import time
import yfinance as yf

START_CASH = 300000000
TICKET_SIZE = 3000000       
FEE_RATE = 0.00015
TAX_RATE = 0.003  
HR_DICT = {'Open': '09:00', 'Low': '11:00', 'High': '13:00', 'Close': '15:30'}
BOUNDS_FILE = 'bounds.xlsx'

class speedychecker():
    def __init__(self): 
        self.initial_cash = START_CASH
        self.code_to_test = '005930.ks'
        self.start_date = '2019-07-06'
        self.end_date = time.strftime("%Y-%m-%d")
        target = yf.Ticker(self.code_to_test)
        self.target_data = target.history(start = self.start_date, end=self.end_date, auto_adjust=False) # volume in number of stocks
        self.mb = pd.DataFrame(columns = ['volume', 'avg_price', 'cur_price', 'retrate', 'ninv'])
        self.stat = {'cash': START_CASH, 't_inv': 0, 'retrate': 0}
        self.bounds_prep()

    def run_(self):
        for cur_date in self.target_data.index:
            for time_of_day in ['Open', 'Low', 'High', 'Close']:
                # self.sim_time = time.asctime(time.strptime(cur_date.strftime("%Y-%m-%d")+" "+ HR_DICT[time_of_day], "%Y-%m-%d %H:%M"))
                self.speedy_logic(self.target_data.loc[cur_date][time_of_day])
        self.mb = self.mb.astype({'volume':'int', 'avg_price':'int', 'cur_price':'int', 'retrate':'float', 'ninv':'int'})
        print(self.mb)
        print(self.stat)

    def speedy_logic(self, cur_price):
        if len(self.mb) == 0:
            self.purchase(cur_price, 0, 0, -1) # initial purchase
        else: 
            l = self.mb.iloc[-1] 
            if l.volume == 0: # all sold situation
                self.purchase(cur_price, 0, 0, -1)
            else: 
                if l.ninv < 5:
                    rr = round((cur_price*(1-TAX_RATE-FEE_RATE)/(l.avg_price*(1+FEE_RATE)) - 1), 4)
                    if rr <= self.bounds_table.at['LB', int(l.ninv)]:
                        self.sell(cur_price, l.volume)
                    elif rr >= self.bounds_table.at['UB', int(l.ninv)]:
                        self.purchase(cur_price, l.volume, l.avg_price, l.ninv)
                    else:
                        pass
                        ########## LLB NOT IMPLEMENTED ###########
                elif l.ninv < 10:
                    self.mb.at[len(self.mb), 'ninv'] = l.ninv + 1
                else: 
                    self.sell(cur_price, l.volume)

    def purchase(self, cur_price, pvol, pavg_price, ninv):
            volume = int(round(TICKET_SIZE/cur_price))
            avg_price = int(round((pvol*pavg_price + volume*cur_price)/(pvol+volume)))
            rr = float(format((cur_price - avg_price)/avg_price, '.4f'))
            record = [pvol+volume, avg_price, cur_price, rr, ninv+1]
            self.mb.loc[len(self.mb)] = record
            self.stat['cash'] = int(round(self.stat['cash'] - volume*cur_price*(1+FEE_RATE)))
            self.stat['t_inv'] = int(round(self.stat['t_inv'] + volume*cur_price*(1+FEE_RATE)))
            total_value = self.stat['cash'] + cur_price*(pvol+volume)*(1-TAX_RATE-FEE_RATE)
            self.stat['retrate'] = float(format(total_value/START_CASH*100, '.4f'))
    
    def sell(self, cur_price, pvol): 
            record = [0, 0, cur_price, 0, -1]
            self.mb.loc[len(self.mb)] = record
            self.stat['cash'] = int(round(self.stat['cash'] + pvol*cur_price*(1-TAX_RATE-FEE_RATE)))
            self.stat['t_inv'] = 0
            self.stat['retrate'] = float(format(self.stat['cash']/START_CASH*100, '.4f'))

    def bounds_prep(self):
        self.bounds_table = pd.read_excel(BOUNDS_FILE, index_col=None).iloc[29:32, 1:13]
        self.bounds_table.columns = ['var', 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.bounds_table = self.bounds_table.set_index('var')

if __name__ == '__main__': 
    sc = speedychecker()
    sc.run_()