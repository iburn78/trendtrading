from Kiwoom import *

class TrTrader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.km = Kiwoom()
        if km.connect_status == False: 
            pass
        self.load_master_book() 

    def check_balance(self):
        # account number to be read from Kiwoom class directly hard coded
        account_number = self.kiwoom.get_login_info("ACCNO")
        account_number = account_number.split(';')[0]

        self.kiwoom.set_input_value("계좌번호", account_number)
        self.kiwoom.comm_rq_data("opw00018_req", "opw00018", 0, "2000")

        while self.kiwoom.remained_data:
            self.kiwoom.set_input_value("계좌번호", account_number)
            self.kiwoom.comm_rq_data("opw00018_req", "opw00018", 2, "2000")

        # cash balance
        self.kiwoom.set_input_value("계좌번호", account_number)
        self.kiwoom.comm_rq_data("opw00001_req", "opw00001", 0, "2000")

        # balance
        # cash = self.kiwoom.d2_deposit
        # for i in range(1, 6): # other balance data
            # self.kiwoom.opw00018_output['single'][i - 1]

        # purchased stock list
        # self.kiwoom.opw00018_output['multi']

        # for j in range(item_count):
            # row = self.kiwoom.opw00018_output['multi'][j]
            # for i in range(len(row)):
                # row[i]

    def load_master_book(self):
        try: 
            self.master_book = pd.read_excel(MASTER_BOOK_FILE, index_col=None, converters={'code': str})
        except Exception as e:
            print(e)
            self.master_book = pd.DataFrame()
        

    def trade_stocks(self):
        
        account = self.account_number
        buy_order = 1  
        sell_order = 2
        
        # buy_command to be implemented buy_list -> master_book
        for i in buy_list.index: 
            if buy_list["Tr"][i] == 'yet' or buy_list["Tr"][i] == 'failed':
                hoga = HOGA_LOOKUP[buy_list["Order_type"][i]]
                if hoga == "00": 
                    price = buy_list["Price"][i]
                elif hoga == "03":
                    price = 0 
                res = self.kiwoom.send_order("send_order_req", "0101", account, buy_order, buy_list["Code"][i], int(buy_list["Amount"][i]), price, hoga,"")

                if res[0] == 0 and res[1] != "":
                    self.label_8.setText("Order sent: " + str(res[1]))
                    buy_list.at[i, "Tr"] = 'ordered'
                else:
                    self.label_8.setText("Errer in order processing")
                    buy_list.at[i, "Tr"] = 'failed'

        # may need to save master book and save it to file 

        # sell_command to be implemented sell_list -> master_book
        for i in sell_list.index: 
            if sell_list["Tr"][i] == 'yet' or sell_list["Tr"][i] == 'failed':
                hoga = HOGA_LOOKUP[sell_list["Order_type"][i]]
                if hoga == "00": 
                    price = sell_list["Price"][i]
                elif hoga == "03":
                    price = 0 
                res = self.kiwoom.send_order("send_order_req", "0101", account, sell_order, sell_list["Code"][i], int(sell_list["Amount"][i]), price, hoga,"")
                if res[0] == 0 and res[1] != "":
                    self.label_8.setText("Order sent: "+str(res[1]))
                    sell_list.at[i, "Tr"] = 'ordered'
                else:
                    self.label_8.setText("Errer in order processing")
                    sell_list.at[i, "Tr"] = 'failed'

        # may need to save master book and save it to file 
                

###########################################################################
##### ALGORITHMS
###########################################################################

    def autotrade_list_gen(self): 
        sell_list = self.algo_sell_by_return_range(1.5, -1) # args are in percentage points

    def algo_sell_by_return_range(self, upperlimit, lowerlimit): 
        my_stocks = self.kiwoom.get_my_stock_list()
        for exception_code in exception_list:
            my_stocks = my_stocks[my_stocks.index != exception_code]
        profit_sell_list = my_stocks[my_stocks['earning_rate'] > upperlimit] 
        loss_sell_list = my_stocks[my_stocks['earning_rate'] < lowerlimit] 
        print('Profit Sell List (up to 50 items): \n', tabulate(profit_sell_list[:50], headers='keys', tablefmt='psql'))
        print('Loss Sell List (up to 50 items): \n', tabulate(loss_sell_list[:50], headers='keys', tablefmt='psql'))
        return profit_sell_list.append(loss_sell_list)

