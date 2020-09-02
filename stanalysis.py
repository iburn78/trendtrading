from Kiwoom import *

app = QApplication([''])
k = Kiwoom()

STA_CODE = '005930'
STA_DATE_PERIOD = '0'
STA_START_DATE = '0' # ignored if STA_DATE_PERIOD = '0'
STA_END_DATE = '20200828'
STA_UNIT = '1'
STA_NUMBER_TO_RECEIVE_NEXTPAGE = 15


def shortsales_record(): 
    # opt10014 Short Selling  ---------------------------------
    k.set_input_value('종목코드', STA_CODE)
    k.set_input_value('시간구분', STA_DATE_PERIOD) # 0: by date, 1: by period
    k.set_input_value('시작일자', STA_START_DATE) # if by date, this input ignored
    k.set_input_value('종료일자', STA_END_DATE) # should be later than start date
    k.comm_rq_data('opt10014_req', 'opt10014', 0, '2000')
    ss = pd.DataFrame(k.opt10014_multi_data_set)

    for i in range(STA_NUMBER_TO_RECEIVE_NEXTPAGE):
        if k.remained_data:
            k.set_input_value('종목코드', STA_CODE)
            k.set_input_value('시간구분', STA_DATE_PERIOD)
            k.set_input_value('시작일자', STA_START_DATE)
            k.set_input_value('종료일자', STA_END_DATE)
            k.comm_rq_data('opt10014_req', 'opt10014', 2, '2000')
            ss =ss.append(pd.DataFrame(k.opt10014_multi_data_set)) 
        else: 
            break

    # incrate in %
    # volume in a single share
    # shortwgt in %
    # shortamt in 1000
    # clprice = closing price
    ss.reset_index(drop=True, inplace=True)
    ss = ss.astype({0: 'object', 1: 'int64', 2: 'int64', 3: 'int64', 4: 'float64', 5: 'int64', 6: 'int64', 7: 'float64', 8: 'int64', 9: 'int64'})
    ss.rename(columns = {0: 'date', 1: 'clprice', 2: 'deltakey', 3: 'delta', 4: 'incrate', 5: 'volume', 6: 'shortvol', 7: 'shortwgt', 8: 'shortamt', 9: 'shortprice'}, inplace = True)
    ss.clprice = ss.clprice.abs()
    return ss

def investor_history_singlecase(moneyquantity='2', netbuysell='0'):
    # opt10059 By Investor  ---------------------------------
    k.set_input_value('일자', STA_END_DATE)
    k.set_input_value('종목코드', STA_CODE)
    k.set_input_value('금액수량구분', moneyquantity)  # 1: money amount, 2: quantity of units
    k.set_input_value('매매구분', netbuysell)  # 0: net, 1: buy, 2: sell
    k.set_input_value('단위구분', STA_UNIT) # 1000: a thousand unit, 1: a unit
    k.comm_rq_data('opt10059_req', 'opt10059', 0, '3000')
    bi = pd.DataFrame(k.opt10059_multi_data_set)

    for i in range(STA_NUMBER_TO_RECEIVE_NEXTPAGE):
        if k.remained_data:
            k.set_input_value('일자', STA_END_DATE)
            k.set_input_value('종목코드', STA_CODE)
            k.set_input_value('금액수량구분', moneyquantity)  # 1: money amount in 1M KRW, 2: quantity of units
            k.set_input_value('매매구분', netbuysell)  # 0: net, 1: buy, 2: sell
            k.set_input_value('단위구분', STA_UNIT) # 1000: a thousand unit, 1: a unit
            k.comm_rq_data('opt10059_req', 'opt10059', 2, '3000')
            bi =bi.append(pd.DataFrame(k.opt10059_multi_data_set))
        else: 
            break

    bi.reset_index(drop=True, inplace=True)
    bi = bi.astype({0: 'object', 1: 'int64', 2: 'int64', 3: 'int64', 4: 'int64', 5: 'int64', 6: 'int64', 7: 'int64', 8: 'int64', 9: 'int64', 
                    10: 'int64', 11: 'int64', 12: 'int64', 13: 'int64', 14: 'int64', 15: 'int64', 16: 'int64', 17: 'int64', 18: 'int64', 19: 'int64'})
    bi.rename(columns = {0: 'date', 1: 'price', 2: 'deltakey', 3: 'delta', 4: 'incrate', 5: 'volume', 6: 'amount', 7: 'ppl', 8: 'fgn', 9: 't_inst', 10: 'fininv', 
                        11: 'insu', 12: 'trust', 13: 'finetc', 14: 'bank', 15: 'pensvg', 16: 'prieqt', 17: 'nation', 18: 'corpetc', 19: 'fgnetc'}, inplace = True)
    bi.price = bi.price.abs()
    # incrate in basis point
    # amount in million KRW
    # t_inst = fininv + insu + trust + finetc + bank + pensvg + prieqt + nation
    # volume or amount = ppl + fgn + t_inst +  corpetc + fgnetc when buy/sell(negative)
    # 0  = ppl + fgn + t_inst + nation + corpetc + fgnetc when buy when net
    return bi


# for 005930 Samsung, split date = '20180427', drop_period = 0, ratio = 50
# date is the last day with the unsplitted price
# drop_period is the duration of non trading before adjustment: should check with actual data
# ss: short sales
def ss_stock_split_adjustment(ss, date, drop_period=0, ratio=1):
    idx = ss.loc[ss.date == date].index[0]
    top = ss.loc[ss.index < idx-drop_period].copy()
    bot = ss.loc[ss.index >= idx].copy()
    bot.iloc[:, [1, 3, 9]] = bot.iloc[:, [1, 3, 9]]/ratio
    bot.iloc[:, [5, 6]] = bot.iloc[:, [5, 6]]*ratio
    bot.iloc[:, [1, 3, 9]] = bot.iloc[:, [1, 3, 9]].round().astype('int64')
    return top.append(bot).reset_index(drop=True)

