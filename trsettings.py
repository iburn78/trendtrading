import time
import sys, os 
import pandas as pd
import yfinance as yf
from tabulate import tabulate 
import json
from datetime import datetime
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters # For datetime series converting.... 
import multiprocessing
PLT_PAUSE_DURATION = 0.1
PLT_SHOW_DURATION = 10
################################################################################################
WORKING_DIR_PATH = "C:/Users/user/Projects/trendtrading/"
EXTERNAL_TRTRADER_SETTINGS_FILE = 'trtrader_settings.dat' ### TRTRADE_SETTINGS_FILE IS NOT UPLOADED TO GIT - USE THIS FOR CONFIDENTIAL INFO
TRADE_LOG_FILE = WORKING_DIR_PATH + 'data/trade_log.txt'
MASTER_BOOK_FILE = 'data/master_book.xlsx'
MASTER_BOOK_BACKUP_FILE = 'data/backup/master_book.xlsx'
BOUNDS_FILE = 'bounds.xlsx'
with open(WORKING_DIR_PATH+EXTERNAL_TRTRADER_SETTINGS_FILE) as f:
    tsf = json.load(f)
    ACCOUNT_NO = tsf['ACCOUNT_NO'] 
################################################################################################
START_CASH = 300000000
TICKET_SIZE = 3000000       # Target amount to be purchased in KRW
MIN_CASH_FOR_PURCHASE_RATE = 1.5
MIN_CASH_FOR_PURCHASE = TICKET_SIZE*MIN_CASH_FOR_PURCHASE_RATE
MAX_REINVESTMENT = 4        # total 5 investments max
MAX_ELEVATION = 10          # do not change this const unless bounds.xlsx is modified
PRINT_TO_SCREEN = True
################################################################################################
USE_SIMULATOR = True
SIM_LOG_FILE = WORKING_DIR_PATH + 'data/sim_log.txt'
if USE_SIMULATOR:
    FEE_RATE = 0.00015        # real FEE_RATE
    TAX_RATE = 0.003          # real TAX_RATE (may differ by KOSDAQ/KOSPI and by product type, e.g., cheaper tax for derivative products)
else: 
    FEE_RATE = 0.0035           # for Kiwoom Test Server
    TAX_RATE = 0.0025           # for Kiwoom Test Server (may differ by KOSDAQ/KOSPI and by product type, e.g., cheaper tax for derivative products) 
################################################################################################
code_dict = {'005930': '삼성전자'}
HR_DICT = {'Open': '09:00', 'Low': '11:00', 'High': '13:00', 'Close': '15:30'}
code_to_test = '005930.ks'
code_dict = {'005930': '삼성전자'}
start_date = '2019-07-06'
end_date = time.strftime("%Y-%m-%d")
##################################################################
def get_target_data(code_to_test, start_date, end_date):
    target = yf.Ticker(code_to_test)
    target_data = target.history(start=start_date, end=end_date, auto_adjust=False) # volume in number of stocks
    #### manipulation part ####
    target_data.loc['2019-08-01':'2019-08-31'] = target_data.loc['2019-08-01':'2019-08-31']/2 
    for i in range(101,121): 
        target_data.iloc[i] = target_data.iloc[i]*(1+(i-100)/10)
    ###########################
    return target_data

def tl_print(*args, **kwargs):
    file_print(TRADE_LOG_FILE, *args, **kwargs)

def sm_print(*args, **kwargs):
    file_print(SIM_LOG_FILE, *args, **kwargs)

def file_print(filename_, *args, **kwargs): 
    ff = open(filename_, 'a')
    msg = str(args[0])
    for i in args[1:]: 
        msg += " " + str(i)
    ff.write(msg + "\n")
    if PRINT_TO_SCREEN:
        print(*args, **kwargs)
    ff.close()

def remove_master_book_onetime_for_clean_initiation():
    if os.path.exists(MASTER_BOOK_FILE):
        t = time.strftime("_%Y%m%d_%H%M%S")
        n = MASTER_BOOK_BACKUP_FILE[:-5]
        os.rename(WORKING_DIR_PATH+MASTER_BOOK_FILE, WORKING_DIR_PATH+n+t+'.xlsx')

def bounds_prep(draw=False):
    u_step = 0.1
    l_step = -0.05
    ll_step = -0.15
    # index: current period or number of reinv since initial investment / 0: initial investement made / 1: reinvestment made ... etc
    # ub_price: to-be price for reinvestment made 
    # lb_price: to-be price for sell off
    # llb_price: to-be price for LLB suspend
    ub_price = [float(format((1+u_step)**(1+i), '.5f')) for i in range(MAX_ELEVATION+1)]
    lb_price = [float(format(ub_price[i]/(1+u_step)*(1+l_step), '.5f')) for i in range(MAX_ELEVATION+1)]
    llb_price = [float(format(ub_price[i]/(1+u_step)*(1+ll_step), '.5f')) for i in range(MAX_ELEVATION+1)]
    # avg_price: avg_price after the current period's investment made
    for i in range(MAX_ELEVATION+1):
        if i == 0: 
            avg_price = [1]
        elif i <= MAX_REINVESTMENT: 
            avg_price.append(float(format((i+1)/((i)/avg_price[i-1] + 1/ub_price[i-1]), '.5f')))
        else: 
            avg_price.append(avg_price[i-1])
    # ub: to-be return rate to reach ub_price
    # lb: to-be return rate to sell off
    # llb: to-be return rate to LLB suspend
    ub = [float(format((ub_price[i]-avg_price[i])/avg_price[i], '.5f')) for i in range(MAX_ELEVATION+1)]
    lb = [float(format((lb_price[i]-avg_price[i])/avg_price[i], '.5f')) for i in range(MAX_ELEVATION+1)]
    llb = [float(format((llb_price[i]-avg_price[i])/avg_price[i], '.5f')) for i in range(MAX_ELEVATION+1)]
    llb[-1] = -1 # ensure to sell off at MAX_ELEVATION
    # rr: return rate after the current period's investemnt made 
    rr = [0]
    for i in range(MAX_ELEVATION): 
        rr.append(float(format((ub_price[i]-avg_price[i+1])/avg_price[i+1],'.5f')))

    bounds_table = pd.DataFrame([ub, lb, llb], index = ['UB', 'LB', 'LLB'], columns = range(MAX_ELEVATION+1))
    if draw: 
        print(bounds_table)
        fig, ax = plt.subplots()
        ax.plot(rr, label="return rate")
        ax.plot(ub, label="UB")
        ax.plot(lb, label="LB")
        ax.plot(llb, label="LLB")
        ax.set_title("Bounds")
        ax.set_xlabel("Number of reinvestments made")
        ax.set_ylabel("rate (not in %)")
        plt.legend()
        plt.show()

    return bounds_table

if __name__ == "__main__":
    bd = bounds_prep(draw = True)