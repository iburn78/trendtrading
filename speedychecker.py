from trsettings import *

class speedychecker():
    def __init__(self): 
        self.initial_cash = START_CASH
        self.target_data = get_target_data(code_to_test, start_date, end_date)
        self.mb = pd.DataFrame(columns = ['vol', 'avg_price', 'cur_price', 'retrate', 'ninv', 'time', 'cash'])
        self.stat = {'cash': START_CASH, 't_inv': 0, 'c_val': 0, 't_rr': 0}
        self.bounds_table = bounds_prep()
        self.suspended = False

    def run_(self):
        for cur_date in self.target_data.index:
            for time_of_day in ['Open', 'Low', 'High', 'Close']:
                # self.sim_time = time.asctime(time.strptime(cur_date.strftime("%Y-%m-%d")+" "+ HR_DICT[time_of_day], "%Y-%m-%d %H:%M"))
                self.speedy_logic(round(self.target_data.loc[cur_date][time_of_day]), cur_date.strftime("%Y%m%d ") + time_of_day[0])
        self.mb = self.mb.astype({'vol':'int', 'avg_price':'int', 'cur_price':'int', 'retrate':'float', 'ninv':'int', 'time': 'str', 'cash':'int'})
        sm_print(self.mb)
        sm_print(f'cash: {format(int(self.stat["cash"]), ",")}')
        sm_print(f'tinv: {format(int(self.stat["t_inv"]), ",")} - principal amount invested')
        sm_print(f'tpft: {format(int(self.stat["c_val"]+self.stat["cash"]-START_CASH), ",")} - latest price reflected')
        sm_print(f'rate: {format(self.stat["t_rr"]-100, ".4f")} % - latest price reflected')
        if self.suspended: 
            sm_print('(Note: suspended item exists)')

    def speedy_logic(self, cur_price, t):
        if len(self.mb) == 0:
            self.purchase(TICKET_SIZE, cur_price, 0, 0, -1, t) # initial purchase
        else: 
            l = self.mb.iloc[-1] 
            if l.vol == 0: # all sold situation
                self.purchase(TICKET_SIZE, cur_price, 0, 0, -1, t)
            else: 
                rr = round((cur_price*(1-TAX_RATE-FEE_RATE)/(l.avg_price*(1+FEE_RATE)) - 1), 4)
                if not self.suspended and rr <= self.bounds_table.at['LLB', int(l.ninv)]:
                    sm_print(f'{t}: LLB suspend initiated with return rate {rr}')
                    self.stat['c_val'] = round(cur_price*(l.vol)*(1-TAX_RATE-FEE_RATE))
                    self.stat['t_rr'] = round((self.stat['cash']+self.stat['c_val'])/START_CASH*100, 4)
                    self.suspended = True
                    return  
                if self.suspended:
                    if rr >= self.bounds_table.at['LB', int(l.ninv)]:
                        sm_print(f'{t}: Released from LLB suspend with return rate {rr}')
                        self.stat['c_val'] = round(cur_price*(l.vol)*(1-TAX_RATE-FEE_RATE))
                        self.stat['t_rr'] = round((self.stat['cash']+self.stat['c_val'])/START_CASH*100, 4)
                        self.suspended = False
                    return

                if rr <= self.bounds_table.at['LB', int(l.ninv)]:
                    self.sell(cur_price, l.vol, t)
                elif rr >= self.bounds_table.at['UB', int(l.ninv)]:
                    if l.ninv < MAX_REINVESTMENT:
                        self.purchase(TICKET_SIZE, cur_price, l.vol, l.avg_price, l.ninv, t)
                    elif l.ninv < MAX_ELEVATION: 
                        self.purchase(0, cur_price, l.vol, l.avg_price, l.ninv, t)
                    else: # if l.ninv == MAX_ELEVATION:
                        self.sell(cur_price, l.vol, t)

    def purchase(self, size, cur_price, pvol, pavg_price, ninv, t = ''):
        vol = round(size/cur_price)
        avg_price = round((pvol*pavg_price + vol*cur_price)/(pvol+vol))
        rr = round((cur_price*(1-TAX_RATE-FEE_RATE)/(avg_price*(1+FEE_RATE)) - 1), 4)
        cash = self.stat['cash'] - round(vol*cur_price*(1+FEE_RATE))
        record = [pvol+vol, avg_price, cur_price, rr, ninv+1, t, cash]
        self.mb.loc[len(self.mb)] = record
        self.stat['cash'] = cash 
        self.stat['t_inv'] = round(self.stat['t_inv'] + vol*cur_price*(1+FEE_RATE))
        self.stat['c_val'] = round(cur_price*(pvol+vol)*(1-TAX_RATE-FEE_RATE))
        self.stat['t_rr'] = round((self.stat['cash']+self.stat['c_val'])/START_CASH*100, 4)

    def sell(self, cur_price, pvol, t=''): 
        cash = self.stat['cash'] + round(pvol*cur_price*(1-TAX_RATE-FEE_RATE))
        record = [0, 0, cur_price, 0, -1, t, cash]
        self.mb.loc[len(self.mb)] = record
        self.stat['cash'] = cash
        self.stat['t_inv'] = 0
        self.stat['c_val'] = 0
        self.stat['t_rr'] = round(self.stat['cash']/START_CASH*100, 4)

if __name__ == '__main__': 
    sc = speedychecker()
    sc.run_()