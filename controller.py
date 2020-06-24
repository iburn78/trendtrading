from Kiwoom import *
from trtrader import *

class Controller():
    def __init__(self): 
        app = QApplication(sys.argv)
        self.trtrader = TrTrader()
        trtrader.show()
        app.exec_()

    def run(self):
        try: 
            while 1: 
                # datetime.datetime.today().weekday() in range(0,5) and current_time > MARKET_START_TIME and current_time < MARKET_FINISH_TIME:
                # if current time is in MKT_OPEN_TIME and MKT_CLOSE_TIME
                # make the while statement running before MKT_OPEN_TIME, but close after MKT_CLOSE_TIME 
                print('trtrader running - do not interrupt the system')
                self.trtrader.run()
                # put other actions e.g., visualization
                print('the system entered waiting - you may exit by Ctrl-c')
                time.sleep(RUN_WAIT_INTERVAL)
        except Exception as e: 
            print(e)
        # add clean-up codes if any

    def master_book_visualize(self): 
        print(self.trtrader.master_book)
        # user pretty printing of dataframe 
        # pick stock code and print return rate and reinvestment information (amount invested / current total value)
        # consider table or graph (using matplotlib)
        # (if needed) save it to file 

    def result_summary(self):
        pass
        # return summary_statistics 
        # use this function as a basis for optimizer and backtester (to be developed later)
        # implement "PHASE" concept 
       

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


if __name__ = "__main__":
    controller = Controller()
    




