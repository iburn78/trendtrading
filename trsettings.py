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

# pd.set_option('display.max_rows', None)
################################################################################################
PLT_PAUSE_DURATION = 0.1
PLT_SHOW_DURATION = 10
################################################################################################
EXTERNAL_TRTRADER_SETTINGS_FILE = 'trtrader_settings.dat' ### TRTRADE_SETTINGS_FILE IS NOT UPLOADED TO GIT - USE THIS FOR CONFIDENTIAL INFO
with open(EXTERNAL_TRTRADER_SETTINGS_FILE) as f:
    tsf = json.load(f)
    ACCOUNT_NO = tsf['ACCOUNT_NO'] 
TRTRADER_DATA_DIR = 'data/'
TRTRADER_DATA_BACKUP_DIR = 'data/backup/'
TRADE_LOG_FILE = TRTRADER_DATA_DIR+'trade_log.txt'
MASTER_BOOK_FILE = TRTRADER_DATA_DIR+'master_book.xlsx'
MASTER_BOOK_BACKUP_FILE = TRTRADER_DATA_BACKUP_DIR+'master_book.xlsx'
################################################################################################
U_STEP = 0.15
L_STEP = -0.05
LL_STEP = -0.30
################################################################################################
START_CASH = 300000000
TICKET_SIZE = 3000000       # Target amount to be purchased in KRW
MIN_CASH_FOR_PURCHASE_RATE = 1.5
MIN_CASH_FOR_PURCHASE = TICKET_SIZE*MIN_CASH_FOR_PURCHASE_RATE
MAX_REINVESTMENT = 4        # total 5 investments max
MAX_ELEVATION = 10          # do not change this const unless bounds.xlsx is modified
PRINT_TO_SCREEN = True
################################################################################################
USE_SIMULATOR = False
SIM_LOG_FILE = TRTRADER_DATA_DIR+'sim_log.txt'
if USE_SIMULATOR:
    FEE_RATE = 0.00015        # real FEE_RATE
    TAX_RATE = 0.003          # real TAX_RATE (may differ by KOSDAQ/KOSPI and by product type, e.g., cheaper tax for derivative products)
else: 
    FEE_RATE = 0.0035           # for Kiwoom Test Server
    TAX_RATE = 0.0025           # for Kiwoom Test Server (may differ by KOSDAQ/KOSPI and by product type, e.g., cheaper tax for derivative products) 
################################################################################################
HR_DICT = {'Open': '09:00', 'Low': '11:00', 'High': '13:00', 'Close': '15:30'}
code_dict = {'005930': '삼성전자', '000660': 'SK하이닉스', '105560': 'KB금융'}
code_to_test = '105560'
code_to_test_yf = code_to_test+'.ks'
start_date = '2013-01-01'
end_date = '2020-08-21' # time.strftime("%Y-%m-%d")
##################################################################
def get_target_data(code_to_test_yf, start_date, end_date):
    target = yf.Ticker(code_to_test_yf)
    target_data = target.history(start=start_date, end=end_date, auto_adjust=False) # volume in number of stocks
    #### manipulation part ####
    target_data.loc['2019-08-01':'2019-08-31'] = target_data.loc['2019-08-01':'2019-08-31']/2 
    for i in range(101,121): 
        target_data.iloc[i] = target_data.iloc[i]*(1+(i-100)/10)
    for i in range(121,141): 
        target_data.iloc[i] = target_data.iloc[i]*(1+(140-i)/10)
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

def controller_clean_initiation_prep():
    if not os.path.exists(TRTRADER_DATA_DIR):
        os.mkdir(TRTRADER_DATA_DIR)
    if not os.path.exists(TRTRADER_DATA_BACKUP_DIR):
        os.mkdir(TRTRADER_DATA_BACKUP_DIR)
    remove_master_book_onetime_for_clean_initiation()

def remove_master_book_onetime_for_clean_initiation():
    if os.path.exists(MASTER_BOOK_FILE):
        t = time.strftime("_%Y%m%d_%H%M%S")
        n = MASTER_BOOK_BACKUP_FILE[:-5]
        os.rename(MASTER_BOOK_FILE, n+t+'.xlsx')

def bounds_prep(draw=False):
    u_step = U_STEP # 0.15
    l_step = L_STEP # -0.05
    ll_step = LL_STEP # -0.30
    # index: current period or number of reinv since initial investment / 0: initial investement made / 1: reinvestment made ... etc
    # ub_price: to-be price for reinvestment made 
    # lb_price: to-be price for sell off
    # llb_price: to-be price for LLB suspend
    ub_price = [round((1+u_step)**(1+i), 4) for i in range(MAX_ELEVATION+1)]
    lb_price = [round(ub_price[i]/(1+u_step)*(1+l_step), 4) for i in range(MAX_ELEVATION+1)]
    llb_price = [round(ub_price[i]/(1+u_step)*(1+ll_step), 4) for i in range(MAX_ELEVATION+1)]
    # avg_price: avg_price after the current period's investment made
    for i in range(MAX_ELEVATION+1):
        if i == 0: 
            avg_price = [1]
        elif i <= MAX_REINVESTMENT: 
            avg_price.append(round((i+1)/((i)/avg_price[i-1] + 1/ub_price[i-1]), 4))
        else: 
            avg_price.append(avg_price[i-1])
    # ub: to-be return rate to reach ub_price
    # lb: to-be return rate to sell off
    # llb: to-be return rate to LLB suspend
    ub = [round((ub_price[i]-avg_price[i])/avg_price[i], 4) for i in range(MAX_ELEVATION+1)]
    lb = [round((lb_price[i]-avg_price[i])/avg_price[i], 4) for i in range(MAX_ELEVATION+1)]
    llb = [round((llb_price[i]-avg_price[i])/avg_price[i], 4) for i in range(MAX_ELEVATION+1)]
    llb[-1] = -1 # ensure to sell off at MAX_ELEVATION
    # rr: return rate after the current period's investemnt made 
    rr = [0]
    for i in range(MAX_ELEVATION): 
        rr.append(round((ub_price[i]-avg_price[i+1])/avg_price[i+1], 4))

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