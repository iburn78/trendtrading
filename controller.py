from Kiwoom import *
from trtrader import *
from datetime import datetime, time as dtime
import time 
import schedule

HOLIDAYS_2020 = ['20200930', '20201001', '20201002', '20201009', '20201225']
HOLIDAYS = list(map(lambda x: datetime.strptime(x, '%Y%m%d').date(), HOLIDAYS_2020))

VERSION_CHK_TIME = "08:00"
TRTRADE_RUN_TIME = "09:10"
TRTRADE_FIN_TIME = "15:20"
TRTRADE_RUN_INTERVAL = 10 # second
RUN_PENDING_INTERVAL = 10

MKT_OPEN_TIME = TRTRADE_RUN_DTIME = dtime.fromisoformat(TRTRADE_RUN_TIME)
MKT_CLOSE_TIME = TRTRADE_FIN_DTIME = dtime.fromisoformat(TRTRADE_FIN_TIME)
VERSION_CHECK_MSG = 'VERSION CHECK FINISHED'

class Controller():
    def __init__(self): 
        schedule.every().day.at(VERSION_CHK_TIME).do(self.run_)
        schedule.every().day.at(TRTRADE_RUN_TIME).do(self.run_)
        if datetime.now().time() > TRTRADE_RUN_DTIME and datetime.now().time() < TRTRADE_FIN_DTIME:
            self.run_()
        while 1: 
            schedule.run_pending()
            print('.', end='')
            time.sleep(RUN_PENDING_INTERVAL)

    def run_(self): 
        print("\nController run: ", time.strftime("%Y/%m/%d %H:%M:%S"))
        try: 
            os.system("python daytask.py")
        except KeyboardInterrupt:
            print("Keyboard interrupt detected within os.system/daytask.py")
        if datetime.now().time() < TRTRADE_RUN_DTIME: 
            with open(TRADE_LOG_FILE) as f: 
                msg = f.read()
                if msg[-23:-1] == VERSION_CHECK_MSG:
                    print("Version check success ", time.strftime("%Y/%m/%d %H:%M:%S"))
                else:
                    sys.exit("Kiwoom API Version Update Fail")


    def master_book_visualize(self): 
        print(self.trtrader.master_book)
        # user pretty printing of dataframe 
        # pick stock code and print return rate and reinvestment information (amount invested / current total value)
        # consider table or graph (using matplotlib)
        # (if needed) save it to file 

    def result_summary(self): # or performance management
        pass
        # return summary_statistics 
        # use this function as a basis for optimizer and backtester (to be developed later)
        # implement "PHASE" concept 

    def event_alert(self):
        pass
        # fire alerts whenever necessary       

class UserInfoManagement():
    pass
    # Real Server vs Simulator
    # Account management / password together

class BackTester():
    pass
    # utilize: start price, high price, low price, end price per stock per day
    # regarding high/low price, a certain discount factor may be applied 
    # may implement this class in trtrader.py file
    # may not be in a class form
    # of course, in backtesting, there is no need to use waiting interval

class Optimizer():
    pass
    # determine which parameters to optimize: UB/LB/LLB/CB(cash bound)/ticket size
    # determine which parameters to maximize: return rate/current total value
    # consider to build the best experiment design for optimization process
    # in designing optimizer, we may analyze per type of stocks in price evolution (e.g., band style, spike style, 
    # continual evaluation sytle, continual devaluation style)
    # application of AI/ML

class Economics():
    pass
    # Macro economic phase defining and finding


if __name__ == "__main__":
    ct = Controller()
