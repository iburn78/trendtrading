import yfinance as yf
import sqlite3
import pandas as pd

t = yf.Ticker('005930.ks')
d = t.history(start = '2015-01-01', end = '2020-06-30', auto_adjust=False)

con = sqlite3.connect('etc/bi_data.db')

print(d)
print('hello')
d.to_sql('Samsung2', con, if_exists = 'replace')
dr = pd.read_sql_query('SELECT * from Samsung2', con, index_col='Date')
print(dr)

con.close()