# for 005930 Samsung, split date = '20180427', drop_period = 3, ratio = 50
# date is the last day with the unsplitted price
# drop_period is the duration of non trading before adjustment: should check with actual data
# bi: by investors
def bi_stock_split_adjustment(bi, date, drop_period=0, ratio=1, moneyquantity = '2'): 
    idx = bi.loc[bi.date == date].index[0]
    top = bi.loc[bi.index < idx-drop_period].copy()
    bot = bi.loc[bi.index >= idx].copy()
    bot.iloc[:, [1, 3]] = bot.iloc[:, [1, 3]]/ratio
    bot.iloc[:, 5] = bot.iloc[:, 5]*ratio
    if moneyquantity == '2': # if quantity
        bot.iloc[:, 7:] = bot.iloc[:, 7:]*ratio
    elif moneyquantity == '1': # if money
        pass
    else: 
        print('stock_split parameter error')
    bot.iloc[:, 1:] = bot.iloc[:, 1:].round().astype('int64')
    return top.append(bot).reset_index(drop=True)

def reverse_date(df):
    return df.loc[::-1].reset_index(drop=True)

ssr = reverse_date(ss_stock_split_adjustment(shortsales_record(), '20180427', 0, 50))

bi_net = reverse_date(bi_stock_split_adjustment(investor_history_singlecase(), '20180427', 3, 50))
bs_net = bi_net.merge(ssr.iloc[:, [0,6,7,8,9]], on='date', how='inner').reset_index(drop=True) 

bi_buy = reverse_date(bi_stock_split_adjustment(investor_history_singlecase(netbuysell='1'), '20180427', 3, 50))
bi_sell = reverse_date(bi_stock_split_adjustment(investor_history_singlecase(netbuysell='2'), '20180427', 3, 50))

# bi_net.to_excel("etc/bi_net.xlsx", index=False)
# bi_buy.to_excel("etc/bi_buy.xlsx", index=False)
# bi_sell.to_excel("etc/bi_sell.xlsx", index=False)


SAMSUNG_TOTAL_SHARE = 5969782550
INIT_PPL_SHARE = 0.1
INIT_INST_SHARE = 0.1
INIT_FGN_SHARE = 0.4

bi_net['ppl_ap'] = bi_net['price'].astype('float64')
bi_net['ppl_ca'] = bi_net['ppl'].cumsum() + round(SAMSUNG_TOTAL_SHARE*INIT_PPL_SHARE)
bi_net['ppl_en'] = 0

for i in range(1, len(bi_net)):
    bi_net.at[i, 'ppl_ap'] = round((bi_net.at[i-1, 'ppl_ap']*bi_net.at[i-1, 'ppl_ca']+bi_net.at[i,'price']*bi_buy.at[i,'ppl'])/(bi_net.at[i-1,'ppl_ca']+bi_buy.at[i,'ppl']), 1)
    bi_net.at[i, 'ppl_en'] = round((bi_net.at[i, 'price']-bi_net.at[i-1, 'ppl_ap'])*(-bi_sell.at[i,'ppl'])+bi_net.at[i-1,'ppl_en'])

bi_net['fgn_ap'] = bi_net['price'].astype('float64')
bi_net['fgn_ca'] = bi_net['fgn'].cumsum() + round(SAMSUNG_TOTAL_SHARE*INIT_FGN_SHARE)
bi_net['fgn_en'] = 0

for i in range(1, len(bi_net)):
    bi_net.at[i, 'fgn_ap'] = round((bi_net.at[i-1, 'fgn_ap']*bi_net.at[i-1, 'fgn_ca']+bi_net.at[i,'price']*bi_buy.at[i,'fgn'])/(bi_net.at[i-1,'fgn_ca']+bi_buy.at[i,'fgn']), 1)
    bi_net.at[i, 'fgn_en'] = round((bi_net.at[i, 'price']-bi_net.at[i-1, 'fgn_ap'])*(-bi_sell.at[i,'fgn'])+bi_net.at[i-1,'fgn_en'])

bi_net['t_inst_ap'] = bi_net['price'].astype('float64')
bi_net['t_inst_ca'] = bi_net['t_inst'].cumsum() + round(SAMSUNG_TOTAL_SHARE*INIT_INST_SHARE)
bi_net['t_inst_en'] = 0

for i in range(1, len(bi_net)):
    bi_net.at[i, 't_inst_ap'] = round((bi_net.at[i-1, 't_inst_ap']*bi_net.at[i-1, 't_inst_ca']+bi_net.at[i,'price']*bi_buy.at[i,'t_inst'])/(bi_net.at[i-1,'t_inst_ca']+bi_buy.at[i,'t_inst']), 1)
    bi_net.at[i, 't_inst_en'] = round((bi_net.at[i, 'price']-bi_net.at[i-1, 't_inst_ap'])*(-bi_sell.at[i,'t_inst'])+bi_net.at[i-1,'t_inst_en'])


fig, (ax1, ax2, ax3)= plt.subplots(3, 1, sharex=True)
bi_net.loc[:, ['ppl_en', 'fgn_en', 't_inst_en']].plot(ax = ax1)
bi_net.loc[:, ['ppl_ca', 'fgn_ca', 't_inst_ca']].plot(ax = ax2)
bi_net.loc[:, ['ppl_ap', 'fgn_ap', 't_inst_ap']].plot(ax = ax3)
plt.show()
